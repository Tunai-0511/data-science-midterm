"""第 9 題：以 Selenium 擷取 Google 新聞指定分類。"""

from __future__ import annotations

import json
import time

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

from search_tools import (
    NEWS_OUTPUT_CATEGORIES,
    extract_google_news_sections,
    is_verification_page,
)
from support import SourceBlocked, SourceChanged, close_browser, make_browser, pause_for_user, run_cli


URL = "https://news.google.com/?hl=zh-TW&gl=TW&ceid=TW%3Azh-Hant"


def run(job, args):
    driver = make_browser(args)
    try:
        driver.get(URL)
        WebDriverWait(driver, 20).until(
            lambda browser: browser.find_elements(By.CSS_SELECTOR, "main, [role='main']")
            or is_verification_page(
                browser.title, browser.page_source, browser.current_url
            )
        )

        if is_verification_page(driver.title, driver.page_source, driver.current_url):
            job.save_text("news_verification.html", driver.page_source)
            job.capture(driver, "news_verification.png")
            if not getattr(args, "interactive", False):
                raise SourceBlocked("Google 新聞顯示人工驗證頁；已保存證據並停止")
            pause_for_user(driver, args, "Google 新聞要求人工驗證")
            if is_verification_page(driver.title, driver.page_source, driver.current_url):
                raise SourceBlocked("人工操作後仍是驗證頁；未重複嘗試規避")

        # 有界捲動：只在目前首頁內觸發懶載入，不巡覽其他導覽連結。
        stable_rounds = 0
        previous_count = -1
        previous_height = -1
        scroll_complete = False
        for _ in range(10):
            current_count = len(
                driver.find_elements(
                    By.CSS_SELECTOR,
                    "main a[href*='/read/'], main a[href*='/articles/'], "
                    "[role='main'] a[href*='/read/'], [role='main'] a[href*='/articles/']",
                )
            )
            current_height = driver.execute_script("return document.body.scrollHeight")
            if current_count == previous_count and current_height == previous_height:
                stable_rounds += 1
            else:
                stable_rounds = 0
            at_bottom = driver.execute_script(
                "return window.scrollY + window.innerHeight >= document.body.scrollHeight - 5"
            )
            if at_bottom and stable_rounds >= 2:
                scroll_complete = True
                break
            previous_count = current_count
            previous_height = current_height
            driver.execute_script(
                "window.scrollTo(0, document.body.scrollHeight);"
            )
            time.sleep(0.7)

        html = driver.page_source
        sections, missing = extract_google_news_sections(html)
        rows = [
            {"category": category, "title": item["title"], "url": item["url"]}
            for category in NEWS_OUTPUT_CATEGORIES
            for item in sections.get(category, [])
        ]
        notes = {
            "scope": "Google 新聞繁體中文／台灣首頁；最多捲動 10 次，連續 2 次新聞連結數不變即停止",
            "requested_categories": list(NEWS_OUTPUT_CATEGORIES),
            "focus_summary": {
                "expected_subsections": ["焦點新聞", "地方新聞"],
                "available_subsections": [
                    name for name in ("焦點新聞", "地方新聞") if name in sections
                ],
            },
            "available_categories": list(sections),
            "missing_categories": missing,
            "row_counts": {name: len(items) for name, items in sections.items()},
            "claim": "只擷取可由實際標題定位且界定於該容器內的新聞；未出現的分類不補造",
            "scroll_complete": scroll_complete,
        }
        job.save_text("news_notes.json", json.dumps(notes, ensure_ascii=False, indent=2))
        job.save_text("news_page.html", html)
        job.capture(driver, "news.png")
        if not rows:
            raise SourceChanged("目前版面找不到可由題目分類標題界定的新聞，已保存實際頁面與說明")
        job.save_csv("news.csv", ["category", "title", "url"], rows)

        if missing or not scroll_complete:
            limits = []
            if missing:
                limits.append(f"未出現分類：{', '.join(missing)}")
            if not scroll_complete:
                limits.append("10 次捲動上限內未證實到達穩定頁尾")
            return {
                "status": "partial",
                "rows": len(rows),
                "note": f"實際取得 {len(rows)} 筆；{'；'.join(limits)}。範圍為目前首頁的有界捲動結果",
            }
        return {
            "status": "passed",
            "rows": len(rows),
            "note": f"焦點提要的兩個子區與其餘兩區共 {len(rows)} 筆；已到達穩定頁尾",
        }
    finally:
        close_browser(driver, args)


if __name__ == "__main__":
    run_cli(9, run)
