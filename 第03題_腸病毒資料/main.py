"""
第 3 題（中）：抓取政府資料開放平臺的「健保門診及住院就診人次統計－腸病毒」
================================================
題目要求
    1. 從政府資料開放平臺 https://data.gov.tw/ 抓取「健保門診及住院就診人次統計-腸病毒」
    2. 將資料存到本地 NHI_EnteroviralInfection.csv
    （課堂補充：不能只用滑鼠點網頁下載，要由程式抓到資料）

做法（requests）
    1. 用 requests 呼叫政府資料開放平臺的 API，查詢這個資料集（編號 14590）的詳細資料。
       平臺回傳 JSON，其中 distribution 列出各種格式的下載網址。
    2. 從 JSON 中找出 CSV 格式的「資料下載網址」（resourceDownloadUrl）。
    3. 再用 requests 下載這個 CSV，存成 NHI_EnteroviralInfection.csv。

    注意：資料下載網址在疾管署網站（od.cdc.gov.tw），它的 HTTPS 憑證鏈
    不完整，Python 內建的憑證清單會驗證失敗。程式用 truststore 套件改用
    作業系統（Windows／macOS）的憑證庫驗證，這樣不必關掉安全檢查也能下載。

輸出
    NHI_EnteroviralInfection.csv（約 8 MB，與本程式同一個資料夾，重新執行會直接覆蓋）

執行
    python 第03題_腸病毒資料/main.py
"""

import csv
import io
from pathlib import Path

import truststore

truststore.inject_into_ssl()  # 改用作業系統憑證庫驗證 HTTPS（必須在 import requests 之前）

import requests  # noqa: E402  （故意放在 truststore 設定之後）

DATASET_ID = 14590  # 「健保門診及住院就診人次統計-腸病毒」在平臺上的資料集編號
API_URL = f"https://data.gov.tw/api/v2/rest/dataset/{DATASET_ID}"
OUTPUT = Path(__file__).parent / "NHI_EnteroviralInfection.csv"


def find_csv_url():
    """呼叫政府資料開放平臺 API，回傳（資料集名稱, CSV 下載網址）。"""
    response = requests.get(API_URL, timeout=30)
    response.raise_for_status()
    dataset = response.json()["result"]  # 平臺回傳的是 JSON

    # distribution 是這個資料集提供的各種檔案（CSV、JSON…），挑出 CSV 那一個
    for resource in dataset["distribution"]:
        if resource["resourceFormat"].upper() == "CSV":
            return dataset["title"], resource["resourceDownloadUrl"]
    raise RuntimeError("這個資料集沒有提供 CSV 檔")


def download_csv(url):
    """下載 CSV，回傳文字內容。"""
    response = requests.get(url, timeout=120)
    response.raise_for_status()
    return response.content.decode("utf-8-sig")  # 官方檔案是 UTF-8


def main():
    title, csv_url = find_csv_url()
    print(f"資料集：{title}")
    print(f"CSV 下載網址：{csv_url}")

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
