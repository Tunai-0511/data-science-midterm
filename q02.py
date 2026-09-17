"""原題 2：擷取臺灣銀行最新牌告匯率。"""
import re

from bs4 import BeautifulSoup

from support import SourceBlocked, SourceChanged, run_cli


URL = "https://rate.bot.com.tw/xrt?Lang=zh-TW"
FIELDS = ["幣別", "現金買入", "現金賣出", "即期買入", "即期賣出", "牌價時間"]


def parse_rates(html):
    soup = BeautifulSoup(html, "html.parser")
    timestamp_match = re.search(
        r"牌價最新掛牌時間\s*[：:]?\s*([0-9]{4}/[0-9]{1,2}/[0-9]{1,2}\s+[0-9]{1,2}:[0-9]{2})",
        soup.get_text(" ", strip=True),
    )
    if not timestamp_match:
        raise SourceChanged("找不到牌價最新掛牌時間")
    timestamp = timestamp_match.group(1)
    rows = []
    for source_row in soup.select("table.table tbody tr"):
        currency = source_row.select_one("td.currency .visible-phone")
        cash = source_row.select("td.rate-content-cash.print_hide")
        spot = source_row.select("td.rate-content-sight.print_hide")
        if not currency:
            continue
        if len(cash) != 2 or len(spot) != 2:
            raise SourceChanged("匯率欄位數量與預期不符")
        rows.append({
            "幣別": currency.get_text(" ", strip=True),
            "現金買入": cash[0].get_text(" ", strip=True),
            "現金賣出": cash[1].get_text(" ", strip=True),
            "即期買入": spot[0].get_text(" ", strip=True),
            "即期賣出": spot[1].get_text(" ", strip=True),
            "牌價時間": timestamp,
        })
    if not rows:
        raise SourceChanged("找不到臺灣銀行匯率表")
    return rows


def run(job, args):
    response = job.fetch(URL, name="bank_source.html")
    response.encoding = "utf-8"
    if "Challenge Validation" in response.text or "驗證成功" in response.text:
        raise SourceBlocked("臺灣銀行回傳網站驗證頁；未把驗證內容當成匯率")
    rows = parse_rates(response.text)
    job.save_csv("bank.csv", FIELDS, rows)
    return {"status": "passed", "note": f"最新牌告匯率共 {len(rows)} 種幣別；已排除響應式重複欄位。", "rows": len(rows)}


if __name__ == "__main__":
    run_cli(2, run)
