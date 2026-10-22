"""
第 14 題（難）：抓取 HoopsHype 的 NBA 球員薪水
================================================
題目要求
    抓 https://hoopshype.com/salaries/players 網頁中的 NBA 球員薪水資訊
    1. 使用 Selenium 和 BeautifulSoup
    2. 抓取前 3 位高薪球員的基本資料（名字、背號及薪資）存入 highest.csv
    3. 抓下本頁表格所有內容存入 all_play.csv

做法（Selenium 操作網頁 + BeautifulSoup 解析）
    薪資表是 JavaScript 動態產生的，而且分頁顯示（每頁 20 位，下方有像「1 of 30」的頁數和左右箭頭），
    所以用 Selenium 換頁，每一頁的網頁原始碼交給 BeautifulSoup 解析。
    1. 開啟薪資頁，用 BeautifulSoup 讀出表格標題列（排名、Player、各球季薪資）與每一列資料。
    2. 按分頁列右邊的箭頭到下一頁，直到「N of N」最後一頁，全部存成 all_play.csv。
    3. 表格是依目前球季薪資由高到低排序，排名 1～3 的就是前 3 高薪的球員；
       第 3 名有人同薪並列時（排名寫 T3），並列的全部列出，highest.csv 多一欄「排名」標出 1、2、T3。
       表格裡沒有背號，所以用 Selenium 打開這幾位球員的個人頁，
       用 BeautifulSoup 讀出姓名與背號（例如 #30），連同排名、薪資存成 highest.csv。
    換頁中途網站卡住（等 30 秒還沒換頁）時，不會整個失敗：先把已抓到的頁數存檔，並印出只抓到第幾頁。

延伸：全聯盟薪資排名圖
    全部球員（五百多位）都畫成有名字的長條會擠成一團看不清楚，所以畫兩張圖：
      左：本季薪資前 20 名的長條圖（單位：百萬美元）；
      右：全部球員依薪資排名畫成一條曲線（每位球員都在線上），標出中位數，
          看得出薪水集中在少數頂薪球員身上。
    被球隊釋出的球員會出現兩列（原球隊還要付的薪水＋新合約），畫圖時把同一位球員加總成一位。
    薪資文字前面可能有 TW（雙向合約）、T／P（球隊／球員選擇權）、Q（合格報價），轉成數字時去掉；
    「-」代表沒有這一季的合約，不列入。程式也會印出總薪資、中位數，以及前 10% 球員領走幾成薪資。

輸出（與本程式同一個資料夾，重新執行會直接覆蓋）
    all_play.csv：排名、Player、各球季薪資（薪資前的 P／T 是網站標示的球員選擇權／球隊選擇權，
                  TW 是雙向合約，Q 是合格報價；排名前的 T 代表同薪並列）
    highest.csv：排名、名字、背號、薪資（目前球季；同薪並列的都列出）
    salary_charts.png（延伸：薪資排名圖）

執行
    python 第14題_NBA球員薪水/main.py
"""

import csv
import re
import statistics
from pathlib import Path
from urllib.parse import urljoin

import matplotlib
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, StaleElementReferenceException, WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

matplotlib.use("Agg")  # 只存圖檔、不開視窗
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402

URL = "https://hoopshype.com/salaries/players"
FOLDER = Path(__file__).parent
# 分頁列長這樣：[<] 1 of 30 [>]，也就是「夾在兩個按鈕中間、文字含 of 的 span」
PAGER = "//span[contains(., ' of ')][preceding-sibling::button][following-sibling::button]"


def parse_table(html):
    """用 BeautifulSoup 解析目前這一頁的薪資表，回傳（欄位名稱, 資料列, 每列的球員網址）。"""
    soup = BeautifulSoup(html, "html.parser")
    table = soup.select_one("table")
    headers = [th.get_text(" ", strip=True) for th in table.select("thead th")]
    headers[0] = "排名"  # 第一欄網站沒有標題，自己命名

    rows, links = [], []
    for tr in table.select("tbody tr"):
        cells = [" ".join(td.get_text().split()) for td in tr.select("td")]
        cells = [cell.replace("$ ", "$") for cell in cells]  # 「$ 62,587,158」→「$62,587,158」
        rows.append(dict(zip(headers, cells)))
        link = tr.select_one("a[href]")  # 球員名字的連結 → 個人頁
        links.append(urljoin(URL, link["href"]) if link else "")
    return headers, rows, links


