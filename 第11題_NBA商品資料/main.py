"""
第 11 題（難）：抓取 NBA 商品資料（每一頁存成一個 CSV）
================================================
題目要求
    抓 https://fchart.github.io/ML/nba_items.html 裡的資料
    1. 列出「所有」NBA 商品資料
    2. 每存完一個 CSV 檔，便印出其編號，如「儲存頁面: 1」
    3. 分頁存入不同的 NBA_Products{1~n}.csv 檔內
    4. 開啟的 CSV 檔不能為亂碼
    （課堂補充：要操作分頁直到最後一頁，第 1 頁到第 n 頁分別存成檔案）

做法（Selenium）
    這個網頁的表格是 JavaScript 動態產生的，一次只顯示 10 筆，要按分頁按鈕才會換資料，
    所以用 Selenium 操作瀏覽器：
    1. 開啟網頁，先從分頁列的「最後一頁 »」按鈕讀出總頁數（按鈕的 value 就是最後一頁的頁碼）。
    2. 讀出目前這一頁表格的每一列（商品編號、商品名稱、價格）。
    3. 存成 NBA_Products{頁碼}.csv，存完立刻印出「儲存頁面: 頁碼」。
    4. 按「下一頁 >」按鈕，等表格內容換掉後，回到第 2 步；
       到了最後一頁就沒有「下一頁」按鈕，迴圈結束，並核對是否真的到了第 1 步讀到的最後一頁。
    5. CSV 用 utf-8-sig 編碼（加上 BOM），Excel 開啟中文不會亂碼。
    6. 開始前先刪掉舊的 NBA_Products*.csv，重新執行就是全新覆蓋。

執行
    python 第11題_NBA商品資料/main.py
"""

import csv
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

URL = "https://fchart.github.io/ML/nba_items.html"
FOLDER = Path(__file__).parent
FIELDS = ["商品編號", "商品名稱", "價格"]


def read_table(driver):
    """讀出目前顯示的表格（tbody#table-body 的每一列）。"""
    products = []
    for tr in driver.find_elements(By.CSS_SELECTOR, "#table-body tr"):
        cells = [td.text for td in tr.find_elements(By.TAG_NAME, "td")]
        products.append(dict(zip(FIELDS, cells)))
    return products


def save_page(page, products):
    """把一頁商品存成 NBA_Products{page}.csv。"""
    path = FOLDER / f"NBA_Products{page}.csv"
    with open(path, "w", newline="", encoding="utf-8-sig") as file:  # utf-8-sig：Excel 不會亂碼
        writer = csv.DictWriter(file, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(products)


def main():
    for old_file in FOLDER.glob("NBA_Products*.csv"):  # 清掉上次的輸出檔
        old_file.unlink()

    driver = webdriver.Chrome()
    wait = WebDriverWait(driver, 20)
    total = 0
    try:
        driver.get(URL)
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "#table-body tr")))
        # 分頁列的「最後一頁 »」按鈕，value 就是最後一頁的頁碼
        last_button = driver.find_element(By.XPATH, "//button[contains(., '最後一頁')]")
        last_page = int(last_button.get_attribute("value"))
        print(f"商品資料共 {last_page} 頁，從第 1 頁一路按「下一頁」到最後一頁\n")

        page = 1
        while True:
            products = read_table(driver)
            for product in products:
                print(product)
            save_page(page, products)
            print(f"儲存頁面: {page}")
            total += len(products)

            next_buttons = driver.find_elements(By.CSS_SELECTOR, "button.nextbtn")  # 「下一頁 >」
            if not next_buttons:  # 最後一頁沒有下一頁按鈕
                break
            first_row = driver.find_element(By.CSS_SELECTOR, "#table-body tr")
            next_buttons[0].click()
            wait.until(EC.staleness_of(first_row))  # 舊的表格列消失，代表已換成下一頁
            page += 1
    finally:
        driver.quit()

    status = "已到最後一頁" if page == last_page else f"注意：只到第 {page} 頁，沒有到最後一頁（第 {last_page} 頁）"
    print(f"\n{status}。全部 {page} 頁、{total} 筆商品，已存成 NBA_Products1.csv ~ NBA_Products{page}.csv")


if __name__ == "__main__":
    main()
