"""原題 5：用 Selenium 依題目路徑取得台北週末票房前 20 名。"""
from bs4 import BeautifulSoup
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

from support import SourceBlocked, SourceChanged, close_browser, make_browser, run_cli


URL = "https://www.atmovies.com.tw/movie/new/"
FIELDS = ["排名", "片名", "本週票房", "累計票房"]


def ensure_source_page(html):
    code = BeautifulSoup(html, "html.parser").select_one(".error-code")
    if code and code.get_text(strip=True).startswith("ERR_"):
        raise SourceBlocked(f"Chrome 無法連上開眼票房來源（{code.get_text(strip=True)}）；未把瀏覽器錯誤頁當作排行")


def parse_context(html):
    soup = BeautifulSoup(html, "html.parser")
    date = soup.select_one("font.boDate")
    date_text = date.get_text(" ", strip=True) if date else ""
    date_text = date_text.removeprefix("統計時間：").strip()
    unit_cell = next(
        (cell for cell in soup.select("td") if "單位：" in cell.get_text(" ", strip=True)),
        None,
    )
    unit = unit_cell.get_text(" ", strip=True).split("單位：", 1)[-1].strip() if unit_cell else ""
    if not date_text or not unit:
        raise SourceChanged("台北票房缺少統計期間或金額單位")
    return date_text, unit


def parse_rankings(html):
    soup = BeautifulSoup(html, "html.parser")
    rows = []
    for title_cell in soup.select("td.at11"):
        title_link = title_cell.select_one("a[href]")
        rank_cell = title_cell.parent.select_one("td b")
        detail_row = title_cell.parent.find_next("tr")
        detail_cells = detail_row.find_all("td", recursive=False) if detail_row else []
        if not title_link or not rank_cell or len(detail_cells) < 4:
            raise SourceChanged("台北票房排行的兩列式欄位結構已改變")
        rank = rank_cell.get_text(" ", strip=True)
        if not rank.isdigit():
            raise SourceChanged("台北票房排名不是數字")
        rows.append({
            "排名": rank,
            "片名": title_link.get_text(" ", strip=True),
            "本週票房": detail_cells[2].get_text(" ", strip=True),
            "累計票房": detail_cells[3].get_text(" ", strip=True),
        })
    if not rows:
        raise SourceChanged("找不到台北週末票房排行")
    if len({row["排名"] for row in rows}) != len(rows):
        raise SourceChanged("台北週末票房排名重複")
    return rows


def find_after_one_refresh(driver, selector, timeout=15):
    for attempt in range(2):
        try:
            return WebDriverWait(driver, timeout).until(
                lambda current: current.find_elements(By.CSS_SELECTOR, selector)
            )
        except TimeoutException:
            if attempt == 0:
                driver.refresh()
    raise SourceBlocked("開眼票房頁正常載入及重新整理各一次仍逾時")


def run(job, args):
    driver = make_browser(args)
    wait = WebDriverWait(driver, 25)
    try:
        driver.get(URL)
        job.sources.append(URL)
        print("Q05：已開啟本週新片頁", flush=True)
        boxoffice = wait.until(lambda d: d.find_elements(By.CSS_SELECTOR, "a[href*='app2.atmovies.com.tw/boxoffice/']"))[0]
        driver.execute_script("arguments[0].click();", boxoffice)
        wait.until(lambda d: "/boxoffice/" in d.current_url)
        wait.until(lambda d: d.execute_script("return document.readyState") == "complete")
        job.sources.append(driver.current_url)
        print("Q05：已點入票房排行榜", flush=True)
        job.save_text("boxoffice_overview_source.html", driver.page_source)
        job.capture(driver, "boxoffice_overview.png")
        ensure_source_page(driver.page_source)
        overview_links = driver.find_elements(By.CSS_SELECTOR, "a[href*='/boxoffice/twweekend/']")
        print(f"Q05：台北票房候選連結 {len(overview_links)} 個", flush=True)
        more = wait.until(
            lambda d: d.find_elements(
                By.CSS_SELECTOR,
                "a.viewMore[href*='/boxoffice/twweekend/']",
            )
        )[0]
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", more)
        more.click()
        wait.until(lambda d: "/boxoffice/twweekend/" in d.current_url)
        wait.until(lambda d: d.find_elements(By.CSS_SELECTOR, "td.at11"))
        job.sources.append(driver.current_url)
        print("Q05：已點入台北 more 並載入排行", flush=True)
        job.save_text("Taipei_boxoffice_source.html", driver.page_source)
        job.capture(driver, "Taipei_boxoffice.png")
        rows = parse_rankings(driver.page_source)
        period, unit = parse_context(driver.page_source)
        job.save_csv("Taipei_movies.csv", FIELDS, rows)
    finally:
        close_browser(driver, args)
    if len(rows) == 20:
        return {"status": "passed", "note": f"已依序點入票房排行榜與台北 more，取得完整 20 名；統計期間 {period}，金額單位 {unit}。", "rows": 20}
    return {"status": "partial", "note": f"網站當下只提供 {len(rows)} 名；統計期間 {period}，金額單位 {unit}；未補造到 20 名。", "rows": len(rows)}


if __name__ == "__main__":
    run_cli(5, run)
