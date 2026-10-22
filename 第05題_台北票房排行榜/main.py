"""
第 5 題（難）：開眼電影網「台北週末票房排行榜」
================================================
題目要求
    抓 http://www.atmovies.com.tw/movie/new/ 裡的電影
    1. 按「票房排行榜」
    2. 列出台北排行榜的排名、片名及票房
    3. 按下 more 後，將本頁排行（20 筆）存入 Taipei_movies.csv，
       內容包括排名、片名、本週票房及累計票房
    （課堂補充：要模擬滑鼠移動及點選動作，再抓取資料）

做法（Selenium：ActionChains 模擬滑鼠）
    1. 開啟題目網址（本週新片頁）。
    2. 滑鼠移到上方選單的「電影」，下拉選單展開後，移到「票房排行榜」並點下去。
    3. 在票房排行榜頁讀出「台北週末票房排行榜」前 5 名的排名、片名、本週票房並印出。
    4. 滑鼠移到台北排行榜下方的「more」並點下去，進入完整的台北週末票房排行。
    5. 每部電影在網頁上占兩列：第一列是「排名、片名」，第二列是「百分比、本週票房、
       累計票房…」，把 20 部電影整理成一筆一筆存成 Taipei_movies.csv。

    網站上的兩個干擾，程式都有處理：
    - 點連結時有時會跳出 Google 全版廣告（網址後面多了 #google_vignette），
      這時像真人一樣按廣告右上角的「關閉」，網頁就會繼續前往剛剛點的連結。
    - 票房網站（app2.atmovies.com.tw）偶爾連線逾時，等不到內容就重新整理再試。

輸出
    Taipei_movies.csv        題目要求：排名、片名、本週票房（萬）、累計票房（萬）（網站的票房單位是萬元）
    Taipei_movies_detail.csv 延伸：數值票房、占比與累積占比
    boxoffice_charts.png     延伸：前 10 名橫條圖、累積占比圖

延伸：票房集中程度
    去除 $ 與千分位逗號，轉換為萬元；揭露無效本週票房並排除於占比。
    依本週票房排序，以未四捨五入的數值計算占比與累積占比。
    繪製前 10 名橫條圖與榜內累積曲線，80% 僅為參考線。
    動態計算前約 20% 片數占比；僅描述本次榜單，不直接宣稱二八法則或推論市場成因。

執行
    python 第05題_台北票房排行榜/main.py
    python 第05題_台北票房排行榜/main.py --analyze-only  # 直接以既有 CSV 產生圖表與分析討論
"""

import csv
import sys
import time
from pathlib import Path

import matplotlib
import pandas as pd
from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

matplotlib.use("Agg")  # 只存圖檔、不開視窗
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402

URL = "https://www.atmovies.com.tw/movie/new/"
OUTPUT = Path(__file__).parent / "Taipei_movies.csv"
DETAIL_OUTPUT = Path(__file__).parent / "Taipei_movies_detail.csv"
CHART_OUTPUT = Path(__file__).parent / "boxoffice_charts.png"
FIELDS = ["排名", "片名", "本週票房（萬）", "累計票房（萬）"]  # 網站的票房單位是萬元

TAIPEI_TITLE = "//h3[contains(., '台北週末票房排行榜')]"  # 台北排行榜的標題（XPath）


def open_chrome():
    options = webdriver.ChromeOptions()
    options.add_argument("--window-size=1280,900")
    # 網頁上的廣告會一直載入；主要內容出現就先操作，不必等全部廣告載完
    options.page_load_strategy = "eager"
    driver = webdriver.Chrome(options=options)
    driver.set_page_load_timeout(60)
    return driver


