"""
第 17 題（難）：使用 Selenium 自動登入 GitHub，抓取首頁兩個視窗的資料
================================================
題目要求（網址 https://github.com/）
    1. 使用 Selenium 及 WebDriver 自動登入帳號
    2. 抓取題目附圖中 1 號視窗的頁面資料（首頁左欄）
    3. 抓取題目附圖中 2 號視窗的頁面資料（首頁中間主欄）
    （課堂補充：難點在於登入表單裡有隱藏的 key 值）

做法（Selenium）
    1. 執行時在終端機輸入 GitHub 帳號與密碼（帳號照常顯示，密碼每個字顯示成「•」；密碼不會存檔）。
       也可以事先設定環境變數 GITHUB_USERNAME、GITHUB_PASSWORD，就不用每次輸入。
    2. 開啟 https://github.com/login，由 Selenium 自動把帳密填進
       #login_field、#password，再按「Sign in」。
       「隱藏的 key 值」：登入表單裡有 authenticity_token（防止偽造請求的金鑰）等隱藏欄位，
       每次開頁面都不一樣。用 requests 登入必須自己先從網頁抓出這個值、跟帳密一起送出；
       用 Selenium 是在真的瀏覽器裡按登入，瀏覽器會自動把隱藏欄位一起送出。
       程式會找出這些隱藏欄位，並印出 authenticity_token 的開頭，讓你看到它確實存在。
    3. 送出帳密後，GitHub 可能還要再驗證一次，請在跳出的 Chrome 視窗裡手動完成，
       程式最多等 5 分鐘，直到登入成功（程式一開始也會先提醒）：
       - 有開二階段驗證（2FA）：輸入驗證 App／簡訊的 6 位數驗證碼，或用通行金鑰（passkey）確認；
       - 沒開 2FA：程式每次都開全新的 Chrome，GitHub 會當成新裝置，通常會寄 Email 驗證碼，
         到信箱查看後輸入即可。
    4. 登入後回到 https://github.com/ 首頁：
       1 號視窗＝左欄（aside.feed-left-sidebar）：新帳號會顯示「Create your first project」，
                 已有專案的帳號會顯示「Top repositories」清單。
       2 號視窗＝中間主欄（#dashboard 的 .news 區塊）：題目附圖當時是「Updates to your
                 homepage feed」提示卡；GitHub 改版後是首頁動態／Copilot、Pull requests 等面板。
       依「位置」抓取，不寫死文字，所以新舊版首頁都能抓到這兩個區域的全部文字。
       首頁的區塊是陸續載入的（中間主欄一開始只有轉圈圈，左欄的 Top repositories 也比 Home、Feed 晚出現），
       所以兩個視窗一起等：都有文字、區塊裡沒有轉圈圈或灰色骨架（載入中），而且連續 3 秒沒有再變，
       才開始讀取，最多等 45 秒。
    5. 兩個視窗分開存：內容載入完成後，印出文字並存成 CSV，再截下那個區塊的畫面。
       CSV 有兩欄：內容（一行文字一列）、連結（那行文字是連結的話，用 get_attribute("href")
       取完整網址，例如 Top repositories 的 https://github.com/Tunai-0511/…；不是連結就空白）。
       1 號視窗（左欄）：github_window1_left.csv、github_window1_left.png
       2 號視窗（中間主欄）：github_window2_center.csv、github_window2_center.png
       （抓到的是登入帳號自己的首頁內容；重新執行會直接覆蓋。）

執行
    python 第17題_GitHub登入首頁/main.py
"""

import base64
import csv
import getpass
import os
import sys
import time
from pathlib import Path

from selenium import webdriver
from selenium.common.exceptions import StaleElementReferenceException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

LOGIN_URL = "https://github.com/login"
HOME_URL = "https://github.com/"
FOLDER = Path(__file__).parent

