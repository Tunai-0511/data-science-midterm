"""
第 11 題（難）：抓取 NBA 商品資料（每一頁存成一個 CSV）
================================================
題目要求
    抓 https://fchart.github.io/ML/nba_items.html 裡的資料
    1. 列出「所有」NBA 商品資料
    2. 每存完一個 CSV 檔，便印出其編號，如「儲存頁面: 1」
    3. 分頁存入不同的 NBA_Products{1~n}.csv 檔內
    4. 開啟的 CSV 檔不能為亂碼
    （課堂補充：要操作分頁直到最後一頁，第 1 頁到第 n 頁分別存成檔案）

做法（Selenium）
    這個網頁的表格是 JavaScript 動態產生的，一次只顯示 10 筆，要按分頁按鈕才會換資料，
    所以用 Selenium 操作瀏覽器：
    1. 開啟網頁，先從分頁列的「最後一頁 »」按鈕讀出總頁數（按鈕的 value 就是最後一頁的頁碼）。
    2. 讀出目前這一頁表格的每一列（商品編號、商品名稱、價格）。
    3. 存成 NBA_Products{頁碼}.csv，存完立刻印出「儲存頁面: 頁碼」。
    4. 按「下一頁 >」按鈕，等表格內容換掉後，回到第 2 步；
       到了最後一頁就沒有「下一頁」按鈕，迴圈結束，並核對是否真的到了第 1 步讀到的最後一頁。
       結束前把分頁列捲到畫面中間、停一下（秒數由 PAUSE_SECONDS 設定），讓看程式執行的人看清楚已經到最後一頁。
    5. CSV 用 utf-8-sig 編碼（加上 BOM），Excel 開啟中文不會亂碼。
    6. 開始前先刪掉舊的 NBA_Products*.csv，重新執行就是全新覆蓋。

輸出
    NBA_Products1.csv ~ NBA_ProductsN.csv 題目要求：各頁商品分別存檔
    nba_products_all.csv                延伸：合併記錄、規則分類、數值價格
    nba_products_charts.png             延伸：類別數量與價格箱型圖

延伸：商品規則分類與價格分布
    合併各頁 CSV；以名稱關鍵字分類為上衣、褲子、帽子、球衣、其他。
    連帽、帽 T、Hoodie 歸上衣；配件先行辨識，背心暫歸球衣。
    商品數包含全部記錄，價格統計僅用有效正價格；每類均揭露有效樣本數。
    分類屬規則判斷，仍可能誤判；不以商品數推論銷量或以價格推論成本。

執行
    python 第11題_NBA商品資料/main.py
    python 第11題_NBA商品資料/main.py --analyze-only  # 直接以既有 CSV 產生圖表與分析討論
"""

import csv
import re
import sys
import time
from pathlib import Path

import matplotlib
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

matplotlib.use("Agg")  # 只存圖檔、不開視窗
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402

URL = "https://fchart.github.io/ML/nba_items.html"
FOLDER = Path(__file__).parent
FIELDS = ["商品編號", "商品名稱", "價格"]
MERGED_OUTPUT = FOLDER / "nba_products_all.csv"
CHART_OUTPUT = FOLDER / "nba_products_charts.png"
PAUSE_SECONDS = 1  # 到最後一頁時，瀏覽器停留幾秒再關閉


def read_table(driver):
    """讀出目前顯示的表格（tbody#table-body 的每一列）。"""
    products = []
    for tr in driver.find_elements(By.CSS_SELECTOR, "#table-body tr"):
        cells = [td.text for td in tr.find_elements(By.TAG_NAME, "td")]
        products.append(dict(zip(FIELDS, cells)))
    return products