def rank_number(text):
    """排名欄「1」「T3」→ 1、3（T 代表同薪並列）；讀不出數字的排在最後。"""
    digits = re.sub(r"\D", "", text or "")
    return int(digits) if digits else 10**6


def top_three(rows, links):
    """第 1 頁排名 1～3 的球員與個人頁網址；第 3 名同薪並列（排名寫 T3）時，並列的全部算進來。"""
    return [(row, link) for row, link in zip(rows, links) if rank_number(row.get("排名")) <= 3]


def page_numbers(driver):
    """讀出分頁列的「目前頁 of 總頁數」，回傳 (目前頁, 總頁數)。"""
    text = driver.find_element(By.XPATH, PAGER).text  # 例如 "1 of 30"
    current, total = re.findall(r"\d+", text)
    return int(current), int(total)


def first_player(driver):
    """目前表格第一列的球員名字（用來判斷表格是否已換頁）。"""
    return driver.find_element(By.CSS_SELECTOR, "table tbody tr td:nth-child(2)").text


def collect_all_pages(driver):
    """從第 1 頁一路按到最後一頁，回傳全部資料。"""
    # 換頁時表格會重畫，找不到元素或元素失效都先忽略，繼續等
    wait = WebDriverWait(driver, 30, ignored_exceptions=(NoSuchElementException, StaleElementReferenceException,
                                                          ValueError))  # ValueError：分頁列文字還沒更新完
    driver.get(URL)
    wait.until(EC.presence_of_element_located((By.XPATH, PAGER)))

    all_rows, top = [], []
    while True:
        headers, rows, links = parse_table(driver.page_source)
        all_rows.extend(rows)
        if not top:
            top = top_three(rows, links)  # 第 1 頁就有最高薪的幾位
        current, total = page_numbers(driver)
        print(f"薪資表第 {current}/{total} 頁：{len(rows)} 位，累計 {len(all_rows)} 位")
        if current == total:
            break

        # 分頁列「1 of 30」右邊的按鈕就是下一頁
        try:
            previous_first = first_player(driver)
            next_button = driver.find_element(By.XPATH, PAGER + "/following-sibling::button[1]")
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", next_button)
            driver.execute_script("arguments[0].click();", next_button)  # 用 JS 點擊，避免被浮動廣告擋住
            # 等頁碼變成下一頁、而且表格第一列換人，才算換頁完成
            wait.until(lambda d: page_numbers(d)[0] == current + 1 and first_player(d) != previous_first)
        except WebDriverException as error:  # 含 TimeoutException：網站卡住，先保留已抓到的頁數
            print(f"（換到第 {current + 1} 頁失敗：{type(error).__name__}；只抓到第 {current}/{total} 頁，先把這些存檔）")
            break
    return headers, all_rows, top


def get_player_profile(driver, url):
    """打開球員個人頁，用 BeautifulSoup 讀出姓名與背號。"""
    driver.get(url)
    WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.TAG_NAME, "h2")))
    soup = BeautifulSoup(driver.page_source, "html.parser")
    name_tag = soup.select_one("h2")  # 個人頁上方的大標題就是球員全名
    name = name_tag.get_text(" ", strip=True)
    number_text = name_tag.parent.find(string=re.compile(r"^#\d+$"))  # 背號在姓名旁邊，格式像「#30」
    number = number_text.strip("#") if number_text else ""
    return name, number


