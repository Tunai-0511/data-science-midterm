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
       評價「平均很讚8.5分（滿分10分），共6,789則評論」→ 評分 8.5、評價等級「很讚」、評論數 6789。
    9. 存成 agoda_result_processed.csv，並印出每一步移除了幾筆。

輸出（與本程式同一個資料夾，重新執行會直接覆蓋）
    agoda_result.csv            沒有資料處理（網頁原始文字，比題目要求多了頁數、飯店 ID 等 10 個欄位）
    agoda_result_processed.csv  有資料處理（移除沒有價格、移除重複、格式轉換）

    價格說明：Agoda 顯示的是「每晚價格（不含稅及其他費用）」，日期與房價會隨查詢當天變動。
    執行時間：每頁約 40 秒，全部約 3～4 分鐘。中途出錯或按 Ctrl+C，已抓到的資料照樣存檔處理。

執行
    python 第16題_Agoda台中飯店/main.py
"""

import re
import time
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlsplit

import pandas as pd
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

URL = "https://www.agoda.com/zh-tw/"
KEYWORD = "台中"
FOLDER = Path(__file__).parent
RAW_OUTPUT = FOLDER / "agoda_result.csv"                 # 沒有資料處理
PROCESSED_OUTPUT = FOLDER / "agoda_result_processed.csv"  # 有資料處理（前處理）
MAX_PAGES = 20  # 安全上限，避免無限翻頁
HOTEL_NAME = "[data-selenium='hotel-name']"
NEXT_BUTTON = "[data-selenium='pagination-next-btn']"


# ======================================================================
# 第一部分：爬蟲 —— 抓下網頁上的原始資料（沒有資料處理）
# ======================================================================

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

    # 3. 按「搜出好價」，結果會開在新分頁
    tabs_before = len(driver.window_handles)
    search_button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button[data-element-name='search-button']")))
    search_button.click()
    wait.until(lambda d: len(d.window_handles) > tabs_before)
    driver.switch_to.window(driver.window_handles[-1])  # 切換到新分頁
    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, HOTEL_NAME)))


def text_of(card, selector):
    """卡片裡某個欄位的文字；這間飯店沒有這個欄位就回傳空字串。"""
    node = card.select_one(selector)
    return node.get_text(" ", strip=True) if node else ""


def first_text_of(card, selector):
    """欄位裡的第一段文字，例如評價欄的「平均很讚8.5分（滿分10分），共6,789則評論」。"""
    node = card.select_one(selector)
    return next((s.strip() for s in node.find_all(string=True) if s.strip()), "") if node else ""


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
        "評價": first_text_of(card, "[data-element-name='property-card-review']"),
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
    driver.set_window_size(1366, 900)  # 視窗太小時 Agoda 會改成手機版面
    hotels = {}  # (頁數, 飯店 ID) → 原始資料
    try:
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
    """用正規表示式從文字裡取出數字（去掉千分位逗號）；取不到的變成空值。"""
    numbers = text_series.str.extract(pattern)[0].str.replace(",", "")
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

    # 2. 移除重複的飯店（同一間飯店出現在不同頁），用飯店 ID 判斷，只留第一次出現的
    before = len(data)
    data = data.drop_duplicates(subset="飯店ID", keep="first")
    print(f"2. 移除重複的：{before - len(data)} 筆")

    # 3. 格式轉換：把文字轉成可以計算的數字（原本的文字欄位換成整理後的欄位）
    clean = pd.DataFrame({
        "飯店ID": data["飯店ID"],
        "飯店名": data["飯店名"],
        "價格(元)": to_number(data["價格"], r"([\d,]+)"),                          # NT$ 1,474 → 1474
        "原價(元)": to_number(data["原價"], r"([\d,]+)").astype("Int64"),          # 原始價格：4,574 → 4574
        "星級": to_number(data["星級"], r"獲得([\d.]+)顆星"),                      # …住宿獲得4顆星 → 4
        "評分": to_number(data["評價"], r"([\d.]+)分"),                            # 平均很讚8.5分… → 8.5
        "評價等級": data["評價"].str.extract(r"平均(\D+?)[\d.]+分")[0],            # 平均很讚8.5分 → 很讚
        "評論數": to_number(data["評價"], r"共([\d,]+)則").astype("Int64"),        # 共6,789則評論 → 6789
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
    print(data[["飯店名", "價格(元)", "評分", "評論數", "地區"]].head(5).to_string(index=False))


if __name__ == "__main__":
    main()
