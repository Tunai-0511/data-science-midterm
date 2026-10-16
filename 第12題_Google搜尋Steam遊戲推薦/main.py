"""
第 12 題（難）：從 Google 搜尋「Steam 遊戲推薦」
================================================
題目要求
    1. 使用 Selenium 和 WebDriver
    2. 列出搜尋結果及其超連結
    3. 存入 CSV 檔中
    （課堂補充：一定要使用 Selenium 與 WebDriver）

做法（Selenium）
    1. 開啟 Google 首頁，在搜尋框（name="q"）自動輸入「Steam 遊戲推薦」並按 Enter。
    2. 每一筆搜尋結果的標題是 #search 區塊裡、包在 <a> 連結中的 <h3>；
       讀出 h3 的文字（標題）與外層 <a> 的 href（超連結）。
    3. Google 現在把搜尋結果的連結包成轉址 https://www.google.com/goto?url=…，
       後面那串是加密過的，看不出原本是哪個網站。所以用 requests 對這個轉址送一次請求、
       但「不跟著跳轉」（allow_redirects=False），Google 回應的 302 裡，標頭 Location 就是原網站的網址。
    4. 印出結果，並存成 steam_games.csv（標題、網址），重新執行會直接覆蓋。

    關於 Google 的機器人驗證：
    Google 偶爾會判定自動化瀏覽器是機器人，跳出「我不是機器人」驗證頁。
    程式不會（也不應該）自動破解驗證；遇到時會在終端機提示，
    請在跳出的 Chrome 視窗中「手動」完成驗證，程式會等待最多 5 分鐘再繼續。

執行
    python 第12題_Google搜尋Steam遊戲推薦/main.py
"""

import csv
from pathlib import Path
from urllib.parse import urlparse

import requests
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait

URL = "https://www.google.com/?hl=zh-TW"
KEYWORD = "Steam 遊戲推薦"
OUTPUT = Path(__file__).parent / "steam_games.csv"
RESULT_TITLE = "#search a h3"  # 搜尋結果的標題（h3 包在連結 a 裡面）


def wait_for_results(driver):
    """等搜尋結果出現；若跳出機器人驗證頁（網址含 /sorry/），請使用者手動完成。"""
    WebDriverWait(driver, 30).until(
        lambda d: "/sorry/" in d.current_url or d.find_elements(By.CSS_SELECTOR, RESULT_TITLE)
    )
    if "/sorry/" in driver.current_url:
        print("Google 跳出「我不是機器人」驗證：請在 Chrome 視窗中手動完成，程式最多等 5 分鐘…")
        print("（如果一直出現新的圖片、怎麼選都過不了，代表 Google 擋下了程式控制的瀏覽器，可按 Ctrl+C 結束）")
        try:
            WebDriverWait(driver, 300).until(lambda d: d.find_elements(By.CSS_SELECTOR, RESULT_TITLE))
        except TimeoutException:
            raise SystemExit("等了 5 分鐘仍未通過 Google 的機器人驗證，程式結束。可以換個時間或換一台電腦再執行。")


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
    """讀出這一頁的每筆搜尋結果（標題與超連結），以網址去除重複。"""
    results = {}
    for h3 in driver.find_elements(By.CSS_SELECTOR, RESULT_TITLE):
        link = h3.find_element(By.XPATH, "./ancestor::a[1]")  # h3 外層的 <a>
        url = link.get_attribute("href")
        if h3.text and url:
            results.setdefault(real_url(url), h3.text)  # 存原網站的網址，不存 Google 轉址
    return [{"標題": title, "網址": url} for url, title in results.items()]


def main():
    driver = webdriver.Chrome()
    try:
        driver.get(URL)
        search_box = WebDriverWait(driver, 20).until(lambda d: d.find_element(By.NAME, "q"))
        search_box.send_keys(KEYWORD)  # 自動輸入關鍵字
        search_box.send_keys(Keys.ENTER)  # 按 Enter 送出搜尋
        wait_for_results(driver)
        print("讀取搜尋結果，並把 Google 的轉址連結換成原網站的網址…\n")
        results = get_results(driver)
    finally:
        driver.quit()

    print(f"搜尋「{KEYWORD}」的結果：\n")
    for number, row in enumerate(results, start=1):
        print(f"{number}. {row['標題']}")
        print(f"   {row['網址']}")

    with open(OUTPUT, "w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=["標題", "網址"])
        writer.writeheader()
        writer.writerows(results)
    print(f"\n共 {len(results)} 筆搜尋結果，已存成 {OUTPUT.name}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:  # 使用者按 Ctrl+C 中止
        print("\n已取消執行。")
