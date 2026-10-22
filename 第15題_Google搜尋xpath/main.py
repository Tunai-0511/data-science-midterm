"""
第 15 題（難）：進入 Google 搜尋「xpath」，捲動抓取資料並取得更多結果
================================================
題目要求（網址 https://www.google.com）
    1. 使用 WebDriver
    2. 搜尋列中輸入 xpath，並滾動滑鼠抓取全部資料，列印出本頁資訊
    3. 按下「更多結果」獲取更多資訊，並存入 xpath.csv
    （課堂補充：要由程式模擬滑鼠滾動，不能依賴人工操作）

做法（Selenium WebDriver）
    1. 建立 Chrome WebDriver 並加入防機器人特徵設定（關閉自動化標記與 CDP 注入）。
    2. 開啟 Google 首頁，在搜尋框（name="q"）以微延遲逐字輸入 xpath 關鍵字並按 Enter 送出。
    3. 用 ActionChains.scroll_by_amount 模擬「滑鼠滾輪」一段一段往下捲，直到捲到頁面最底，
       讀出本頁每筆結果（#search 裡 <a> 內的 <h3> 是標題，<a> 的 href 是網址）並印出。
       Google 現在把連結包成轉址 https://www.google.com/goto?url=…（加密過，看不出原網站），
       所以用 requests 對轉址送一次請求但「不跟著跳轉」，回應標頭 Location 就是原網站的網址。
    4. 按「更多結果」載入更多資料，捲動後再讀一次（要按幾次由 MORE_TIMES 設定，目前 9 次＝讀到第 10 頁）。
       Google 已經把無限捲動的「更多結果」按鈕改回分頁的「下一頁」（id="pnnext"），
       所以程式會先找「更多結果」，沒有的話就按「下一頁」，效果一樣是取得更多搜尋結果。
       「xpath」的結果有 30 頁以上，不建議一路按到底：每多一頁就是多一次自動搜尋，更容易被 Google 擋下。
    5. 所有讀到的結果合併（以網址去除重複）存成 xpath.csv（重新執行會直接覆蓋）。

    關於 Google 的機器人驗證與防偵測機制：
    程式透過 ChromeOptions 排除自動化開關並注入 CDP 腳本隱藏 webdriver 特徵，
    搭配真人打字節奏，已大幅降低觸發 reCAPTCHA 的機率。
    遇到「我不是機器人」驗證頁時，程式會在終端機提示並等待在 Chrome 視窗中手動完成（最多 5 分鐘）後繼續；
    若無下一頁、驗證沒通過、翻頁失敗或按 Ctrl+C 時會停止翻頁，已抓到的結果照樣安全存檔。

執行
    python 第15題_Google搜尋xpath/main.py
"""

import csv
from pathlib import Path
import random
import time
from urllib.parse import urlparse

import requests
from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait

URL = "https://www.google.com/?hl=zh-TW"
KEYWORD = "xpath"
# 按幾次「更多結果／下一頁」：9 次＝第 1 頁再往後翻 9 頁，讀到第 10 頁。
# Google 的「xpath」結果有 30 頁以上，按越多次越容易被 Google 擋下；
# 沒有下一頁、被擋下或按 Ctrl+C 時都會提早停止，已抓到的結果照樣存檔。
MORE_TIMES = 9
OUTPUT = Path(__file__).parent / "xpath.csv"
RESULT_TITLE = "#search a h3"  # 搜尋結果的標題


def create_driver():
    """建立 Chrome WebDriver，並隱藏自動化測試特徵以大幅降低觸發 Google 機器人驗證的機率。"""
    options = webdriver.ChromeOptions()
    # 關閉 Blink 引擎的自動化控制特徵
    options.add_argument("--disable-blink-features=AutomationControlled")
    # 移除 Chrome 頂部的「Chrome 目前受到自動化測試軟體控制」資訊列
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    driver = webdriver.Chrome(options=options)
    # 利用 CDP 在所有新頁面注入 JS，確保 navigator.webdriver 屬性為 undefined
    driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument",
        {
            "source": """
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                })
            """
        },
    )
    return driver


