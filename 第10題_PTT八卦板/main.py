"""
第 10 題（中）：抓取 PTT 八卦板（Gossiping）文章列表
================================================
題目要求
    URL = "https://www.ptt.cc/bbs/Gossiping/index.html"
    1. 使用 Selenium 解決分級問題（八卦板要先確認已滿 18 歲）
    2. 列出網站 title，例如：批踢踢實業坊
    3. 列出該網站列表（網址、標題及作者），格式如：
           /bbs/Gossiping/M.1704514524.A.426.html
           Re: [新聞] 國三車禍台積電副理下車搖燈示警被撞身亡
           topahot9303
    （課堂補充：網站有 Cookie 分級確認，需先點選解決；Cookie over18 的值為 1 即視為已成年）

做法（Selenium）
    1. 開啟八卦板網址，網站會先轉到分級確認頁（/ask/over18）。
    2. 用 Selenium 點「我同意，我已年滿十八歲」按鈕（<button name="yes">）。
       點完網站會設定 Cookie over18=1，並帶回八卦板；程式也會印出這個 Cookie 確認。
    3. 印出網站 title。
    4. 每篇文章在 <div class="r-ent"> 裡：網址與標題＝.title a，作者＝.meta .author。
       已被刪除的文章沒有連結，跳過。
    5. 依題目格式印出，並另存 ptt_gossiping.csv（網址、標題、作者），重新執行會直接覆蓋。

執行
    python 第10題_PTT八卦板/main.py
"""

import csv
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

URL = "https://www.ptt.cc/bbs/Gossiping/index.html"
OUTPUT = Path(__file__).parent / "ptt_gossiping.csv"


def pass_age_check(driver):
    """如果出現分級確認頁，就點「我同意，我已年滿十八歲」。"""
    buttons = driver.find_elements(By.CSS_SELECTOR, "button[name='yes']")
    if buttons:
        print(f"分級確認頁的 title：{driver.title}")
        buttons[0].click()
    # 等到文章列表出現，代表已進入八卦板
    WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.r-ent")))
    cookie = driver.get_cookie("over18") or {}
    print(f"Cookie over18 = {cookie.get('value')}（1 代表已確認滿 18 歲）")


def get_articles(driver):
    """讀出目前列表頁的每一篇文章（網址、標題、作者）。"""
    articles = []
    for entry in driver.find_elements(By.CSS_SELECTOR, "div.r-ent"):
        links = entry.find_elements(By.CSS_SELECTOR, ".title a")
        if not links:  # 被刪除的文章沒有連結
            continue
        articles.append({
            # get_dom_attribute 取 HTML 裡原本寫的網址，也就是題目範例的 /bbs/Gossiping/....html
            "網址": links[0].get_dom_attribute("href"),
            "標題": links[0].text,
            "作者": entry.find_element(By.CSS_SELECTOR, ".meta .author").text,
        })
    return articles


def main():
    driver = webdriver.Chrome()
    try:
        driver.get(URL)
        pass_age_check(driver)
        title = driver.title
        articles = get_articles(driver)
    finally:
        driver.quit()

    print(f"網站 title：{title}\n")
    for article in articles:
        print(article["網址"])
        print(article["標題"])
        print(article["作者"])
        print()

    with open(OUTPUT, "w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=["網址", "標題", "作者"])
        writer.writeheader()
        writer.writerows(articles)
    print(f"本頁共 {len(articles)} 篇文章，已存成 {OUTPUT.name}")


if __name__ == "__main__":
    main()
