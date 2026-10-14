"""
第 14 題（難）：抓取 HoopsHype 的 NBA 球員薪水
================================================
題目要求
    抓 https://hoopshype.com/salaries/players 網頁中的 NBA 球員薪水資訊
    1. 使用 Selenium 和 BeautifulSoup
    2. 抓取前 3 位高薪球員的基本資料（名字、背號及薪資）存入 highest.csv
    3. 抓下本頁表格所有內容存入 all_play.csv

做法（Selenium 操作網頁 + BeautifulSoup 解析）
    薪資表是 JavaScript 動態產生的，而且分頁顯示（每頁 20 位，下方有「1 of 30」和左右箭頭），
    所以用 Selenium 換頁，每一頁的網頁原始碼交給 BeautifulSoup 解析。
    1. 開啟薪資頁，用 BeautifulSoup 讀出表格標題列（排名、Player、各球季薪資）與每一列資料。
    2. 按分頁列右邊的箭頭到下一頁，直到「N of N」最後一頁，全部存成 all_play.csv。
    3. 表格是依目前球季薪資由高到低排序，前 3 列就是前 3 位高薪球員。
       表格裡沒有背號，所以用 Selenium 打開這 3 位球員的個人頁，
       用 BeautifulSoup 讀出姓名與背號（例如 #30），連同薪資存成 highest.csv。

輸出（與本程式同一個資料夾，重新執行會直接覆蓋）
    all_play.csv：排名、球員、各球季薪資（薪資前的 P／T 是網站標示的球員選擇權／球隊選擇權）
    highest.csv：名字、背號、薪資（目前球季）

執行
    python 第14題_NBA球員薪水/main.py
"""

import csv
import re
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, StaleElementReferenceException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

URL = "https://hoopshype.com/salaries/players"
FOLDER = Path(__file__).parent
# 分頁列長這樣：[<] 1 of 30 [>]，也就是「夾在兩個按鈕中間、文字含 of 的 span」
PAGER = "//span[contains(., ' of ')][preceding-sibling::button][following-sibling::button]"


def parse_table(html):
    """用 BeautifulSoup 解析目前這一頁的薪資表，回傳（欄位名稱, 資料列, 每列的球員網址）。"""
    soup = BeautifulSoup(html, "html.parser")
    table = soup.select_one("table")
    headers = [th.get_text(" ", strip=True) for th in table.select("thead th")]
    headers[0] = "排名"  # 第一欄網站沒有標題，自己命名

    rows, links = [], []
    for tr in table.select("tbody tr"):
        cells = [" ".join(td.get_text().split()) for td in tr.select("td")]
        cells = [cell.replace("$ ", "$") for cell in cells]  # 「$ 62,587,158」→「$62,587,158」
        rows.append(dict(zip(headers, cells)))
        link = tr.select_one("a[href]")  # 球員名字的連結 → 個人頁
        links.append(urljoin(URL, link["href"]) if link else "")
    return headers, rows, links


def page_numbers(driver):
    """讀出分頁列的「目前頁 of 總頁數」，回傳 (目前頁, 總頁數)。"""
    text = driver.find_element(By.XPATH, PAGER).text  # 例如 "1 of 30"
    current, total = re.findall(r"\d+", text)
    return int(current), int(total)


def first_player(driver):
    """目前表格第一列的球員名字（用來判斷表格是否已換頁）。"""
    return driver.find_element(By.CSS_SELECTOR, "table tbody tr td:nth-child(2)").text


def collect_all_pages(driver):
    """從第 1 頁一路按到最後一頁，回傳全部資料。"""
    # 換頁時表格會重畫，找不到元素或元素失效都先忽略，繼續等
    wait = WebDriverWait(driver, 30, ignored_exceptions=(NoSuchElementException, StaleElementReferenceException))
    driver.get(URL)
    wait.until(EC.presence_of_element_located((By.XPATH, PAGER)))

    all_rows, top_links = [], []
    while True:
        headers, rows, links = parse_table(driver.page_source)
        all_rows.extend(rows)
        if not top_links:
            top_links = links[:3]  # 第 1 頁的前 3 位就是最高薪的 3 位
        current, total = page_numbers(driver)
        print(f"薪資表第 {current}/{total} 頁：{len(rows)} 位，累計 {len(all_rows)} 位")
        if current == total:
            break

        # 分頁列「1 of 30」右邊的按鈕就是下一頁
        previous_first = first_player(driver)
        next_button = driver.find_element(By.XPATH, PAGER + "/following-sibling::button[1]")
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", next_button)
        driver.execute_script("arguments[0].click();", next_button)  # 用 JS 點擊，避免被浮動廣告擋住
        # 等頁碼變成下一頁、而且表格第一列換人，才算換頁完成
        wait.until(lambda d: page_numbers(d)[0] == current + 1 and first_player(d) != previous_first)
    return headers, all_rows, top_links


def get_player_profile(driver, url):
    """打開球員個人頁，用 BeautifulSoup 讀出姓名與背號。"""
    driver.get(url)
    WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.TAG_NAME, "h2")))
    soup = BeautifulSoup(driver.page_source, "html.parser")
    name_tag = soup.select_one("h2")  # 個人頁上方的大標題就是球員全名
    name = name_tag.get_text(" ", strip=True)
    number_text = name_tag.parent.find(string=re.compile(r"^#\d+$"))  # 背號在姓名旁邊，格式像「#30」
    number = number_text.strip("#") if number_text else ""
    return name, number


def save_csv(path, fields, rows):
    with open(path, "w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main():
    options = webdriver.ChromeOptions()
    options.page_load_strategy = "eager"  # 網頁廣告很多，主要內容出現就先操作
    driver = webdriver.Chrome(options=options)
    try:
        headers, all_rows, top_links = collect_all_pages(driver)
        season = headers[2]  # 第三欄是目前球季，例如 2026-27

        highest = []
        for row, url in zip(all_rows[:3], top_links):
            name, number = get_player_profile(driver, url)
            highest.append({"名字": name, "背號": number, "薪資": row[season]})
    finally:
        driver.quit()

    save_csv(FOLDER / "all_play.csv", headers, all_rows)
    save_csv(FOLDER / "highest.csv", ["名字", "背號", "薪資"], highest)

    print(f"\n{season} 球季薪資前 3 名：")
    for player in highest:
        print(f"  {player['名字']} #{player['背號']}：{player['薪資']}")
    print(f"\n薪資表共 {len(all_rows)} 位球員，已存成 all_play.csv；前 3 名已存成 highest.csv")


if __name__ == "__main__":
    main()