def wait_for_results(driver):
    """等搜尋結果出現；若跳出機器人驗證頁（網址含 /sorry/），請使用者手動完成。回傳 True＝結果已出現。"""
    WebDriverWait(driver, 30).until(
        lambda d: "/sorry/" in d.current_url or d.find_elements(By.CSS_SELECTOR, RESULT_TITLE)
    )
    if "/sorry/" not in driver.current_url:
        return True
    print("Google 跳出「我不是機器人」驗證：請在 Chrome 視窗中手動完成，程式最多等 5 分鐘…")
    print("（如果一直出現新的圖片、怎麼選都過不了，代表 Google 擋下了程式控制的瀏覽器，可按 Ctrl+C 結束）")
    try:
        WebDriverWait(driver, 300).until(lambda d: d.find_elements(By.CSS_SELECTOR, RESULT_TITLE))
        return True
    except TimeoutException:
        print("等了 5 分鐘仍未通過 Google 的機器人驗證。")
        return False


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


def real_url(url):
    """把 Google 的轉址連結（google.com/goto?url=…）換成原網站的網址；本來就是原網址的直接回傳。"""
    link = urlparse(url)
    if "google." not in link.netloc or link.path != "/goto":
        return url
    try:
        # 不跟著跳轉：Google 回應「302 跳轉」，標頭 Location 就是要跳去的原網址
        response = requests.get(url, allow_redirects=False, timeout=15)
    except requests.RequestException:
        return url  # 連不上就保留轉址連結
    location = response.headers.get("Location", "")
    return location if location.startswith("http") and "/sorry/" not in location else url


def get_results(driver):
    """讀出目前頁面的每筆搜尋結果（標題、原網站的網址）。"""
    results = []
    for h3 in driver.find_elements(By.CSS_SELECTOR, RESULT_TITLE):
        link = h3.find_element(By.XPATH, "./ancestor::a[1]")  # h3 外層的 <a>
        if h3.text:
            results.append({"標題": h3.text, "網址": real_url(link.get_attribute("href"))})
    return results


def click_more(driver):
    """按「更多結果」；新版 Google 沒有這個按鈕，就改按「下一頁」。回傳 True＝已載入更多結果。"""
    more = driver.find_elements(By.XPATH, "//a[.//span[text()='更多結果']]")
    buttons = more or driver.find_elements(By.ID, "pnnext")  # pnnext＝下一頁
    if not buttons:
        print("\n已經沒有「更多結果／下一頁」了。")
        return False
    button = buttons[0]
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
    return wait_for_results(driver)


def print_results(results):
    for number, row in enumerate(results, start=1):
        print(f"{number}. {row['標題']}")
        print(f"   {row['網址']}")


def main():
    driver = create_driver()
    all_results = {}  # 網址 → 標題（用 dict 去除重複）
    try:
        driver.get(URL)
        search_box = WebDriverWait(driver, 20).until(lambda d: d.find_element(By.NAME, "q"))
        for char in KEYWORD:
            search_box.send_keys(char)
            time.sleep(random.uniform(0.05, 0.12))
        time.sleep(0.3)
        search_box.send_keys(Keys.ENTER)
        if not wait_for_results(driver):
            raise SystemExit("第 1 頁就被 Google 擋下，沒有抓到資料。可以換個時間或換一台電腦再執行。")

        try:
            for round_number in range(MORE_TIMES + 1):
                if round_number > 0 and not click_more(driver):  # 沒有下一頁或被擋下就停止
                    break
                scroll_with_mouse_wheel(driver)  # 滾動滑鼠，讓本頁內容全部出現
                results = get_results(driver)
                print(f"===== 本頁資訊（第 {round_number + 1} 次載入，{len(results)} 筆）=====")
                print_results(results)
                for row in results:
                    all_results.setdefault(row["網址"], row["標題"])
        except KeyboardInterrupt:  # 按 Ctrl+C：停止翻頁，已抓到的照樣存檔
            print("\n中途停止，先把已抓到的結果存檔。")
        except WebDriverException as error:  # 含 TimeoutException：翻頁等太久或點不到，前面抓到的照樣存檔
            print(f"\n翻頁時發生問題（{type(error).__name__}），先把已抓到的結果存檔。")
    finally:
        driver.quit()

    with open(OUTPUT, "w", newline="", encoding="utf-8-sig") as file:
        # 每格加引號：標題開頭是 # 時，有些 CSV 檢視器會把整行當成註解
        writer = csv.DictWriter(file, fieldnames=["標題", "網址"], quoting=csv.QUOTE_ALL)
        writer.writeheader()
        writer.writerows({"標題": title, "網址": url} for url, title in all_results.items())
    print(f"\n共 {len(all_results)} 筆搜尋結果，已存成 {OUTPUT.name}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:  # 使用者按 Ctrl+C 中止
        print("\n已取消執行。")
