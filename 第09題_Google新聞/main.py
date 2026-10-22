"""
第 9 題（中）：使用 Selenium 從 Google 新聞輸出各分類的新聞標題
================================================
題目要求（使用 Selenium）
    焦點提要：[焦點新聞，地方新聞]
    焦點新聞：[所有包含的新聞標題]
    地方新聞：[所有包含的新聞標題]
    您的主題：[所有包含的新聞標題]
    更多新聞：[所有包含的新聞標題]
    （課堂補充：要使用 Selenium 找到網頁標題）

做法（Selenium）
    1. 開啟 Google 新聞（繁體中文／台灣版）首頁，印出網頁標題 driver.title。
    2. 新聞是往下捲才陸續載入，所以一直捲到頁面最底，直到高度不再增加。
    3. 用 XPath 依「區塊標題文字」找到 焦點新聞、地方新聞、您的主題、更多新聞：
       從標題往上找，第一個「裡面有新聞連結」的外層元素，就是這個分類的範圍。
    4. 在每個分類範圍裡，讀出所有新聞連結（網址含 ./read/）的文字，就是新聞標題；
       同一則新聞常有圖片連結和文字連結兩個，以網址去除重複。
    5. 依題目格式印出，並另存 google_news.csv（分類、標題、網址），重新執行會直接覆蓋。

    注意：Google 新聞的內容即時變動；「地方新聞」會依連線所在地區顯示。

執行
    python 第09題_Google新聞/main.py
"""

import csv
import time
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

URL = "https://news.google.com/home?hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
OUTPUT = Path(__file__).parent / "google_news.csv"
CATEGORIES = ["焦點新聞", "地方新聞", "您的主題", "更多新聞"]
NEWS_LINK = ".//a[contains(@href, './read/')]"  # 新聞文章的連結（相對網址都以 ./read/ 開頭）


def scroll_to_bottom(driver):
    """一直捲到頁面最底；連續 3 次高度都沒變，代表新聞已全部載入（最多捲 40 次，避免頁面一直變長時停不下來）。"""
    last_height = 0
    unchanged = 0
    for _ in range(40):
        if unchanged >= 3:
            break
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(1.5)  # 等新內容載入
        height = driver.execute_script("return document.body.scrollHeight")
        unchanged = unchanged + 1 if height == last_height else 0
        last_height = height


def get_titles(driver, category):
    """找出某個分類（例如「焦點新聞」）裡的所有新聞標題與網址。"""
    # 分類標題可能是 h2 或 h3，例如 <h3>焦點新聞</h3>
    headings = driver.find_elements(
        By.XPATH, f"//*[self::h2 or self::h3][normalize-space()='{category}']"
    )
    if not headings:  # 例如「地方新聞」要看所在地區，有時不會出現：這個分類就是 0 則，其他分類照常抓
        print(f"（找不到「{category}」這個分類，跳過）")
        return []
    heading = headings[0]
    # 從標題往上找「第一個裡面有新聞連結的祖先元素」，它就是這個分類的範圍
    section = heading.find_element(By.XPATH, f"./ancestor::*[{NEWS_LINK}][1]")

    news = {}  # 網址 → 標題（用 dict 自動去除重複的網址）
    for link in section.find_elements(By.XPATH, NEWS_LINK):
        title = link.get_attribute("textContent").strip()
        if title:  # 圖片連結沒有文字，跳過
            news.setdefault(link.get_attribute("href"), title)
    return [{"分類": category, "標題": title, "網址": url} for url, title in news.items()]


def main():
    driver = webdriver.Chrome()
    try:
        driver.get(URL)
        WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.XPATH, NEWS_LINK)))
        print(f"網頁標題：{driver.title}\n")

        scroll_to_bottom(driver)
        results = {category: get_titles(driver, category) for category in CATEGORIES}
    finally:
        driver.quit()

    print("焦點提要：[焦點新聞，地方新聞]")
    for category, news in results.items():
        print(f"\n{category}：（共 {len(news)} 則）")
        for item in news:
            print(f"  - {item['標題']}")

    with open(OUTPUT, "w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=["分類", "標題", "網址"])
        writer.writeheader()
        for news in results.values():
            writer.writerows(news)
    total = sum(len(news) for news in results.values())
    print(f"\n四個分類共 {total} 則新聞，已存成 {OUTPUT.name}")


if __name__ == "__main__":
    main()
