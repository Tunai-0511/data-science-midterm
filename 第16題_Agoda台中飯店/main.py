"""
第 16 題（難）：抓取 Agoda 搜尋「台中」的飯店資料（全部結果頁），並做資料前處理
================================================
題目要求（網址 https://www.agoda.com/zh-tw/）
    1. 輸入「台中」
    2. 抓取結果頁面存入 agoda_result.csv，包括飯店名及價格
    3. <加分> 使用 Selenium 及 WebDriver 自動輸入「台中」，並加入 CSV 檔
    （老師補充：可以同時做「有資料處理」和「沒有資料處理」的版本、抓更多資料欄位，
      並在報告說明抓這些資料的意義）

資料的意義
    在同一個入住日期、同樣 2 位大人 1 間房的條件下，把台中所有能訂的飯店價格和評價
    一次抓下來，就能比較台中各地區住一晚大概要多少錢、評分和價格的關係，
    找出評分高、價格又合理的飯店，作為旅遊訂房的參考，也能看出台中住宿的價格分布。

做法
    第一部分：爬蟲（Selenium 操作網頁 + BeautifulSoup 解析）→ 沒有資料處理的原始資料
    1. 開啟 Agoda 首頁，在目的地搜尋框自動輸入「台中」（加分項），從建議清單點選「台中市」。
       選完 Agoda 會自動打開日曆，按 Esc 關掉，沿用網站預設的入住／退房日期。
    2. 按「搜出好價」，結果頁會開在新分頁，切換過去。
    3. 結果頁的飯店卡片要捲到畫面上才會載入內容，所以一段一段慢慢往下捲，
       每捲一次就用 BeautifulSoup 讀出已載入的卡片。除了題目要的飯店名、價格，
       還抓原價、星級、評價、位置得分、地區、附近地標、標籤（免費取消／促銷廣告）、網址。
    4. 捲到底後按「下一頁」，重複第 3 步，直到沒有下一頁為止
       （Agoda 的總頁數會隨搜尋結果變動，所以不寫死頁數）。
    5. 網頁上看到的全部照原樣存成 agoda_result.csv：文字不轉換，
       已額滿（沒有價格）的飯店、在不同頁重複出現的飯店也都保留。

    第二部分：資料前處理（pandas）→ 有資料處理的版本
    6. 移除沒有價格的飯店（已額滿或不開放預訂）。
    7. 移除重複的飯店（同一間飯店出現在不同頁，用 Agoda 的飯店 ID 判斷，只留第一次）。
    8. 格式轉換：把文字轉成可以計算的數字，例如價格「NT$ 1,474」→ 1474、
       評價「8.5 很讚 14,621 篇評鑑」→ 評分 8.5、評價等級「很讚」、評論數 14621
       （Agoda 舊版寫成「平均很讚8.5分（滿分10分），共6,789則評論」，兩種寫法都能轉換）。
    9. 存成 agoda_result_processed.csv，並印出每一步移除了幾筆。

輸出
    agoda_result.csv           題目要求與額外欄位的原始資料
    agoda_result_processed.csv 清理後資料
    agoda_charts.png           延伸：平台地區房價、價格評分散布圖

    價格為每晚、不含稅及其他費用，會隨查詢日期變動。
    執行時間：每頁約 40 秒，全部約 4～5 分鐘。中途出錯或按 Ctrl+C，已抓到的資料照樣存檔處理。

延伸：平台地區房價與價格評分關係
    平台地區可能是行政區、商圈或景點，保留原分類，不稱為統一行政區。
    地區價格統計使用全部有效正價格；相關分析使用價格及評分皆有效的樣本。
    箱型圖合併各少於 4 筆的地區；對數價格軸顯示完整範圍，保留所有高價點。
    動態列出樣本數、中位數、Pearson 相關、高價組平均與低於 8.5 分筆數。
    僅描述本次查詢，不推論因果、統計顯著性或住宿品質成因。

執行
    python 第16題_Agoda台中飯店/main.py
    python 第16題_Agoda台中飯店/main.py --analyze-only  # 直接以既有清理資料產生圖表與分析討論
"""

import re
import sys
import time
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlsplit

import matplotlib
import pandas as pd
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

