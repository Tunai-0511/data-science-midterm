"""第 15 題：Google 搜尋 xpath、捲動並取得有界的更多結果。"""

from __future__ import annotations

import time

from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait

from search_tools import (
    completion_status,
    extract_google_results,
    is_verification_page,
    pagination_action,
    search_box_score,
)
from support import SourceBlocked, SourceChanged, close_browser, make_browser, pause_for_user, run_cli, safe_url


URL = "https://www.google.com/?hl=zh-TW"
QUERY = "xpath"


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

        all_rows = []
        seen = set()
        load_number = 1
        navigation_actions = 0
        stop_reason = "no_control"
        while True:
            if is_verification_page(driver.title, driver.page_source, driver.current_url):
                job.save_text(f"verification_load_{load_number}.html", driver.page_source)
                job.capture(driver, f"verification_load_{load_number}.png")
                if not all_rows:
                    if getattr(args, "interactive", False):
                        pause_for_user(driver, args, "Google 搜尋結果要求人工驗證")
                        if not is_verification_page(
                            driver.title, driver.page_source, driver.current_url
                        ):
                            continue
                    raise SourceBlocked("Google 搜尋結果顯示人工驗證頁；已保存證據並停止")
                stop_reason = "blocked"
                break

            # 每個目前結果頁最多捲動 10 次；連續兩次筆數不變便停止。
            stable_rounds = 0
            previous_count = -1
            previous_height = -1
            scroll_complete = False
            for _ in range(10):
                count = len(extract_google_results(driver.page_source))
                height = driver.execute_script("return document.body.scrollHeight")
                if count == previous_count and height == previous_height:
                    stable_rounds += 1
                else:
                    stable_rounds = 0
                at_bottom = driver.execute_script(
                    "return window.scrollY + window.innerHeight >= document.body.scrollHeight - 5"
                )
                if at_bottom and stable_rounds >= 2:
                    scroll_complete = True
                    break
                previous_count = count
                previous_height = height
                driver.execute_script(
                    "window.scrollTo(0, document.body.scrollHeight);"
                )
                time.sleep(0.7)

            page_rows = extract_google_results(driver.page_source)
            print(
                f"載入範圍 {load_number}：本頁自然結果 {len(page_rows)} 筆；網址 {safe_url(driver.current_url)}",
                flush=True,
            )
            for row in page_rows:
                if row["url"] in seen:
                    continue
                seen.add(row["url"])
                all_rows.append(
                    {"page": str(load_number), "title": row["title"], "url": row["url"]}
                )
                print(f"  {row['title']} | {row['url']}", flush=True)
            if not page_rows and not all_rows:
                job.save_text("xpath_unexpected.html", driver.page_source)
                job.capture(driver, "xpath_unexpected.png")
                raise SourceChanged("結果主區塊存在，但找不到可驗證的自然搜尋結果")
            if not scroll_complete:
                stop_reason = "scroll_bound"
                break

            controls = []
            for element in driver.find_elements(By.CSS_SELECTOR, "a, button"):
                if not element.is_displayed() or not element.is_enabled():
                    continue
                action = pagination_action(
                    element.text or "", element.get_attribute("aria-label") or ""
                )
                if action:
                    controls.append((0 if action == "more" else 1, action, element))
            controls.sort(key=lambda item: item[0])
            if not controls:
                stop_reason = (
                    "no_next_after_navigation" if navigation_actions else "no_control"
                )
                break
            if load_number >= args.max_pages:
                stop_reason = "max_pages"
                break

            _, action, control = controls[0]
            verified_label = (
                " ".join((control.text or control.get_attribute("aria-label") or "").split())
            )
            print(f"操作：{verified_label}（{action}）", flush=True)
            old_url = driver.current_url
            old_count = len(page_rows)
            driver.execute_script(
                "arguments[0].scrollIntoView({block: 'center'});", control
            )
            try:
                control.click()
            except WebDriverException:
                job.save_text(f"pagination_failure_{load_number}.html", driver.page_source)
                job.capture(driver, f"pagination_failure_{load_number}.png")
                stop_reason = "control_failed"
                break
            try:
                WebDriverWait(driver, 20).until(
                    lambda browser: is_verification_page(
                        browser.title, browser.page_source, browser.current_url
                    )
                    or browser.current_url != old_url
                    or len(extract_google_results(browser.page_source)) > old_count
                )
            except TimeoutException:
                job.save_text(f"pagination_timeout_{load_number}.html", driver.page_source)
                job.capture(driver, f"pagination_timeout_{load_number}.png")
                stop_reason = "control_timeout"
                break
            load_number += 1
            navigation_actions += 1

        if not all_rows:
            raise SourceChanged("未取得任何 xpath 自然搜尋結果；未建立空 CSV")
        job.save_csv("xpath.csv", ["page", "title", "url"], all_rows)
        if "xpath.png" not in job.files:
            job.capture(driver, "xpath.png")
        status = completion_status(stop_reason)
        if stop_reason == "no_next_after_navigation":
            note = f"取得目前可載入範圍的 {len(all_rows)} 筆自然結果；已無更多結果或下一頁控制"
        elif stop_reason == "max_pages":
            note = (
                f"取得 {len(all_rows)} 筆後達安全上限 {args.max_pages} 個載入範圍；"
                "仍有更多結果，因此只標示部分完成"
            )
        elif stop_reason == "blocked":
            note = f"取得 {len(all_rows)} 筆後遇到人工驗證頁；已保存證據並停止，結果為部分"
        elif stop_reason == "no_control":
            note = f"取得第一個結果頁 {len(all_rows)} 筆，但沒有題目所述的更多結果或實際下一頁控制；介面已變更，結果為部分"
        elif stop_reason == "scroll_bound":
            note = f"取得 {len(all_rows)} 筆後達目前頁 10 次捲動上限，未證實到達穩定頁尾；結果為部分"
        else:
            note = f"取得 {len(all_rows)} 筆後分頁控制未能載入新資料；結果為部分"
        return {"status": status, "rows": len(all_rows), "note": note}
    finally:
        close_browser(driver, args)


if __name__ == "__main__":
    run_cli(15, run)
