"""原題 8：擷取「近期上映強片」橫向輪播的全部電影。"""
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from support import SourceChanged, run_cli


URL = "https://www.atmovies.com.tw/movie/new/"
CURRENT_MOVIE_HOME = "https://www.atmovies.com.tw/movie/"
FIELDS = ["標題", "上映日期", "網址"]


def parse_featured(html, base_url=URL):
    soup = BeautifulSoup(html, "html.parser")
    heading = next(
        (node for node in soup.select("h2.title") if node.get_text(" ", strip=True) == "近期上映強片"),
        None,
    )
    section = heading.find_parent("div", class_="c-section") if heading else None
    if not section:
        raise SourceChanged("找不到題目指定的「近期上映強片」橫向輪播")
    rows, seen = [], set()
    for card in section.select(".c-flickityList .c-item.c-item-card"):
        link = card.select_one("a[href]")
        title_box = card.select_one(".my-filmtitle")
        date = card.select_one(".my-date")
        if not link or not title_box or not date:
            raise SourceChanged("「近期上映強片」輪播卡片缺少名稱、日期或網址")
        url = urljoin(base_url, link["href"])
        if url in seen:
            continue
        seen.add(url)
        date_text = date.get_text(" ", strip=True)
        title = " ".join(text.strip() for text in title_box.find_all(string=True, recursive=False) if text.strip())
        if not title or not date_text:
            raise SourceChanged("「近期上映強片」輪播卡片內容為空")
        rows.append({"標題": title, "上映日期": date_text, "網址": url})
    if not rows:
        raise SourceChanged("「近期上映強片」輪播沒有電影卡片")
    return rows


def run(job, args):
    original = job.fetch(URL, name="original_new_page.html")
    original.encoding = "utf-8"
    moved = False
    try:
        rows = parse_featured(original.text, URL)
    except SourceChanged:
        current = job.fetch(CURRENT_MOVIE_HOME, name="current_movie_home.html")
        current.encoding = "utf-8"
        rows = parse_featured(current.text, CURRENT_MOVIE_HOME)
        moved = True
    job.save_csv("movies.csv", FIELDS, rows)
    if moved:
        return {
            "status": "partial",
            "note": f"原題 URL 現已移除該輪播；同站電影首頁仍有同名「近期上映強片」輪播，共 {len(rows)} 部。已保存並明確標記來源位置改變，未改抓側欄或 More 清單。",
            "rows": len(rows),
        }
    return {"status": "passed", "note": f"題目 URL 的「近期上映強片」輪播共 {len(rows)} 部，含所有離屏項目。", "rows": len(rows)}


if __name__ == "__main__":
    run_cli(8, run)