matplotlib.use("Agg")  # 只存圖檔、不開視窗
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402

URL = "https://www.agoda.com/zh-tw/"
KEYWORD = "台中"
FOLDER = Path(__file__).parent
RAW_OUTPUT = FOLDER / "agoda_result.csv"                 # 沒有資料處理
PROCESSED_OUTPUT = FOLDER / "agoda_result_processed.csv"  # 有資料處理（前處理）
CHART_OUTPUT = FOLDER / "agoda_charts.png"              # 延伸圖表
MAX_PAGES = 20  # 安全上限，避免無限翻頁
HOTEL_NAME = "[data-selenium='hotel-name']"
NEXT_BUTTON = "[data-selenium='pagination-next-btn']"


# ======================================================================
# 第一部分：爬蟲 —— 抓下網頁上的原始資料（沒有資料處理）
# ======================================================================

def visible_search_button(driver):
    """「搜出好價」按鈕。Agoda 的按鈕名稱有 search-button、search-button-sticky（上方固定搜尋列）等版本，
    所以找名稱以 search-button 開頭的按鈕，挑看得見、能按的那一個；還沒有就回傳 False，讓 WebDriverWait 繼續等。"""
    buttons = driver.find_elements(By.CSS_SELECTOR, "button[data-element-name^='search-button']")
    return next((b for b in buttons if b.is_displayed() and b.is_enabled()), False)


def search_taichung(driver):
    """在首頁自動輸入「台中」，選「台中市」，再按「搜出好價」。"""
    wait = WebDriverWait(driver, 30)
    driver.get(URL)

    # 1. 自動輸入「台中」
    search_box = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "input[data-selenium='textInput']")))
    search_box.click()
    search_box.send_keys(KEYWORD)

    # 2. 點建議清單裡的「台中市」
    city = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "[role='option'][data-element-value='台中市']")))
    city.click()
    time.sleep(1)
    ActionChains(driver).send_keys(Keys.ESCAPE).perform()  # 關掉自動跳出的日曆
    check_in = driver.find_element(By.CSS_SELECTOR, "[data-selenium='checkInText']").text
    check_out = driver.find_element(By.CSS_SELECTOR, "[data-selenium='checkOutText']").text
    print(f"目的地：台中市｜入住 {check_in}｜退房 {check_out}｜2 位大人、1 間房（網站預設）\n")

    # 3. 按「搜出好價」，結果會開在新分頁；偶爾按了沒反應，15 秒沒開新分頁就再按一次（最多 3 次）
    tabs_before = len(driver.window_handles)
    for attempt in range(1, 4):
        search_button = wait.until(visible_search_button)
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", search_button)
        search_button.click()
        try:
            WebDriverWait(driver, 15).until(lambda d: len(d.window_handles) > tabs_before)
            break
        except TimeoutException:
            if attempt == 3:
                raise
            print("（按了「搜出好價」沒有開出結果頁，再按一次）")
    driver.switch_to.window(driver.window_handles[-1])  # 切換到新分頁
    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, HOTEL_NAME)))


def text_of(card, selector):
    """卡片裡某個欄位的文字；這間飯店沒有這個欄位就回傳空字串。"""
    node = card.select_one(selector)
    return node.get_text(" ", strip=True) if node else ""


def first_text_of(card, selector):
    """欄位裡的第一段文字，例如原價欄的「原始價格：4,574」（後面還有折扣等其他文字）。"""
    node = card.select_one(selector)
    return next((s.strip() for s in node.find_all(string=True) if s.strip()), "") if node else ""


def review_of(card):
    """評價文字。Agoda 有兩種版面：有的先有一段「平均很讚8.5分（滿分10分），共14,621則評論」，
    有的只有「8.5 很讚 14,621 篇評鑑」（第一段只是分數 8.5）。先取第一段，只拿到分數時改取整段。"""
    selector = "[data-element-name='property-card-review']"
    review = first_text_of(card, selector)
    return review if "評" in review else text_of(card, selector)


