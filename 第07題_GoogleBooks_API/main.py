"""
第 7 題（難）：使用 Google Books API 抓取「Python」書籍資料
================================================
題目要求
    1. 使用 Google API，給予下列參數 url_params：
           url = "https://www.googleapis.com/books/v1/volumes"
           url_params = {'q': 'Python', 'maxResults': 10, 'projection': 'lite'}
           r = requests.get(url, params=url_params)
    2. 將本頁資料存入 pythonbook.csv
    3. 進入下一頁，再將那一頁存入 pythonbook.csv（共兩頁資料）

做法（requests 呼叫 API，回傳 JSON）
    1. 照題目的參數呼叫 API，取得第 1 頁（10 本書），寫入 pythonbook.csv（含標題列）。
    2. 「下一頁」= 加上參數 startIndex=10（從第 11 本開始），取得第 2 頁，
       以「附加（append）」模式接著寫進同一個 pythonbook.csv。
    3. 從 JSON 的 items[].volumeInfo 取出書名、作者、出版社、出版日期、網址。

    關於 API 金鑰：Google 目前常常拒絕「不帶金鑰」的呼叫（回傳 429 配額用完），
    所以程式一開始會請你在終端機輸入自己的 Google Books API 金鑰（輸入時每個字顯示成「•」，不會存檔），
    再把金鑰加進參數 key；直接按 Enter 則照題目原本的寫法、不帶金鑰呼叫。
    也可以事先設定環境變數 GOOGLE_BOOKS_API_KEY，就不會再詢問。
    金鑰的申請方式：Google Cloud Console 啟用「Books API」→「憑證」→「建立憑證」→「API 金鑰」。
    （金鑰不要寫進程式或上傳到 GitHub。）

輸出
    pythonbook.csv        題目要求：兩頁搜尋結果
    pythonbook_detail.csv 延伸：書籍 ID、出版年份、整理後出版社
    books_api_charts.png  延伸：年代分布、出版社筆數

延伸：出版年代與出版社分布
    擷取出版年份、整理出版社、檢查可辨識書籍 ID 的重複與缺漏。
    年份統計以有效年份為分母，出版社統計包含未知並以全部記錄為範圍。
    以十年為單位繪製年代分布；不依年代臆測主題或搜尋命中原因。
    重複資料保留並揭露；分析僅限本次兩頁搜尋結果。

執行
    python 第07題_GoogleBooks_API/main.py
    python 第07題_GoogleBooks_API/main.py --analyze-only  # 直接以既有 CSV 產生圖表與分析討論
"""

import csv
import getpass
import os
import re
import sys
from pathlib import Path

import matplotlib
import pandas as pd
import requests

matplotlib.use("Agg")  # 只存圖檔、不開視窗
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402

url = "https://www.googleapis.com/books/v1/volumes"
url_params = {"q": "Python", "maxResults": 10, "projection": "lite"}  # 題目指定的參數

OUTPUT = Path(__file__).parent / "pythonbook.csv"
DETAIL_OUTPUT = Path(__file__).parent / "pythonbook_detail.csv"
CHART_OUTPUT = Path(__file__).parent / "books_api_charts.png"
FIELDS = ["頁數", "書名", "作者", "出版社", "出版日期", "網址"]


def ask_api_key():
    """取得 API 金鑰：先看環境變數 GOOGLE_BOOKS_API_KEY，沒有的話請使用者在終端機輸入。"""
    api_key = os.environ.get("GOOGLE_BOOKS_API_KEY")
    if api_key:
        return api_key
    print("Google 目前常拒絕不帶金鑰的呼叫，請輸入你的 Google Books API 金鑰。")
    return ask_secret("API 金鑰（直接按 Enter 則不帶金鑰）：").strip()


