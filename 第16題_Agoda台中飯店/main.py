"""
第 16 題（難）：抓取 Agoda 搜尋「台中」的飯店名稱與價格
================================================
題目要求（網址 https://www.agoda.com/zh-tw/）
    1. 輸入「台中」
    2. 抓取結果頁面存入 agoda_result.csv，包括飯店名及價格
    3. <加分> 使用 Selenium 及 WebDriver 自動輸入「台中」，並加入 CSV 檔

做法（Selenium 操作網頁 + BeautifulSoup 解析，含加分項：由程式自動輸入「台中」）
    1. 開啟 Agoda 首頁，在目的地搜尋框（data-selenium="textInput"）自動輸入「台中」。
    2. 從跳出的建議清單點選「台中市」。
       選完 Agoda 會自動打開日曆，按 Esc 關掉，沿用網站預設的入住／退房日期。
    3. 按「搜出好價」，結果頁會開在新分頁，切換過去。
    4. 結果頁的飯店卡片要捲到畫面上才會載入內容，所以一段一段慢慢往下捲，
       每捲一次就用 BeautifulSoup 讀出已載入的卡片：飯店名（data-selenium="hotel-name"）、
       價格（幣別 hotel-currency + 金額 display-price）。已額滿、沒有價格的飯店略過。
    5. 存成 agoda_result.csv（飯店名、價格），重新執行會直接覆蓋。

    價格說明：Agoda 顯示的是「每晚價格（不含稅及其他費用）」，日期與房價會隨查詢當天變動。

執行
    python 第16題_Agoda台中飯店/main.py
"""

import csv
import time
from pathlib import Path

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

URL = "https://www.agoda.com/zh-tw/"
KEYWORD = "台中"
OUTPUT = Path(__file__).parent / "agoda_result.csv"


def search_taichung(driver):
    """在首頁自動輸入「台中」，選「台中市」，再按「搜出好價」。"""
    wait = WebDriverWait(driver, 30)
    driver.get(URL)

    # 1. 自動輸入「台中」
    search_box = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "input[data-selenium='textInput']")))
    search_box.click()
    search_box.send_keys(KEYWORD)

    # 2. 點建議清單裡的「台中市」
    city = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "[role='option'][data-element-value='台中市']")))
    city.click()
    time.sleep(1)
    ActionChains(driver).send_keys(Keys.ESCAPE).perform()  # 關掉自動跳出的日曆
    check_in = driver.find_element(By.CSS_SELECTOR, "[data-selenium='checkInText']").text
    check_out = driver.find_element(By.CSS_SELECTOR, "[data-selenium='checkOutText']").text
    print(f"目的地：台中市｜入住 {check_in}｜退房 {check_out}")

    # 3. 按「搜出好價」，結果會開在新分頁
    tabs_before = len(driver.window_handles)
    search_button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button[data-element-name='search-button']")))
    search_button.click()
    wait.until(lambda d: len(d.window_handles) > tabs_before)
    driver.switch_to.window(driver.window_handles[-1])  # 切換到新分頁
    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "[data-selenium='hotel-name']")))


def collect_hotels(driver):
    """慢慢往下捲到底，邊捲邊用 BeautifulSoup 讀出已載入的飯店名與價格。"""
    hotels = {}  # 飯店名 → 價格（用 dict 避免同一間飯店重複）
    for _ in range(100):  # 最多捲 100 次，避免無限迴圈
        soup = BeautifulSoup(driver.page_source, "html.parser")
        for card in soup.select("li[data-selenium='hotel-item']"):
            name = card.select_one("[data-selenium='hotel-name']")
            price = card.select_one("[data-selenium='display-price']")
            currency = card.select_one("[data-selenium='hotel-currency']")
            if name and price:  # 還沒載入或已額滿的卡片沒有價格，先跳過
                hotels.setdefault(name.get_text(strip=True), f"{currency.get_text(strip=True)} {price.get_text(strip=True)}")

        at_bottom = driver.execute_script(
            "return window.innerHeight + window.scrollY >= document.body.scrollHeight - 2"
        )
        if at_bottom:
            break
        driver.execute_script("window.scrollBy(0, 700);")  # 往下捲 700 像素
        time.sleep(1)  # 等新的卡片載入
    return [{"飯店名": name, "價格": price} for name, price in hotels.items()]


def main():
    driver = webdriver.Chrome()
    driver.set_window_size(1366, 900)  # 視窗太小時 Agoda 會改成手機版面
    try:
        search_taichung(driver)
        hotels = collect_hotels(driver)
    finally:
        driver.quit()

    for number, hotel in enumerate(hotels, start=1):
        print(f"{number}. {hotel['飯店名']}：{hotel['價格']}")

    with open(OUTPUT, "w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=["飯店名", "價格"])
        writer.writeheader()
        writer.writerows(hotels)
    print(f"\n結果頁共 {len(hotels)} 間有價格的飯店，已存成 {OUTPUT.name}")


if __name__ == "__main__":
    main()