# 兩個視窗：名稱、在首頁上的位置（CSS 選擇器；後面的是舊版首頁的備用寫法）、輸出檔名（.csv 和 .png）
WINDOWS = [
    ("1號視窗（左欄）", ["aside.feed-left-sidebar", ".dashboard-sidebar"], "github_window1_left"),
    ("2號視窗（中間主欄）", ["#dashboard .news", "#dashboard"], "github_window2_center"),
]


def ask_account():
    """讀取帳密：先看環境變數，沒有的話請使用者在終端機輸入。"""
    print("提醒：送出帳密後，GitHub 可能要求再驗證一次，請在跳出的 Chrome 視窗中完成：")
    print("  - 有開二階段驗證（2FA）：輸入驗證 App 或簡訊的 6 位數驗證碼，或用通行金鑰確認")
    print("  - 沒開 2FA：GitHub 會把這個新開的瀏覽器當成新裝置，通常會寄 Email 驗證碼，請到信箱查看")
    print("  程式會等你最多 5 分鐘。\n")
    username = os.environ.get("GITHUB_USERNAME") or input("GitHub 帳號（或 Email）：").strip()
    password = os.environ.get("GITHUB_PASSWORD") or ask_secret("GitHub 密碼：")
    if not username or not password:
        raise SystemExit("帳號和密碼都不能空白。")
    return username, password


def ask_secret(prompt):
    """輸入密碼或金鑰：每打一個字顯示一個「•」，不顯示實際內容（可以用退格鍵修改）。
    如果不是在一般終端機執行（無法逐字讀鍵盤），改用 getpass，輸入時什麼都不顯示。"""
    if not sys.stdin.isatty():
        return getpass.getpass(prompt)
    print(prompt, end="", flush=True)
    dot = "•" if "•".encode(sys.stdout.encoding or "utf-8", "ignore") else "*"
    chars = []

    def show(text):
        sys.stdout.write(text)
        sys.stdout.flush()

    def handle(ch):
        """處理一個按鍵；回傳 True 代表輸入結束。"""
        if ch in ("\r", "\n"):
            return True
        if ch == "\x03":  # Ctrl+C
            raise KeyboardInterrupt
        if ch in ("\x08", "\x7f"):  # 退格鍵：刪掉最後一個字和一個點
            if chars:
                chars.pop()
                show("\b \b")
        elif ch.isprintable():
            chars.append(ch)
            show(dot)
        return False

    try:
        if os.name == "nt":  # Windows：用 msvcrt 一次讀一個按鍵
            import msvcrt
            while True:
                ch = msvcrt.getwch()
                if ch in ("\x00", "\xe0"):  # 方向鍵等特殊鍵會送兩個字元，略過
                    msvcrt.getwch()
                    continue
                if handle(ch):
                    break
        else:  # macOS／Linux：暫時把終端機切成逐字模式，結束後一定要還原
            import termios
            import tty
            fd = sys.stdin.fileno()
            old_settings = termios.tcgetattr(fd)
            try:
                tty.setraw(fd, termios.TCSANOW)  # TCSANOW：保留已經先打進去的字
                while True:
                    ch = sys.stdin.read(1)
                    if ch == "\x1b":  # 方向鍵等特殊鍵會送出「ESC [ A」這樣一串字元，整串略過，不算進密碼
                        if sys.stdin.read(1) in ("[", "O"):
                            while not ("@" <= sys.stdin.read(1) <= "~"):  # 讀到這串的最後一個字元為止
                                pass
                        continue
                    if handle(ch):
                        break
            finally:
                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    except KeyboardInterrupt:
        print()
        raise SystemExit("已取消輸入。")
    print()
    return "".join(chars)


