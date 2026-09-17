"""第 6 題：Basketball Reference 三隊 2023-24 roster。"""
import time

from bs4 import BeautifulSoup, Comment

from support import SourceChanged, run_cli

TEAMS = ("CLE", "HOU", "GSW")
FIELDS = ["球隊", "背號", "姓名", "位置", "體重", "生日", "經驗", "大學"]
STAT_FIELDS = {
    "背號": "number",
    "姓名": "player",
    "位置": "pos",
    "體重": "weight",
    "生日": "birth_date",
    "經驗": "years_experience",
    "大學": "college",
}


def _cell_text(row, stat):
    cell = row.select_one(f'[data-stat="{stat}"]')
    if cell is None:
        return ""
    return " ".join(cell.stripped_strings).replace(" ,", ",")


def parse_roster(html, team):
    """只解析 roster；保留字串型背號、R 與空白大學。"""
    soup = BeautifulSoup(html, "html.parser")
    table = soup.select_one("table#roster")
    if table is None:
        for comment in soup.find_all(string=lambda value: isinstance(value, Comment)):
            if 'id="roster"' not in comment and "id='roster'" not in comment:
                continue
            table = BeautifulSoup(comment, "html.parser").select_one("table#roster")
            if table is not None:
                break
    if table is None:
        raise SourceChanged(f"{team} 頁面找不到 roster 表格；未以其他來源代替")

    rows = []
    for tr in table.select("tbody tr"):
        player = _cell_text(tr, "player")
        if not player or player.lower() == "player":
            continue
        rows.append({"球隊": team, **{label: _cell_text(tr, stat) for label, stat in STAT_FIELDS.items()}})
    if not rows:
        raise SourceChanged(f"{team} roster 沒有可辨識球員列；未建立假資料")
    return rows


def run(job, args):
    rows = []
    for index, team in enumerate(TEAMS):
        if index:
            # Basketball Reference 要求控制請求頻率；三隊之間保留間隔。
            time.sleep(3.2)
        url = f"https://www.basketball-reference.com/teams/{team}/2024.html"
        response = job.fetch(url, f"source_{team}.html")
        rows.extend(parse_roster(response.text, team))
    job.save_csv("players.csv", FIELDS, rows)
    return {
        "status": "passed",
        "note": f"固定 2024 頁面；CLE、HOU、GSW roster 合計 {len(rows)} 筆，體重保留來源磅值",
        "rows": len(rows),
    }


if __name__ == "__main__":
    run_cli(6, run)
