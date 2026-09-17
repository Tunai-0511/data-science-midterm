"""第 16 題：以 Selenium 實際輸入台中後取得 Agoda 第一個結果頁。"""
import re
from datetime import date, datetime
from urllib.parse import urlencode, urljoin

from bs4 import BeautifulSoup
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

from support import SourceChanged, close_browser, make_browser, run_cli, safe_url

URL = "https://www.agoda.com/zh-tw/"
FIELDS = [
    "飯店名", "價格", "幣別", "價格範圍", "稅費", "入住日", "退房日", "晚數",
    "房數", "成人數", "擷取時間", "來源網址",
]
CARD_SELECTORS = '[data-selenium="hotel-item"], [data-selenium="property-card"], [data-element-name="property-card"]'
NAME_SELECTORS = '[data-selenium="hotel-name"], [data-selenium="property-name"], [data-element-name="property-card-title"]'
PRICE_SELECTORS = '[data-selenium="display-price"], [data-selenium="price-number"], [data-element-name="final-price"], [data-element-name="property-card-price"]'


def validate_stay(check_in, check_out, adults, today=None):
    try:
        start, end = date.fromisoformat(check_in), date.fromisoformat(check_out)
    except (TypeError, ValueError):
        raise ValueError("入住日與退房日必須為 YYYY-MM-DD") from None
    today = today or date.today()
    if start < today:
        raise ValueError("入住日不可早於今天")
    if end <= start:
        raise ValueError("退房日必須晚於入住日")
    if adults < 1:
        raise ValueError("成人數必須至少為 1")
    return (end - start).days


def _clean_text(node):
    return " ".join(node.stripped_strings) if node else ""


def _tax_text(card):
    explicit = card.select_one('[data-selenium="taxes-and-fees"], [data-element-name="taxes-and-fees"]')
    if explicit:
        return _clean_text(explicit)
    text = _clean_text(card)
    match = re.search(r"(?:另加|未含|不含|含)(?:稅(?:金)?(?:和|及)?其他費用|稅(?:金)?|其他費用)", text)
    return match.group(0).strip() if match else "頁面未明示"


def _price_scope(card, price_node):
    text = _clean_text(card).lower()
    if "總價" in text or "整趟" in text or "whole stay" in text or "total" in text:
        return "整趟總價"
    if "每晚" in text or "per night" in text:
        return "每晚"
    return "頁面未明示"


def parse_results(html, *, check_in, check_out, adults, captured_at, source_url):
    nights = validate_stay(check_in, check_out, adults)
    soup = BeautifulSoup(html, "html.parser")
    rows, seen = [], set()
    for card in soup.select(CARD_SELECTORS):
        name_node = card.select_one(NAME_SELECTORS)
        price_node = card.select_one(PRICE_SELECTORS)
        name, price = _clean_text(name_node), _clean_text(price_node)
        if not name or not price:
            continue
        link = card.select_one('a[href*="hotel"], a[href]')
        href = link.get("href") if link else ""
        property_url = urljoin(source_url, href) if href else source_url
        identity = card.get("data-hotelid") or (property_url if href else name)
        if identity in seen:
            continue
        seen.add(identity)
        rows.append({
            "飯店名": name,
            "價格": price,
            "幣別": "TWD" if re.search(r"(?:NT\$|TWD)", price, re.I) else "頁面未明示",
            "價格範圍": _price_scope(card, price_node),
            "稅費": _tax_text(card),
            "入住日": check_in,
            "退房日": check_out,
            "晚數": str(nights),
            "房數": "1",
            "成人數": str(adults),
            "擷取時間": captured_at,
            "來源網址": property_url,
        })
    if not rows:
        raise SourceChanged("Agoda 第一個結果頁沒有同卡片內可配對的飯店名與價格；未建立空白或錯配 CSV")
    return rows


def _select_destination(driver, wait):
    field = wait.until(lambda browser: browser.find_element(By.CSS_SELECTOR, '[data-selenium="textInput"]'))
    field.click()
    field.clear()
    field.send_keys("台中")
    suggestion = wait.until(
        lambda browser: browser.find_element(
            By.CSS_SELECTOR,
            '[role="option"][data-element-object-id="12080"], [role="option"][data-element-value="台中市"]',
        )
    )
    suggestion.click()
    wait.until(lambda browser: browser.find_element(By.CSS_SELECTOR, '[data-selenium="textInput"]').get_attribute("value") == "台中市")


def _select_date(driver, wait, value):
    selector = f'[data-selenium-date="{value}"]'
    for _ in range(18):
        matches = [element for element in driver.find_elements(By.CSS_SELECTOR, selector) if element.is_displayed()]
        if matches:
            matches[0].click()
            return
        next_button = wait.until(lambda browser: browser.find_element(By.CSS_SELECTOR, '[data-selenium="calendar-next-month-button"]'))
        if next_button.get_attribute("aria-disabled") == "true":
            break
        next_button.click()
    raise SourceChanged(f"Agoda 日期選擇器無法選到 {value}")


def _date_picker_is_visible(driver):
    return any(element.is_displayed() for element in driver.find_elements(By.CSS_SELECTOR, '[data-selenium-date]'))


