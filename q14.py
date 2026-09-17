"""第 14 題：HoopsHype 現行薪資表與前三名球員個人頁背號。"""
import re
from dataclasses import dataclass
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

from support import SourceChanged, close_browser, make_browser, run_cli, safe_url

URL = "https://www.hoopshype.com/salaries/players/"


@dataclass(frozen=True)
class PlayerSalary:
    name: str
    salary: str
    url: str


@dataclass(frozen=True)
class SalaryTable:
    fields: list
    rows: list
    top_three: list
    season: str


def _money_number(text):
    match = re.search(r"\$\s*([0-9][0-9,]*)", text)
    return int(match.group(1).replace(",", "")) if match else None


def parse_salary_table(html, require_top_three=True):
    soup = BeautifulSoup(html, "html.parser")
    table = next(
        (
            candidate
            for candidate in soup.select("table")
            if "Player" in [th.get_text(" ", strip=True) for th in candidate.select("thead th")]
            and candidate.select("tbody tr")
        ),
        None,
    )
    if table is None:
        raise SourceChanged("HoopsHype 現行頁面找不到已載入的薪資表")

    fields = [th.get_text(" ", strip=True) or "排名" for th in table.select("thead th")]
    if len(fields) < 3 or len(set(fields)) != len(fields) or not re.fullmatch(r"\d{4}-\d{2}", fields[2]):
        raise SourceChanged("HoopsHype 薪資表欄位已變更，無法確認目前賽季薪資欄")

    rows, players = [], []
    for tr in table.select("tbody tr"):
        cells = [td.get_text(" ", strip=True) for td in tr.select("td")]
        if not tr.get_text(" ", strip=True):
            continue
        if len(cells) != len(fields):
            raise SourceChanged("HoopsHype 薪資表有欄位數不一致的資料列，未宣稱已保存全部內容")
        if not cells[1]:
            raise SourceChanged("HoopsHype 薪資表有缺少球員姓名的資料列")
        row = dict(zip(fields, cells))
        link = tr.select_one("td:nth-of-type(2) a[href]")
        rows.append(row)
        players.append(
            PlayerSalary(
                name=cells[1],
                salary=cells[2],
                url=urljoin(URL, link.get("href")) if link else "",
            )
        )
    if require_top_three and len(rows) < 3:
        raise SourceChanged(f"薪資表只有 {len(rows)} 筆可辨識資料，無法取得前三名")

    salaries = [_money_number(player.salary) for player in players]
    if require_top_three:
        if any(value is None for value in salaries[:3]) or any(
            current < following for current, following in zip(salaries, salaries[1:])
            if current is not None and following is not None
        ):
            raise SourceChanged("目前薪資欄不是可驗證的由高到低排序，未任意挑選前三名")
        if any(not player.url for player in players[:3]):
            raise SourceChanged("前三名球員缺少個人頁連結，無法驗證背號")
    return SalaryTable(fields, rows, players[:3] if require_top_three else [], fields[2])


def parse_jersey(html, expected_name):
    soup = BeautifulSoup(html, "html.parser")
    name_token = expected_name.split()[-1].lower()
    for text in soup.find_all(string=re.compile(r"^\s*#\d{1,2}\s*$")):
        context = text.parent
        for _ in range(7):
            if context is None or context.name in {"script", "style"}:
                break
            context_text = context.get_text(" ", strip=True)
            # 現行個人頁的號碼、位置、姓名及球隊在同一個簡短 profile header；
            # 薪資排名、文章 hashtag 或頁面其他 #數字 不具此上下文。
            if name_token in context_text.lower() and len(context_text) <= 300 and context.find("h1") is None:
                return text.strip().lstrip("#")
            context = context.parent
    return None


def parse_pagination(html):
    text = BeautifulSoup(html, "html.parser").get_text(" ", strip=True)
    match = re.search(r"\b(\d+)\s+of\s+(\d+)\b", text)
    return (int(match.group(1)), int(match.group(2))) if match else (1, 1)


