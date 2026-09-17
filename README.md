# PDF 原題 1–17 程式

這一版只提供原題程式、操作說明、測試與實際執行紀錄，不製作 Word 或簡報，也不以自選資料集替代原題。先前六題版保持不變。

「有程式」不等於「來源網站已實測成功」。GitHub 版的既有結果請看 [2026-09-10 實測摘要](docs/status-2026-09-10.md)；網站阻擋、介面變更、配額及本人登入需求均會保留實際狀態，不填入假資料。

GitHub 只收錄程式、說明及手工測試樣本；完整抓取結果、截圖、瀏覽器狀態、虛擬環境與私人設定不提交。原本本機的 `逐題狀態.md` 和結果檔案仍保留，沒有刪除。

## 安裝與執行

需要 Python 3.10 以上、Google Chrome 與網路。第一次啟動 Selenium 可能需要下載相容的驅動。

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python q01.py
```

Windows 啟動虛擬環境改用 `.venv\Scripts\activate`。

Selenium 題目預設會開啟看得到的 Chrome，由程式自動輸入、點擊與換頁，保留 Chrome 原生的自動測試控制提示，不載入你的私人瀏覽器設定檔。一般執行結束會關閉該視窗；公開網頁題目可加 `--keep-open` 保留，之後自行關閉。第 10、17 題不保留視窗，以免留下登入或個人操作狀態。只使用 requests／API 的題目不會開啟 Chrome。

```sh
# 照片中的第 14 題：顯示 Chrome，自動讀取薪資表與前三名資料，結束保留視窗
# 2026-09-10 實測薪資表有 29 頁；若頁數增加，上限 100 仍可繼續讀取
python q14.py --max-pages 100 --keep-open

# 若不需要看操作過程，才加上 --headless
python q11.py --headless

# 只執行指定題號
python run_all.py --questions 1 5 11

# 依序執行所有原題；需要本人操作的題目會先記錄 needs_user
python run_all.py

# 本人在場時允許互動暫停，自行完成必要操作
python q10.py --interactive
python q17.py --interactive

# 第 16 題可自行固定住宿條件；僅搜尋，不預訂
python q16.py --check-in 2026-10-01 --check-out 2026-10-02 --adults 2

# 離線程式測試，不連線真實網站
python -m unittest discover -s tests -v
```

每次執行會產生 `results/時間/q題號/`，不覆寫舊檔；批次入口另附 `summary.json`。每題 `status.json` 記錄來源、起訖時間、輸出檔案、CSV 筆數與檔案 SHA-256。`--output` 可以指定另一個結果根目錄。

## 題號對照

| 程式 | 原題 | 主要輸出 |
| --- | --- | --- |
| q01.py | 開眼本週新片：標題、內容、片長、網址 | new_movies.csv |
| q02.py | 台銀最新牌價 | bank.csv |
| q03.py | 腸病毒健保就診資料 | NHI_EnteroviralInfection.csv |
| q04.py | 博客來「演算法」書籍 | booklist.csv |
| q05.py | 開眼台北票房排行榜 20 筆 | Taipei_movies.csv |
| q06.py | CLE、HOU、GSW 的 2024 球員名單 | players.csv |
| q07.py | Google Books Python 兩頁 | pythonbook.csv |
| q08.py | 開眼近期上映強片 | movies.csv |
| q09.py | Google 新聞指定分類 | news.csv 與分類狀態 |
| q10.py | PTT 八卦板列表及網站 title | ptt_gossiping.csv、page_title.txt |
| q11.py | NBA 商品所有動態分頁 | NBA_Products1.csv 至 NBA_ProductsN.csv |
| q12.py | Google 搜尋 Steam 遊戲推薦 | steam_search.csv |
| q13.py | momo 自動搜尋 nba | NBA_test.html |
| q14.py | 球員薪資全表與前三名背號 | all_play.csv、highest.csv |
| q15.py | Google 搜尋 xpath 與更多結果 | xpath.csv |
| q16.py | Agoda 台中飯店與價格 | agoda_result.csv |
| q17.py | GitHub 登入後 PDF 指定的兩個提示區塊 | github_panel_1.txt、github_panel_2.txt、panel_status.json |

## 狀態如何判讀

- `passed`：本次已執行且符合程式檢查的題目範圍，不代表日後網站不會改版。
- `partial`：已有部分資料，或原題要求的欄位、區塊、筆數、操作未全部達成；詳見 note。
- `blocked`：HTTP、TLS、配額或網站驗證使資料無法正常取得。
- `needs_user`：需要本人登入、年齡確認或提供自己的設定。
- `error`：其他執行錯誤，不能視為成功。

單題退出碼依序為成功 0、部分 2、阻擋 3、待本人 4、錯誤 1；批次只要有任何題未成功就回傳 2，但仍會處理後面的題目。沒有成功資料時，可能只會有錯誤回應或 `status.json`，不會產生看似完成的空 CSV。

## 需要注意的題目

第 7 題使用自己的 Google Books API key 時，請在本機設定 `GOOGLE_BOOKS_API_KEY` 環境變數，不要把 key 放入程式、聊天或交付檔。程式不代辦帳號、申請配額或付費。

第 10 題不注入 `over18` cookie，也不代替本人點選年齡按鈕。請以互動模式執行並自行完成適用的確認。

第 17 題的帳號與密碼由本人在本機輸入，密碼採隱藏輸入；程式可自動填入一般登入表單。2FA、通行金鑰、SSO 及裝置驗證仍由本人完成。留空帳號可改為本人手動登入，但會明列未達原題的自動表單要求。只保存 PDF 指定提示文字，不保存帳密、cookie 或整份私人首頁。舊版提示卡片在目前帳號不存在時，不拿其他區塊冒充。

第 14、15 題預設最多 5 頁，可用 `--max-pages` 調整；第 14 題需提高上限才能讀完目前的薪資全表。遇到安全上限、驗證或尚未到結尾時，會標為部分完成，不宣稱已全部爬完。第 16 題預設為執行日起 21 天後入住、一晚、兩位成人；可自行指定日期。價格只能在相同日期、人數、幣別與稅費條件下比較。

網站回應與 HTML 可能改版。測試資料放在 `tests/fixtures/`，僅用於驗證解析邏輯，不能當成真實完成截圖或即時資料。API 的原始回應如含本人提供的 key 會遮蔽後才儲存。

參考：[Selenium 等待策略](https://www.selenium.dev/documentation/webdriver/waits/)、[GitHub 登入方式](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/about-authentication-to-github)。各題資料來源保留在程式與實測狀態中。
