# 資料科學期中報告：網路爬蟲 17 題

每一題是一個資料夾，裡面有 **程式 `main.py`** 和 **執行後的輸出檔**（CSV／HTML）。
程式可以單獨執行，重新執行會**直接覆蓋**同一個輸出檔，不會另外產生新檔案。
每支程式最上面都有一段說明：題目要求、做法、輸出檔、執行指令。

> 本 repo 整合了組員兩個版本（[Einosensokami/Data_Science_Einosensokami](https://github.com/Einosensokami/Data_Science_Einosensokami)、[Tunai-0511/data-science-midterm](https://github.com/Tunai-0511/data-science-midterm) 舊版），
> 並依 2026-10-14 各網站的實際版面重新撰寫、逐題實測。

---

## 一、安裝環境（只要做一次）

需要：**Python 3.10 以上**、**Google Chrome**。
ChromeDriver 不用自己下載，Selenium 會自動下載與 Chrome 版本相符的驅動程式。

```bash
pip install -r requirements.txt
```

如果想裝在虛擬環境裡（可選）：

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
source .venv/bin/activate       # macOS / Linux
pip install -r requirements.txt
```

> macOS 若 `python` 指令不存在，請改用 `python3`。

## 二、執行方式

在本資料夾（`requirements.txt` 所在位置）開終端機：

```bash
# 執行單一題
python 第01題_本週新片/main.py

# 一次執行第 1～16 題，最後列出每題成功／失敗
python run_all.py

# 只執行指定題號（第 17 題要登入 GitHub，請用這種方式單獨執行）
python run_all.py 2 5 11
python run_all.py 17
```

用到 Selenium 的題目會自動打開 Chrome 視窗操作，完成後自動關閉，可以直接看到程式操作的過程。

---

## 三、題目總覽

| 題 | 題目 | 使用技術 | 輸出檔 | 需要人工 |
|:-:|---|---|---|---|
| 1 | 開眼電影網本週新片 | requests + BeautifulSoup | `new_movies.csv` | — |
| 2 | 臺灣銀行牌告匯率 | Selenium 載入 + BeautifulSoup | `bank.csv` | — |
| 3 | 政府資料開放平臺：健保門診及住院就診人次統計－腸病毒 | Selenium 模擬搜尋與點選 + requests 下載 | `NHI_EnteroviralInfection.csv` | — |
| 4 | 博客來「演算法」搜尋結果 | Selenium 載入 + BeautifulSoup + JSON | `booklist.csv`（另存 `booklist.json`） | 偶爾需勾選真人驗證 |
| 5 | 開眼台北週末票房排行榜（20 筆） | Selenium（ActionChains 模擬滑鼠） | `Taipei_movies.csv` | — |
| 6 | Basketball Reference：CLE、HOU、GSW 球員 | requests + BeautifulSoup | `players.csv` | — |
| 7 | Google Books API 搜尋 Python（兩頁） | requests（API 回傳 JSON） | `pythonbook.csv` | 需要 API 金鑰 |
| 8 | 開眼近期上映強片 | requests + BeautifulSoup | `movies.csv` | — |
| 9 | Google 新聞各分類標題 | Selenium | `google_news.csv`（另印出） | — |
| 10 | PTT 八卦板文章列表 | Selenium（點選年齡確認） | `ptt_gossiping.csv`（另印出） | — |
| 11 | NBA 商品資料，每頁一個 CSV | Selenium（操作分頁） | `NBA_Products1.csv`～`NBA_Products17.csv` | — |
| 12 | Google 搜尋「Steam 遊戲推薦」 | Selenium | `steam_games.csv` | 可能要完成 Google 機器人驗證 |
| 13 | momo 自動搜尋 nba | Selenium | `NBA_test.html` | — |
| 14 | HoopsHype 球員薪水 | Selenium + BeautifulSoup | `highest.csv`、`all_play.csv` | — |
| 15 | Google 搜尋「xpath」，捲動並取得更多結果 | Selenium（模擬滑鼠滾輪） | `xpath.csv` | 可能要完成 Google 機器人驗證 |
| 16 | Agoda 搜尋台中飯店與價格（含加分項） | Selenium + BeautifulSoup | `agoda_result.csv` | — |
| 17 | GitHub 自動登入，抓首頁兩個視窗 | Selenium | `github_dashboard.csv`、`github_dashboard.png` | 執行時輸入帳密 |

### 對應期中配分要求

| 要求 | 本 repo 可對應的題目 |
|---|---|
| 要求 1：使用 requests 抓取資料 | 第 7 題（Google Books API）、第 1、6、8 題（requests 下載網頁）；第 3 題也用 requests 下載 CSV |
| 要求 2：使用 BeautifulSoup 抓取資料 | 第 1、6、8 題；第 2、4、13、14、16 題也用 BeautifulSoup 解析 |
| 要求 3：使用 Selenium 抓取動態網站 | 第 3、5、9、10、11、12、13、14、15、16、17 題；第 2、4 題用 Selenium 載入網頁 |

---

## 四、各題說明

### 第 1 題：開眼電影網本週新片
- **題目**：抓 <http://www.atmovies.com.tw/movie/new/> 的本週新片，包括標題、內容、片長、網址。
- **做法**：requests 下載頁面 → BeautifulSoup 找每個 `<article class="filmList">`，取標題、簡介、片長（正規表示式取「片長：117分」）、網址。
- **輸出**：`new_movies.csv`（標題、內容、片長、網址）
- **執行**：`python 第01題_本週新片/main.py`

### 第 2 題：臺灣銀行牌告匯率
- **題目**：抓 <https://rate.bot.com.tw/xrt?Lang=zh-TW> 最新掛牌資料，存入 `bank.csv`。
- **做法**：臺銀網站現在有「瀏覽器驗證」，requests 只會拿到驗證頁，所以用 Selenium 開 Chrome 載入，再用 BeautifulSoup 解析匯率表。每個儲存格都有 `data-table` 屬性（例如「本行現金買入」），依屬性取值，避免題目「參考範例」那種欄位錯位、重複的問題。
- **輸出**：`bank.csv`（幣別、現金匯率-本行買入／賣出、即期匯率-本行買入／賣出），並印出牌價最新掛牌時間。
- **執行**：`python 第02題_台銀牌價/main.py`

### 第 3 題：健保門診及住院就診人次統計－腸病毒
- **題目**：從政府資料開放平臺抓取這份資料，存成 `NHI_EnteroviralInfection.csv`。課堂補充：不能自己用滑鼠點網頁找到資料就說抓到了，要用程式模擬。
- **做法**：照題目附圖的步驟，由 Selenium 模擬操作：開啟 data.gov.tw → 首頁搜尋框輸入「腸病毒」並按搜尋 → 在結果中點「健保門診及住院就診人次統計-腸病毒」（開在新分頁，程式會切換過去）→ 讀出資料集頁面「CSV」按鈕的下載網址 → 用 requests 下載並存檔。
  （用完整名稱搜尋時，平臺會把同系列的其他疾病排在前面，所以用「腸病毒」搜尋，目標資料集就在第一頁。）
  下載網址在疾管署網站，憑證鏈不完整、Python 預設會驗證失敗，所以先用 `truststore` 改用作業系統的憑證庫驗證；還是失敗時才改用不驗證憑證的方式下載，並印出提示。
- **輸出**：`NHI_EnteroviralInfection.csv`（約 19 萬筆、8 MB）
- **執行**：`python 第03題_腸病毒資料/main.py`

### 第 4 題：博客來「演算法」書籍
- **題目**：`https://search.books.com.tw/search/query/key/{0}/cat/all`，`{0}` = 演算法；存入 `booklist.csv`，欄位 書名、網址、作者、書價。課堂補充：要把 URL 抓到的資料整理成 JSON 格式，再跑過裡面的內容。
- **做法**：博客來有 Cloudflare 防護，requests 會被擋（403），改用 Selenium 開 Chrome 載入題目網址，再用 BeautifulSoup 解析每本書：書名、作者、書價（優惠後售價，元）、網址（換成正式商品頁 `https://www.books.com.tw/products/商品編號`）。
  博客來的搜尋網址回傳的是 HTML（網站沒有 JSON 介面），所以把解析結果整理成 JSON 格式（一本書一個物件）存成 `booklist.json`，再讀回 JSON、用迴圈逐筆跑過裡面的每本書，寫入 `booklist.csv`。
- **範圍**：題目網址就是搜尋結果第 1 頁（60 本）。換到第 2 頁時博客來會跳出「Verify you are human」真人驗證，程式不繞過驗證，所以只抓題目指定的網址。
- **輸出**：`booklist.json`（JSON 格式）、`booklist.csv`
- **執行**：`python 第04題_博客來書籍/main.py`

### 第 5 題：開眼台北週末票房排行榜
- **題目**：按「票房排行榜」→ 列出台北排行榜的排名、片名、票房 → 按 more → 20 筆存入 `Taipei_movies.csv`（排名、片名、本週票房、累計票房）。課堂補充：要模擬滑鼠移動及點選。
- **做法**：Selenium `ActionChains`：滑鼠移到「電影」選單展開 → 點「票房排行榜」→ 印出台北前 5 名 → 點台北排行榜的「more」→ 讀出 20 筆（每部電影在網頁上占兩列，第二列才是票房數字）。
- **網站干擾的處理**：點連結時偶爾會跳出 Google 全版廣告（網址出現 `#google_vignette`），程式會像真人一樣按「關閉」再繼續；票房網站偶爾連線逾時，會自動重新整理再試。
- **輸出**：`Taipei_movies.csv`（金額單位：萬新台幣）
- **執行**：`python 第05題_台北票房排行榜/main.py`

### 第 6 題：NBA 球隊球員（Basketball Reference）
- **題目**：`https://www.basketball-reference.com/teams/{0}/2024.html`，抓 CLE、HOU、GSW 三隊，欄位 球隊、背號、姓名、位置、體重、生日、經驗、大學，存入 `players.csv`。課堂補充：要找到指定隊伍 Roster & Stats 頁面的球員資料。
- **做法**：題目網址就是各隊的「Roster & Stats」頁。requests 下載三隊頁面 → BeautifulSoup 找 `table#roster`（Roster 名單），依每格的 `data-stat` 屬性取值。三隊之間間隔 3 秒，避免請求太快被封鎖。
- **資料說明**：體重單位為磅；經驗 `R` 代表新秀；沒讀大學的球員「大學」為空白。
- **輸出**：`players.csv`（三隊共 53 位；檔名依 PDF 題目，課堂筆記寫的是 player.csv）
- **執行**：`python 第06題_NBA球隊球員/main.py`

### 第 7 題：Google Books API
- **題目**：用題目給的 `url_params = {'q': 'Python', 'maxResults': 10, 'projection': 'lite'}` 呼叫 API，本頁存入 `pythonbook.csv`，再進入下一頁存入同一個檔案（共兩頁）。
- **做法**：第 1 頁以「覆蓋」模式寫入（含標題列）；下一頁＝加上 `startIndex=10`，以「附加」模式寫入同一個檔案。從 JSON 的 `items[].volumeInfo` 取書名、作者、出版社、出版日期、網址。
- **需要 API 金鑰**：Google 目前常拒絕「不帶金鑰」的呼叫（回傳 429，配額為 0）。請到 [Google Cloud Console](https://console.cloud.google.com/apis/library/books.googleapis.com) 啟用 Books API 並建立 API 金鑰，再設定環境變數後執行：
  ```bash
  set GOOGLE_BOOKS_API_KEY=你的金鑰            # Windows（cmd）
  $env:GOOGLE_BOOKS_API_KEY="你的金鑰"         # Windows（PowerShell）
  export GOOGLE_BOOKS_API_KEY=你的金鑰         # macOS / Linux
  python 第07題_GoogleBooks_API/main.py
  ```
  金鑰不要寫進程式或上傳到 GitHub。
- **輸出**：`pythonbook.csv`（頁數、書名、作者、出版社、出版日期、網址；20 筆）

### 第 8 題：開眼近期上映強片
- **題目**：列出「所有」近期上映強片的名稱、上映時間、連結網址，存入 `movies.csv`。課堂補充：沒有這個區塊可改找其他適合的標籤。
- **做法**：開眼改版後，「近期上映強片」輪播（和題目附圖相同）從 `/movie/new/` 移到電影首頁 <https://www.atmovies.com.tw/movie/>，所以改抓這一頁。輪播畫面一次只顯示 4 部，但 HTML 裡有全部卡片，BeautifulSoup 全部讀出。
- **輸出**：`movies.csv`（名稱、上映時間、連結網址）
- **執行**：`python 第08題_近期上映強片/main.py`

### 第 9 題：Google 新聞
- **題目**：用 Selenium 輸出 焦點提要：[焦點新聞，地方新聞]，以及焦點新聞、地方新聞、您的主題、更多新聞的所有新聞標題。課堂補充：要用 Selenium 找到網頁標題。
- **做法**：開啟 Google 新聞（台灣繁中版），印出網頁標題 → 捲到頁面最底讓新聞全部載入 → 用 XPath 依「區塊標題文字」找到四個分類，再從標題往上找出含新聞連結的範圍，讀出所有標題（以網址去重）。
- **輸出**：依題目格式印出，另存 `google_news.csv`（分類、標題、網址）。新聞內容即時變動；「地方新聞」依連線所在地區顯示。
- **執行**：`python 第09題_Google新聞/main.py`

### 第 10 題：PTT 八卦板
- **題目**：用 Selenium 解決分級問題 → 列出網站 title → 列出文章列表（網址、標題、作者）。課堂補充：Cookie `over18` 的值為 1 即視為已成年。
- **做法**：開啟八卦板後網站會先轉到分級確認頁，Selenium 點「我同意，我已年滿十八歲」，網站就會設定 Cookie `over18=1`（程式會印出確認）。之後印出網站 title，並依題目範例的格式（網址／標題／作者各一行）印出本頁每篇文章；已刪除的文章沒有連結，略過。
- **輸出**：印出列表，另存 `ptt_gossiping.csv`。最新一頁的文章數會隨時間變動（含置底公告）。
- **執行**：`python 第10題_PTT八卦板/main.py`

### 第 11 題：NBA 商品資料
- **題目**：列出所有商品；每存完一個 CSV 就印出「儲存頁面: 編號」；分頁存成 `NBA_Products{1~n}.csv`；CSV 不能亂碼。課堂補充：要點到最後一頁，第 1～n 頁各存一個檔案（像 Excel 底下的頁籤）。
- **做法**：表格由 JavaScript 產生、一次 10 筆，Selenium 讀完一頁就存檔並印出「儲存頁面: n」，再按「下一頁 >」，直到最後一頁沒有下一頁按鈕。CSV 用 `utf-8-sig`（含 BOM），Excel 開啟中文不亂碼。重新執行前會先刪除舊的 `NBA_Products*.csv`。
- **輸出**：`NBA_Products1.csv`～`NBA_Products17.csv`（共 165 筆）
- **執行**：`python 第11題_NBA商品資料/main.py`

### 第 12 題：Google 搜尋「Steam 遊戲推薦」
- **題目**：用 Selenium 和 WebDriver，列出搜尋結果及其超連結，存入 CSV。
- **做法**：Google 首頁搜尋框自動輸入關鍵字並按 Enter → 讀出 `#search` 裡每筆結果的標題（`h3`）與連結（外層 `a` 的 href）。
- **Google 機器人驗證**：Google 常把自動化瀏覽器判定為機器人，跳出「我不是機器人」驗證。程式不會自動破解驗證，會在終端機提示，請在 Chrome 視窗中手動完成，程式最多等 5 分鐘後繼續。
- **輸出**：`steam_games.csv`（標題、網址）
- **執行**：`python 第12題_Google搜尋Steam遊戲推薦/main.py`

### 第 13 題：momo 搜尋 nba
- **題目**：開啟題目給的 momo 網址，自動輸入 nba，存檔為 `NBA_test.html`。
- **做法**：Selenium 找到搜尋框自動輸入 nba 並按 Enter，等商品載入後把網頁原始碼存檔。存檔前移除 `<script>`、加上 `<base>`，讓檔案用瀏覽器打開時版面與商品圖片都正常顯示。
- **輸出**：`NBA_test.html`（可直接用瀏覽器打開）
- **執行**：`python 第13題_momo搜尋nba/main.py`

### 第 14 題：HoopsHype 球員薪水
- **題目**：用 Selenium 和 BeautifulSoup，前 3 位高薪球員的名字、背號、薪資存入 `highest.csv`；本頁表格所有內容存入 `all_play.csv`。
- **做法**：薪資表現在改成分頁（每頁 20 位、共 30 頁），Selenium 逐頁按下一頁，每頁交給 BeautifulSoup 解析，全部存成 `all_play.csv`。表格依本季薪資由高到低排列，前 3 位的背號表格上沒有，所以再打開他們的個人頁讀出姓名與背號（例如 #30）。
- **輸出**：`all_play.csv`（排名、球員、各球季薪資；`P`／`T` 是網站標示的球員／球隊選擇權）、`highest.csv`（名字、背號、薪資）
- **執行**：`python 第14題_NBA球員薪水/main.py`

### 第 15 題：Google 搜尋「xpath」
- **題目**：用 WebDriver 在搜尋列輸入 xpath，滾動滑鼠抓取全部資料並列印本頁資訊，再按「更多結果」取得更多資訊，存入 `xpath.csv`。課堂補充：要由程式模擬滑鼠滾動。
- **做法**：自動輸入 xpath 並搜尋 → 用 `ActionChains.scroll_by_amount` 模擬滑鼠滾輪一路捲到底 → 印出本頁結果 → 按「更多結果」後再捲動、讀取，合併存檔。
  Google 已取消無限捲動的「更多結果」按鈕，改回分頁「下一頁」，所以程式會先找「更多結果」，沒有就按「下一頁」，一樣是取得更多結果。
- **Google 機器人驗證**：同第 12 題，遇到時請在 Chrome 視窗中手動完成。
- **輸出**：`xpath.csv`（標題、網址）
- **執行**：`python 第15題_Google搜尋xpath/main.py`

### 第 16 題：Agoda 台中飯店
- **題目**：輸入「台中」，結果頁的飯店名及價格存入 `agoda_result.csv`；加分：用 Selenium 及 WebDriver 自動輸入「台中」。
- **做法**（含加分項）：Selenium 在首頁搜尋框自動輸入「台中」→ 點建議清單的「台中市」→ 按 Esc 關掉自動跳出的日曆（沿用網站預設日期）→ 按「搜出好價」→ 切到結果的新分頁 → 慢慢往下捲讓飯店卡片載入，用 BeautifulSoup 讀出飯店名與價格。已額滿、沒有價格的飯店略過。
- **輸出**：`agoda_result.csv`（飯店名、價格；價格為每晚、不含稅及其他費用，會隨查詢日期變動）
- **執行**：`python 第16題_Agoda台中飯店/main.py`

### 第 17 題：GitHub 自動登入
- **題目**：用 Selenium 及 WebDriver 自動登入帳號，抓取附圖 1 號視窗與 2 號視窗的頁面資料。課堂補充：難點在登入表單裡隱藏的 key 值。
- **做法**：
  1. 執行時在終端機輸入 GitHub 帳號、密碼（密碼不會顯示、不會存檔）；也可事先設定環境變數 `GITHUB_USERNAME`、`GITHUB_PASSWORD`。
  2. Selenium 開啟登入頁，自動填入帳密並按 Sign in。登入表單裡有 `authenticity_token` 等隱藏欄位（就是「隱藏的 key 值」，每次開頁都不同）：用 requests 登入要自己先從網頁抓出來、跟帳密一起送出；用 Selenium 是在瀏覽器裡按登入，瀏覽器會自動送出。程式會找出這些隱藏欄位，印出欄位名稱和 `authenticity_token` 的開頭幾個字元。
  3. 若有二階段驗證，請在 Chrome 視窗中完成，程式最多等 5 分鐘。
  4. 登入後抓首頁：**1 號視窗＝左欄**（新帳號顯示「Create your first project」，已有專案的帳號顯示「Top repositories」）；**2 號視窗＝中間主欄**（附圖當時是「Updates to your homepage feed」提示卡，改版後是首頁動態面板）。依區塊位置抓取，新舊版首頁都適用。
- **輸出**：印出兩個視窗的內容，另存 `github_dashboard.csv`（視窗、內容）與登入後截圖 `github_dashboard.png`。這兩個檔案含個人帳號資料，已列入 `.gitignore`，不會上傳。
- **執行**：`python 第17題_GitHub登入首頁/main.py`

---

## 五、網站改版造成與題目附圖不同的地方

| 題 | 改版情形 | 本程式的處理 |
|:-:|---|---|
| 2 | 臺銀加了瀏覽器驗證，requests 拿不到匯率表 | 用 Selenium 載入，再用 BeautifulSoup 解析 |
| 3 | 平臺用資料集全名搜尋時，目標資料集不在第一頁 | 改用「腸病毒」搜尋 |
| 4 | 博客來有 Cloudflare 防護（requests 403），換頁會要求真人驗證 | 用 Selenium 載入題目網址（第 1 頁） |
| 5 | 點連結會跳出 Google 全版廣告；票房網站偶爾逾時 | 自動按「關閉」；逾時自動重新整理 |
| 7 | Google Books API 不帶金鑰常回傳 429 | 支援環境變數 `GOOGLE_BOOKS_API_KEY` |
| 8 | 「近期上映強片」移到電影首頁 `/movie/` | 改抓電影首頁同名區塊 |
| 14 | 薪資表改為分頁 | 逐頁讀完全部資料 |
| 15 | 「更多結果」按鈕改為「下一頁」 | 先找「更多結果」，沒有就按「下一頁」 |
| 17 | GitHub 首頁改版 | 依左欄／中間主欄位置抓取 |

## 六、檔案結構

```
data-science-midterm/
├── README.md            本說明
├── requirements.txt     需要安裝的套件
├── run_all.py           一次執行多題
├── 第01題_本週新片/
│   ├── main.py          程式
│   └── new_movies.csv   輸出（重新執行會覆蓋）
├── 第02題_台銀牌價/
│   ├── main.py
│   └── bank.csv
└── …（第 03～17 題同樣的結構）
```

各資料夾裡附的輸出檔是 2026-10-14 實際執行的結果，網站資料會隨時間變動，重新執行即會更新。
