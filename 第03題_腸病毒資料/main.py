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

    注意：資料下載網址在疾管署網站（od.cdc.gov.tw），它的 HTTPS 憑證鏈不完整，
    Python 內建的憑證清單會驗證失敗。程式用 truststore 套件改用作業系統（Windows／macOS）
    的憑證庫驗證；如果還是驗證失敗，最後才改用不驗證憑證的方式下載，並印出提示。

輸出
    NHI_EnteroviralInfection.csv（約 8 MB，與本程式同一個資料夾，重新執行會直接覆蓋）

執行
    python 第03題_腸病毒資料/main.py
"""

import csv
import io
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

HOME_URL = "https://data.gov.tw/"
KEYWORD = "腸病毒"
DATASET_NAME = "健保門診及住院就診人次統計-腸病毒"
OUTPUT = Path(__file__).parent / "NHI_EnteroviralInfection.csv"


def find_csv_url():
    """用 Selenium 模擬：搜尋 → 點進資料集 → 讀出 CSV 的資料下載網址。"""
    driver = webdriver.Chrome()
    driver.set_window_size(1366, 900)  # 視窗太小時，上方固定的搜尋列會擋住搜尋結果
    wait = WebDriverWait(driver, 30)
    try:
        # 1. 首頁搜尋框輸入關鍵字，按搜尋按鈕
        driver.get(HOME_URL)
        search_box = wait.until(EC.element_to_be_clickable((By.ID, "searchbar-input")))
        search_box.send_keys(KEYWORD)
        driver.find_element(By.CSS_SELECTOR, "button.searchbar-submit-btn").click()

        # 2. 等搜尋結果載入完成（轉圈圈的遮罩消失），點資料集名稱；
        #    連結會開新分頁，所以要切換到新分頁
        dataset_link = wait.until(
            EC.element_to_be_clickable((By.XPATH, f"//a[normalize-space()='{DATASET_NAME}']"))
        )
        wait.until(EC.invisibility_of_element_located((By.CSS_SELECTOR, ".el-loading-mask")))
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", dataset_link)
        dataset_link.click()
        wait.until(lambda d: len(d.window_handles) > 1)
        driver.switch_to.window(driver.window_handles[-1])
        print(f"已進入資料集頁面：{driver.title}（{driver.current_url}）")

        # 3. 「資料資源下載網址」裡的 CSV 按鈕（title="CSV下載檔案"），它的 href 就是資料下載網址
        csv_button = wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "a[title='CSV下載檔案']"))
        )
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
    print(f"CSV 資料下載網址：{csv_url}")

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


if __name__ == "__main__":
    main()
