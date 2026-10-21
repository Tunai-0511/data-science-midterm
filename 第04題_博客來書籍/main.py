"""
第 4 題（中）：抓取博客來「演算法」的搜尋結果
================================================
題目要求
    1. 網址 https://search.books.com.tw/search/query/key/{0}/cat/all，{0} = "演算法"
    2. 抓取資料存入 booklist.csv，內容包括 ["書名", "網址", "作者", "書價"]

做法（Selenium 載入網頁 + BeautifulSoup 解析）
    博客來搜尋頁前面有 Cloudflare 防護：用 requests 直接抓會得到 403
    「連線暫時異常」，所以改用 Selenium 開真的 Chrome 載入網頁，再交給 BeautifulSoup 解析。

    1. 把「演算法」放進題目給的網址 {0}，開啟搜尋結果（題目網址就是第 1 頁，共 60 本）。
    2. 每本書在 <div class="table-td" id="prod-itemlist-商品編號"> 裡：
       書名 = h4 連結的 title，作者 = p.author 裡的連結，書價 = ul.price 裡最後一個數字（元）。
       搜尋頁的連結是博客來的轉址網址，改寫成正式商品頁 https://www.books.com.tw/products/商品編號。
    3. 逐筆印出每本書，寫入 booklist.csv（重新執行會直接覆蓋）。

    為什麼只抓題目網址這一頁：博客來（例：2026-10 時網站顯示共 673 筆、12 頁）在換到第 2 頁時會跳出
    Cloudflare 的「Verify you are human」真人驗證；2026-10 實測放慢翻頁、由真人在程式開的
    瀏覽器裡勾選，都無法通過。程式不應該繞過驗證，所以只抓題目指定的網址（第 1 頁）。

輸出
    booklist.csv          題目要求：書名、網址、作者、書價
    book_price_charts.png 延伸：價格直方圖、箱型圖

延伸：書價分布與離群值
    書價去逗號轉數值；非正值或無法解析的價格保留為缺漏。
    以有效價格計算平均數、中位數、四分位數、IQR 與上側離群界線。
    動態顯示 300～550 元的本數與比例，檢查重複網址及網址缺漏。
    直方圖自動分箱，箱型圖保留完整範圍；僅描述本頁優惠售價，不推論定價原因。

執行
    python 第04題_博客來書籍/main.py
    python 第04題_博客來書籍/main.py --analyze-only  # 直接以既有 CSV 產生圖表與分析討論
"""

import csv
import re
import sys
from pathlib import Path
from urllib.parse import quote

import matplotlib
import pandas as pd
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

matplotlib.use("Agg")  # 只存圖檔、不開視窗
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402

KEYWORD = "演算法"
URL_TEMPLATE = "https://search.books.com.tw/search/query/key/{0}/cat/all"  # 題目給的網址
OUTPUT = Path(__file__).parent / "booklist.csv"
CHART_OUTPUT = Path(__file__).parent / "book_price_charts.png"
FIELDS = ["書名", "網址", "作者", "書價"]
BOOK_SELECTOR = "div.table-td[id^='prod-itemlist-']"  # 每一本書的區塊


def get_html_with_chrome(url):
    """用 Selenium 開 Chrome 載入搜尋頁，等書籍出現後回傳網頁原始碼。"""
    driver = webdriver.Chrome()
    try:
        driver.get(url)
        if "Just a moment" in driver.title:  # Cloudflare 驗證頁的標題
            print("博客來要求真人驗證：請在 Chrome 視窗中手動勾選，程式最多等 2 分鐘。")
        try:
            WebDriverWait(driver, 120).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, BOOK_SELECTOR))
            )
        except TimeoutException:
            raise SystemExit("等了 2 分鐘仍沒有看到搜尋結果（可能被博客來暫時擋下），請稍後再執行。")
        return driver.page_source
    finally:
        driver.quit()


def parse_books(html):
    """解析搜尋結果頁，回傳書籍清單。"""
    soup = BeautifulSoup(html, "html.parser")
    books = []
    for item in soup.select(BOOK_SELECTOR):
        product_id = item["id"].replace("prod-itemlist-", "")  # 例如 0011055506
        title = item.select_one("h4 a")["title"]  # 書名連結的 title 屬性就是完整書名
        authors = [a.get_text(strip=True) for a in item.select("p.author a")]
        # 價格文字像「優惠價: 79 折, 316 元」或「優惠價: 316 元」，取最後一個數字（實際售價）
        price_text = item.select_one("ul.price").get_text(" ", strip=True)
        numbers = re.findall(r"\d[\d,]*", price_text)

        books.append({
            "書名": title,
            "網址": f"https://www.books.com.tw/products/{product_id}",
            "作者": "、".join(authors),
            "書價": numbers[-1].replace(",", "") if numbers else "",
        })
    return books


