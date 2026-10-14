"""
第 13 題（中）：momo 購物網自動搜尋 nba，並存成 NBA_test.html
================================================
題目要求
    網址 https://www.momoshop.com.tw/main/Main.jsp?cid=memb&oid=back2hp&mdiv=1099800000-bt_0_150_01-bt_0_150_01_e1&ctype=B
    1. 自動輸入 nba 關鍵字
    2. 存檔為 NBA_test.html

做法（Selenium）
    1. 開啟題目給的 momo 網址。
    2. 找到上方搜尋框（data-testid="header-search-input"），自動輸入 nba 並按 Enter。
    3. 等搜尋結果頁的商品名稱（a.prdName）出現，代表商品已載入。
    4. 取得瀏覽器目前的網頁原始碼 driver.page_source，存成 NBA_test.html（UTF-8）。
       存檔前用 BeautifulSoup 做兩個小調整，讓老師用瀏覽器打開檔案時畫面正常：
       - 移除 <script>：不然網頁程式會在本機重新執行，把已載入的商品清掉；
       - 加上 <base href="https://www.momoshop.com.tw/">：讓 CSS、圖片的相對網址仍連到 momo。
    （與本程式同一個資料夾，重新執行會直接覆蓋）

執行
    python 第13題_momo搜尋nba/main.py
"""

from pathlib import Path

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

URL = (
    "https://www.momoshop.com.tw/main/Main.jsp"
    "?cid=memb&oid=back2hp&mdiv=1099800000-bt_0_150_01-bt_0_150_01_e1&ctype=B"
)
KEYWORD = "nba"
OUTPUT = Path(__file__).parent / "NBA_test.html"


def make_offline_html(html):
    """移除 <script> 並加上 <base>，讓存下來的 HTML 離線打開也能正常顯示。"""
    soup = BeautifulSoup(html, "html.parser")
    for script in soup.find_all("script"):
        script.decompose()
    soup.head.insert(0, soup.new_tag("base", href="https://www.momoshop.com.tw/"))
    return str(soup)


def main():
    options = webdriver.ChromeOptions()
    options.page_load_strategy = "eager"  # 首頁圖片很多，主要內容出現就先操作
    driver = webdriver.Chrome(options=options)
    wait = WebDriverWait(driver, 30)
    try:
        driver.get(URL)

        # 1. 找到搜尋框，自動輸入 nba 並按 Enter
        search_box = wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "input[data-testid='header-search-input']"))
        )
        search_box.send_keys(KEYWORD)
        search_box.send_keys(Keys.ENTER)

        # 2. 等搜尋結果的商品名稱出現
        wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "a.prdName")))
        products = driver.find_elements(By.CSS_SELECTOR, "a.prdName")
        print(f"搜尋結果網址：{driver.current_url}")
        print(f"網頁標題：{driver.title}")
        print(f"本頁商品 {len(products)} 筆，例如：")
        for product in products[:5]:
            print(f"  - {product.text}")

        # 3. 把搜尋結果頁存成 NBA_test.html
        OUTPUT.write_text(make_offline_html(driver.page_source), encoding="utf-8")
    finally:
        driver.quit()

    print(f"\n已存成 {OUTPUT.name}（可直接用瀏覽器打開）")


if __name__ == "__main__":
    main()
