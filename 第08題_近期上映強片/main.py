"""
第 8 題（難）：抓取開眼電影網「近期上映強片」
================================================
題目要求
    抓 http://www.atmovies.com.tw/movie/new/ 裡的近期上映強片電影
    1. 列出「所有」的近期上映強片電影
    2. 列出名稱、上映時間及連結網址
    3. 存入 movies.csv

做法（requests + BeautifulSoup）
    開眼網站改版後，「近期上映強片」的橫向輪播已經從本週新片頁（/movie/new/）
    移到「電影」首頁 https://www.atmovies.com.tw/movie/（題目網址上方選單的「電影」），
    標題、海報與日期的樣子和題目附圖相同，所以改抓這一頁。

    1. 用 requests 下載電影首頁。
    2. 找到標題文字是「近期上映強片」的區塊（<h2 class="title">），往上找到整個區塊。
    3. 輪播一次只「顯示」4 部，但 HTML 裡其實有全部電影的卡片（.c-item-card），
       全部讀出來才是「所有」近期上映強片。
    4. 每張卡片：名稱＝.my-filmtitle 的文字、上映時間＝.my-date、連結網址＝卡片連結。
    5. 印出並存成 movies.csv（重新執行會直接覆蓋）。

輸出
    movies.csv        題目要求：名稱、上映時間、連結網址
    movies_detail.csv 延伸：日期、分析基準日（抓資料那天）、距基準日天數、ISO 週別、上映月份
    movies_charts.png 延伸：逐片上映日期圖、各有資料週上映片數

延伸：上映日期與 ISO 週別
    日期轉換失敗時保留缺漏，明列有效日期數。
    分析基準日＝抓資料那天：距基準日天數就是「抓到資料時，距離上映還有幾天」。
    重新抓資料時用當天日期；只跑 --analyze-only 時沿用 movies_detail.csv 記下的那次抓資料日期，
    同一份資料不管哪天分析，結果都一樣。
    週別採 ISO 年與週數（週一至週日），正確處理跨年週。
    左圖每部電影各占一列，不限制 13 部；右圖只顯示有資料週的片數。
    僅描述網站選列的強片清單，不推論整體市場的檔期策略或票房效果。

執行
    python 第08題_近期上映強片/main.py
    python 第08題_近期上映強片/main.py --analyze-only  # 直接以既有 CSV 產生圖表與分析討論
"""

import csv
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin

import matplotlib
import pandas as pd
import requests
from bs4 import BeautifulSoup

matplotlib.use("Agg")  # 只存圖檔、不開視窗
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402

URL = "https://www.atmovies.com.tw/movie/"  # 「近期上映強片」所在的頁面（見上方說明）
OUTPUT = Path(__file__).parent / "movies.csv"
DETAIL_OUTPUT = Path(__file__).parent / "movies_detail.csv"
CHART_OUTPUT = Path(__file__).parent / "movies_charts.png"
FIELDS = ["名稱", "上映時間", "連結網址"]


def get_html(url):
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    response.encoding = "utf-8"
    return response.text


def parse_upcoming(html):
    """找出「近期上映強片」區塊，回傳區塊裡所有電影。"""
    soup = BeautifulSoup(html, "html.parser")

    # 1. 找到標題是「近期上映強片」的 h2，再往上找整個區塊 <div class="c-section">
    heading = next(h for h in soup.select("h2.title") if h.get_text(strip=True) == "近期上映強片")
    section = heading.find_parent("div", class_="c-section")

    # 2. 讀出區塊裡的每一張電影卡片（包含輪播還沒轉到、畫面上看不到的）
    movies = []
    for card in section.select(".c-item-card"):
        link = card.select_one("a")
        title_box = card.select_one(".my-filmtitle")  # 裡面是「片名 + <p class="my-date">日期</p>」
        date = card.select_one(".my-date").get_text(strip=True)
        # 片名是 .my-filmtitle 自己的文字（不含裡面 <p> 的日期）
        title = "".join(title_box.find_all(string=True, recursive=False)).strip()
        movies.append({
            "名稱": title,
            "上映時間": date,
            "連結網址": urljoin(URL, link["href"]),
        })
    return movies


