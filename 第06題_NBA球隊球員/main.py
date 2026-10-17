"""
第 6 題（難）：抓取 Basketball Reference 的 NBA 球隊球員名單
================================================
題目要求
    抓 https://www.basketball-reference.com/teams/{0}/2024.html 裡的運動員
    1. 抓取 ["CLE", "HOU", "GSW"] 三隊
    2. 內容包括 ["球隊","背號","姓名","位置","體重","生日","經驗","大學"]
    3. 存入 players.csv

做法（requests + BeautifulSoup）
    1. 把三個球隊代碼依序放進網址的 {0}，用 requests 下載各隊 2024（2023-24 球季）頁面。
    2. 用 BeautifulSoup 找到 id="roster" 的表格（Roster 名單）。
    3. 表格每個儲存格都有 data-stat 屬性（例如 data-stat="weight"），依屬性取值，
       不必擔心欄位順序。網站多出來的身高、出生國旗欄位不需要，就不取。
    4. 三隊合併後存成 players.csv（重新執行會直接覆蓋）。

    資料說明：體重單位是磅（lb）；經驗是進入該球季前的 NBA 年資，R 代表新秀；
    沒讀大學的球員「大學」欄是空白。網站要求不要連續快速請求，所以每隊之間停 3 秒。

延伸：多抓身高、算出年齡，換成公制單位，並畫成圖表
    1. 同一個 Roster 表格裡還有身高（data-stat="height"，例如 6-9 代表 6 呎 9 吋），
       它的 csk 屬性是換算好的英寸數（81.0），乘上 2.54 就是公分；體重的磅乘上 0.4536 換成公斤。
    2. 生日的 csk 屬性是 YYYYMMDD（19980421），用來算年齡。年齡以 2024 年 2 月 1 日計算，
       這是 Basketball Reference 的「球季年齡」算法（2023-24 球季），所以每次重跑結果都一樣。
    3. 加上這些欄位存成 players_detail.csv，印出各隊平均年齡、身高、體重，
       並用 matplotlib 畫兩張圖存成 players_charts.png：
         左：身高與體重的散布圖（依球隊上色）——看得出長得越高通常越重，中鋒集中在右上角；
         右：各隊年齡的盒狀圖——比較三隊陣容的年齡結構（老將多還是年輕球員多）。

輸出
    players.csv（題目要求的欄位）
    players_detail.csv（延伸：加上身高、身高（公分）、體重（公斤）、年齡）
    players_charts.png（延伸：圖表）

執行
    python 第06題_NBA球隊球員/main.py
"""

import csv
import time
from datetime import date, datetime
from pathlib import Path

import matplotlib
import requests
from bs4 import BeautifulSoup

matplotlib.use("Agg")  # 只存圖檔、不開視窗
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402

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

# 延伸
DETAIL_OUTPUT = Path(__file__).parent / "players_detail.csv"
CHART_OUTPUT = Path(__file__).parent / "players_charts.png"
DETAIL_FIELDS = FIELDS + ["身高", "身高（公分）", "體重（公斤）", "年齡"]
SEASON_DATE = date(2024, 2, 1)  # 2023-24 球季的「球季年齡」以這天計算
TEAM_COLORS = {"CLE": "#860038", "HOU": "#CE1141", "GSW": "#1D428A"}  # 各隊代表色


def get_roster(team):
    """下載一支球隊的頁面，回傳該隊的球員名單（每位球員一個 dict）。"""
    url = URL_TEMPLATE.format(team)
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    # 網站回應沒寫編碼，requests 會當成 ISO-8859-1，Šarić 這類名字會變亂碼；網頁實際是 UTF-8
    response.encoding = "utf-8"
    soup = BeautifulSoup(response.text, "html.parser")

    players = []
    roster_table = soup.select_one("table#roster")  # Roster（球員名單）表格
    for tr in roster_table.select("tbody tr"):
        player = {"球隊": team}
        for field, data_stat in COLUMNS.items():
            cell = tr.select_one(f"[data-stat='{data_stat}']")
            # 把多餘的空白、換行整理成一個空白，例如 "Memphis, Eastern Michigan"
            player[field] = " ".join(cell.get_text().split())

        # 延伸：身高、身高（公分）、體重（公斤）、年齡
        height = tr.select_one("[data-stat='height']")
        birth = tr.select_one("[data-stat='birth_date']")
        player["身高"] = height.get_text(strip=True)  # 例如 6-9（6 呎 9 吋）
        player["身高（公分）"] = round(float(height["csk"]) * 2.54)  # csk＝英寸數
        player["體重（公斤）"] = round(int(player["體重"]) * 0.4536)
        player["年齡"] = age_on(datetime.strptime(birth["csk"], "%Y%m%d").date(), SEASON_DATE)
        players.append(player)
    return players


