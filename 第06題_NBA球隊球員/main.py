"""
第 6 題（難）：抓取 Basketball Reference 的 NBA 球隊球員名單
================================================
題目要求
    抓 https://www.basketball-reference.com/teams/{0}/2024.html 裡的運動員
    1. 抓取 ["CLE", "HOU", "GSW"] 三隊
    2. 內容包括 ["球隊","背號","姓名","位置","體重","生日","經驗","大學"]
    3. 存入 players.csv
    （課堂補充：要找到指定隊伍 Roster & Stats 頁面裡的 Roster 球員資料）

做法（requests + BeautifulSoup）
    1. 把三個球隊代碼依序放進網址的 {0}，用 requests 下載各隊 2024（2023-24 球季）頁面。
    2. 用 BeautifulSoup 找到 id="roster" 的表格（Roster 名單）。
    3. 表格每個儲存格都有 data-stat 屬性（例如 data-stat="weight"），依屬性取值，
       不必擔心欄位順序。網站多出來的身高、出生國旗欄位不需要，就不取。
    4. 三隊合併後存成 players.csv（重新執行會直接覆蓋）。

    資料說明：體重單位是磅（lb）；經驗是進入該球季前的 NBA 年資，R 代表新秀；
    沒讀大學的球員「大學」欄是空白。網站要求不要連續快速請求，所以每隊之間停 3 秒。

執行
    python 第06題_NBA球隊球員/main.py
"""

import csv
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

TEAMS = ["CLE", "HOU", "GSW"]
URL_TEMPLATE = "https://www.basketball-reference.com/teams/{0}/2024.html"
OUTPUT = Path(__file__).parent / "players.csv"

# CSV 欄位 → 網頁表格儲存格的 data-stat 屬性
COLUMNS = {
    "背號": "number",
    "姓名": "player",
    "位置": "pos",
    "體重": "weight",
    "生日": "birth_date",
    "經驗": "years_experience",
    "大學": "college",
}
FIELDS = ["球隊", *COLUMNS]


def get_roster(team):
    """下載一支球隊的頁面，回傳該隊的球員名單（每位球員一個 dict）。"""
    url = URL_TEMPLATE.format(team)
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    players = []
    roster_table = soup.select_one("table#roster")  # Roster（球員名單）表格
    for tr in roster_table.select("tbody tr"):
        player = {"球隊": team}
        for field, data_stat in COLUMNS.items():
            cell = tr.select_one(f"[data-stat='{data_stat}']")
            # 把多餘的空白、換行整理成一個空白，例如 "Memphis, Eastern Michigan"
            player[field] = " ".join(cell.get_text().split())
        players.append(player)
    return players


def main():
    all_players = []
    for index, team in enumerate(TEAMS):
        if index > 0:
            time.sleep(3)  # 禮貌性間隔，避免請求太快被網站封鎖
        players = get_roster(team)
        all_players.extend(players)
        print(f"{team}：{len(players)} 位球員")

    with open(OUTPUT, "w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(all_players)

    print()
    for player in all_players[:5]:
        print(player)
    print(f"...\n三隊共 {len(all_players)} 位球員，已存成 {OUTPUT.name}")


if __name__ == "__main__":
    main()