def use_chinese_font():
    """matplotlib 預設字型沒有中文，挑選系統已安裝的中文字型。"""
    candidates = ["Microsoft JhengHei", "PingFang TC", "Heiti TC", "Noto Sans CJK TC", "Arial Unicode MS"]
    installed = {font.name for font in font_manager.fontManager.ttflist}
    plt.rcParams["font.sans-serif"] = [name for name in candidates if name in installed] + ["DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False


def scrape_date(df):
    """上次抓資料的日期。movies_detail.csv 記著抓資料那天，但只有在它的片單跟現在的 movies.csv 一樣時才沿用
    （movies.csv 被換過就不算數）；否則用 movies.csv 存檔那天（台灣當地時間），再沒有就用今天。"""
    if DETAIL_OUTPUT.exists():
        recorded = pd.read_csv(DETAIL_OUTPUT)
        same_list = recorded.get("名稱") is not None and recorded["名稱"].astype(str).tolist() == df["名稱"].astype(str).tolist()
        if same_list and "分析基準日" in recorded and recorded["分析基準日"].notna().any():
            return pd.to_datetime(recorded["分析基準日"].dropna().iloc[0])
    if OUTPUT.exists():
        return pd.Timestamp(datetime.fromtimestamp(OUTPUT.stat().st_mtime)).normalize()  # fromtimestamp＝電腦的當地時間
    return pd.Timestamp.today().normalize()


def analyze_and_draw(df=None, base_date=None):
    """按上映日期與 ISO 週別分析，時間圖每部電影各占一列。base_date＝抓資料那天（沒給就用上次抓資料的日期）。"""
    if df is None:
        if not OUTPUT.exists():
            print(f"找不到 {OUTPUT.name}，無法進行分析。")
            return
        df = pd.read_csv(OUTPUT)
    if df.empty or "上映時間" not in df.columns:
        print("\n沒有任何電影資料，略過延伸分析。")
        return
    if base_date is None:
        base_date = scrape_date(df)
    clean = df.copy()
    clean["上映日期_dt"] = pd.to_datetime(clean["上映時間"], format="%Y/%m/%d", errors="coerce")
    clean["分析基準日"] = base_date.strftime("%Y-%m-%d")
    clean["距基準日天數"] = (clean["上映日期_dt"] - base_date).dt.days.astype("Int64")
    iso = clean["上映日期_dt"].dt.isocalendar()
    clean["上映週別"] = iso["year"].astype("string") + "-W" + iso["week"].astype("string").str.zfill(2)
    clean["上映月份"] = clean["上映日期_dt"].dt.strftime("%Y-%m")
    clean.to_csv(DETAIL_OUTPUT, index=False, encoding="utf-8-sig")
    valid = clean.dropna(subset=["上映日期_dt"]).sort_values("上映日期_dt", kind="stable").reset_index(drop=True)
    print(f"\n分析基準日（抓資料那天）{base_date:%Y/%m/%d}；有效日期 {len(valid)}／{len(clean)} 部；無效日期 {len(clean)-len(valid)} 部。")
    if valid.empty:
        print("沒有有效上映日期，略過繪圖。")
        return
    weeks = valid["上映週別"].value_counts().sort_index()
    print("週別使用 ISO 年與週數（週一至週日）；各有資料週的上映片數：")
    print(weeks.to_string())
    for week, count in weeks[weeks.gt(1)].items():
        names = valid.loc[valid["上映週別"].eq(week), "名稱"].astype(str)
        print(f"{week} 同週 {count} 部：{'、'.join(names)}")
    print("資料僅為網站選列的近期強片，未包含所有上映電影；只能描述這份清單，無法判定全市場檔期策略與票房效果。")
    use_chinese_font()
    import matplotlib.dates as mdates
    fig, (ax_time, ax_bar) = plt.subplots(1, 2, figsize=(17, max(6, len(valid)*.43)), layout="constrained")
    y = list(range(len(valid)))
    ax_time.scatter(valid["上映日期_dt"], y, color="#1D428A", s=45)
    ax_time.set_yticks(y, labels=valid["名稱"].astype(str), fontsize=9)
    ax_time.invert_yaxis()
    for i, row in valid.iterrows():
        ax_time.annotate(f"{row['上映日期_dt']:%Y/%m/%d}", (row["上映日期_dt"], i), xytext=(7, 0), textcoords="offset points", va="center", fontsize=8)
    ax_time.axvline(base_date, color="gray", linestyle="--", label=f"抓資料那天 {base_date:%Y/%m/%d}")
    ax_time.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=3, maxticks=6))
    ax_time.xaxis.set_major_formatter(mdates.DateFormatter("%Y/%m"))
    low = min(base_date, valid["上映日期_dt"].min())
    high = max(base_date, valid["上映日期_dt"].max())
    pad = max(45, (high-low).days*.18)
    ax_time.set_xlim(low-pd.Timedelta(days=15), high+pd.Timedelta(days=pad))
    ax_time.set(title=f"近期強片上映日期（有效 {len(valid)} 部）", xlabel="上映日期")
    ax_time.legend(loc="upper right", fontsize=8)
    bars = ax_bar.bar(weeks.index, weeks.values, color=["#C8102E" if v>1 else "#1D428A" for v in weeks.values])
    ax_bar.bar_label(bars, padding=3)
    ax_bar.tick_params(axis="x", rotation=55, labelsize=8)
    ax_bar.set(title="各 ISO 週上映片數（僅顯示有資料週）", ylabel="本清單上映片數", ylim=(0, weeks.max()+1))
    ax_bar.yaxis.set_major_locator(plt.MaxNLocator(integer=True))
    for ax in (ax_time, ax_bar):
        ax.grid(alpha=.25)
    fig.savefig(CHART_OUTPUT, dpi=150)
    plt.close(fig)
    print(f"已產生 {DETAIL_OUTPUT.name}、{CHART_OUTPUT.name}")


def main():
    movies = parse_upcoming(get_html(URL))

    for number, movie in enumerate(movies, start=1):
        print(f"{number}. {movie['名稱']}｜上映時間 {movie['上映時間']}｜{movie['連結網址']}")

    with open(OUTPUT, "w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(movies)
    print(f"\n近期上映強片共 {len(movies)} 部，已存成 {OUTPUT.name}")

    # 延伸：強片排期時間軸與檔期分析（分析基準日＝今天，也就是抓資料那天）
    analyze_and_draw(pd.DataFrame(movies), base_date=pd.Timestamp.today().normalize())


if __name__ == "__main__":
    if "--analyze-only" in sys.argv:
        analyze_and_draw()
    else:
        main()
