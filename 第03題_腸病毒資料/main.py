"""
第 3 題（中）：抓取政府資料開放平臺的「健保門診及住院就診人次統計－腸病毒」
================================================
題目要求
    1. 從政府資料開放平臺 https://data.gov.tw/ 抓取「健保門診及住院就診人次統計-腸病毒」
    2. 將資料存到本地 NHI_EnteroviralInfection.csv
    （課堂補充：不能自己用滑鼠點網頁找到資料就說抓到了，要用程式模擬這些操作）

做法（Selenium 模擬操作 + requests 下載）
    照題目附圖的步驟，由 Selenium 模擬人在網站上的操作：
    1. 開啟 https://data.gov.tw/，在首頁搜尋框輸入「腸病毒」，按搜尋按鈕。
       （用完整名稱搜尋時，平臺會把「腹瀉、水痘…」等同系列資料集排在前面，
         用「腸病毒」搜尋，目標資料集就會出現在第一頁。）
    2. 在搜尋結果中找到「健保門診及住院就診人次統計-腸病毒」並點進去（會開在新分頁，切換過去）。
    3. 在資料集頁面的「資料資源下載網址」找到 CSV 按鈕，讀出它的連結（資料下載網址）。
    4. 用 requests 下載這個 CSV，存成 NHI_EnteroviralInfection.csv（重新執行會直接覆蓋）。

    放慢操作讓人看清楚：每一步要操作的元素（搜尋框、搜尋按鈕、資料集連結、CSV 按鈕）
    都會先捲到畫面中間，終端機印出「步驟 n」說明，停 STEP_PAUSE 秒（預設 2 秒）再動作，
    看得出程式在瀏覽器裡一步一步操作。想跑快一點可以把 STEP_PAUSE 改成 0。

    注意：資料下載網址在疾管署網站（od.cdc.gov.tw），它的 HTTPS 憑證鏈不完整，
    Python 內建的憑證清單會驗證失敗。程式用 truststore 套件改用作業系統（Windows／macOS）
    的憑證庫驗證；如果還是驗證失敗，最後才改用不驗證憑證的方式下載，並印出提示。

延伸：哪些年齡最常得腸病毒、各縣市的就診人次地圖
    下載的資料是每週、每個縣市、每個年齡層的「腸病毒健保就診人次」（門診＋住院）。
    用 pandas 把整份資料（2016 年到最新一週）加總，畫成一張圖 enterovirus_charts.png：
      左：各年齡層的就診人次長條圖——0～12 歲占九成，3～6 歲（學齡前）最多；
      右：台灣地圖，各縣市的累計就診人次分 5 級上色（由黃到紅，越紅人次越多）。
    注意是「就診人次」不是「人數」：同一個人看兩次診會算兩次。
    地圖的縣市邊界是同資料夾的 taiwan_counties.geojson，由內政部國土測繪中心
    「直轄市、縣市界線(TWD97經緯度)」（https://data.gov.tw/dataset/7442）經
    taiwan-atlas 專案（MIT 授權）簡化而來；用 json 讀進來、matplotlib 畫多邊形，
    不需要另外安裝地圖套件。地圖旁邊列出 22 個縣市的排名與人次；澎湖、金門、連江三個離島
    另外放大畫在左下角的框裡（金門的框只畫大、小金門，遠在東北方的烏坵不畫）。

輸出
    NHI_EnteroviralInfection.csv（約 8 MB，與本程式同一個資料夾，重新執行會直接覆蓋）
    enterovirus_charts.png（延伸：年齡別長條圖＋縣市地圖）

執行
    python 第03題_腸病毒資料/main.py
"""

import csv
import io
import json
import math
import time
from pathlib import Path

try:
    import truststore
    truststore.inject_into_ssl()  # 改用作業系統憑證庫驗證 HTTPS（必須在 import requests 之前）
except ImportError:
    pass

