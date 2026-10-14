"""
第 4 題（中）：抓取博客來「演算法」的搜尋結果
================================================
題目要求
    1. 網址 https://search.books.com.tw/search/query/key/{0}/cat/all，{0} = "演算法"
    2. 抓取資料存入 booklist.csv，內容包括 ["書名", "網址", "作者", "書價"]

做法（Selenium 載入網頁 + BeautifulSoup 解析）
    博客來搜尋頁前面有 Cloudflare 防護：用 requests 直接抓會得到 403
    「連線暫時異常」，所以改用 Selenium 開真的 Chrome 載入網頁，再交給
    BeautifulSoup 解析。（搜尋結果直接寫在 HTML 裡，沒有另外的 JSON 資料。）

    1. 把「演算法」放進題目給的網址 {0}，開啟搜尋結果（題目網址就是第 1 頁，共 60 本）。
    2. 每本書在 <div class="table-td" id="prod-itemlist-商品編號"> 裡：
       書名 = h4 連結的 title，作者 = p.author 裡的連結，書價 = ul.price 裡最後一個數字（元）。
       搜尋頁的連結是博客來的轉址網址，改寫成正式商品頁 https://www.books.com.tw/products/商品編號。
    3. 存成同資料夾的 booklist.csv（重新執行會直接覆蓋）。

    為什麼只抓題目網址這一頁：博客來在換到第 2 頁時會跳出 Cloudflare 的
    「Verify you are human」真人驗證，程式不應該繞過驗證，所以只抓題目指定的網址。

執行
    python 第04題_博客來書籍/main.py
"""

import csv
import re
from pathlib import Path
from urllib.parse import quote

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

KEYWORD = "演算法"
URL_TEMPLATE = "https://search.books.com.tw/search/query/key/{0}/cat/all"  # 題目給的網址
OUTPUT = Path(__file__).parent / "booklist.csv"
FIELDS = ["書名", "網址", "作者", "書價"]
BOOK_SELECTOR = "div.table-td[id^='prod-itemlist-']"  # 每一本書的區塊


def get_html_with_chrome(url):
    """用 Selenium 開 Chrome 載入搜尋頁，等書籍出現後回傳網頁原始碼。"""
    driver = webdriver.Chrome()
    try:
        driver.get(url)
        if "Just a moment" in driver.title:  # Cloudflare 驗證頁的標題
            print("博客來要求真人驗證：請在 Chrome 視窗中手動勾選，程式最多等 2 分鐘。")
        try:
            WebDriverWait(driver, 120).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, BOOK_SELECTOR))
            )
        except TimeoutException:
            raise SystemExit("等了 2 分鐘仍沒有看到搜尋結果（可能被博客來暫時擋下），請稍後再執行。")
        return driver.page_source
    finally:
        driver.quit()


def parse_books(html):
    """解析搜尋結果頁，回傳書籍清單。"""
    soup = BeautifulSoup(html, "html.parser")
    books = []
    for item in soup.select(BOOK_SELECTOR):
        product_id = item["id"].replace("prod-itemlist-", "")  # 例如 0011055506
        title = item.select_one("h4 a")["title"]  # 書名連結的 title 屬性就是完整書名
        authors = [a.get_text(strip=True) for a in item.select("p.author a")]
        # 價格文字像「優惠價: 79 折, 316 元」或「優惠價: 316 元」，取最後一個數字（實際售價）
        price_text = item.select_one("ul.price").get_text(" ", strip=True)
        numbers = re.findall(r"\d[\d,]*", price_text)

        books.append({
            "書名": title,
            "網址": f"https://www.books.com.tw/products/{product_id}",
            "作者": "、".join(authors),
            "書價": numbers[-1].replace(",", "") if numbers else "",
        })
    return books


def save_csv(rows, path):
    """存成 CSV（utf-8-sig：Excel 開啟中文不會亂碼）。"""
    with open(path, "w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def main():
    url = URL_TEMPLATE.format(quote(KEYWORD))  # 把「演算法」轉成網址編碼後放進 {0}
    print(f"搜尋網址：{url}\n")

    html = get_html_with_chrome(url)
    books = parse_books(html)

    for number, book in enumerate(books, start=1):
        print(f"{number}. {book['書名']}｜{book['作者']}｜{book['書價']} 元｜{book['網址']}")

    save_csv(books, OUTPUT)
    print(f"\n「{KEYWORD}」搜尋結果共 {len(books)} 本書，已存成 {OUTPUT.name}")


if __name__ == "__main__":
    main()
