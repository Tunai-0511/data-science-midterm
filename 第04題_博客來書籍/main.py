"""
第 4 題（中）：抓取博客來「演算法」的全部搜尋結果
================================================
題目要求
    1. 網址 https://search.books.com.tw/search/query/key/{0}/cat/all，{0} = "演算法"
    2. 抓取資料存入 booklist.csv，內容包括 ["書名", "網址", "作者", "書價"]
    （課堂補充：要抓 URL 的資料整理成 JSON 格式，再跑過裡面的內容）

做法（Selenium 操作網頁 + BeautifulSoup 解析 + JSON）
    博客來搜尋頁前面有 Cloudflare 防護：用 requests 直接抓會得到 403「連線暫時異常」，
    所以用 Selenium 開真的 Chrome 操作網頁，每一頁的網頁原始碼交給 BeautifulSoup 解析。

    1. 把「演算法」放進題目給的網址 {0}，開啟搜尋結果第 1 頁（每頁 60 本），
       並讀出網頁上的「搜尋結果共 N 筆，頁數 1 / 總頁數」。
    2. 每本書在 <div class="table-td" id="prod-itemlist-商品編號"> 裡：
       書名 = h4 連結的 title，作者 = p.author 裡的連結，書價 = ul.price 裡最後一個數字（元）。
       搜尋頁的連結是博客來的轉址網址，改寫成正式商品頁 https://www.books.com.tw/products/商品編號。
    3. 按頁面下方的「下一頁」，重複第 2 步，直到最後一頁
       （最後一頁的「下一頁」連結會變成 javascript:void(0)）。
    4. 博客來的搜尋網址回傳的是 HTML（網站沒有提供 JSON），所以把全部的書整理成
       JSON 格式（一本書一個物件），存成 booklist.json。
    5. 讀回 booklist.json，用迴圈逐筆跑過裡面的每本書，寫入 booklist.csv（重新執行會直接覆蓋）。

    關於真人驗證：換頁時博客來（Cloudflare）會跳出「Verify you are human」。
    程式不會偽裝成一般瀏覽器、也不會繞過驗證；遇到時會暫停，請你在 Chrome 視窗中
    親手勾選，通過後自動繼續抓下一頁（每次最多等 5 分鐘）。
    如果勾了一直重來，或想提早結束，按 Ctrl+C 即可，已抓到的頁面會先存檔。
    程式最後會印出「抓到幾本／網站共幾筆」，方便確認有沒有抓齊。

執行
    python 第04題_博客來書籍/main.py
"""

import csv
import json
import re
import time
from pathlib import Path
from urllib.parse import quote

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

KEYWORD = "演算法"
URL_TEMPLATE = "https://search.books.com.tw/search/query/key/{0}/cat/all"  # 題目給的網址
OUTPUT = Path(__file__).parent / "booklist.csv"
JSON_OUTPUT = Path(__file__).parent / "booklist.json"
FIELDS = ["書名", "網址", "作者", "書價"]
BOOK_SELECTOR = "div.table-td[id^='prod-itemlist-']"  # 每一本書的區塊


def wait_for_books(driver):
    """等這一頁的書出現；被 Cloudflare 真人驗證擋下時，請使用者親手勾選。回傳 True＝書已出現。"""
    WebDriverWait(driver, 30).until(
        lambda d: d.find_elements(By.CSS_SELECTOR, BOOK_SELECTOR) or "Just a moment" in d.title
    )
    if driver.find_elements(By.CSS_SELECTOR, BOOK_SELECTOR):
        return True

    print("\n========== 需要你幫忙 ==========")
    print("博客來跳出「Verify you are human」真人驗證：請到 Chrome 視窗勾選方框。")
    print("通過後程式會自動繼續；最多等 5 分鐘，或按 Ctrl+C 結束（已抓到的會先存檔）。")
    try:
        WebDriverWait(driver, 300).until(EC.presence_of_element_located((By.CSS_SELECTOR, BOOK_SELECTOR)))
    except TimeoutException:
        return False
    print("驗證通過，繼續抓取。\n")
    return True