def login(driver, username, password):
    """打開登入頁、自動填入帳密並按 Sign in，等到登入成功。"""
    driver.get(LOGIN_URL)
    wait = WebDriverWait(driver, 30)
    username_box = wait.until(EC.presence_of_element_located((By.ID, "login_field")))

    # 找出登入表單裡的隱藏欄位（<input type="hidden">），其中 authenticity_token 就是「隱藏的 key 值」：
    # 每次打開登入頁都不一樣，登入時必須跟帳密一起送出，GitHub 才會接受這次登入。
    hidden = driver.find_elements(By.CSS_SELECTOR, "form[action='/session'] input[type='hidden']")
    print(f"登入表單的隱藏欄位：{', '.join(field.get_attribute('name') for field in hidden)}")
    token = driver.find_element(By.NAME, "authenticity_token").get_attribute("value")
    print(f"隱藏的 key 值 authenticity_token：{token[:12]}…（共 {len(token)} 個字元，只顯示開頭）")
    print("→ 用 Selenium 在瀏覽器裡按登入，瀏覽器會自動把這個 key 值跟帳密一起送出。\n")

    # 自動填入帳密並按下 Sign in
    username_box.send_keys(username)
    driver.find_element(By.ID, "password").send_keys(password)
    driver.find_element(By.NAME, "commit").click()

    # 登入成功後，頁面的 <meta name="user-login"> 會是使用者名稱
    print("已送出登入資料。如果 Chrome 畫面要求驗證碼或通行金鑰，請在那裡完成（最多等 5 分鐘）…")
    # 換頁時舊元素會失效（stale），先忽略、繼續等
    try:
        WebDriverWait(driver, 300, ignored_exceptions=[StaleElementReferenceException]).until(
            lambda d: logged_in_user(d) or login_failed(d)
        )
    except TimeoutException:
        raise SystemExit("等了 5 分鐘仍未登入成功（可能是二階段驗證或 Email 驗證碼沒有完成），程式結束。")
    if login_failed(driver):
        raise SystemExit("登入失敗：帳號或密碼錯誤。")
    print(f"登入成功：{logged_in_user(driver)}\n")


def logged_in_user(driver):
    meta = driver.find_elements(By.CSS_SELECTOR, "meta[name='user-login']")
    return meta[0].get_attribute("content") if meta else ""


def login_failed(driver):
    """登入頁上方出現紅色錯誤訊息（例如 Incorrect username or password）就是登入失敗。"""
    return any(error.is_displayed() for error in driver.find_elements(By.CSS_SELECTOR, ".flash-error"))


def find_block(driver, selectors):
    """依序嘗試選擇器，回傳第一個找到的區塊；都找不到回傳 None。"""
    for selector in selectors:
        blocks = driver.find_elements(By.CSS_SELECTOR, selector)
        if blocks:
            return blocks[0]
    return None


def read_window(driver, selectors):
    """回傳區塊裡「畫面上看得到」的每一行文字；找不到區塊回傳 None。"""
    block = find_block(driver, selectors)
    if block is None:
        return None
    try:
        return [line.strip() for line in block.text.splitlines() if line.strip()]
    except StaleElementReferenceException:  # 區塊剛好在重新載入，當作還沒好
        return []


def read_links(block):
    """找出區塊裡所有連結：連結上的每一行文字 → 完整網址。
    同樣的文字可能出現好幾次（例如兩個「View all」），所以每個文字對應一個清單，照網頁上的順序排。"""
    links = {}
    try:
        for link in block.find_elements(By.TAG_NAME, "a"):
            # get_attribute 會把 /Tunai-0511/xxx 補成完整網址
            href = link.get_attribute("href")
            for text in link.text.splitlines():  # 只看得到畫面上顯示的文字，隱藏的連結會是空字串
                if text.strip() and href:
                    links.setdefault(text.strip(), []).append(href)
    except StaleElementReferenceException:  # 區塊剛好重新載入，這次就不抓連結
        pass
    return links


