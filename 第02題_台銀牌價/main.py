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
    表格的完整內容是：幣別、現金匯率（買入／賣出）、即期匯率（買入／賣出）、
    遠期匯率、歷史匯率。遠期、歷史匯率在表上只是「查詢」連結（另外的網頁），
    所以存它們的網址；再加上表格上方的「牌價最新掛牌時間」。
    （網頁為了列印另外藏了一組重複欄位，標題寫著「歷史匯率」，但數字和現金、即期匯率
      完全一樣，不是另外的資料，所以只取第一個符合的格子。）

延伸：買賣價差——哪種外幣換起來最虧
    銀行「賣出」價（你跟銀行買外幣）一定比「買入」價（你把外幣賣回給銀行）高，中間的差就是銀行賺的。
    價差（%）＝（賣出 − 買入）÷ 賣出 × 100，代表用台幣買進外幣、再立刻賣回去，會損失幾 %。
    分別算現金與即期的價差，另存 bank_detail.csv，並印出現金價差最大的 5 種外幣；
    網頁上「-」代表這種幣別沒有提供，不計算。

輸出
    bank.csv：幣別、現金匯率-本行買入、現金匯率-本行賣出、即期匯率-本行買入、即期匯率-本行賣出、
              遠期匯率（查詢網址）、歷史匯率（查詢網址）、掛牌時間
    bank_detail.csv（延伸）：幣別、現金與即期的買入、賣出、價差、價差（%）
    （與本程式同一個資料夾，重新執行會直接覆蓋）

執行
    python 第02題_台銀牌價/main.py
"""

import csv
from pathlib import Path
from urllib.parse import urljoin

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
# 遠期、歷史匯率在表上是「查詢」連結，存連結的網址
LINK_COLUMNS = {
    "遠期匯率": "遠期匯率買入/賣出",
    "歷史匯率": "歷史匯率",
}
FIELDS = ["幣別", *COLUMNS, *LINK_COLUMNS, "掛牌時間"]

# 延伸：買賣價差
DETAIL_OUTPUT = Path(__file__).parent / "bank_detail.csv"
DETAIL_FIELDS = ["幣別",
                 "現金買入", "現金賣出", "現金價差", "現金價差（%）",
                 "即期買入", "即期賣出", "即期價差", "即期價差（%）"]


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
        for field, data_table in LINK_COLUMNS.items():
            link = tr.select_one(f"td[data-table='{data_table}'] a")
            row[field] = urljoin(URL, link["href"]) if link else ""  # /xrt/forward/USD → 完整網址
        row["掛牌時間"] = listed_time
        rows.append(row)
    return listed_time, rows


def spread(buy_text, sell_text):
    """延伸：回傳（價差, 價差 %）；網頁上「-」代表沒有提供，回傳兩個空字串。"""
    if "-" in (buy_text, sell_text):
        return "", ""
    buy, sell = float(buy_text), float(sell_text)
    return round(sell - buy, 5), round((sell - buy) / sell * 100, 2)


def spread_rows(rows):
    """延伸：算出每種幣別現金與即期的買賣價差。"""
    result = []
    for row in rows:
        detail = {"幣別": row["幣別"]}
        for kind in ("現金", "即期"):
            buy, sell = row[f"{kind}匯率-本行買入"], row[f"{kind}匯率-本行賣出"]
            detail[f"{kind}買入"], detail[f"{kind}賣出"] = buy, sell
            detail[f"{kind}價差"], detail[f"{kind}價差（%）"] = spread(buy, sell)
        result.append(detail)
    return result


def save_csv(rows, path, fields):
    """存成 CSV（utf-8-sig：Excel 開啟中文不會亂碼）。"""
    with open(path, "w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main():
    html = get_html_with_chrome(URL)
    listed_time, rows = parse_rates(html)

    print(f"牌價最新掛牌時間：{listed_time}\n")
    print("幣別 | 現金買入 | 現金賣出 | 即期買入 | 即期賣出")
    for row in rows:
        print(" | ".join(row[field] for field in ["幣別", *COLUMNS]))

    save_csv(rows, OUTPUT, FIELDS)
    print(f"\n共 {len(rows)} 種幣別，已存成 {OUTPUT.name}"
          f"（另含遠期、歷史匯率的查詢網址與掛牌時間）")

    # 延伸：買賣價差
    details = spread_rows(rows)
    save_csv(details, DETAIL_OUTPUT, DETAIL_FIELDS)
    cash = [d for d in details if d["現金價差（%）"] != ""]
    print("\n延伸：現金價差最大的 5 種外幣（買進再賣回會損失的比例）")
    for d in sorted(cash, key=lambda d: d["現金價差（%）"], reverse=True)[:5]:
        sight = f"，即期只有 {d['即期價差（%）']}%" if d["即期價差（%）"] != "" else "，沒有即期匯率"
        print(f"  {d['幣別']}：現金 {d['現金價差（%）']}%{sight}")
    print(f"已存成 {DETAIL_OUTPUT.name}")


if __name__ == "__main__":
    main()