import requests  # noqa: E402  （故意放在 truststore 設定之後）
from selenium import webdriver  # noqa: E402
from selenium.webdriver.common.by import By  # noqa: E402
from selenium.webdriver.support import expected_conditions as EC  # noqa: E402
from selenium.webdriver.support.ui import WebDriverWait  # noqa: E402

import matplotlib  # noqa: E402
import pandas as pd  # noqa: E402

matplotlib.use("Agg")  # 只存圖檔、不開視窗
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402
from matplotlib.patches import Polygon  # noqa: E402

HOME_URL = "https://data.gov.tw/"
KEYWORD = "腸病毒"
DATASET_NAME = "健保門診及住院就診人次統計-腸病毒"
OUTPUT = Path(__file__).parent / "NHI_EnteroviralInfection.csv"
STEP_PAUSE = 2  # 每一步停幾秒，讓人看清楚瀏覽器在做什麼（改成 0 就不停）

# 延伸
CHART_OUTPUT = Path(__file__).parent / "enterovirus_charts.png"
MAP_FILE = Path(__file__).parent / "taiwan_counties.geojson"  # 縣市邊界
AGE_ORDER = ["0~2", "3~6", "7~12", "13~15", "16~18", "19~24", "25~64", "65+"]
# 離島另外放大畫在地圖左下角的框裡：
#   範圍＝框裡要顯示的經緯度（西、東、南、北）；位置＝框在地圖上的左、下、寬、高（占整張地圖的比例）
#   澎湖是直長的，放左邊的高框；金門、連江偏寬，疊在右邊
ISLAND_VIEWS = {
    "澎湖縣": ((119.29, 119.72, 23.16, 23.80), (0.0, 0.02, 0.18, 0.40)),
    "金門縣": ((118.13, 118.50, 24.36, 24.55), (0.19, 0.27, 0.23, 0.15)),  # 烏坵在東北方很遠，只畫大、小金門
    "連江縣": ((119.88, 120.54, 25.92, 26.41), (0.19, 0.02, 0.23, 0.21)),
}
# 依就診人次分 5 級上色：（下限（萬）, 圖例文字, 顏色）。由黃到紅，最淺的一級也看得出來
COLOR_CLASSES = [
    (40, "40 萬以上", "#7F0000"),  # 深紅
    (20, "20～40 萬", "#D7191C"),  # 紅
    (10, "10～20 萬", "#F37021"),  # 橘
    (5, "5～10 萬", "#FBB040"),    # 琥珀
    (0, "5 萬以下", "#FFE066"),    # 黃
]


def show_step(driver, element, message):
    """把要操作的元素捲到畫面中間，印出步驟說明，再停 STEP_PAUSE 秒。"""
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
    print(message)
    time.sleep(STEP_PAUSE)


def find_csv_url():
    """用 Selenium 模擬：搜尋 → 點進資料集 → 讀出 CSV 的資料下載網址。"""
    driver = webdriver.Chrome()
    driver.set_window_size(1366, 900)  # 視窗太小時，上方固定的搜尋列會擋住搜尋結果
    wait = WebDriverWait(driver, 30)
    try:
        # 1. 首頁搜尋框輸入關鍵字，按搜尋按鈕
        driver.get(HOME_URL)
        search_box = wait.until(EC.element_to_be_clickable((By.ID, "searchbar-input")))
        show_step(driver, search_box, f"步驟 1：開啟 {HOME_URL}，找到首頁的搜尋框")
        search_box.send_keys(KEYWORD)
        print(f"        在搜尋框輸入「{KEYWORD}」")
        time.sleep(STEP_PAUSE)
        search_button = driver.find_element(By.CSS_SELECTOR, "button.searchbar-submit-btn")
        show_step(driver, search_button, "步驟 2：按下搜尋按鈕")
        search_button.click()

        # 2. 等搜尋結果載入完成（轉圈圈的遮罩消失），點資料集名稱；
        #    連結會開新分頁，所以要切換到新分頁
        dataset_link = wait.until(
            EC.element_to_be_clickable((By.XPATH, f"//a[normalize-space()='{DATASET_NAME}']"))
        )
        wait.until(EC.invisibility_of_element_located((By.CSS_SELECTOR, ".el-loading-mask")))
        show_step(driver, dataset_link, f"步驟 3：在搜尋結果中找到「{DATASET_NAME}」，點進去")
        dataset_link.click()
        wait.until(lambda d: len(d.window_handles) > 1)
        driver.switch_to.window(driver.window_handles[-1])
        print(f"        已進入資料集頁面：{driver.title}（{driver.current_url}）")

        # 3. 「資料資源下載網址」裡的 CSV 按鈕（title="CSV下載檔案"），它的 href 就是資料下載網址
        csv_button = wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "a[title='CSV下載檔案']"))
        )
        show_step(driver, csv_button, "步驟 4：在「資料資源下載網址」找到 CSV 按鈕，讀出它的下載網址")
        return csv_button.get_attribute("href")
    finally:
        driver.quit()