def pagination_is_complete(*, current_page, total_pages, loaded_pages, issue):
    return not issue and current_page == total_pages and loaded_pages == total_pages


def validate_rank_sequence(rows):
    seen_rows = set()
    previous_rank = None
    for position, row in enumerate(rows, 1):
        player = row.get("Player", "").strip()
        identity = tuple(row.items())
        if not player or identity in seen_rows:
            raise SourceChanged("HoopsHype 分頁包含空白球員或完全重複資料列，可能是重複/陳舊頁面")
        seen_rows.add(identity)
        match = re.fullmatch(r"T?(\d+)", row.get("排名", "").strip())
        if match is None:
            raise SourceChanged("HoopsHype 排名格式無法驗證")
        rank = int(match.group(1))
        if position == 1:
            valid = rank == 1
        else:
            valid = rank == previous_rank or rank == position
        if not valid:
            raise SourceChanged("HoopsHype 排名序列不連續，可能跳頁或重複載入")
        previous_rank = rank


def _advanced_page_ready(driver, previous_page, previous_first_player):
    if driver.find_elements(By.CSS_SELECTOR, "span.react-loading-skeleton"):
        return False
    html = driver.page_source
    current, _total = parse_pagination(html)
    if current != previous_page + 1:
        return False
    try:
        table = parse_salary_table(html, require_top_three=False)
    except SourceChanged:
        return False
    return bool(table.rows and table.rows[0]["Player"] != previous_first_player)


def _next_page_button(driver, current, total):
    wanted = f"{current} of {total}"
    for span in driver.find_elements(By.XPATH, "//span[contains(normalize-space(.), ' of ')]"):
        if span.text.strip() != wanted:
            continue
        buttons = span.find_element(By.XPATH, "..").find_elements(By.TAG_NAME, "button")
        if len(buttons) >= 2 and buttons[-1].is_enabled():
            return buttons[-1]
    return None


def _click_next_page(driver, button):
    driver.execute_script(
        "arguments[0].scrollIntoView({block: 'center', inline: 'nearest'});",
        button,
    )
    wait = WebDriverWait(driver, 10)
    wait.until(lambda _browser: button.is_displayed() and button.is_enabled())
    wait.until(
        lambda browser: browser.execute_script(
            "const r=arguments[0].getBoundingClientRect();"
            "const e=document.elementFromPoint(r.left+r.width/2,r.top+r.height/2);"
            "return e===arguments[0] || arguments[0].contains(e);",
            button,
        )
    )
    # 保留 Selenium 正常點擊；不以 JavaScript click 穿透廣告或遮罩。
    button.click()


def _load_profile(driver, player, job, index):
    try:
        driver.get(player.url)
        WebDriverWait(driver, 25).until(lambda browser: browser.find_elements(By.CSS_SELECTOR, "h1"))
        job.sources.append(safe_url(driver.current_url))
        profile_html = driver.page_source
        job.save_text(f"profile_{index}.html", profile_html)
        job.capture(driver, f"profile_{index}.png")
        return parse_jersey(profile_html, player.name)
    except (TimeoutException, WebDriverException):
        return None


