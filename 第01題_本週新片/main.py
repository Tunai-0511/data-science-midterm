"""
第 1 題（易）：抓取開眼電影網「本週新片」
================================================
題目要求
    抓 http://www.atmovies.com.tw/movie/new/ 裡本週新片的電影，
    包括「標題、內容、片長、網址」。

做法（requests + BeautifulSoup）
    1. 用 requests 下載本週新片頁面的 HTML。
    2. 用 BeautifulSoup 找出每一部電影的區塊 <article class="filmList">。
    3. 從區塊裡取出：標題（.filmTitle a）、內容簡介（p）、片長（.runtime）、
       網址（標題連結的 href，補成完整網址）。
    4. 印出結果，並存成同資料夾的 new_movies.csv（重新執行會直接覆蓋）。

執行
    python 第01題_本週新片/main.py
"""

import csv
import re
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

URL = "https://www.atmovies.com.tw/movie/new/"
OUTPUT = Path(__file__).parent / "new_movies.csv"  # 輸出檔放在本程式旁邊
FIELDS = ["標題", "內容", "片長", "網址"]


def get_html(url):
    """下載網頁，並以 UTF-8 解碼成文字。"""
    response = requests.get(url, timeout=30)
    response.raise_for_status()  # 網站回傳錯誤（例如 404）就直接停止
    response.encoding = "utf-8"
    return response.text


def parse_movies(html):
    """從本週新片頁面解析每一部電影的標題、內容、片長、網址。"""
    soup = BeautifulSoup(html, "html.parser")
    movies = []

    # 每一部電影都包在 <article class="filmList"> 裡
    for card in soup.select("article.filmList"):
        title_link = card.select_one(".filmTitle a")  # 電影名稱的超連結
        intro = card.select_one("p")  # 內容簡介
        runtime = card.select_one(".runtime")  # 「片長：117分 上映日期：...」那一行

        # .runtime 的文字像「片長：117分 上映日期：10/8/2026」，用正規表示式取出片長
        runtime_text = runtime.get_text(" ", strip=True) if runtime else ""
        match = re.search(r"片長[：:]\s*(\d+\s*分)", runtime_text)

        movies.append({
            "標題": title_link.get_text(" ", strip=True),
            "內容": intro.get_text(" ", strip=True) if intro else "",
            "片長": match.group(1) if match else "",
            "網址": urljoin(URL, title_link["href"]),  # /movie/xxx/ → 完整網址
        })
    return movies


def save_csv(rows, path):
    """存成 CSV。utf-8-sig 會加上 BOM，Excel 開啟中文才不會亂碼。"""
    with open(path, "w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def main():
    html = get_html(URL)
    movies = parse_movies(html)

    for number, movie in enumerate(movies, start=1):
        print(f"{number}. {movie['標題']}（片長 {movie['片長']}）")
        print(f"   內容：{movie['內容']}")
        print(f"   網址：{movie['網址']}")

    save_csv(movies, OUTPUT)
    print(f"\n本週新片共 {len(movies)} 部，已存成 {OUTPUT.name}")


if __name__ == "__main__":
    main()
