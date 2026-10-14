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
    Taipei_movies.csv（金額單位：萬新台幣；與本程式同一個資料夾，重新執行會直接覆蓋）

執行
    python 第05題_台北票房排行榜/main.py
"""

import csv
import time
from pathlib import Path

from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

URL = "https://www.atmovies.com.tw/movie/new/"
OUTPUT = Path(__file__).parent / "Taipei_movies.csv"
FIELDS = ["排名", "片名", "本週票房", "累計票房"]

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
    """關閉 Google 全版廣告：廣告在 iframe 裡，切進去按「關閉」（#dismiss-button）。"""
    for _ in range(10):  # 廣告可能還在載入，最多試 10 次
        for frame in driver.find_elements(By.CSS_SELECTOR, "iframe[id^='aswift']"):
            try:
                if not frame.is_displayed():
                    continue
                driver.switch_to.frame(frame)
                buttons = driver.find_elements(By.ID, "dismiss-button")
                if buttons and buttons[0].is_displayed():
                    buttons[0].click()
                    return
            except WebDriverException:
                pass  # 廣告框架剛好被換掉，換下一個再試
            finally:
                driver.switch_to.default_content()  # 一定要切回主網頁
        time.sleep(0.5)


def mouse_click(driver, element, url_part):
    """模擬滑鼠：移到元素上再點下去，並確認網址換到 url_part 那一頁。"""
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
    ActionChains(driver).move_to_element(element).pause(0.5).click().perform()

    # 點下去後，不是換到目標頁，就是被 Google 全版廣告擋住
    WebDriverWait(driver, 30).until(
        lambda d: url_part in d.current_url or "google_vignette" in d.current_url
    )
    if "google_vignette" in driver.current_url:
        print("（跳出 Google 全版廣告，按「關閉」後繼續）")
        close_vignette_ad(driver)
        WebDriverWait(driver, 30).until(lambda d: url_part in d.current_url)


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
            "本週票房": cells[2].text,
            "累計票房": cells[3].text,
        })
    return movies


def save_csv(rows, path):
    with open(path, "w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def main():
    driver = open_chrome()
    try:
        # 1. 開啟題目網址，滑鼠移到「電影」選單，再點「票房排行榜」
        driver.get(URL)
        movie_menu = WebDriverWait(driver, 30).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, "#dropdownMenu .menuTitle.arrow"))
        )
        ActionChains(driver).move_to_element(movie_menu).perform()  # 滑鼠移入 → 展開下拉選單
        box_office = WebDriverWait(driver, 10).until(
            EC.visibility_of_element_located((By.LINK_TEXT, "票房排行榜"))
        )
        mouse_click(driver, box_office, "/boxoffice/")

        # 2. 列出台北排行榜的排名、片名、票房（頁面上顯示前 5 名）
        wait_for(driver, TAIPEI_TITLE)
        period = driver.find_element(By.XPATH, TAIPEI_TITLE + "/following::*[contains(text(), '統計時間')][1]").text
        print(f"台北週末票房排行榜（{period}）")
        for movie in read_top5(driver):
            print(f"  第 {movie['排名']} 名：{movie['片名']}，本週票房 {movie['本週票房']}")

        # 3. 滑鼠點台北排行榜下方的 more，進入完整排行
        more = driver.find_element(By.XPATH, TAIPEI_TITLE + "/following::a[contains(@class, 'viewMore')][1]")
        mouse_click(driver, more, "/twweekend/")
        wait_for(driver, "//td[contains(@class, 'at11')]")
        movies = read_full_ranking(driver)
    finally:
        driver.quit()

    print("\n按下 more 後的完整排行（單位：萬新台幣）")
    for movie in movies:
        print(f"  {movie['排名']:>2}. {movie['片名']}｜本週 {movie['本週票房']}｜累計 {movie['累計票房']}")

    save_csv(movies, OUTPUT)
    print(f"\n共 {len(movies)} 筆，已存成 {OUTPUT.name}")


if __name__ == "__main__":
    main()