def search_summary(html):
    """讀出「搜尋結果共 673 筆, 頁數 1 / 12」，回傳 (總筆數, 總頁數)。"""
    text = BeautifulSoup(html, "html.parser").get_text(" ", strip=True)
    match = re.search(r"搜尋結果共\s*([\d,]+)\s*筆.*?頁數\s*\d+\s*/\s*(\d+)", text)
    return int(match.group(1).replace(",", "")), int(match.group(2))


def parse_books(html):
    """解析一頁搜尋結果，回傳這一頁的書籍清單。"""
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


def collect_all_books(driver, url):
    """從題目網址（第 1 頁）開始，一頁一頁按「下一頁」到最後一頁，回傳（全部的書, 網站顯示的總筆數）。"""
    books = {}  # 網址 → 書（同一本書若重複出現，用網址去除重複）
    total_books = total_pages = 0
    page = 1
    driver.get(url)
    try:
        while True:
            if not wait_for_books(driver):
                print(f"第 {page} 頁一直沒有通過真人驗證，停止翻頁，先把已抓到的 {len(books)} 本存檔。")
                break
            if page == 1:
                total_books, total_pages = search_summary(driver.page_source)
                print(f"網站顯示：搜尋結果共 {total_books} 筆，{total_pages} 頁\n")

            page_books = parse_books(driver.page_source)
            for book in page_books:
                books.setdefault(book["網址"], book)
            print(f"第 {page}/{total_pages} 頁：{len(page_books)} 本，累計 {len(books)} 本")

            # 找「下一頁」；到了最後一頁，下一頁的連結是 javascript:void(0)，就結束
            next_links = [
                link for link in driver.find_elements(By.CSS_SELECTOR, "ul.page a.next")
                if "javascript" not in (link.get_attribute("href") or "")
            ]
            if not next_links:
                break
            time.sleep(2)  # 每頁之間稍等，不要連續快速翻頁
            first_book = driver.find_element(By.CSS_SELECTOR, BOOK_SELECTOR)
            next_links[0].click()
            WebDriverWait(driver, 30).until(EC.staleness_of(first_book))  # 舊頁面的書消失＝已經在換頁
            page += 1
    except (KeyboardInterrupt, WebDriverException):  # 按了 Ctrl+C，或 Chrome 視窗被關掉
        print(f"\n中途停止，先把已抓到的 {len(books)} 本存檔。")
    return list(books.values()), total_books


def save_json(books, path):
    """把書籍清單存成 JSON 格式（ensure_ascii=False 讓中文直接顯示，不會變成 \\u 編碼）。"""
    with open(path, "w", encoding="utf-8") as file:
        json.dump(books, file, ensure_ascii=False, indent=2)


def json_to_csv(json_path, csv_path):
    """讀回 JSON，逐筆跑過裡面的每本書，寫入 CSV（utf-8-sig：Excel 開啟中文不會亂碼）。"""
    with open(json_path, encoding="utf-8") as file:
        books = json.load(file)  # JSON 陣列 → Python 的 list，裡面每本書是一個 dict

    with open(csv_path, "w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDS)
        writer.writeheader()
        for number, book in enumerate(books, start=1):  # 跑過 JSON 裡的每一筆
            print(f"{number}. {book['書名']}｜{book['作者']}｜{book['書價']} 元｜{book['網址']}")
            writer.writerow(book)
    return len(books)


def main():
    url = URL_TEMPLATE.format(quote(KEYWORD))  # 把「演算法」轉成網址編碼後放進 {0}
    print(f"搜尋網址：{url}")

    driver = webdriver.Chrome()
    try:
        books, total_books = collect_all_books(driver, url)
    finally:
        driver.quit()
    if not books:
        raise SystemExit("第 1 頁就被博客來擋下，沒有抓到任何書，請稍後再執行。")

    save_json(books, JSON_OUTPUT)
    print(f"\n已整理成 JSON 格式，存成 {JSON_OUTPUT.name}；第一筆長這樣：")
    print(json.dumps(books[0], ensure_ascii=False, indent=2), "\n")

    count = json_to_csv(JSON_OUTPUT, OUTPUT)
    print(f"\n「{KEYWORD}」共抓到 {count} 本書（網站顯示 {total_books} 筆），已存成 {OUTPUT.name}")
    if count < total_books:
        print("注意：這次沒有抓齊全部頁面（真人驗證沒有通過或中途停止），可以再執行一次。")


if __name__ == "__main__":
    main()