def save_csv(path, fields, rows):
    with open(path, "w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def salary_number(text):
    """延伸：「$62,587,158」「TW$678,882」「P$60,156,000」「Q$10,469,414」→ 數字；「-」（沒有合約）→ None。"""
    digits = re.sub(r"\D", "", text)  # 去掉 $、逗號和前面的 TW／T／P／Q
    return int(digits) if digits else None


def use_chinese_font():
    """matplotlib 預設字型沒有中文，從電腦上已有的中文字型挑一個（Windows／macOS 都適用）。"""
    candidates = ["Microsoft JhengHei", "PingFang TC", "Heiti TC", "Noto Sans CJK TC", "Arial Unicode MS"]
    installed = {font.name for font in font_manager.fontManager.ttflist}
    plt.rcParams["font.sans-serif"] = [name for name in candidates if name in installed] + ["DejaVu Sans"]


def draw_salary_charts(rows, season, path):
    """延伸：左邊畫前 20 名長條圖，右邊畫全部球員的薪資排名曲線；回傳印出用的統計數字。"""
    totals = {}
    for row in rows:
        salary = salary_number(row[season])
        if salary:  # 被釋出的球員會出現兩列（原球隊還要付的＋新合約），同一位球員加總
            totals[row["Player"]] = totals.get(row["Player"], 0) + salary
    players = sorted(totals.items(), key=lambda p: p[1], reverse=True)
    millions = [salary / 1_000_000 for _, salary in players]  # 換成百萬美元
    total = sum(millions)
    median = statistics.median(millions)
    top10 = sum(millions[: len(millions) // 10]) / total * 100  # 前 10% 球員占總薪資的比例

    use_chinese_font()
    fig, (left, right) = plt.subplots(1, 2, figsize=(14, 6))

    names = [name for name, _ in players[:20]]
    left.barh(names[::-1], millions[:20][::-1], color="#1D428A")  # 反過來畫，第 1 名在最上面
    for y, value in enumerate(millions[:20][::-1]):
        left.text(value + 0.5, y, f"{value:.1f}", va="center", fontsize=8)
    left.set_xlim(0, millions[0] * 1.12)  # 右邊留空間給數字
    left.set_title(f"{season} 球季薪資前 20 名")
    left.set_xlabel("薪資（百萬美元）")
    left.tick_params(axis="y", labelsize=8)

    ranks = range(1, len(millions) + 1)
    right.plot(ranks, millions, color="#C8102E")
    right.fill_between(ranks, millions, color="#C8102E", alpha=0.15)
    right.axhline(median, color="black", linestyle="--", linewidth=1)
    right.text(len(millions) * 0.55, median + 2, f"中位數 {median:.1f} 百萬美元")
    right.set_title(f"全部 {len(millions)} 位球員的薪資排名（前 10% 球員領走 {top10:.0f}% 的薪資）")
    right.set_xlabel("薪資排名")
    right.set_ylabel("薪資（百萬美元）")

    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return len(millions), total, median, top10


def main():
    options = webdriver.ChromeOptions()
    options.page_load_strategy = "eager"  # 網頁廣告很多，主要內容出現就先操作
    driver = webdriver.Chrome(options=options)
    try:
        headers, all_rows, top = collect_all_pages(driver)
        season = headers[2]  # 第三欄是目前球季，例如 2026-27

        highest = []
        for row, url in top:
            name, number = get_player_profile(driver, url)
            highest.append({"排名": row["排名"], "名字": name, "背號": number, "薪資": row[season]})
    finally:
        driver.quit()

    save_csv(FOLDER / "all_play.csv", headers, all_rows)
    save_csv(FOLDER / "highest.csv", ["排名", "名字", "背號", "薪資"], highest)

    print(f"\n{season} 球季薪資前 3 名（同薪並列的都列出，共 {len(highest)} 位）：")
    for player in highest:
        print(f"  {player['排名']:>3}  {player['名字']} #{player['背號']}：{player['薪資']}")
    print(f"\n薪資表共 {len(all_rows)} 位球員，已存成 all_play.csv；前 3 名已存成 highest.csv")

    # 延伸：全聯盟薪資排名圖
    count, total, median, top10 = draw_salary_charts(all_rows, season, FOLDER / "salary_charts.png")
    print(f"\n延伸：{season} 球季有合約的 {count} 位球員（同一位球員的多列已加總），總薪資 {total:,.0f} 百萬美元、"
          f"中位數 {median:.1f} 百萬美元；前 10% 球員領走 {top10:.0f}% 的薪資")
    print("已存成 salary_charts.png")


if __name__ == "__main__":
    main()