def download_csv(url):
    """用 requests 下載 CSV，回傳文字內容。"""
    try:
        response = requests.get(url, timeout=120)
    except requests.exceptions.SSLError:
        print("（HTTPS 憑證驗證失敗，改用不驗證憑證的方式下載）")
        response = requests.get(url, timeout=120, verify=False)
    response.raise_for_status()
    return response.content.decode("utf-8-sig")  # 官方檔案是 UTF-8


def main():
    csv_url = find_csv_url()
    print(f"        CSV 資料下載網址：{csv_url}")

    print("步驟 5：用 requests 下載 CSV（約 8 MB）…")
    text = download_csv(csv_url)

    # 以 utf-8-sig（加 BOM）存檔，用 Excel 開啟中文不會亂碼
    with open(OUTPUT, "w", newline="", encoding="utf-8-sig") as file:
        file.write(text)

    # 讀回來確認是正常的 CSV，並顯示欄位與前 5 筆
    rows = list(csv.reader(io.StringIO(text)))
    print(f"欄位：{rows[0]}")
    for row in rows[1:6]:
        print(row)
    print(f"\n共 {len(rows) - 1} 筆資料，已存成 {OUTPUT.name}")

    # 延伸：年齡別長條圖＋縣市地圖
    data = pd.read_csv(OUTPUT)
    period = f"{data['年'].min()}～{data['年'].max()} 年"
    by_age = data.groupby("年齡別")["腸病毒健保就診人次"].sum().reindex(AGE_ORDER)
    by_county = data.groupby("縣市")["腸病毒健保就診人次"].sum().sort_values(ascending=False)
    print_summary(period, by_age, by_county)
    draw_charts(period, by_age, by_county)
    print(f"已存成 {CHART_OUTPUT.name}")


def print_summary(period, by_age, by_county):
    """延伸：印出各年齡層占比與就診人次最多的 5 個縣市。"""
    share = by_age / by_age.sum() * 100
    print(f"\n延伸：{period}腸病毒健保就診人次（門診＋住院）")
    print("  各年齡層占比：" + "、".join(f"{age} 歲 {value:.1f}%" for age, value in share.items()))
    print(f"  0～12 歲合計占 {share[['0~2', '3~6', '7~12']].sum():.1f}%")
    print("  就診人次最多的 5 個縣市：" + "、".join(f"{name} {count:,}" for name, count in by_county.head(5).items()))


def use_chinese_font():
    """matplotlib 預設字型沒有中文，從電腦上已有的中文字型挑一個（Windows／macOS 都適用）。"""
    candidates = ["Microsoft JhengHei", "PingFang TC", "Heiti TC", "Noto Sans CJK TC", "Arial Unicode MS"]
    installed = {font.name for font in font_manager.fontManager.ttflist}
    plt.rcParams["font.sans-serif"] = [name for name in candidates if name in installed] + ["DejaVu Sans"]


def ring_area(points):
    """多邊形面積（鞋帶公式），用來決定畫圖順序。"""
    return abs(sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(points, points[1:] + points[:1]))) / 2


def county_color(count):
    """依就診人次找出所屬的級距顏色。"""
    for low, _, color in COLOR_CLASSES:
        if count / 10_000 >= low:
            return color