def close_vignette_ad(driver):
    """關閉 Google 全版廣告：廣告在 iframe 裡，切進去按「關閉」（#dismiss-button）。有按到回傳 True。"""
    for _ in range(10):  # 廣告可能還在載入，最多試 10 次
        for frame in driver.find_elements(By.CSS_SELECTOR, "iframe[id^='aswift']"):
            try:
                if not frame.is_displayed():
                    continue
                driver.switch_to.frame(frame)
                buttons = driver.find_elements(By.ID, "dismiss-button")
                if buttons and buttons[0].is_displayed():
                    buttons[0].click()
                    return True
            except WebDriverException:
                pass  # 廣告框架剛好被換掉，換下一個再試
            finally:
                driver.switch_to.default_content()  # 一定要切回主網頁
        time.sleep(0.5)
    return False


def mouse_click(driver, find_element, url_part, tries=3):
    """模擬滑鼠：移到元素上再點下去，並確認網址換到 url_part 那一頁。
    find_element 是「找出要點的元素」的函式。點下去 20 秒還沒換頁（例如剛好沒點到、網站沒反應），
    就重新找一次元素再點（最多 tries 次）。"""
    for attempt in range(1, tries + 1):
        element = find_element()
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
        ActionChains(driver).move_to_element(element).pause(0.5).click().perform()
        try:
            # 點下去後，不是換到目標頁，就是被 Google 全版廣告擋住
            WebDriverWait(driver, 20).until(
                lambda d: url_part in d.current_url or "google_vignette" in d.current_url
            )
            break
        except TimeoutException:
            if attempt == tries:
                raise SystemExit(f"點了 {tries} 次都沒有換頁（網站可能暫時連不上），請稍後再執行一次。")
            print("（點下去沒有換頁，再點一次）")

    if "google_vignette" in driver.current_url:
        print("（跳出 Google 全版廣告，按「關閉」後繼續）")
        if not close_vignette_ad(driver):  # 找不到關閉按鈕：直接打開廣告後面的目標網址
            print("（找不到廣告的「關閉」按鈕，直接打開目標網址）")
            driver.get(driver.current_url.split("#google_vignette")[0])
        try:
            WebDriverWait(driver, 30).until(lambda d: url_part in d.current_url and "google_vignette" not in d.current_url)
        except TimeoutException:
            raise SystemExit("關掉廣告後沒有換到目標頁（網站可能暫時連不上），請稍後再執行一次。")


def hover_movie_menu(driver, tries=3):
    """滑鼠移到上方選單的「電影」，等下拉選單裡的「票房排行榜」出現並回傳。
    網頁剛載入時選單偶爾沒展開，這時把滑鼠移開再移回來重試（最多 tries 次）。"""
    for _ in range(tries):
        movie_menu = WebDriverWait(driver, 30).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, "#dropdownMenu .menuTitle.arrow"))
        )
        ActionChains(driver).move_to_element(movie_menu).perform()  # 滑鼠移入 → 展開下拉選單
        try:
            return WebDriverWait(driver, 5).until(
                EC.visibility_of_element_located((By.LINK_TEXT, "票房排行榜"))
            )
        except TimeoutException:
            ActionChains(driver).move_by_offset(0, 300).perform()  # 選單沒展開：滑鼠先移開
    raise SystemExit("滑鼠移到「電影」選單後，下拉選單一直沒有展開，請再執行一次。")


def wait_for(driver, xpath, tries=3):
    """等待元素出現；票房網站偶爾連線逾時，逾時就重新整理再試（最多 tries 次）。"""
    for attempt in range(1, tries + 1):
        try:
            return WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.XPATH, xpath))
            )
        except TimeoutException:
            if attempt == tries:
                raise
            print("網頁載入逾時，重新整理再試一次…")
            driver.refresh()


def read_top5(driver):
    """讀出票房排行榜頁面上「台北週末票房排行榜」的前 5 名（排名、片名、本週票房）。"""
    rows = driver.find_elements(By.XPATH, TAIPEI_TITLE + "/following::table[1]//tr[td/b]")
    top5 = []
    for row in rows:
        cells = row.find_elements(By.TAG_NAME, "td")
        top5.append({"排名": cells[0].text, "片名": cells[1].text, "本週票房": cells[2].text})
    return top5