def screenshot_block(driver, block, path):
    """截下整個區塊的畫面。一般的元素截圖只截得到視窗裡看得到的部分，
    區塊比視窗高時下面會被切掉，所以改用 Chrome 的 captureBeyondViewport（超出視窗也截）。"""
    rect = driver.execute_script(
        "const r = arguments[0].getBoundingClientRect();"
        "return {x: r.left + window.scrollX, y: r.top + window.scrollY, width: r.width, height: r.height};",
        block,
    )
    shot = driver.execute_cdp_cmd("Page.captureScreenshot", {
        "format": "png",
        "captureBeyondViewport": True,
        "clip": {**rect, "scale": 1},  # 只截這個區塊的位置與大小
    })
    path.write_bytes(base64.b64decode(shot["data"]))  # Chrome 回傳的是 base64 編碼的 PNG


# 載入中的標記：還沒載入的片段（include-fragment）、aria-busy、轉圈圈、灰色骨架
LOADING = ("include-fragment, [aria-busy='true'], .anim-rotate, "
           "[class*='Spinner'], [class*='spinner'], [class*='Skeleton'], [class*='skeleton']")


def still_loading(driver, selectors):
    """區塊裡還有看得到的「載入中」元素就回傳 True。"""
    block = find_block(driver, selectors)
    if block is None:
        return False
    try:
        return any(el.is_displayed() for el in block.find_elements(By.CSS_SELECTOR, LOADING))
    except StaleElementReferenceException:  # 區塊剛好在重新載入
        return True


def wait_until_loaded(driver, timeout=45):
    """首頁的區塊是陸續載入的：中間主欄一開始只有轉圈圈，左欄的 Top repositories 也比 Home、Feed 晚出現。
    每 0.5 秒把兩個視窗的文字一起讀一次，等到「都有文字、沒有載入中的元素、而且連續 3 秒都沒再變」
    才算載入完成；最多等 timeout 秒。回傳 True 代表載入完成，False 代表等到時間到。"""
    last = None
    unchanged_since = time.time()
    deadline = time.time() + timeout
    while time.time() < deadline:
        texts = [read_window(driver, selectors) for _, selectors, _ in WINDOWS]
        if texts != last:  # 內容還在變，重新計時
            last, unchanged_since = texts, time.time()
        elif all(texts) and time.time() - unchanged_since >= 3 and not any(
            still_loading(driver, selectors) for _, selectors, _ in WINDOWS
        ):
            return True
        time.sleep(0.5)
    return False


def main():
    username, password = ask_account()
    driver = webdriver.Chrome()
    try:
        driver.set_window_size(1400, 1000)  # 視窗夠寬，首頁才會顯示左欄與中間兩欄
        login(driver, username, password)

        driver.get(HOME_URL)
        print("等首頁內容載入完成（中間主欄會先轉圈圈，左欄的 repo 清單也比較晚出現，最多等 45 秒）…\n")
        if not wait_until_loaded(driver):
            print("等了 45 秒首頁還在載入，先讀目前看得到的內容。\n")
        for window, selectors, name in WINDOWS:
            lines = read_window(driver, selectors)
            if lines is None:
                lines = ["（找不到這個區塊，GitHub 首頁版面可能又改了）"]
            elif not lines:
                lines = ["（等了 45 秒這個區塊還沒載入出文字）"]
            # 每行文字如果是連結，就配上它的完整網址（同樣文字出現好幾次就照順序取）
            block = find_block(driver, selectors)
            links = read_links(block) if block is not None else {}
            rows = [(line, links[line].pop(0) if links.get(line) else "") for line in lines]

            print(f"【{window}】")
            for line, href in rows:
                print(f"  {line}" + (f"  → {href}" if href else ""))

            # 這個視窗的文字和連結存成自己的 CSV（一行文字一列）
            with open(FOLDER / f"{name}.csv", "w", newline="", encoding="utf-8-sig") as file:
                writer = csv.writer(file)
                writer.writerow(["內容", "連結"])
                writer.writerows(rows)

            # 內容載入完成後，只截這個區塊的畫面（不是整個網頁）
            if block is not None:
                screenshot_block(driver, block, FOLDER / f"{name}.png")
            print(f"  → 已存成 {name}.csv、{name}.png\n")
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
