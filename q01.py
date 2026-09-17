"""原題 1：擷取開眼電影本週新片。"""
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from support import SourceChanged, run_cli


URL = "https://www.atmovies.com.tw/movie/new/"
FIELDS = ["標題", "內容", "片長分鐘", "網址"]


def parse_movies(html, base_url=URL):
    soup = BeautifulSoup(html, "html.parser")
    rows = []
    for card in soup.select("article.filmList"):
        link = card.select_one(".filmTitle a[href]")
        content = card.select_one("p")
        runtime = card.select_one(".runtime")
        if not link or not content or not runtime:
            raise SourceChanged("本週新片卡片缺少標題、內容或片長欄位")
        match = re.search(r"片長\s*[：:]\s*(\d+)\s*分", runtime.get_text(" ", strip=True))
        rows.append({
            "標題": link.get_text(" ", strip=True),
            "內容": content.get_text(" ", strip=True),
            "片長分鐘": match.group(1) if match else "",
            "網址": urljoin(base_url, link["href"]),
        })
    if not rows:
        raise SourceChanged("找不到本週新片卡片")
    if len({row["網址"] for row in rows}) != len(rows):
        raise SourceChanged("本週新片網址重複，來源結構可能已改變")
    return rows


def run(job, args):
    response = job.fetch(URL, name="new_movies_source.html")
    response.encoding = "utf-8"
    rows = parse_movies(response.text)
    job.save_csv("new_movies.csv", FIELDS, rows)
    missing = sum(not row["片長分鐘"] for row in rows)
    if missing:
        return {"status": "partial", "note": f"本週新片共 {len(rows)} 筆；{missing} 筆原頁片長無法解析，已保留空白。", "rows": len(rows)}
    return {"status": "passed", "note": f"本週新片共 {len(rows)} 筆；片長以分鐘保存。", "rows": len(rows)}


if __name__ == "__main__":
    run_cli(1, run)