def read_full_ranking(driver):
    """讀出 more 頁面的完整台北週末票房排行（每部電影占兩列）。"""
    movies = []
    # 第一列：有 <td class="at11"> 的那一列，內容是排名與片名
    for title_row in driver.find_elements(By.XPATH, "//td[contains(@class, 'at11')]/.."):
        rank = title_row.find_element(By.TAG_NAME, "b").text
        title = title_row.find_element(By.CSS_SELECTOR, "td.at11 a").text
        # 第二列：緊接在後面的那一列，依序是 空白、百分比、本週票房、累計票房、上週、週數
        stats = title_row.find_element(By.XPATH, "following-sibling::tr[1]")
        cells = stats.find_elements(By.TAG_NAME, "td")
        movies.append({
            "排名": rank,
            "片名": title,
            "本週票房（萬）": cells[2].text,
            "累計票房（萬）": cells[3].text,
        })
    return movies


def save_csv(rows, path):
    with open(path, "w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def use_chinese_font():
    """matplotlib 預設字型沒有中文，挑選系統已安裝的中文字型。"""
    candidates = ["Microsoft JhengHei", "PingFang TC", "Heiti TC", "Noto Sans CJK TC", "Arial Unicode MS"]
    installed = {font.name for font in font_manager.fontManager.ttflist}
    plt.rcParams["font.sans-serif"] = [name for name in candidates if name in installed] + ["DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False


def short_title(title, limit=20):
    """圖表用的片名：去掉後面的英文原名（「快打旋風 Street Fighter」→「快打旋風」），太長再截短。"""
    text = str(title).strip()
    cjk = [i for i, ch in enumerate(text) if ord(ch) > 0x2E80]  # 最後一個中文字（含「」）的位置
    if cjk:
        text = text[:cjk[-1] + 1]
    return text if len(text) <= limit else text[:limit - 1] + "…"


def analyze_and_draw(df=None):
    """由未四捨五入的票房計算榜內占比，展示集中程度。"""
    if df is None:
        if not OUTPUT.exists():
            print(f"找不到 {OUTPUT.name}，無法進行分析。")
            return
        df = pd.read_csv(OUTPUT)
    clean = df.copy()
    for name in ("本週票房", "累計票房"):
        source = name + "（萬）" if name + "（萬）" in clean.columns else name  # 舊版 CSV 的欄名沒有「（萬）」
        clean[name + "(萬)"] = pd.to_numeric(
            clean[source].astype("string").str.replace(r"[$,]", "", regex=True), errors="coerce"
        )
        clean = clean.drop(columns=source)  # 延伸 CSV 只留轉好的數字，不跟原本「$220」這種文字重複
    valid = clean["本週票房(萬)"].notna() & clean["本週票房(萬)"].ge(0)
    print(f"票房有效 {valid.sum()}／{len(clean)} 筆；無效本週票房 {len(clean)-valid.sum()} 筆（不納入占比）。")
    clean = clean.loc[valid].sort_values("本週票房(萬)", ascending=False, kind="stable").reset_index(drop=True)
    total = clean["本週票房(萬)"].sum()
    if clean.empty or total <= 0:
        print("沒有可分析的正票房總額，略過繪圖。")
        return
    clean["本週票房佔比(%)"] = clean["本週票房(萬)"] / total * 100
    clean["累積票房佔比(%)"] = clean["本週票房(萬)"].cumsum() / total * 100
    clean.to_csv(DETAIL_OUTPUT, index=False, encoding="utf-8-sig")
    print(f"\n榜內有效 {len(clean)} 部電影，本週票房合計 {total:,.2f} 萬元。")
    for n in (3, 5, 10):
        k = min(n, len(clean))
        print(f"前 {k} 名占榜內 {clean['本週票房(萬)'].head(k).sum()/total*100:.1f}%。")
    top_fifth = max(1, (len(clean) + 4) // 5)
    share = clean["本週票房(萬)"].head(top_fifth).sum() / total * 100
    print(f"前約 20% 片數（{top_fifth} 部）占榜內 {share:.1f}%；應依此描述集中程度，不能直接宣稱符合二八法則。")
    print("範圍僅限本次榜單；未蒐集全市場票房、排片或行銷資料，無法推論全市場占比與成因。")
    use_chinese_font()
    fig, (ax_bar, ax_cum) = plt.subplots(1, 2, figsize=(16, 6), layout="constrained")
    top = clean.head(10)
    labels = [short_title(t) for t in top["片名"]]
    bars = ax_bar.barh(range(len(top)), top["本週票房(萬)"], color="#1D428A")
    ax_bar.set_yticks(range(len(top)), labels=labels, fontsize=9)
    ax_bar.invert_yaxis()
    ax_bar.set_xlim(0, top["本週票房(萬)"].max()*1.4)
    for bar, (_, row) in zip(bars, top.iterrows()):
        ax_bar.text(bar.get_width()+total*.002, bar.get_y()+bar.get_height()/2,
                    f"{row['本週票房(萬)']:g} 萬（{row['本週票房佔比(%)']:.1f}%）", va="center", fontsize=8)
    ax_bar.set(title=f"本週票房前 {len(top)} 名（占比以本次榜單為分母）", xlabel="本週票房（萬元新台幣）")
    ranks = list(range(1, len(clean)+1))
    ax_cum.plot([0]+ranks, [0]+clean["累積票房佔比(%)"].tolist(), marker="o", color="#C8102E")
    ax_cum.axhline(80, color="gray", linestyle="--", label="80% 參考線")
    ax_cum.set(title=f"榜內 {len(clean)} 部電影本週票房累積占比", xlabel="依本週票房排序的電影數", ylabel="榜內累積占比（%）", ylim=(0, 105))
    ax_cum.legend()
    for ax in (ax_bar, ax_cum):
        ax.grid(alpha=.25)
    fig.savefig(CHART_OUTPUT, dpi=150)
    plt.close(fig)
    print(f"已產生 {DETAIL_OUTPUT.name}、{CHART_OUTPUT.name}")


def main():
    driver = open_chrome()
    try:
        # 1. 開啟題目網址，滑鼠移到「電影」選單，再點「票房排行榜」
        driver.get(URL)
        # 「票房排行榜」在下拉選單裡，每次點之前都要先把滑鼠移到「電影」讓選單展開
        mouse_click(driver, lambda: hover_movie_menu(driver), "/boxoffice/")

        # 2. 列出台北排行榜的排名、片名、票房（頁面上顯示前 5 名）
        wait_for(driver, TAIPEI_TITLE)
        period = driver.find_element(By.XPATH, TAIPEI_TITLE + "/following::*[contains(text(), '統計時間')][1]").text
        print(f"台北週末票房排行榜（{period}）")
        for movie in read_top5(driver):
            print(f"  第 {movie['排名']} 名：{movie['片名']}，本週票房 {movie['本週票房']}")

        # 3. 滑鼠點台北排行榜下方的 more，進入完整排行
        more = TAIPEI_TITLE + "/following::a[contains(@class, 'viewMore')][1]"
        mouse_click(driver, lambda: driver.find_element(By.XPATH, more), "/twweekend/")
        wait_for(driver, "//td[contains(@class, 'at11')]")
        movies = read_full_ranking(driver)
    finally:
        driver.quit()

    print("\n按下 more 後的完整排行（單位：萬新台幣）")
    for movie in movies:
        print(f"  {movie['排名']:>2}. {movie['片名']}｜本週 {movie['本週票房']}｜累計 {movie['累計票房']}")

    save_csv(movies, OUTPUT)
    print(f"\n共 {len(movies)} 筆，已存成 {OUTPUT.name}")

    # 延伸：票房集中度分析與繪圖
    analyze_and_draw(pd.DataFrame(movies))


if __name__ == "__main__":
    if "--analyze-only" in sys.argv:
        analyze_and_draw()
    else:
        main()