def age_on(birthday, day):
    """算出 birthday 出生的人在 day 這天幾歲（還沒過生日就少 1 歲）。"""
    before_birthday = (day.month, day.day) < (birthday.month, birthday.day)
    return day.year - birthday.year - before_birthday


def save_csv(rows, path, fields):
    """存成 CSV（utf-8-sig：Excel 開啟中文不會亂碼）；fields 以外的欄位不寫入。"""
    with open(path, "w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def print_team_summary(players):
    """延伸：印出各隊人數、平均年齡、平均身高、平均體重。"""
    print("\n延伸：各隊平均")
    for team in TEAMS:
        members = [p for p in players if p["球隊"] == team]
        average = lambda field: sum(p[field] for p in members) / len(members)  # noqa: E731
        print(f"  {team}：{len(members)} 人，平均 {average('年齡'):.1f} 歲、"
              f"{average('身高（公分）'):.1f} 公分、{average('體重（公斤）'):.1f} 公斤")


def use_chinese_font():
    """matplotlib 預設字型沒有中文，從電腦上已有的中文字型挑一個（Windows／macOS 都適用）。"""
    candidates = ["Microsoft JhengHei", "PingFang TC", "Heiti TC", "Noto Sans CJK TC", "Arial Unicode MS"]
    installed = {font.name for font in font_manager.fontManager.ttflist}
    plt.rcParams["font.sans-serif"] = [name for name in candidates if name in installed] + ["DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False  # 中文字型下負號才不會變方框


def draw_charts(players):
    """延伸：左邊畫身高與體重的散布圖，右邊畫各隊年齡的盒狀圖，存成 PNG。"""
    use_chinese_font()
    fig, (left, right) = plt.subplots(1, 2, figsize=(12, 5))

    for team in TEAMS:
        members = [p for p in players if p["球隊"] == team]
        left.scatter([p["身高（公分）"] for p in members], [p["體重（公斤）"] for p in members],
                     label=team, color=TEAM_COLORS[team], alpha=0.75)
    left.set_title("身高與體重（每個點是一位球員）")
    left.set_xlabel("身高（公分）")
    left.set_ylabel("體重（公斤）")
    left.legend()

    ages = [[p["年齡"] for p in players if p["球隊"] == team] for team in TEAMS]
    box = right.boxplot(ages, patch_artist=True)
    right.set_xticks(range(1, len(TEAMS) + 1), TEAMS)
    for patch, team in zip(box["boxes"], TEAMS):
        patch.set_facecolor(TEAM_COLORS[team])
        patch.set_alpha(0.6)
    right.set_title("各隊年齡分布（2023-24 球季）")
    right.set_ylabel("年齡（歲）")

    fig.tight_layout()
    fig.savefig(CHART_OUTPUT, dpi=150)
    plt.close(fig)


def main():
    all_players = []
    for index, team in enumerate(TEAMS):
        if index > 0:
            time.sleep(3)  # 禮貌性間隔，避免請求太快被網站封鎖
        players = get_roster(team)
        all_players.extend(players)
        print(f"{team}：{len(players)} 位球員")

    save_csv(all_players, OUTPUT, FIELDS)  # 題目要求的欄位

    print()
    for player in all_players[:5]:
        print({field: player[field] for field in FIELDS})
    print(f"...\n三隊共 {len(all_players)} 位球員，已存成 {OUTPUT.name}")

    # 延伸：加上身高、年齡等欄位另存一份，印出各隊平均並畫圖
    save_csv(all_players, DETAIL_OUTPUT, DETAIL_FIELDS)
    print_team_summary(all_players)
    draw_charts(all_players)
    print(f"\n延伸：已存成 {DETAIL_OUTPUT.name}、{CHART_OUTPUT.name}")


if __name__ == "__main__":
    main()