def ask_secret(prompt):
    """輸入密碼或金鑰：每打一個字顯示一個「•」，不顯示實際內容（可以用退格鍵修改）。
    如果不是在一般終端機執行（無法逐字讀鍵盤），改用 getpass，輸入時什麼都不顯示。"""
    if not sys.stdin.isatty():
        return getpass.getpass(prompt)
    print(prompt, end="", flush=True)
    dot = "•" if "•".encode(sys.stdout.encoding or "utf-8", "ignore") else "*"
    chars = []

    def show(text):
        sys.stdout.write(text)
        sys.stdout.flush()

    def handle(ch):
        """處理一個按鍵；回傳 True 代表輸入結束。"""
        if ch in ("\r", "\n"):
            return True
        if ch == "\x03":  # Ctrl+C
            raise KeyboardInterrupt
        if ch in ("\x08", "\x7f"):  # 退格鍵：刪掉最後一個字和一個點
            if chars:
                chars.pop()
                show("\b \b")
        elif ch.isprintable():
            chars.append(ch)
            show(dot)
        return False

    try:
        if os.name == "nt":  # Windows：用 msvcrt 一次讀一個按鍵
            import msvcrt
            while True:
                ch = msvcrt.getwch()
                if ch in ("\x00", "\xe0"):  # 方向鍵等特殊鍵會送兩個字元，略過
                    msvcrt.getwch()
                    continue
                if handle(ch):
                    break
        else:  # macOS／Linux：暫時把終端機切成逐字模式，結束後一定要還原
            import termios
            import tty
            fd = sys.stdin.fileno()
            old_settings = termios.tcgetattr(fd)
            try:
                tty.setraw(fd, termios.TCSANOW)  # TCSANOW：保留已經先打進去的字
                while not handle(sys.stdin.read(1)):
                    pass
            finally:
                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    except KeyboardInterrupt:
        print()
        raise SystemExit("已取消輸入。")
    print()
    return "".join(chars)


def get_page(page, api_key):
    """呼叫 Google Books API 取得第 page 頁（每頁 10 本），回傳 JSON（dict）。"""
    params = dict(url_params)
    params["startIndex"] = (page - 1) * url_params["maxResults"]  # 第 1 頁從 0、第 2 頁從 10 開始
    if api_key:
        params["key"] = api_key

    r = requests.get(url, params=params, timeout=30)
    if r.status_code == 429:
        raise SystemExit("Google 回傳 429（配額用完）：不帶金鑰的呼叫被拒絕了，請重新執行並輸入 API 金鑰。")
    if r.status_code in (400, 403):
        raise SystemExit(f"Google 回傳 {r.status_code}：API 金鑰無效，或這把金鑰的專案還沒有啟用 Books API。")
    r.raise_for_status()
    return r.json()


def to_rows(data, page):
    """把 API 回傳的 JSON 整理成 CSV 的每一列。"""
    rows = []
    for item in data.get("items", []):
        info = item["volumeInfo"]  # 書籍資訊都在 volumeInfo 裡
        rows.append({
            "頁數": page,
            "書名": info.get("title", ""),
            "作者": "、".join(info.get("authors", [])),  # 作者可能有好幾位
            "出版社": info.get("publisher", ""),
            "出版日期": info.get("publishedDate", ""),
            "網址": info.get("infoLink", ""),
        })
    return rows


def save_page(rows, mode):
    """mode="w"：新建（覆蓋）檔案並寫標題列；mode="a"：附加在檔案後面。"""
    with open(OUTPUT, mode, newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDS)
        if mode == "w":
            writer.writeheader()
        writer.writerows(rows)