def run(job, args):
    driver = make_browser(args)
    try:
        driver.get(URL)
        WebDriverWait(driver, 35).until(
            lambda browser: "Player" in browser.page_source
            and "$" in browser.page_source
            and not browser.find_elements(By.CSS_SELECTOR, "span.react-loading-skeleton")
        )
        job.sources.append(safe_url(driver.current_url))
        salary_html = driver.page_source
        job.save_text("source_salaries.html", salary_html)
        job.capture(driver, "source_salaries.png")
        first_table = parse_salary_table(salary_html)
        current_page, total_pages = parse_pagination(salary_html)
        if current_page != 1:
            raise SourceChanged(f"HoopsHype 初始頁不是第 1 頁，而是第 {current_page} 頁")
        loaded_pages = 1
        all_rows = list(first_table.rows)
        validate_rank_sequence(all_rows)
        current_first_player = first_table.rows[0]["Player"]
        max_pages = getattr(args, "max_pages", 5)
        pagination_issue = ""
        while current_page < total_pages and loaded_pages < max_pages:
            try:
                next_button = _next_page_button(driver, current_page, total_pages)
                if next_button is None:
                    raise SourceChanged(f"第 {current_page} 頁找不到可用的下一頁按鈕")
                _click_next_page(driver, next_button)
                previous_page = current_page
                WebDriverWait(driver, 25).until(
                    lambda browser: _advanced_page_ready(browser, previous_page, current_first_player)
                )
                page_html = driver.page_source
                current_page, observed_total = parse_pagination(page_html)
                if current_page != previous_page + 1:
                    raise SourceChanged("HoopsHype 分頁沒有依序前進一頁")
                if observed_total != total_pages:
                    raise SourceChanged("HoopsHype 分頁總數在擷取途中改變")
                page_table = parse_salary_table(page_html, require_top_three=False)
                if page_table.fields != first_table.fields or page_table.season != first_table.season:
                    raise SourceChanged("HoopsHype 分頁欄位在擷取途中改變")
                combined_rows = all_rows + page_table.rows
                validate_rank_sequence(combined_rows)
                all_rows = combined_rows
                current_first_player = page_table.rows[0]["Player"]
                loaded_pages += 1
                job.save_text(f"source_salaries_page_{current_page}.html", page_html)
            except (TimeoutException, WebDriverException, SourceChanged) as error:
                pagination_issue = f"第 {current_page} 頁後分頁未完成（{type(error).__name__}）"
                job.save_text(f"pagination_failure_page_{current_page}.html", driver.page_source)
                try:
                    job.capture(driver, "pagination_failure.png")
                except (OSError, WebDriverException):
                    pass
                break

        table = SalaryTable(first_table.fields, all_rows, first_table.top_three, first_table.season)
        # 表格要求可獨立完成；先保存，避免某個個人頁失敗時遺失 requirement 3。
        job.save_csv("all_play.csv", table.fields, table.rows)

        jerseys = []
        for index, player in enumerate(table.top_three, 1):
            jerseys.append(_load_profile(driver, player, job, index))
    finally:
        if getattr(args, "keep_open", False) and not getattr(args, "headless", False):
            try:
                driver.get(URL)
            except WebDriverException:
                pass
        close_browser(driver, args)

    salary_field = f"薪資（{table.season}，USD）"
    highest = [
        {"名字": player.name, "背號": jersey or "未提供", salary_field: player.salary}
        for player, jersey in zip(table.top_three, jerseys)
    ]
    job.save_csv("highest.csv", ["名字", "背號", salary_field], highest)
    missing = sum(jersey is None for jersey in jerseys)
    incomplete_pages = not pagination_is_complete(
        current_page=current_page,
        total_pages=total_pages,
        loaded_pages=loaded_pages,
        issue=pagination_issue,
    )
    status = "partial" if missing or incomplete_pages else "passed"
    table_note = (
        f"完整 {total_pages}/{total_pages} 頁、{len(table.rows)} 筆"
        if not incomplete_pages
        else (
            f"只保存前 {loaded_pages}/{total_pages} 頁、{len(table.rows)} 筆（{pagination_issue}）"
            if pagination_issue
            else f"只保存前 {loaded_pages}/{total_pages} 頁、{len(table.rows)} 筆（達 --max-pages={max_pages}）"
        )
    )
    profile_note = (
        "前三名均由個人頁驗證背號"
        if not missing
        else f"{missing}/3 位球員個人頁未提供可驗證背號，已標示未提供"
    )
    return {
        "status": status,
        "note": f"{table.season} 賽季美元薪資表：{table_note}；{profile_note}",
        "rows": len(table.rows),
    }


if __name__ == "__main__":
    run_cli(14, run)