def hotel_url(href):
    """飯店頁網址：去掉後面一長串查詢參數，只保留 propertyId（新版連結靠它分辨是哪一間飯店）。"""
    parts = urlsplit(urljoin(URL, href))
    property_id = parse_qs(parts.query).get("propertyId")
    query = f"?propertyId={property_id[0]}" if property_id else ""
    return f"{parts.scheme}://{parts.netloc}{parts.path}{query}"


def parse_card(card, page):
    """把一張飯店卡片整理成一筆原始資料（全部保留網頁上的文字，不做任何轉換）。"""
    link = card.select_one("a[href]")
    currency = text_of(card, "[data-selenium='hotel-currency']")  # NT$（已額滿的飯店沒有）
    price = text_of(card, "[data-selenium='display-price']")      # 1,474
    tags = [text_of(card, selector) for selector in (
        "[data-element-name='ssr-free-cancellation-badge']",  # 免費取消
        "[data-element-name='sponsored-badge']",              # 促銷廣告
    )]
    return {
        "頁數": page,
        "飯店ID": card.get("data-hotelid", ""),
        "飯店名": text_of(card, HOTEL_NAME),
        "價格": f"{currency} {price}".strip(),
        "原價": first_text_of(card, "[data-element-name='fpc-cor-price']"),  # 劃線的原始價格
        "星級": text_of(card, "[data-element-name='ssr-property-card-star-rating']"),
        "評價": review_of(card),
        "位置得分": text_of(card, "[data-element-name='property-card-location-score-inline']"),
        "地區": text_of(card, "[data-selenium='area-city-text']"),
        "附近地標": text_of(card, "[data-selenium='popular-landmarks-text']"),
        "標籤": "、".join(tag for tag in tags if tag),
        "網址": hotel_url(link["href"]) if link else "",
    }


def collect_page(driver, hotels, page):
    """把目前這一頁慢慢往下捲到底，邊捲邊讀出已載入的飯店卡片，加進 hotels。回傳這一頁讀到幾間。"""
    before = len(hotels)
    for _ in range(100):  # 最多捲 100 次，避免無限迴圈
        soup = BeautifulSoup(driver.page_source, "html.parser")
        for card in soup.select("li[data-selenium='hotel-item']"):
            if not card.select_one(HOTEL_NAME):  # 還沒載入的卡片（只有灰色外框），先跳過
                continue
            row = parse_card(card, page)
            # 捲動時同一張卡片會被讀到好幾次，用「頁數＋飯店 ID」當鑰匙只記一筆；
            # 如果先讀到時價格還沒載入，之後讀到有價格的版本就更新
            key = (page, row["飯店ID"] or row["飯店名"])
            if key not in hotels or (not hotels[key]["價格"] and row["價格"]):
                hotels[key] = row

        at_bottom = driver.execute_script(
            "return window.innerHeight + window.scrollY >= document.body.scrollHeight - 2"
        )
        if at_bottom:
            break
        driver.execute_script("window.scrollBy(0, 700);")  # 往下捲 700 像素
        time.sleep(0.8)  # 等新的卡片載入
    return len(hotels) - before


def go_to_next_page(driver):
    """按「下一頁」，等第一間飯店換掉（代表新的一頁已載入）。沒有下一頁就回傳 False。"""
    buttons = [b for b in driver.find_elements(By.CSS_SELECTOR, NEXT_BUTTON) if b.is_displayed() and b.is_enabled()]
    if not buttons:
        return False
    first_hotel = driver.find_element(By.CSS_SELECTOR, HOTEL_NAME).text
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", buttons[0])
    time.sleep(0.5)
    buttons[0].click()
    WebDriverWait(driver, 30).until(
        lambda d: d.find_elements(By.CSS_SELECTOR, HOTEL_NAME)
        and d.find_element(By.CSS_SELECTOR, HOTEL_NAME).text != first_hotel
    )
    driver.execute_script("window.scrollTo(0, 0);")  # 回到新頁面的最上面，再開始往下捲
    time.sleep(1)
    return True


