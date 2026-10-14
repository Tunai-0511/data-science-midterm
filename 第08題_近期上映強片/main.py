"""
第 8 題（難）：抓取開眼電影網「近期上映強片」
================================================
題目要求
    抓 http://www.atmovies.com.tw/movie/new/ 裡的近期上映強片電影
    1. 列出「所有」的近期上映強片電影
    2. 列出名稱、上映時間及連結網址
    3. 存入 movies.csv

做法（requests + BeautifulSoup）
    開眼網站改版後，「近期上映強片」的橫向輪播已經從本週新片頁（/movie/new/）
    移到「電影」首頁 https://www.atmovies.com.tw/movie/（題目網址上方選單的「電影」），
    標題、海報與日期的樣子和題目附圖相同，所以改抓這一頁。

    1. 用 requests 下載電影首頁。
    2. 找到標題文字是「近期上映強片」的區塊（<h2 class="title">），往上找到整個區塊。
    3. 輪播一次只「顯示」4 部，但 HTML 裡其實有全部電影的卡片（.c-item-card），
       全部讀出來才是「所有」近期上映強片。
    4. 每張卡片：名稱＝.my-filmtitle 的文字、上映時間＝.my-date、連結網址＝卡片連結。
    5. 印出並存成 movies.csv（重新執行會直接覆蓋）。

執行
    python 第08題_近期上映強片/main.py
"""

import csv
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

URL = "https://www.atmovies.com.tw/movie/"  # 「近期上映強片」所在的頁面（見上方說明）
OUTPUT = Path(__file__).parent / "movies.csv"
FIELDS = ["名稱", "上映時間", "連結網址"]


def get_html(url):
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    response.encoding = "utf-8"
    return response.text


def parse_upcoming(html):
    """找出「近期上映強片」區塊，回傳區塊裡所有電影。"""
    soup = BeautifulSoup(html, "html.parser")

    # 1. 找到標題是「近期上映強片」的 h2，再往上找整個區塊 <div class="c-section">
    heading = next(h for h in soup.select("h2.title") if h.get_text(strip=True) == "近期上映強片")
    section = heading.find_parent("div", class_="c-section")

    # 2. 讀出區塊裡的每一張電影卡片（包含輪播還沒轉到、畫面上看不到的）
    movies = []
    for card in section.select(".c-item-card"):
        link = card.select_one("a")
        title_box = card.select_one(".my-filmtitle")  # 裡面是「片名 + <p class="my-date">日期</p>」
        date = card.select_one(".my-date").get_text(strip=True)
        # 片名是 .my-filmtitle 自己的文字（不含裡面 <p> 的日期）
        title = "".join(title_box.find_all(string=True, recursive=False)).strip()
        movies.append({
            "名稱": title,
            "上映時間": date,
            "連結網址": urljoin(URL, link["href"]),
        })
    return movies


def main():
    movies = parse_upcoming(get_html(URL))

    for number, movie in enumerate(movies, start=1):
        print(f"{number}. {movie['名稱']}｜上映時間 {movie['上映時間']}｜{movie['連結網址']}")

    with open(OUTPUT, "w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(movies)
    print(f"\n近期上映強片共 {len(movies)} 部，已存成 {OUTPUT.name}")


if __name__ == "__main__":
    main()
