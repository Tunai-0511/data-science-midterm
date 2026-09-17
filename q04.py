"""原題 4：擷取博客來「演算法」第一頁搜尋結果。"""
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from support import SourceChanged, run_cli


URL = "https://search.books.com.tw/search/query/key/%E6%BC%94%E7%AE%97%E6%B3%95/cat/all"
FIELDS = ["書名", "網址", "作者", "書價"]


def parse_books(html, base_url=URL):
    soup = BeautifulSoup(html, "html.parser")
    rows, seen = [], set()
    for title_link in soup.select("div.table-td h4 a[href]"):
        card = title_link.find_parent("div", class_="table-td")
        author_item = next(
            (item for item in card.select("li") if item.get_text(" ", strip=True).startswith("作者")),
            None,
        )
        price_box = card.select_one(".price")
        if not author_item or not price_box:
            raise SourceChanged("博客來搜尋卡片缺少作者或書價")
        authors = [a.get_text(" ", strip=True) for a in author_item.select("a")]
        if not authors:
            author_text = re.sub(r"^作者\s*[：:]\s*", "", author_item.get_text(" ", strip=True))
            authors = [author_text] if author_text else []
        prices = re.findall(r"([0-9][0-9,]*)\s*元", price_box.get_text(" ", strip=True))
        if not authors or not prices:
            raise SourceChanged("博客來作者或新臺幣書價格式已改變")
        url = urljoin(base_url, title_link["href"])
        if url in seen:
            continue
        seen.add(url)
        rows.append({
            "書名": title_link.get_text(" ", strip=True),
            "網址": url,
            "作者": "、".join(authors),
            "書價": prices[-1].replace(",", "") + "元",
        })
    if not rows:
        raise SourceChanged("找不到博客來搜尋結果；可能是驗證頁或網站改版")
    return rows


def run(job, args):
    response = job.fetch(URL, name="books_search_source.html")
    response.encoding = "utf-8"
    rows = parse_books(response.text)
    job.save_csv("booklist.csv", FIELDS, rows)
    return {"status": "passed", "note": f"僅擷取題目指定搜尋頁的第一頁，共 {len(rows)} 筆；未改用其他書店。", "rows": len(rows)}


if __name__ == "__main__":
    run_cli(4, run)
