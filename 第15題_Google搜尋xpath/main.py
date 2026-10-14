"""
第 15 題（難）：進入 Google 搜尋「xpath」，捲動抓取資料並取得更多結果
================================================
題目要求（網址 https://www.google.com）
    1. 使用 WebDriver
    2. 搜尋列中輸入 xpath，並滾動滑鼠抓取全部資料，列印出本頁資訊
    3. 按下「更多結果」獲取更多資訊，並存入 xpath.csv
    （課堂補充：要由程式模擬滑鼠滾動，不能依賴人工操作）

做法（Selenium WebDriver）
    1. 開啟 Google 首頁，在搜尋框（name="q"）自動輸入 xpath 並按 Enter。
    2. 用 ActionChains.scroll_by_amount 模擬「滑鼠滾輪」一段一段往下捲，直到捲到頁面最底，
       讀出本頁每筆結果（#search 裡 <a> 內的 <h3> 是標題，<a> 的 href 是網址）並印出。
    3. 按「更多結果」載入更多資料，捲動後再讀一次。
       Google 已經把無限捲動的「更多結果」按鈕改回分頁的「下一頁」（id="pnnext"），
       所以程式會先找「更多結果」，沒有的話就按「下一頁」，效果一樣是取得更多搜尋結果。
    4. 兩次的結果合併（以網址去除重複）存成 xpath.csv（重新執行會直接覆蓋）。

    關於 Google 的機器人驗證：遇到「我不是機器人」驗證頁時，程式不會自動破解，
    會提示並等待你在 Chrome 視窗中手動完成（最多 5 分鐘）後繼續。

執行
    python 第15題_Google搜尋xpath/main.py
"""

import csv
import time
from pathlib import Path

from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait

URL = "https://www.google.com/?hl=zh-TW"
KEYWORD = "xpath"
MORE_TIMES = 1  # 按幾次「更多結果／下一頁」
OUTPUT = Path(__file__).parent / "xpath.csv"
RESULT_TITLE = "#search a h3"  # 搜尋結果的標題


def wait_for_results(driver):
    """等搜尋結果出現；若跳出機器人驗證頁（網址含 /sorry/），請使用者手動完成。"""
    WebDriverWait(driver, 30).until(
        lambda d: "/sorry/" in d.current_url or d.find_elements(By.CSS_SELECTOR, RESULT_TITLE)
    )
    if "/sorry/" in driver.current_url:
        print("Google 跳出「我不是機器人」驗證：請在 Chrome 視窗中手動完成，程式最多等 5 分鐘…")
        try:
            WebDriverWait(driver, 300).until(lambda d: d.find_elements(By.CSS_SELECTOR, RESULT_TITLE))
        except TimeoutException:
            raise SystemExit("等了 5 分鐘仍未完成 Google 的機器人驗證，程式結束。請重新執行並在 Chrome 視窗中完成驗證。")


def scroll_with_mouse_wheel(driver):
    """模擬滑鼠滾輪，每次往下滾 500 像素，直到頁面最底（最多滾 50 次，避免無限迴圈）。"""
    for _ in range(50):
        ActionChains(driver).scroll_by_amount(0, 500).perform()  # 滑鼠滾輪往下滾
        time.sleep(0.5)
        at_bottom = driver.execute_script(
            "return window.innerHeight + window.scrollY >= document.body.scrollHeight - 2"
        )
        if at_bottom:
            break


def get_results(driver):
    """讀出目前頁面的每筆搜尋結果（標題、網址）。"""
    results = []
    for h3 in driver.find_elements(By.CSS_SELECTOR, RESULT_TITLE):
        link = h3.find_element(By.XPATH, "./ancestor::a[1]")  # h3 外層的 <a>
        if h3.text:
            results.append({"標題": h3.text, "網址": link.get_attribute("href")})
    return results


def click_more(driver):
    """按「更多結果」；新版 Google 沒有這個按鈕，就改按「下一頁」。"""
    more = driver.find_elements(By.XPATH, "//a[.//span[text()='更多結果']]")
    button = more[0] if more else driver.find_element(By.ID, "pnnext")  # pnnext＝下一頁
    print(f"\n>>> 按下「{'更多結果' if more else '下一頁'}」取得更多結果\n")

    old_url = driver.current_url
    old_count = len(driver.find_elements(By.CSS_SELECTOR, RESULT_TITLE))
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", button)
    ActionChains(driver).move_to_element(button).click().perform()  # 滑鼠移過去再點
    # 「下一頁」會換網址；「更多結果」會在同一頁多出結果
    WebDriverWait(driver, 30).until(
        lambda d: d.current_url != old_url
        or len(d.find_elements(By.CSS_SELECTOR, RESULT_TITLE)) > old_count
    )
    wait_for_results(driver)


def print_results(results):
    for number, row in enumerate(results, start=1):
        print(f"{number}. {row['標題']}")
        print(f"   {row['網址']}")


def main():
    driver = webdriver.Chrome()
    all_results = {}  # 網址 → 標題（用 dict 去除重複）
    try:
        driver.get(URL)
        search_box = WebDriverWait(driver, 20).until(lambda d: d.find_element(By.NAME, "q"))
        search_box.send_keys(KEYWORD)
        search_box.send_keys(Keys.ENTER)
        wait_for_results(driver)

        for round_number in range(MORE_TIMES + 1):
            if round_number > 0:
                click_more(driver)
            scroll_with_mouse_wheel(driver)  # 滾動滑鼠，讓本頁內容全部出現
            results = get_results(driver)
            print(f"===== 本頁資訊（第 {round_number + 1} 次載入，{len(results)} 筆）=====")
            print_results(results)
            for row in results:
                all_results.setdefault(row["網址"], row["標題"])
    finally:
        driver.quit()

    with open(OUTPUT, "w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=["標題", "網址"])
        writer.writeheader()
        writer.writerows({"標題": title, "網址": url} for url, title in all_results.items())
    print(f"\n共 {len(all_results)} 筆搜尋結果，已存成 {OUTPUT.name}")


if __name__ == "__main__":
    main()