def save_page(page, products):
    """把一頁商品存成 NBA_Products{page}.csv。"""
    path = FOLDER / f"NBA_Products{page}.csv"
    with open(path, "w", newline="", encoding="utf-8-sig") as file:  # utf-8-sig：Excel 不會亂碼
        writer = csv.DictWriter(file, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(products)


def use_chinese_font():
    """matplotlib 預設字型沒有中文，挑選系統已安裝的中文字型。"""
    candidates = ["Microsoft JhengHei", "PingFang TC", "Heiti TC", "Noto Sans CJK TC", "Arial Unicode MS"]
    installed = {font.name for font in font_manager.fontManager.ttflist}
    plt.rcParams["font.sans-serif"] = [name for name in candidates if name in installed] + ["DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False


def classify_product(name):
    """依名稱做規則分類；先辨識配件與褲子，避免連帽衣被當成帽子。"""
    if pd.isna(name):
        return "其他"
    n = str(name).lower()
    if any(k in n for k in ["襪", "頭帶", "髮帶", "臂套", "袖套", "護腕", "腕帶", "手環"]):
        return "其他"
    if "褲" in n or re.search(r"\b(shorts|pants|trousers)\b", n):
        return "褲子"
    if any(k in n for k in ["連帽", "帽t", "帽 t", "hoodie", "hooded"]):
        return "上衣"
    if any(k in n for k in ["帽子", "棒球帽", "老帽", "毛帽", "漁夫帽", "鴨舌帽"]) or re.search(r"\b(cap|hat|beanie)\b", n):
        return "帽子"
    if "球衣" in n or "背心" in n or re.search(r"\bjersey\b", n):
        return "球衣"
    if any(k in n for k in ["上衣", "短t", "長t", "t恤", "tee", "短袖", "長袖", "衛衣", "外套", "風衣", "jacket", "t-shirt"]):
        return "上衣"
    return "其他"


def analyze_and_draw():
    """合併各頁資料，以規則分類並呈現數量及有效價格分布。"""
    csv_files = sorted(
        (p for p in FOLDER.glob("NBA_Products*.csv") if re.fullmatch(r"NBA_Products\d+", p.stem)),
        key=lambda p: int(re.search(r"\d+", p.stem).group()),
    )
    if not csv_files:
        print("找不到各頁 NBA 商品 CSV。")
        return
    dfs = []
    for path in csv_files:
        df = pd.read_csv(path)
        df["來源頁碼"] = int(re.search(r"\d+", path.stem).group())
        dfs.append(df)
    all_df = pd.concat(dfs, ignore_index=True)
    text = all_df["價格"].astype("string").str.replace(",", "", regex=False).str.replace(r"^(?:NT\$|\$)\s*", "", regex=True).str.strip()
    all_df["價格(元)"] = pd.to_numeric(text, errors="coerce")
    all_df.loc[all_df["價格(元)"] <= 0, "價格(元)"] = float("nan")
    all_df["商品類型"] = all_df["商品名稱"].apply(classify_product)
    all_df.to_csv(MERGED_OUTPUT, index=False, encoding="utf-8-sig")
    print(f"\n合併 {len(csv_files)} 頁，共 {len(all_df)} 筆；無效價格 {all_df['價格(元)'].isna().sum()} 筆。")
    if all_df.empty:
        return
    order = [c for c in ["上衣", "褲子", "帽子", "球衣", "其他"] if c in all_df["商品類型"].values]
    counts = all_df["商品類型"].value_counts().reindex(order)
    print("各類數量（分母為全部商品記錄）：")
    for cat in order:
        prices = all_df.loc[all_df["商品類型"].eq(cat), "價格(元)"].dropna()
        print(f"  {cat}：{counts[cat]} 筆（{counts[cat]/len(all_df)*100:.1f}%）；有效價格 {len(prices)} 筆", end="")
        if not prices.empty:
            print(f"；中位數 {prices.median():,.1f} 元；範圍 {prices.min():,.0f}～{prices.max():,.0f} 元。")
        else:
            print("；無有效價格。")
    print("類型由商品名稱關鍵字判斷，背心暫歸球衣，仍可能有誤判；其他含配件、鞋與球等。")
    print("本次僅合併記錄，未依流水號或名稱去重；商品數不代表銷量，價格差異也無法推論製作成本或消費偏好。")
    use_chinese_font()
    fig, (ax_bar, ax_box) = plt.subplots(1, 2, figsize=(14, 6), layout="constrained")
    bars = ax_bar.bar(order, counts.values, color="#1D428A")
    ax_bar.bar_label(bars, labels=[f"{v} 筆\n({v/len(all_df)*100:.1f}%)" for v in counts], padding=4)
    ax_bar.set(title=f"商品規則分類（{len(csv_files)} 頁，共 {len(all_df)} 筆）", ylabel="記錄筆數", ylim=(0, counts.max()*1.25))
    price_order = [c for c in order if all_df.loc[all_df["商品類型"].eq(c), "價格(元)"].notna().any()]
    if price_order:
        price_data = [all_df.loc[all_df["商品類型"].eq(c), "價格(元)"].dropna() for c in price_order]
        ax_box.boxplot(price_data, patch_artist=True, showmeans=True, medianprops={"color": "#C8102E"})
        ax_box.set_xticks(range(1, len(price_order)+1), labels=[f"{c}\n(n={len(p)})" for c,p in zip(price_order,price_data)])
        for i, prices in enumerate(price_data, 1):
            ax_box.annotate(f"{prices.median():,.0f}", (i, prices.median()), xytext=(12, 5), textcoords="offset points", fontsize=8, color="#C8102E")
    else:
        ax_box.text(.5, .5, "沒有有效價格", transform=ax_box.transAxes, ha="center")
    ax_box.set(title="各類有效價格箱型圖（紅線為中位數）", ylabel="價格（新台幣元）")
    for ax in (ax_bar, ax_box):
        ax.grid(axis="y", alpha=.25)
    fig.savefig(CHART_OUTPUT, dpi=150)
    plt.close(fig)
    print(f"已產生 {MERGED_OUTPUT.name}、{CHART_OUTPUT.name}")


def main():
    for old_file in FOLDER.glob("NBA_Products*.csv"):  # 清掉上次的輸出檔
        old_file.unlink()

    driver = webdriver.Chrome()
    wait = WebDriverWait(driver, 20)
    total = 0
    try:
        driver.get(URL)
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "#table-body tr")))
        # 分頁列的「最後一頁 »」按鈕，value 就是最後一頁的頁碼
        last_button = driver.find_element(By.XPATH, "//button[contains(., '最後一頁')]")
        last_page = int(last_button.get_attribute("value"))
        print(f"商品資料共 {last_page} 頁，從第 1 頁一路按「下一頁」到最後一頁\n")

        page = 1
        while True:
            products = read_table(driver)
            for product in products:
                print(product)
            save_page(page, products)
            print(f"儲存頁面: {page}")
            total += len(products)

            next_buttons = driver.find_elements(By.CSS_SELECTOR, "button.nextbtn")  # 「下一頁 >」
            if not next_buttons:  # 最後一頁沒有下一頁按鈕
                # 把分頁列捲到畫面中間並停一下，讓人在瀏覽器上看清楚已經到最後一頁
                pager = driver.find_element(By.ID, "pagination-wrapper")
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", pager)
                print(f"\n已到最後一頁（第 {page} 頁），瀏覽器停留 {PAUSE_SECONDS} 秒…")
                time.sleep(PAUSE_SECONDS)
                break
            first_row = driver.find_element(By.CSS_SELECTOR, "#table-body tr")
            next_buttons[0].click()
            wait.until(EC.staleness_of(first_row))  # 舊的表格列消失，代表已換成下一頁
            page += 1
    finally:
        driver.quit()

    status = "已到最後一頁" if page == last_page else f"注意：只到第 {page} 頁，沒有到最後一頁（第 {last_page} 頁）"
    print(f"\n{status}。全部 {page} 頁、{total} 筆商品，已存成 NBA_Products1.csv ~ NBA_Products{page}.csv")

    # 延伸：合併分類與圖表繪製
    analyze_and_draw()


if __name__ == "__main__":
    if "--analyze-only" in sys.argv:
        analyze_and_draw()
    else:
        main()
