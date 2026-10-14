"""
第 17 題（難）：使用 Selenium 自動登入 GitHub，抓取首頁兩個視窗的資料
================================================
題目要求（網址 https://github.com/）
    1. 使用 Selenium 及 WebDriver 自動登入帳號
    2. 抓取題目附圖中 1 號視窗的頁面資料（首頁左欄）
    3. 抓取題目附圖中 2 號視窗的頁面資料（首頁中間主欄）
    （課堂補充：難點在於登入表單裡有隱藏的 key 值）

做法（Selenium）
    1. 執行時在終端機輸入 GitHub 帳號與密碼（密碼不會顯示在畫面上，也不會存檔）。
       也可以事先設定環境變數 GITHUB_USERNAME、GITHUB_PASSWORD，就不用每次輸入。
    2. 開啟 https://github.com/login，由 Selenium 自動把帳密填進
       #login_field、#password，再按「Sign in」。
       「隱藏的 key 值」：登入表單裡有 authenticity_token（防偽造請求的金鑰）等隱藏欄位，
       每次開頁面都不一樣。用 requests 登入必須自己先抓出這些值一起送出；
       用 Selenium 是在真的瀏覽器裡按登入，瀏覽器會自動把隱藏欄位一起送出。
       程式會把這些隱藏欄位的名稱印出來，讓你看到它們確實存在。
    3. 如果帳號有二階段驗證（2FA）或裝置驗證，請在跳出的 Chrome 視窗裡手動完成，
       程式最多等 5 分鐘，直到登入成功。
    4. 登入後回到 https://github.com/ 首頁：
       1 號視窗＝左欄（aside.feed-left-sidebar）：新帳號會顯示「Create your first project」，
                 已有專案的帳號會顯示「Top repositories」清單。
       2 號視窗＝中間主欄（#dashboard 的 .news 區塊）：題目附圖當時是「Updates to your
                 homepage feed」提示卡；GitHub 改版後是首頁動態／Copilot、Pull requests 等面板。
       依「位置」抓取，不寫死文字，所以新舊版首頁都能抓到這兩個區域的全部文字。
    5. 印出兩個視窗的內容，存成 github_dashboard.csv（視窗、內容），
       並存一張登入後的首頁截圖 github_dashboard.png，方便對照兩個區域。
       （這兩個檔案含個人帳號資料，已列入 .gitignore，不會上傳到 GitHub；重新執行會直接覆蓋。）

執行
    python 第17題_GitHub登入首頁/main.py
"""

import csv
import getpass
import os
import time
from pathlib import Path

from selenium import webdriver
from selenium.common.exceptions import StaleElementReferenceException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

LOGIN_URL = "https://github.com/login"
HOME_URL = "https://github.com/"
FOLDER = Path(__file__).parent

# 兩個視窗在首頁上的位置（CSS 選擇器）；後面的是舊版首頁的備用寫法
WINDOWS = {
    "1號視窗（左欄）": ["aside.feed-left-sidebar", ".dashboard-sidebar"],
    "2號視窗（中間主欄）": ["#dashboard .news", "#dashboard"],
}


def ask_account():
    """讀取帳密：先看環境變數，沒有的話請使用者在終端機輸入（密碼隱藏）。"""
    username = os.environ.get("GITHUB_USERNAME") or input("GitHub 帳號（或 Email）：").strip()
    password = os.environ.get("GITHUB_PASSWORD") or getpass.getpass("GitHub 密碼（輸入時不會顯示）：")
    return username, password


def login(driver, username, password):
    """打開登入頁、自動填入帳密並按 Sign in，等到登入成功。"""
    driver.get(LOGIN_URL)
    wait = WebDriverWait(driver, 30)
    username_box = wait.until(EC.presence_of_element_located((By.ID, "login_field")))

    # 印出登入表單裡的隱藏欄位名稱（值是每次都會變的金鑰，不需要也不印出來）
    hidden = driver.find_elements(By.CSS_SELECTOR, "form[action='/session'] input[type='hidden']")
    names = [field.get_attribute("name") for field in hidden]
    print(f"登入表單的隱藏欄位：{', '.join(names)}")
    print("→ 其中 authenticity_token 就是隱藏的 key 值，瀏覽器按登入時會自動一起送出。\n")

    # 自動填入帳密並按下 Sign in
    username_box.send_keys(username)
    driver.find_element(By.ID, "password").send_keys(password)
    driver.find_element(By.NAME, "commit").click()

    # 登入成功後，頁面的 <meta name="user-login"> 會是使用者名稱
    print("已送出登入資料；如有二階段驗證，請在 Chrome 視窗中完成（最多等 5 分鐘）…")
    # 換頁時舊元素會失效（stale），先忽略、繼續等
    try:
        WebDriverWait(driver, 300, ignored_exceptions=[StaleElementReferenceException]).until(
            lambda d: logged_in_user(d) or login_failed(d)
        )
    except TimeoutException:
        raise SystemExit("等了 5 分鐘仍未登入成功（可能是二階段驗證沒有完成），程式結束。")
    if login_failed(driver):
        raise SystemExit("登入失敗：帳號或密碼錯誤。")
    print(f"登入成功：{logged_in_user(driver)}\n")


def logged_in_user(driver):
    meta = driver.find_elements(By.CSS_SELECTOR, "meta[name='user-login']")
    return meta[0].get_attribute("content") if meta else ""


def login_failed(driver):
    """登入頁上方出現紅色錯誤訊息（例如 Incorrect username or password）就是登入失敗。"""
    return any(error.is_displayed() for error in driver.find_elements(By.CSS_SELECTOR, ".flash-error"))


def read_window(driver, selectors):
    """依序嘗試選擇器，找到區塊後回傳裡面每一行文字。"""
    for selector in selectors:
        blocks = driver.find_elements(By.CSS_SELECTOR, selector)
        if blocks:
            return [line.strip() for line in blocks[0].text.splitlines() if line.strip()]
    return ["（找不到這個區塊，GitHub 首頁版面可能又改了）"]


def main():
    username, password = ask_account()
    driver = webdriver.Chrome()
    driver.set_window_size(1400, 1000)  # 視窗夠寬，首頁才會顯示左欄與中間兩欄
    rows = []
    try:
        login(driver, username, password)

        driver.get(HOME_URL)
        # 首頁各區塊是陸續載入的：先等左欄的標題（Top repositories／Create your first project）出現，
        # 再多等 3 秒讓中間主欄也載入完成
        try:
            WebDriverWait(driver, 30).until(EC.presence_of_element_located(
                (By.CSS_SELECTOR, "aside.feed-left-sidebar h2, aside.feed-left-sidebar h3")
            ))
        except TimeoutException:
            pass  # 舊版首頁的標題寫法可能不同，照樣往下抓
        time.sleep(3)
        driver.save_screenshot(str(FOLDER / "github_dashboard.png"))

        for window, selectors in WINDOWS.items():
            lines = read_window(driver, selectors)
            print(f"【{window}】")
            for line in lines:
                print(f"  {line}")
                rows.append({"視窗": window, "內容": line})
            print()
    finally:
        driver.quit()

    with open(FOLDER / "github_dashboard.csv", "w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=["視窗", "內容"])
        writer.writeheader()
        writer.writerows(rows)
    print("已存成 github_dashboard.csv 與截圖 github_dashboard.png")


if __name__ == "__main__":
    main()
