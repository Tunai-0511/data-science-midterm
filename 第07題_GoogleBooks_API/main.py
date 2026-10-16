"""
第 7 題（難）：使用 Google Books API 抓取「Python」書籍資料
================================================
題目要求
    1. 使用 Google API，給予下列參數 url_params：
           url = "https://www.googleapis.com/books/v1/volumes"
           url_params = {'q': 'Python', 'maxResults': 10, 'projection': 'lite'}
           r = requests.get(url, params=url_params)
    2. 將本頁資料存入 pythonbook.csv
    3. 進入下一頁，再將那一頁存入 pythonbook.csv（共兩頁資料）

做法（requests 呼叫 API，回傳 JSON）
    1. 照題目的參數呼叫 API，取得第 1 頁（10 本書），寫入 pythonbook.csv（含標題列）。
    2. 「下一頁」= 加上參數 startIndex=10（從第 11 本開始），取得第 2 頁，
       以「附加（append）」模式接著寫進同一個 pythonbook.csv。
    3. 從 JSON 的 items[].volumeInfo 取出書名、作者、出版社、出版日期、網址。

    關於 API 金鑰：Google 目前常常拒絕「不帶金鑰」的呼叫（回傳 429 配額用完），
    所以程式一開始會請你在終端機輸入自己的 Google Books API 金鑰（輸入時看得到，方便核對；不會存檔），
    再把金鑰加進參數 key；直接按 Enter 則照題目原本的寫法、不帶金鑰呼叫。
    也可以事先設定環境變數 GOOGLE_BOOKS_API_KEY，就不會再詢問。
    金鑰的申請方式：Google Cloud Console 啟用「Books API」→「憑證」→「建立憑證」→「API 金鑰」。
    （金鑰不要寫進程式或上傳到 GitHub。）

輸出
    pythonbook.csv（20 筆＝2 頁；與本程式同一個資料夾，重新執行會直接覆蓋）

執行
    python 第07題_GoogleBooks_API/main.py
"""

import csv
import os
from pathlib import Path

import requests

url = "https://www.googleapis.com/books/v1/volumes"
url_params = {"q": "Python", "maxResults": 10, "projection": "lite"}  # 題目指定的參數

OUTPUT = Path(__file__).parent / "pythonbook.csv"
FIELDS = ["頁數", "書名", "作者", "出版社", "出版日期", "網址"]


def ask_api_key():
    """取得 API 金鑰：先看環境變數 GOOGLE_BOOKS_API_KEY，沒有的話請使用者在終端機輸入。"""
    api_key = os.environ.get("GOOGLE_BOOKS_API_KEY")
    if api_key:
        return api_key
    print("Google 目前常拒絕不帶金鑰的呼叫，請輸入你的 Google Books API 金鑰。")
    return input("API 金鑰（直接按 Enter 則不帶金鑰）：").strip()


def get_page(page, api_key):
    """呼叫 Google Books API 取得第 page 頁（每頁 10 本），回傳 JSON（dict）。"""
    params = dict(url_params)
    params["startIndex"] = (page - 1) * url_params["maxResults"]  # 第 1 頁從 0、第 2 頁從 10 開始
    if api_key:
        params["key"] = api_key

    r = requests.get(url, params=params, timeout=30)
    if r.status_code == 429:
        raise SystemExit("Google 回傳 429（配額用完）：不帶金鑰的呼叫被拒絕了，請重新執行並輸入 API 金鑰。")
    if r.status_code in (400, 403):
        raise SystemExit(f"Google 回傳 {r.status_code}：API 金鑰無效，或這把金鑰的專案還沒有啟用 Books API。")
    r.raise_for_status()
    return r.json()


def to_rows(data, page):
    """把 API 回傳的 JSON 整理成 CSV 的每一列。"""
    rows = []
    for item in data.get("items", []):
        info = item["volumeInfo"]  # 書籍資訊都在 volumeInfo 裡
        rows.append({
            "頁數": page,
            "書名": info.get("title", ""),
            "作者": "、".join(info.get("authors", [])),  # 作者可能有好幾位
            "出版社": info.get("publisher", ""),
            "出版日期": info.get("publishedDate", ""),
            "網址": info.get("infoLink", ""),
        })
    return rows


def save_page(rows, mode):
    """mode="w"：新建（覆蓋）檔案並寫標題列；mode="a"：附加在檔案後面。"""
    with open(OUTPUT, mode, newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDS)
        if mode == "w":
            writer.writeheader()
        writer.writerows(rows)


def main():
    api_key = ask_api_key()

    # 要求 2：本頁（第 1 頁）存入 pythonbook.csv
    first = to_rows(get_page(1, api_key), page=1)
    save_page(first, mode="w")
    print(f"第 1 頁：{len(first)} 本，已存入 {OUTPUT.name}")

    # 要求 3：進入下一頁（第 2 頁），再存入同一個 pythonbook.csv
    second = to_rows(get_page(2, api_key), page=2)
    save_page(second, mode="a")
    print(f"第 2 頁：{len(second)} 本，已附加到 {OUTPUT.name}\n")

    for row in first + second:
        print(f"[第 {row['頁數']} 頁] {row['書名']}｜{row['作者']}｜{row['出版日期']}")
    print(f"\n共兩頁 {len(first) + len(second)} 本書，已存成 {OUTPUT.name}")


if __name__ == "__main__":
    main()
