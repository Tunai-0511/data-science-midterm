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

延伸：點進每部電影的內頁，多抓更完整的資料
    題目只要求列表頁上的四個欄位；我們再用 requests 打開每部電影的內頁，
    多抓下列欄位，和原本四個欄位一起存成 new_movies_detail.csv：
      上映日期、上映廳數（.runtime 那一行）
      評分、評分人數（#rating-summary；沒人評分時評分留白，避免 0 分誤導）
      導演、演員、影片年份、出品國、語言、發行商（#filmCastDataBlock，每個欄位以 <b>欄位名：</b> 開頭）
    每部片之間停 1 秒，避免連續請求造成網站負擔。

    這些欄位的意義：
      上映廳數＝片商排了多少廳，代表對票房的期待（院線規模）；
      評分要搭配評分人數看，人數很少時評分參考價值低；
      出品國、語言看得出本週新片來自哪些國家；
      影片年份比上映日期早很多的，是重新上映的舊片。

輸出
    new_movies.csv（題目要求的四個欄位）
    new_movies_detail.csv（延伸：四個欄位＋內頁欄位）

執行
    python 第01題_本週新片/main.py
"""

import csv
import re
import time
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup, NavigableString

URL = "https://www.atmovies.com.tw/movie/new/"
OUTPUT = Path(__file__).parent / "new_movies.csv"  # 輸出檔放在本程式旁邊
FIELDS = ["標題", "內容", "片長", "網址"]

# 延伸：內頁多抓的欄位
DETAIL_OUTPUT = Path(__file__).parent / "new_movies_detail.csv"
CAST_FIELDS = ["導演", "演員", "影片年份", "出品國", "語言", "發行商"]  # 內頁演職員區塊裡要的欄位
DETAIL_FIELDS = FIELDS + ["上映日期", "上映廳數", "評分", "評分人數"] + CAST_FIELDS


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


def parse_cast_block(block):
    """解析內頁的演職員區塊，回傳 {欄位名: 內容}。
    區塊裡每個欄位都是「<b>欄位名：</b>」後面接內容：導演、演員是人名連結（一位一個 <a>），
    影片年份、出品國等是直接寫在 <li> 裡的文字。網頁的 <li> 沒有正確關閉，層層巢狀，
    所以依「出現順序」走過區塊裡的每個節點：遇到 <b> 就換欄位，之後的人名或文字都歸到這個欄位。"""
    info = {}
    label = None
    for node in block.descendants:
        if node.name == "ul":  # 換到下一個清單，前一個欄位結束
            label = None
        elif node.name == "b":
            label = re.sub(r"[\s　：:]", "", node.get_text())  # 「出  品  國：」→「出品國」
            info.setdefault(label, [])
        elif label and node.name == "a" and "/star/" in node.get("href", ""):
            info[label].append(node.get_text(strip=True))  # 人名連結（導演、演員…）
        elif label and isinstance(node, NavigableString) and node.parent.name == "li" and node.strip():
            info[label].append(node.strip())  # 直接寫在 <li> 裡的文字（年份、出品國…）
    return {label: "、".join(values) for label, values in info.items()}


def parse_detail(html):
    """延伸：從電影內頁取出上映日期、廳數、評分、評分人數與演職員資料。"""
    soup = BeautifulSoup(html, "html.parser")
    detail = {}

    # 「片長：119分 上映日期：2026/10/16 廳數 (90)」
    runtime = soup.select_one(".runtime")
    runtime_text = runtime.get_text(" ", strip=True) if runtime else ""
    date = re.search(r"上映日期[：:]\s*([\d/]+)", runtime_text)
    halls = re.search(r"廳數\s*\((\d+)\)", runtime_text)
    detail["上映日期"] = date.group(1) if date else ""
    detail["上映廳數"] = halls.group(1) if halls else ""

    # 評分區塊：「5.00 ★」「共 4 人評分」
    average = soup.select_one("#rating-summary #avg")
    count = soup.select_one("#rating-summary #count")
    score = re.search(r"[\d.]+", average.get_text()) if average else None
    people = re.search(r"\d+", count.get_text()) if count else None
    detail["評分人數"] = people.group() if people else ""
    # 0 人評分時網頁顯示「0 ★」，那不是真的 0 分，所以評分留白
    detail["評分"] = score.group() if score and detail["評分人數"] not in ("", "0") else ""

    block = soup.select_one("#filmCastDataBlock")
    cast = parse_cast_block(block) if block else {}
    for field in CAST_FIELDS:
        detail[field] = cast.get(field, "")
    return detail


def save_csv(rows, path, fields):
    """存成 CSV。utf-8-sig 會加上 BOM，Excel 開啟中文才不會亂碼。"""
    with open(path, "w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main():
    html = get_html(URL)
    movies = parse_movies(html)

    for number, movie in enumerate(movies, start=1):
        print(f"{number}. {movie['標題']}（片長 {movie['片長']}）")
        print(f"   內容：{movie['內容']}")
        print(f"   網址：{movie['網址']}")

    save_csv(movies, OUTPUT, FIELDS)
    print(f"\n本週新片共 {len(movies)} 部，已存成 {OUTPUT.name}")

    # 延伸：點進每部電影的內頁，多抓更完整的資料
    print("\n延伸：點進每部電影的內頁，多抓上映日期、廳數、評分、導演、演員等資料\n")
    details = []
    for number, movie in enumerate(movies, start=1):
        if number > 1:
            time.sleep(1)  # 每部片之間停 1 秒，避免連續請求造成網站負擔
        detail = {**movie, **parse_detail(get_html(movie["網址"]))}
        details.append(detail)
        score = f"{detail['評分']} 分（{detail['評分人數']} 人）" if detail["評分"] else "尚無評分"
        print(f"{number}. {movie['標題']}｜{detail['上映日期'] or '日期未定'} 上映、{detail['上映廳數']} 廳｜{score}"
              f"｜導演 {detail['導演'] or '－'}｜{detail['出品國']}")

    save_csv(details, DETAIL_OUTPUT, DETAIL_FIELDS)
    print(f"\n已存成 {DETAIL_OUTPUT.name}（{len(DETAIL_FIELDS)} 個欄位）")


if __name__ == "__main__":
    main()
