"""原題 7：透過 Google Books API 取得 Python 搜尋結果兩頁。"""
import os

from support import SourceChanged, run_cli


URL = "https://www.googleapis.com/books/v1/volumes"
FIELDS = ["頁碼", "ID", "書名", "作者", "出版日期", "網址"]


def parse_page(payload, page):
    if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
        raise SourceChanged(f"Google Books 第 {page} 頁不是預期的書籍回應")
    if not payload["items"]:
        raise SourceChanged(f"Google Books 第 {page} 頁沒有書籍")
    rows = []
    for item in payload["items"]:
        info = item.get("volumeInfo") or {}
        if not item.get("id") or not info.get("title"):
            raise SourceChanged(f"Google Books 第 {page} 頁有書籍缺少 ID 或書名")
        rows.append({
            "頁碼": page,
            "ID": item["id"],
            "書名": info["title"],
            "作者": "；".join(info.get("authors") or []),
            "出版日期": info.get("publishedDate", ""),
            "網址": info.get("infoLink", ""),
        })
    return rows


def run(job, args):
    key = os.environ.get("GOOGLE_BOOKS_API_KEY")
    rows, seen = [], set()
    for page, start_index in enumerate((0, 10), start=1):
        params = {"q": "Python", "maxResults": 10, "projection": "lite", "startIndex": start_index}
        if key:
            params["key"] = key
        response = job.fetch(URL, name=f"google_books_page{page}.json", params=params)
        try:
            page_rows = parse_page(response.json(), page)
        except ValueError:
            raise SourceChanged(f"Google Books 第 {page} 頁不是 JSON") from None
        for row in page_rows:
            if row["ID"] not in seen:
                seen.add(row["ID"])
                rows.append(row)
    if {row["頁碼"] for row in rows} != {1, 2}:
        raise SourceChanged("去重後的資料沒有同時涵蓋兩個成功頁面")
    job.save_csv("pythonbook.csv", FIELDS, rows)
    return {"status": "passed", "note": f"startIndex=0、10 兩頁均成功，共保存 {len(rows)} 本唯一書籍；API key 未寫入紀錄。", "rows": len(rows)}


if __name__ == "__main__":
    run_cli(7, run)