def scrape_all_pages():
    """執行完整的爬蟲流程，回傳每一筆原始資料（list of dict）。"""
    driver = webdriver.Chrome()
    hotels = {}  # (頁數, 飯店 ID) → 原始資料
    try:
        driver.set_window_size(1366, 900)  # 視窗太小時 Agoda 會改成手機版面
        search_taichung(driver)
        for page in range(1, MAX_PAGES + 1):
            count = collect_page(driver, hotels, page)
            print(f"第 {page} 頁：讀到 {count} 間，累計 {len(hotels)} 筆")
            if not go_to_next_page(driver):
                print("已經沒有下一頁，全部結果頁都抓完了。\n")
                break
    except (KeyboardInterrupt, WebDriverException) as error:  # 按 Ctrl+C、逾時或視窗被關掉
        print(f"\n中途停止（{type(error).__name__}），用已抓到的 {len(hotels)} 筆繼續存檔與處理。\n")
    finally:
        driver.quit()
    return list(hotels.values())


# ======================================================================
# 第二部分：資料前處理 —— 移除沒有價格、移除重複、格式轉換（pandas）
# ======================================================================

def to_number(text_series, pattern):
    """用正規表示式從文字裡取出數字（去掉千分位逗號）；取不到的變成空值。
    pattern 可以用 | 寫好幾種寫法，取第一個有對到的。"""
    numbers = text_series.str.extract(pattern).bfill(axis=1)[0].str.replace(",", "")
    return pd.to_numeric(numbers, errors="coerce")


def distance_to_center(area_text):
    """「距市中心1.9公里」→ 1.9；「距市中心700公尺」→ 0.7；「位於市中心」→ 0。"""
    if "位於市中心" in area_text:
        return 0.0
    match = re.search(r"距市中心([\d.]+)\s*(公里|公尺|m)", area_text)
    if not match:
        return None
    value = float(match.group(1))
    return value if match.group(2) == "公里" else value / 1000  # 公尺換算成公里


def preprocess(raw):
    """資料前處理：原始資料（DataFrame）→ 處理後的資料（DataFrame），並印出每一步的結果。"""
    print("========== 資料前處理 ==========")
    print(f"原始資料：{len(raw)} 筆")

    # 1. 移除沒有價格的飯店（已額滿或不開放預訂，價格欄是空的）
    has_price = raw["價格"].str.contains(r"\d")
    data = raw[has_price]
    print(f"1. 移除沒有價格的：{(~has_price).sum()} 筆")

    # 2. 移除重複的飯店（同一間飯店出現在不同頁），用飯店 ID 判斷，只留第一次出現的；
    #    少數卡片沒有飯店 ID 時改用飯店名判斷（跟爬蟲時一樣），不會把所有沒有 ID 的飯店當成同一間
    before = len(data)
    hotel_key = data["飯店ID"].fillna("").astype(str).where(lambda ids: ids.str.strip().ne(""), "名稱:" + data["飯店名"].astype(str))
    data = data[~hotel_key.duplicated(keep="first")]
    print(f"2. 移除重複的：{before - len(data)} 筆")

    # 3. 格式轉換：把文字轉成可以計算的數字（原本的文字欄位換成整理後的欄位）
    # 評價有新舊兩種寫法：「8.5 很讚 14,621 篇評鑑」、「平均很讚8.5分（滿分10分），共6,789則評論」
    grade = data["評價"].str.extract(r"^([\d.]+)\s+(\S+)|平均(\D+?)[\d.]+分")
    clean = pd.DataFrame({
        "飯店ID": data["飯店ID"],
        "飯店名": data["飯店名"],
        "價格(元)": to_number(data["價格"], r"([\d,]+)"),                          # NT$ 1,474 → 1474
        "原價(元)": to_number(data["原價"], r"([\d,]+)").astype("Int64"),          # 原始價格：4,574 → 4574
        "星級": to_number(data["星級"], r"獲得([\d.]+)顆星"),                      # …住宿獲得4顆星 → 4
        "評分": to_number(data["評價"], r"([\d.]+)"),                              # 8.5 很讚… → 8.5
        "評價等級": grade[1].fillna(grade[2]),                                      # 8.5 很讚… → 很讚
        "評論數": to_number(data["評價"], r"([\d,]+)\s*篇|共([\d,]+)則").astype("Int64"),  # 14,621 篇評鑑 → 14621
        "位置得分": to_number(data["位置得分"], r"([\d.]+)"),                      # 8.8 位置得分 → 8.8
        "地區": data["地區"].str.split(",").str[0].str.strip(),                    # 北區, 台中市 - … → 北區
        "距市中心(公里)": pd.to_numeric(data["地區"].apply(distance_to_center)),   # 距市中心1.9公里 → 1.9
        "免費取消": data["標籤"].str.contains("免費取消").map({True: "是", False: "否"}),
        "促銷廣告": data["標籤"].str.contains("促銷廣告").map({True: "是", False: "否"}),
        "網址": data["網址"],
    })
    print("3. 格式轉換：價格、原價、星級、評分、評論數、位置得分、距市中心轉成數字")
    print(f"處理後：{len(clean)} 筆\n")
    return clean.reset_index(drop=True)