def draw_shapes(ax, shapes, by_county):
    """把縣市的多邊形畫在 ax 上，依人次分級上色。
    面積大的先畫、小的後畫：嘉義市、新竹市在嘉義縣、新竹縣的洞裡，才不會被蓋住。"""
    for name, outline in sorted(shapes, key=lambda shape: ring_area(shape[1]), reverse=True):
        ax.add_patch(Polygon(outline, closed=True, facecolor=county_color(by_county.get(name, 0)),
                             edgecolor="#666666", linewidth=0.4))


def draw_charts(period, by_age, by_county):
    """延伸：左邊畫年齡別長條圖，右邊畫各縣市就診人次的台灣地圖。"""
    use_chinese_font()
    fig, (left, right) = plt.subplots(1, 2, figsize=(14, 8), gridspec_kw={"width_ratios": [1, 1.1]})

    # 左：年齡別長條圖（單位：萬人次），長條上標出占比
    share = by_age / by_age.sum() * 100
    bars = left.bar(by_age.index, by_age / 10_000, color="#2E86AB")
    for bar, value in zip(bars, share):
        left.text(bar.get_x() + bar.get_width() / 2, bar.get_height(), f"{value:.1f}%", ha="center", va="bottom")
    left.set_title(f"各年齡層的腸病毒就診人次（{period}）")
    left.set_xlabel("年齡（歲）")
    left.set_ylabel("就診人次（萬）")

    # 右：台灣地圖。每個縣市是一個或多個多邊形（GeoJSON 的 MultiPolygon），依人次分級上色
    counties = json.loads(MAP_FILE.read_text(encoding="utf-8"))["features"]
    shapes = []
    for county in counties:
        name = county["properties"]["COUNTYNAME"]
        for polygon in county["geometry"]["coordinates"]:
            shapes.append((name, polygon[0]))  # polygon[0] 是外框，後面的是內部的洞
    draw_shapes(right, [shape for shape in shapes if shape[0] not in ISLAND_VIEWS], by_county)  # 本島

    right.set_xlim(118.4, 122.1)  # 左邊的海面留給排名和離島
    right.set_ylim(21.85, 25.4)
    right.set_aspect(1 / math.cos(math.radians(23.7)))  # 經緯度換成實際比例，台灣才不會變胖
    right.axis("off")

    # 左上：22 個縣市的排名與人次（萬），顏色之外也看得到確切數字
    lines = [f"{rank:>2}. {name} {count / 10_000:.1f} 萬"
             for rank, (name, count) in enumerate(by_county.items(), start=1)]
    right.text(118.45, 25.35, "\n".join(lines), fontsize=8, va="top", linespacing=1.25)

    # 左下：離島各畫在一個框裡
    right.text(0.0, 0.445, "離島", transform=right.transAxes, fontsize=11)
    for name, ((west, east, south, north), position) in ISLAND_VIEWS.items():
        box = right.inset_axes(position)
        draw_shapes(box, [shape for shape in shapes if shape[0] == name], by_county)
        box.set_xlim(west, east)
        box.set_ylim(south, north)
        box.set_aspect(1 / math.cos(math.radians((south + north) / 2)))  # 框縮成島的比例，島才不會變形
        box.set_xticks([])
        box.set_yticks([])
        box.set_title(f"{name} {by_county.get(name, 0) / 10_000:.1f} 萬", fontsize=8)

    # 圖例：5 個級距的顏色
    handles = [matplotlib.patches.Patch(facecolor=color, edgecolor="#666666", label=label)
               for _, label, color in COLOR_CLASSES]
    right.legend(handles=handles, title="就診人次", loc="center left", bbox_to_anchor=(1.0, 0.5), frameon=False)
    right.set_title(f"各縣市腸病毒就診人次（{period}累計）")

    fig.tight_layout()
    fig.savefig(CHART_OUTPUT, dpi=150)
    plt.close(fig)


if __name__ == "__main__":
    main()
