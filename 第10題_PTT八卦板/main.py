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
       HTML 裡寫的是 /bbs/Gossiping/….html 這種只有路徑的網址，直接點打不開，
       所以存完整網址 https://www.ptt.cc/bbs/Gossiping/….html。已被刪除的文章沒有連結，跳過。
    5. 依題目格式印出，並另存 ptt_gossiping.csv（網址、標題、作者），重新執行會直接覆蓋。

延伸：多抓推文數，看出哪些文章熱門
    同一個 <div class="r-ent"> 裡，標題左邊的數字就是推文數（.nrec），照網頁上的樣子存下來。
    PTT 的推文數是「推的人數 − 噓的人數」：「爆」＝100 以上；
    「X1」～「X9」＝被噓 10～90 以上、「XX」＝被噓 100 以上；空白＝推噓相抵或沒人推。

輸出
    ptt_gossiping.csv（題目要求的網址、標題、作者）
    ptt_gossiping_detail.csv（延伸：再加推文數）

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
FIELDS = ["網址", "標題", "作者"]
DETAIL_OUTPUT = Path(__file__).parent / "ptt_gossiping_detail.csv"  # 延伸
DETAIL_FIELDS = FIELDS + ["推文數"]


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
            # get_attribute 會把 HTML 裡的 /bbs/Gossiping/….html 補成完整網址，點下去就能打開
            "網址": links[0].get_attribute("href"),
            "標題": links[0].text,
            "作者": entry.find_element(By.CSS_SELECTOR, ".meta .author").text,
            # 延伸：推文數（標題左邊的數字）
            "推文數": entry.find_element(By.CSS_SELECTOR, ".nrec").text,
        })
    return articles


def save_csv(rows, path, fields):
    """存成 CSV（utf-8-sig：Excel 開啟中文不會亂碼）；fields 以外的欄位不寫入。"""
    with open(path, "w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


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

    save_csv(articles, OUTPUT, FIELDS)
    print(f"本頁共 {len(articles)} 篇文章，已存成 {OUTPUT.name}")

    # 延伸：加上推文數另存一份
    save_csv(articles, DETAIL_OUTPUT, DETAIL_FIELDS)
    print("\n延伸：每篇的推文數（推 − 噓；爆＝100 以上，X 開頭＝被噓）")
    for article in articles:
        print(f"  {article['推文數'] or '－':>3}｜{article['標題']}")
    print(f"已存成 {DETAIL_OUTPUT.name}")


if __name__ == "__main__":
    main()