# ======================================================================
# 第三部分：延伸分析 —— 各區房價箱型圖、價格與評分散布圖與討論
# ======================================================================

def use_chinese_font():
    """matplotlib 預設字型沒有中文，挑選系統已安裝的中文字型。"""
    candidates = ["Microsoft JhengHei", "PingFang TC", "Heiti TC", "Noto Sans CJK TC", "Arial Unicode MS"]
    installed = {font.name for font in font_manager.fontManager.ttflist}
    plt.rcParams["font.sans-serif"] = [name for name in candidates if name in installed] + ["DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False


def analyze_and_draw(df):
    """平台地區房價使用所有有效價格，相關分析使用價格與評分皆有效的資料。"""
    data = df.copy()
    for col in ("價格(元)", "評分"):
        data[col] = pd.to_numeric(data[col], errors="coerce")
    data.loc[data["價格(元)"] <= 0, "價格(元)"] = float("nan")
    data.loc[~data["評分"].between(0, 10), "評分"] = float("nan")
    priced = data.dropna(subset=["價格(元)"]).copy()
    priced["平台地區"] = priced["地區"].astype("string").str.strip().replace("", pd.NA).fillna("未提供地區")
    valid = priced.dropna(subset=["評分"])
    print(f"\n清理後 {len(data)} 筆；有效價格 {len(priced)} 筆；價格與評分皆有效 {len(valid)} 筆。")
    if priced.empty:
        print("沒有有效價格，略過分析繪圖。")
        return
    stats = priced.groupby("平台地區")["價格(元)"].agg(樣本數="count", 中位數="median", 平均價="mean", 最低價="min", 最高價="max").sort_values("中位數", ascending=False)
    print("平台地區房價統計（平台分類含行政區、商圈與景點，並非統一行政區）：")
    print(stats.round(2).to_string())
    top = stats.loc[stats["樣本數"].ge(4)].head(3)
    print("至少 4 筆的平台地區中，中位數最高者：")
    print(top[["樣本數", "中位數"]].to_string())
    print("小樣本地區估計較不穩定；各區價格比較保留無評分但有價格的住宿。")
    corr = valid["價格(元)"].corr(valid["評分"]) if len(valid) >= 2 else float("nan")
    if not valid.empty:
        p_med = valid["價格(元)"].median()
        s_med = valid["評分"].median()
        threshold = valid["價格(元)"].quantile(.75)
        high = valid[valid["價格(元)"].ge(threshold)]
        budget = valid[valid["價格(元)"].le(p_med) & valid["評分"].ge(s_med)]
        print(f"價格與評分 Pearson r={corr:.3f}（以 {len(valid)} 筆完整資料計算；不足變異時無法計算）。")
        print(f"高價組定義為價格 >= 第三四分位數 {threshold:,.1f} 元，共 {len(high)} 筆（同價可能超過 25%）。")
        print(f"高價組平均評分 {high['評分'].mean():.2f}；全體完整樣本平均 {valid['評分'].mean():.2f}。")
        print(f"高價組評分低於 8.5 分：{high['評分'].lt(8.5).sum()} 筆。")
        print(f"價格 <= 中位數 {p_med:,.0f} 元且評分 >= 中位數 {s_med:.1f} 分：{len(budget)} 筆。")
    print("以上僅描述本次查詢樣本；相關不代表因果，未檢定統計顯著性，亦無法證明硬體、品牌或服務造成價格差異。")
    print("房價為每晚未稅報價；住宿類型、房型及評論數不同，限制了直接比較的解讀。")
    use_chinese_font()
    fig, (ax_box, ax_scatter) = plt.subplots(1, 2, figsize=(17, 7), layout="constrained")
    counts = priced["平台地區"].value_counts()
    major = counts[counts.ge(4)].index
    priced["繪圖地區"] = priced["平台地區"].where(priced["平台地區"].isin(major), "其他地區（各少於4筆）")
    order = priced.groupby("繪圖地區")["價格(元)"].median().sort_values(ascending=False).index.tolist()
    values = [priced.loc[priced["繪圖地區"].eq(a), "價格(元)"] for a in order]
    ax_box.boxplot(values, patch_artist=True, showmeans=True, medianprops={"color": "#C8102E"})
    ax_box.set_xticks(range(1,len(order)+1), labels=[f"{a}\n(n={len(v)})" for a,v in zip(order,values)], rotation=60, ha="right", fontsize=8)
    ax_box.set_yscale("log")
    ax_box.set(title=f"平台各地區房價（有效 {len(priced)} 筆；三角為平均數）", ylabel="每晚未稅價格（新台幣元，對數刻度）")
    if not valid.empty:
        ax_scatter.scatter(valid["價格(元)"], valid["評分"], color="#1D428A", alpha=.55, edgecolors="white", s=40)
        ax_scatter.set_xscale("log")
        ax_scatter.axvline(p_med, color="gray", linestyle="--", label=f"價格中位數 {p_med:,.0f} 元")
        ax_scatter.axhline(s_med, color="#C8102E", linestyle="--", label=f"評分中位數 {s_med:.1f}")
        ax_scatter.set_ylim(0, 10.3)
        ax_scatter.legend(fontsize=8, loc="lower left")
    else:
        ax_scatter.text(.5, .5, "沒有同時具有效價格與評分的資料", transform=ax_scatter.transAxes, ha="center")
    ax_scatter.set(title=f"價格與評分（完整 {len(valid)} 筆；原始價格 Pearson r={corr:.3f}）", xlabel="每晚未稅價格（新台幣元，對數刻度）", ylabel="評分（滿分10分）")
    from matplotlib.ticker import FuncFormatter
    for axis in (ax_box.yaxis, ax_scatter.xaxis):
        axis.set_major_formatter(FuncFormatter(lambda x, pos: f"{x:,.0f}"))
    for ax in (ax_box, ax_scatter):
        ax.grid(alpha=.25)
    fig.savefig(CHART_OUTPUT, dpi=150)
    plt.close(fig)
    print(f"已產生 {CHART_OUTPUT.name}（保留全部有效價格，未裁切高價點）。")


def main():
    # 第一部分：爬蟲，存成沒有資料處理的原始資料
    rows = scrape_all_pages()
    if not rows:
        raise SystemExit("沒有抓到任何飯店，請稍後再執行。")
    raw = pd.DataFrame(rows)
    raw.to_csv(RAW_OUTPUT, index=False, encoding="utf-8-sig")  # utf-8-sig：Excel 開啟中文不會亂碼
    print(f"沒有資料處理：{len(raw)} 筆，已存成 {RAW_OUTPUT.name}")
    print(raw[["頁數", "飯店名", "價格", "評價"]].head(5).to_string(index=False), "\n")

    # 第二部分：資料前處理，存成有資料處理的版本
    data = preprocess(raw)
    data.to_csv(PROCESSED_OUTPUT, index=False, encoding="utf-8-sig")
    print(f"有資料處理：{len(data)} 筆，已存成 {PROCESSED_OUTPUT.name}")
    print(data[["飯店名", "價格(元)", "評分", "評論數", "地區"]].head(5).to_string(index=False), "\n")

    # 第三部分：延伸分析圖表與討論
    analyze_and_draw(data)


if __name__ == "__main__":
    if "--analyze-only" in sys.argv:
        if not PROCESSED_OUTPUT.exists():
            raise SystemExit(f"找不到 {PROCESSED_OUTPUT.name}，請先執行爬蟲取得資料。")
        clean_data = pd.read_csv(PROCESSED_OUTPUT)
        analyze_and_draw(clean_data)
    else:
        main()
