"""第 12 題：由 Google 首頁搜尋 Steam 遊戲推薦並存第一頁自然結果。"""

from __future__ import annotations

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait

from search_tools import extract_google_results, is_verification_page, search_box_score
from support import SourceBlocked, SourceChanged, close_browser, make_browser, pause_for_user, run_cli


URL = "https://www.google.com/?hl=zh-TW"
QUERY = "Steam 遊戲推薦"


def run(job, args):
    driver = make_browser(args)
    try:
        driver.get(URL)
        WebDriverWait(driver, 15).until(
            lambda browser: browser.find_elements(By.CSS_SELECTOR, "input, textarea")
            or is_verification_page(
                browser.title, browser.page_source, browser.current_url
            )
        )
        if is_verification_page(driver.title, driver.page_source, driver.current_url):
            job.save_text("google_home_verification.html", driver.page_source)
            job.capture(driver, "google_home_verification.png")
            if not getattr(args, "interactive", False):
                raise SourceBlocked("Google 顯示人工驗證頁；已保存證據並停止")
            pause_for_user(driver, args, "Google 要求人工驗證")
            if is_verification_page(driver.title, driver.page_source, driver.current_url):
                raise SourceBlocked("人工操作後仍是首頁驗證頁；未重複嘗試規避")

        ranked = []
        for element in driver.find_elements(By.CSS_SELECTOR, "input, textarea"):
            attrs = {
                name: element.get_attribute(name) or ""
                for name in ("name", "id", "placeholder", "aria-label", "title", "type")
            }
            score = search_box_score(attrs)
            if score and element.is_displayed() and element.is_enabled():
                ranked.append((score, element))
        if not ranked:
            job.save_text("google_home_unexpected.html", driver.page_source)
            job.capture(driver, "google_home_unexpected.png")
            raise SourceChanged("首頁找不到具搜尋語意且可操作的輸入元件")

        search_box = max(ranked, key=lambda pair: pair[0])[1]
        search_box.clear()
        search_box.send_keys(QUERY)
        search_box.send_keys(Keys.ENTER)
        WebDriverWait(driver, 25).until(
            lambda browser: browser.find_elements(By.CSS_SELECTOR, "#search")
            or is_verification_page(
                browser.title, browser.page_source, browser.current_url
            )
        )

        if is_verification_page(driver.title, driver.page_source, driver.current_url):
            job.save_text("google_results_verification.html", driver.page_source)
            job.capture(driver, "google_results_verification.png")
            if not getattr(args, "interactive", False):
                raise SourceBlocked("送出搜尋後出現人工驗證頁；已保存證據並停止")
            pause_for_user(driver, args, "送出搜尋後 Google 要求人工驗證")
            if is_verification_page(driver.title, driver.page_source, driver.current_url):
                raise SourceBlocked("人工操作後仍是驗證頁；未重複嘗試規避")

        rows = extract_google_results(driver.page_source)
        job.save_text("steam_search_page.html", driver.page_source)
        job.capture(driver, "steam_search.png")
        if not rows:
            raise SourceChanged("第一頁找不到可驗證的自然搜尋標題與連結；未建立空 CSV")
        job.save_csv("steam_search.csv", ["title", "url"], rows)
        return {
            "status": "passed",
            "rows": len(rows),
            "note": f"Google 第一個結果頁的自然搜尋結果 {len(rows)} 筆；不含廣告與導覽連結",
        }
    finally:
        close_browser(driver, args)


if __name__ == "__main__":
    run_cli(12, run)