def use_chinese_font():
    """matplotlib 預設字型沒有中文，挑選系統已安裝的中文字型。"""
    candidates = ["Microsoft JhengHei", "PingFang TC", "Heiti TC", "Noto Sans CJK TC", "Arial Unicode MS"]
    installed = {font.name for font in font_manager.fontManager.ttflist}
    plt.rcParams["font.sans-serif"] = [name for name in candidates if name in installed] + ["DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False


def save_csv(books):
    """儲存題目要求的原始欄位，使用 BOM 方便 Excel 開啟。"""
    with OUTPUT.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDS)
        writer.writeheader()
        for number, book in enumerate(books, start=1):
            print(f"{number}. {book['書名']}｜{book['作者']}｜{book['書價']} 元｜{book['網址']}")
            writer.writerow(book)


def analyze_and_draw(df=None):
    """檢查重複、轉換書價，以有效價格計算統計量並繪圖。"""
    if df is None:
        if not OUTPUT.exists():
            print(f"找不到 {OUTPUT.name}，無法進行分析。")
            return
        df = pd.read_csv(OUTPUT)
    clean = df.copy()
    # 爬蟲存的書價已經是數字；若是「1,500」「售完」這類文字也轉成數字，無效或非正值留空
    clean["書價"] = pd.to_numeric(clean["書價"].astype("string").str.replace(",", "", regex=False), errors="coerce")
    clean.loc[clean["書價"] <= 0, "書價"] = float("nan")
    prices = clean["書價"].dropna()
    print("\n========== 延伸分析：博客來書價 ==========")
    print(f"樣本 {len(clean)} 本；有效價格 {len(prices)} 本；缺漏或無效價格 {len(clean)-len(prices)} 本。")
    urls = clean["網址"].dropna().astype(str).str.strip()
    urls = urls[urls.ne("")]
    print(f"重複網址列數（含同組全部列）：{urls.duplicated(keep=False).sum()}；未提供網址：{len(clean)-len(urls)}。")
    if prices.empty:
        print("沒有有效價格，略過統計與繪圖。")
        return
    q1, median, q3 = prices.quantile([.25, .5, .75])
    iqr = q3 - q1
    threshold = q3 + 1.5 * iqr
    count = prices.between(300, 550).sum()
    print(f"最低價 {prices.min():,.2f}；Q1 {q1:,.2f}；中位數 {median:,.2f}；Q3 {q3:,.2f}；最高價 {prices.max():,.2f} 元。")
    print(f"平均價 {prices.mean():,.2f} 元；IQR {iqr:,.2f} 元；上側離群判定界線 {threshold:,.2f} 元。")
    print(f"300～550 元共 {count} 本，占有效價格樣本 {count/len(prices)*100:.1f}%。")
    outliers = clean[clean["書價"] > threshold]
    print(f"超過上側界線的書籍共 {len(outliers)} 本：")
    for _, row in outliers.iterrows():
        print(f"  《{row['書名']}》：{row['書價']:,.0f} 元")
    print("以上為搜尋結果本頁的優惠售價分布；未蒐集頁數、裝訂與成本，無法由價格判定高價原因。")
    use_chinese_font()
    fig, (ax_hist, ax_box) = plt.subplots(1, 2, figsize=(14, 5.5))
    ax_hist.hist(prices, bins="auto", color="#1D428A", edgecolor="white", alpha=.8)
    ax_hist.axvline(median, color="#C8102E", linestyle="--", label=f"中位數 {median:,.1f} 元")
    ax_hist.axvline(prices.mean(), color="#E8A317", linestyle=":", label=f"平均數 {prices.mean():,.1f} 元")
    ax_hist.set(title=f"本頁書價分布（有效 {len(prices)}／全部 {len(clean)} 本）", xlabel="優惠售價（新台幣元）", ylabel="本數")
    ax_hist.legend()
    ax_box.boxplot(prices, patch_artist=True, showmeans=True,
                   boxprops={"facecolor": "#87CEEB"}, medianprops={"color": "#C8102E"})
    ax_box.axhline(threshold, color="gray", linestyle=":", label=f"上側界線 {threshold:,.1f} 元")
    ax_box.set(title="書價箱型圖（鬚線內最遠資料點，圈點為離群值）", ylabel="優惠售價（新台幣元）", xticks=[1], xticklabels=["本頁書籍"])
    ax_box.legend()
    for ax in (ax_hist, ax_box):
        ax.grid(axis="y", linestyle="--", alpha=.3)
    fig.tight_layout()
    fig.savefig(CHART_OUTPUT, dpi=150)
    plt.close(fig)
    print(f"已產生 {CHART_OUTPUT.name}")


def main():
    url = URL_TEMPLATE.format(quote(KEYWORD))  # 把「演算法」轉成網址編碼後放進 {0}
    print(f"搜尋網址：{url}\n")

    html = get_html_with_chrome(url)
    books = parse_books(html)

    save_csv(books)
    print(f"\n「{KEYWORD}」搜尋結果共 {len(books)} 本書，已存成 {OUTPUT.name}")

    # 延伸：書價統計與圖表分析
    analyze_and_draw(pd.DataFrame(books))


if __name__ == "__main__":
    if "--analyze-only" in sys.argv:
        analyze_and_draw()
    else:
        main()
