"""
第 2 題（中）：抓取臺灣銀行牌告匯率最新掛牌資料
================================================
題目要求
    1. 抓 https://rate.bot.com.tw/xrt?Lang=zh-TW 的最新掛牌資料
    2. 存入 bank.csv

做法（Selenium 載入網頁 + BeautifulSoup 解析）
    臺灣銀行網站現在多了一層「瀏覽器驗證」（Challenge Validation）：
    用 requests 直接抓只會拿到驗證頁，拿不到匯率表。
    所以先用 Selenium 開一個真的 Chrome 載入網頁（瀏覽器會自動通過驗證），
    再把網頁原始碼交給 BeautifulSoup 解析匯率表。

    匯率表每一列是一種幣別，每個儲存格都有 data-table 屬性標明欄位，例如
    <td data-table="本行現金買入">31.67</td>，依這個屬性取值就不會錯欄。
    （網頁為了列印另外藏了一組重複欄位，只取第一個符合的格子即可。）

輸出
    bank.csv：幣別、現金匯率-本行買入、現金匯率-本行賣出、即期匯率-本行買入、即期匯率-本行賣出
    （與本程式同一個資料夾，重新執行會直接覆蓋）

執行
    python 第02題_台銀牌價/main.py
"""

import csv
from pathlib import Path

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

URL = "https://rate.bot.com.tw/xrt?Lang=zh-TW"
OUTPUT = Path(__file__).parent / "bank.csv"

# CSV 欄位名稱 → 網頁儲存格的 data-table 屬性
COLUMNS = {
    "現金匯率-本行買入": "本行現金買入",
    "現金匯率-本行賣出": "本行現金賣出",
    "即期匯率-本行買入": "本行即期買入",
    "即期匯率-本行賣出": "本行即期賣出",
}
FIELDS = ["幣別", *COLUMNS]


def get_html_with_chrome(url):
    """用 Selenium 開 Chrome 載入網頁，等匯率表出現後回傳網頁原始碼。"""
    driver = webdriver.Chrome()
    try:
        driver.get(url)
        # 最多等 30 秒，直到匯率表的第一列出現（代表已通過驗證、資料已載入）
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "table[title='牌告匯率'] tbody tr"))
        )
        return driver.page_source
    finally:
        driver.quit()  # 不論成功失敗都關閉瀏覽器


def parse_rates(html):
    """解析牌告匯率表，回傳（掛牌時間, 每種幣別的匯率列表）。"""
    soup = BeautifulSoup(html, "html.parser")
    listed_time = soup.select_one("span.time").get_text(strip=True)  # 牌價最新掛牌時間

    rows = []
    for tr in soup.select("table[title='牌告匯率'] tbody tr"):
        # 幣別名稱，例如「美金 (USD)」；網頁上桌機版與手機版各寫一次，取桌機版
        currency = tr.select_one("td.currency .hidden-phone").get_text(strip=True)
        row = {"幣別": currency}
        for field, data_table in COLUMNS.items():
            cell = tr.select_one(f"td[data-table='{data_table}']")  # 第一個符合的格子
            row[field] = cell.get_text(strip=True)
        rows.append(row)
    return listed_time, rows


def save_csv(rows, path):
    """存成 CSV（utf-8-sig：Excel 開啟中文不會亂碼）。"""
    with open(path, "w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def main():
    html = get_html_with_chrome(URL)
    listed_time, rows = parse_rates(html)

    print(f"牌價最新掛牌時間：{listed_time}\n")
    print("幣別 | 現金買入 | 現金賣出 | 即期買入 | 即期賣出")
    for row in rows:
        print(" | ".join(row[field] for field in FIELDS))

    save_csv(rows, OUTPUT)
    print(f"\n共 {len(rows)} 種幣別，已存成 {OUTPUT.name}")


if __name__ == "__main__":
    main()
