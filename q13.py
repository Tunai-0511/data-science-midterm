"""第 13 題：在 momo 首頁自動搜尋 nba 並保存結果 DOM。"""

from __future__ import annotations

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait

from search_tools import inspect_momo_search_result, search_box_score
from support import SourceBlocked, SourceChanged, close_browser, make_browser, run_cli


URL = "https://www.momoshop.com.tw/main/Main.jsp"
QUERY = "nba"


def run(job, args):
    driver = make_browser(args)
    try:
        driver.get(URL)
        WebDriverWait(driver, 20).until(
            lambda browser: browser.find_elements(By.CSS_SELECTOR, "input, textarea")
            or "驗證或拒絕頁" in inspect_momo_search_result(
                browser.page_source, browser.current_url, QUERY
            )[1]
        )

        initial_ok, initial_note = inspect_momo_search_result(
            driver.page_source, driver.current_url, QUERY
        )
        if "驗證或拒絕頁" in initial_note:
            job.save_text("momo_blocked.html", driver.page_source)
            job.capture(driver, "momo_blocked.png")
            raise SourceBlocked("momo 首頁顯示存取驗證或拒絕頁；已保存瀏覽器證據")

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
            job.save_text("momo_unexpected_home.html", driver.page_source)
            job.capture(driver, "momo_unexpected_home.png")
            raise SourceChanged("momo 首頁找不到具搜尋語意且可操作的輸入元件")

        search_box = max(ranked, key=lambda pair: pair[0])[1]
        search_box.clear()
        search_box.send_keys(QUERY)
        search_box.send_keys(Keys.ENTER)

        WebDriverWait(driver, 30).until(
            lambda browser: inspect_momo_search_result(
                browser.page_source, browser.current_url, QUERY
            )[0]
            or "驗證或拒絕頁" in inspect_momo_search_result(
                browser.page_source, browser.current_url, QUERY
            )[1]
        )
        html = driver.page_source
        ok, note = inspect_momo_search_result(html, driver.current_url, QUERY)
        if not ok:
            job.save_text("momo_failed_result.html", html)
            job.capture(driver, "momo_failed_result.png")
            if "驗證或拒絕頁" in note:
                raise SourceBlocked(f"momo 搜尋後未能正常存取：{note}")
            raise SourceChanged(f"momo 搜尋結果未通過驗證：{note}")

        # 僅在搜尋條件及商品卡皆通過驗證後，才使用題目指定檔名。
        job.save_text("NBA_test.html", html)
        job.capture(driver, "NBA_test.png")
        return {
            "status": "passed",
            "note": f"已從首頁自動輸入 nba，並保存載入完成的搜尋結果 DOM；{note}",
        }
    finally:
        close_browser(driver, args)


if __name__ == "__main__":
    run_cli(13, run)