def use_chinese_font():
    """matplotlib 預設字型沒有中文，挑選系統已安裝的中文字型。"""
    candidates = ["Microsoft JhengHei", "PingFang TC", "Heiti TC", "Noto Sans CJK TC", "Arial Unicode MS"]
    installed = {font.name for font in font_manager.fontManager.ttflist}
    plt.rcParams["font.sans-serif"] = [name for name in candidates if name in installed] + ["DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False


def extract_book_id(url):
    """從 Google Books 網址中擷取唯一的書籍 ID。"""
    match = re.search(r"[?&]id=([a-zA-Z0-9_-]+)", str(url))
    return match.group(1) if match else ""


def extract_year(date_str):
    """統一出版日期格式，擷取 4 位數西元年份。"""
    if pd.isna(date_str):
        return None
    match = re.search(r"(\d{4})", str(date_str))
    return int(match.group(1)) if match else None


def clean_publisher(pub):
    """整理出版社名稱（去引號、標準化名稱、缺失值補齊）。"""
    if pd.isna(pub) or not str(pub).strip():
        return "未提供/未知"
    p = str(pub).strip().strip('"').strip("'")
    if "o'reilly" in p.lower():
        return "O'Reilly Media"
    if "prentice hall" in p.lower():
        return "Prentice Hall"
    if "wiley" in p.lower():
        return "John Wiley & Sons"
    if "mcgraw" in p.lower():
        return "McGraw Hill"
    return p


def analyze_and_draw(df=None):
    """擷取年份、整理出版社；明列缺漏與各統計的分母。"""
    if df is None:
        if not OUTPUT.exists():
            print(f"找不到 {OUTPUT.name}，無法進行分析。")
            return
        df = pd.read_csv(OUTPUT)
    clean = df.copy()
    clean["書籍ID"] = clean["網址"].apply(extract_book_id)
    clean["出版年份"] = clean["出版日期"].apply(extract_year).astype("Int64")
    clean["出版社整理"] = clean["出版社"].apply(clean_publisher)
    clean.to_csv(DETAIL_OUTPUT, index=False, encoding="utf-8-sig")
    ids = clean.loc[clean["書籍ID"].ne(""), "書籍ID"]
    years = clean["出版年份"].dropna().astype(int)
    pubs = clean["出版社整理"].value_counts()
    print(f"\n搜尋樣本 {len(clean)} 本；有效年份 {len(years)} 本；年份缺漏 {len(clean)-len(years)} 本。")
    print(f"可辨識書籍 ID {len(ids)} 筆；缺漏 {len(clean)-len(ids)} 筆；重複 ID 列數（含同組全部列）{ids.duplicated(keep=False).sum()}。")
    if not years.empty:
        print(f"出版年份範圍：{years.min()}～{years.max()}；以下年份比例以 {len(years)} 本有效年份為分母。")
        for label, mask in [("2000 年起", years.ge(2000)), ("1900～1919 年", years.between(1900, 1919))]:
            print(f"  {label}：{mask.sum()} 本（{mask.mean()*100:.1f}%）。")
    print("出版社出現筆數（含未知，分母為全部搜尋樣本）：")
    print(pubs.to_string())
    print("搜尋結果含不同年代與主題；可能與 Python 的多重詞義有關，但現有欄位無法確認每本書的搜尋命中原因。")
    print("僅分析本次兩頁結果，不代表整體 Python 出版市場；重複記錄保留並揭露，年份與出版社圖均以記錄筆數計算。")
    if clean.empty:
        print("沒有搜尋結果，略過繪圖。")
        return
    use_chinese_font()
    fig, (ax_year, ax_pub) = plt.subplots(1, 2, figsize=(15, 6), layout="constrained")
    if not years.empty:
        decades = (years // 10 * 10).value_counts().sort_index()
        bars = ax_year.bar([f"{y}年代" for y in decades.index], decades.values, color="#1D428A")
        ax_year.bar_label(bars, padding=3)
        ax_year.tick_params(axis="x", rotation=45)
        ax_year.set_ylim(0, decades.max()+1)
    else:
        ax_year.text(.5, .5, "沒有有效出版年份", transform=ax_year.transAxes, ha="center")
    ax_year.set(title=f"出版年代分布（有效 {len(years)}／全部 {len(clean)} 本）", ylabel="記錄筆數（僅顯示有資料年代）")
    named = pubs.drop("未提供/未知", errors="ignore")
    if "未提供/未知" in pubs.index:
        named = pd.concat([named, pubs.loc[["未提供/未知"]]])
    bars = ax_pub.barh(named.index, named.values, color="#1D428A")
    ax_pub.bar_label(bars, padding=3)
    ax_pub.invert_yaxis()
    ax_pub.set_xlim(0, named.max()+1)
    ax_pub.set(title=f"出版社出現筆數（全部 {len(clean)} 本）", xlabel="記錄筆數")
    for ax in (ax_year, ax_pub):
        ax.grid(alpha=.25)
    fig.savefig(CHART_OUTPUT, dpi=150)
    plt.close(fig)
    print(f"已產生 {DETAIL_OUTPUT.name}、{CHART_OUTPUT.name}")


def main():
    api_key = ask_api_key()

    # 要求 2：本頁（第 1 頁）存入 pythonbook.csv
    first = to_rows(get_page(1, api_key), page=1)
    save_page(first, mode="w")
    print(f"第 1 頁：{len(first)} 本，已存入 {OUTPUT.name}")

    # 要求 3：進入下一頁（第 2 頁），再存入同一個 pythonbook.csv
    second = to_rows(get_page(2, api_key), page=2)
    save_page(second, mode="a")
    print(f"第 2 頁：{len(second)} 本，已附加到 {OUTPUT.name}\n")

    for row in first + second:
        print(f"[第 {row['頁數']} 頁] {row['書名']}｜{row['作者']}｜{row['出版日期']}")
    print(f"\n共兩頁 {len(first) + len(second)} 本書，已存成 {OUTPUT.name}")

    # 延伸：出版年代與出版社圖表分析
    analyze_and_draw(pd.DataFrame(first + second))


if __name__ == "__main__":
    if "--analyze-only" in sys.argv:
        analyze_and_draw()
    else:
        main()