def _select_dates(driver, wait, check_in, check_out):
    if not _date_picker_is_visible(driver):
        wait.until(lambda browser: browser.find_element(By.CSS_SELECTOR, '[data-selenium="checkInBox"]')).click()
    _select_date(driver, wait, check_in)
    _select_date(driver, wait, check_out)
    selected = (
        driver.find_element(By.CSS_SELECTOR, '[data-selenium="checkInBox"]').get_attribute("data-date"),
        driver.find_element(By.CSS_SELECTOR, '[data-selenium="checkOutBox"]').get_attribute("data-date"),
    )
    if selected != (check_in, check_out):
        raise SourceChanged(f"Agoda 顯示日期 {selected[0]} 至 {selected[1]}，與指定條件不同")


def _set_adults(driver, wait, adults):
    box = wait.until(lambda browser: browser.find_element(By.CSS_SELECTOR, '[data-selenium="occupancyBox"]'))
    visible_panels = [
        panel for panel in driver.find_elements(By.CSS_SELECTOR, '[data-selenium="occupancyAdults"]')
        if panel.is_displayed()
    ]
    if visible_panels:
        panel = visible_panels[0]
    else:
        box.click()
        panel = wait.until(lambda browser: browser.find_element(By.CSS_SELECTOR, '[data-selenium="occupancyAdults"]'))
    value = panel.find_element(By.CSS_SELECTOR, '[data-selenium="desktop-occ-adult-value"]')
    current = int(re.search(r"\d+", value.text).group())
    button_name = "plus" if adults > current else "minus"
    for expected in range(current + (1 if adults > current else -1), adults + (1 if adults > current else -1), 1 if adults > current else -1):
        panel.find_element(By.CSS_SELECTOR, f'button[data-selenium="{button_name}"]').click()
        wait.until(lambda browser, number=expected: int(re.search(r"\d+", value.text).group()) == number)
    # Clicking the summary closes the normal guest picker without submitting anything.
    box.click()


def _accommodation_url(check_in, nights, adults):
    query = urlencode({
        "city": "12080", "checkIn": check_in, "los": nights,
        "rooms": 1, "adults": adults, "children": 0, "currencyCode": "TWD",
    })
    return f"https://www.agoda.com/zh-tw/search?{query}"


def _save_failure_evidence(job, driver):
    try:
        job.sources.append(safe_url(driver.current_url))
        if "source_results.html" not in job.files:
            job.save_text("source_failure.html", driver.page_source)
        if "source_results.png" not in job.files:
            job.capture(driver, "source_failure.png")
    except (OSError, WebDriverException):
        pass


def run(job, args):
    nights = validate_stay(args.check_in, args.check_out, args.adults)
    driver = make_browser(args)
    stage = "開啟 Agoda 首頁"
    try:
        driver.get(URL)
        wait = WebDriverWait(driver, 35)
        stage = "選擇住宿搜尋"
        accommodation_tab = wait.until(
            lambda browser: browser.find_element(By.CSS_SELECTOR, '[role="tab"][data-element-name="all-rooms-tab"]')
        )
        if accommodation_tab.get_attribute("aria-selected") != "true":
            accommodation_tab.click()
        stage = "輸入並選擇台中市"
        _select_destination(driver, wait)
        stage = "設定入住與退房日期"
        _select_dates(driver, wait, args.check_in, args.check_out)
        stage = "設定成人數"
        _set_adults(driver, wait, args.adults)

        stage = "送出住宿搜尋"
        search = wait.until(
            lambda browser: next(
                (button for button in browser.find_elements(By.CSS_SELECTOR, 'button[data-element-name="search-button"]') if button.is_displayed()),
                False,
            )
        )
        search.click()
        try:
            wait.until(lambda browser: browser.current_url != URL)
        except TimeoutException:
            pass
        # 2026-09 的首頁偶爾把住宿按鈕誤導向 activities；保留 UI 輸入步驟後改用同一住宿條件 URL。
        if "/activities/" in driver.current_url or "/search" not in driver.current_url:
            driver.get(_accommodation_url(args.check_in, nights, args.adults))

        stage = "等待第一個住宿結果頁"
        try:
            wait.until(lambda browser: browser.find_elements(By.CSS_SELECTOR, CARD_SELECTORS))
        except TimeoutException:
            pass
        job.sources.append(safe_url(driver.current_url))
        result_html = driver.page_source
        job.save_text("source_results.html", result_html)
        job.capture(driver, "source_results.png")
        captured_at = datetime.now().astimezone().isoformat(timespec="seconds")
        stage = "解析第一個住宿結果頁的飯店名與價格"
        rows = parse_results(
            result_html,
            check_in=args.check_in,
            check_out=args.check_out,
            adults=args.adults,
            captured_at=captured_at,
            source_url=driver.current_url,
        )
    except (TimeoutException, WebDriverException, SourceChanged) as error:
        _save_failure_evidence(job, driver)
        return {
            "status": "partial",
            "note": f"Agoda 在「{stage}」未完成（{type(error).__name__}）；已保存當下 HTML/截圖，未建立假價格或進行預訂",
        }
    finally:
        close_browser(driver, args)

    job.save_csv("agoda_result.csv", FIELDS, rows)
    verified_twd = sum(row["幣別"] == "TWD" for row in rows)
    currency_note = (
        "頁面各筆均顯示 TWD"
        if verified_twd == len(rows)
        else f"請求幣別為 TWD；{len(rows) - verified_twd} 筆頁面未明示幣別"
    )
    return {
        "status": "passed",
        "note": (
            f"台中第一個結果頁 {len(rows)} 筆；{args.check_in} 至 {args.check_out}、1 房、"
            f"{args.adults} 成人、{nights} 晚；{currency_note}；未進行預訂"
        ),
        "rows": len(rows),
    }


if __name__ == "__main__":
    run_cli(16, run)
