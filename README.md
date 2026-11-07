# 香港新聞聚合器

這個專案會自動抓取香港新聞、科技資訊和旅遊優惠，另由 GitHub Actions 收集 Now Sports 足球新聞及精華。所有來源由 `scraper.py` 統一寫入 `news.json`，供網頁顯示。

## 功能

- 抓取新聞、科技和旅遊來源
- GitHub Actions 每小時收集 Now Sports 過去 24 小時的足球新聞及精華標題、發布時間與官方連結，無需本機 Chrome 或登入
- 點新聞分拆為港聞、兩岸、國際、財經
- 支援 HTML、RSS 和專用網站解析器
- 可自訂來源抓取順序
- 自動過濾不相關內容
- 同一來源內按連結去重
- 輸出 UTF-8 JSON
- 網頁支援搜尋、分類篩選和來源篩選
- 選擇分類後，來源會自動只顯示該分類可用來源
- 「科技」→「Artificial Analysis」提供兩個可展開的官方排行榜，直接顯示名次、模型／代理及評測設定、分數和擷取時間

## 檔案

```text
.
├── scraper.py                    # 主抓取程式
├── news.json                     # 抓取結果
├── index.html                    # 靜態新聞網頁
├── README.md                     # 使用說明
└── TECHNICAL_DOCUMENTATION.md    # 技術文件
```

## 安裝

需要 Python 3，並安裝以下套件：

```bash
python -m pip install requests feedparser beautifulsoup4 cryptography
```

使用 VS Code 時，先在「Python: Select Interpreter」選擇專案的 `.venv/bin/python`，並在已啟用 `.venv` 的 Terminal 執行上述安裝指令，確保套件與執行程式使用同一個 Python 環境。

## 執行抓取

在專案目錄執行：

```bash
python scraper.py
```

完成後會更新 `news.json`。

在 VS Code 也可右擊 `scraper.py`，選擇「Run Python File in Terminal」。這會抓取所有來源；若只測試網頁顯示，可直接使用現有 `news.json`，無需先執行抓取。

Terminal 會依抓取順序顯示每個來源的結果，例如：

```text
2026-05-13 17:02:17,980 - INFO - 開始抓取新聞
2026-05-13 17:02:29,923 - INFO - ✓ 點新聞-港聞 抓取 51 篇
2026-05-13 17:02:29,923 - INFO - ✓ 點新聞-兩岸 抓取 47 篇
2026-05-13 17:02:29,923 - INFO - ✓ 點新聞-國際 抓取 27 篇
2026-05-13 17:02:29,923 - INFO - ✓ 點新聞-財經 抓取 10 篇
2026-05-13 17:02:30,528 - INFO - ✓ E-zone 科技焦點當天抓取 8 篇
2026-05-13 17:02:39,924 - INFO - 完成，共 190 篇
2026-05-13 17:02:39,925 - INFO - ✓ 已輸出 news.json
```

## 查看網頁

直接用瀏覽器開啟：

```text
index.html
```

如果瀏覽器因安全限制不能讀取本機 `news.json`，可在專案目錄開一個簡單本機伺服器：

```bash
python -m http.server 8000
```

然後打開：

```text
http://localhost:8000
```

## 新聞來源

| 來源 | 分類 | 網址 | 抓取範圍 |
|---|---|---|---|
| Now Sports | 足球 | `https://sports.now.com/home/video` | 足球新聞及六個足球分類的精華影片，過去 24 小時；由 GitHub Actions 更新 |
| 點新聞-港聞 | 新聞 | `https://www.dotdotnews.com/immed/hknews` | 當天 |
| 點新聞-兩岸 | 新聞 | `https://www.dotdotnews.com/immed/bothsides` | 今天和昨天 |
| 點新聞-國際 | 新聞 | `https://www.dotdotnews.com/immed/inter` | 當天 |
| 點新聞-財經 | 新聞 | `https://www.dotdotnews.com/finance` | 當天；當天沒有內容時抓最近一天 |
| 經濟一週 | 新聞 | `https://www.edigest.hk/category/投資/news/feed/` | RSS，即時財經當天；當天沒有內容時抓最近一天 |
| E-zone | 科技 | `https://ezone.hk/srae001/科技焦點/` | 當天 |
| NewMobileLife | 科技 | `https://www.newmobilelife.com/最新文章/` | 當天 |
| Unwire.hk | 科技 | `https://unwire.hk` | 當天最新文章 |
| Artificial Analysis | 科技 | [Intelligence Index](https://artificialanalysis.ai/evaluations/artificial-analysis-intelligence-index)、[Coding Agent Index](https://artificialanalysis.ai/agents/coding-agents) | 全部有官方分數的模型及設定，隨現有抓取流程更新；Coding Agent 不包括 Router models |
| FlyDayhk | 旅遊 | `https://flyday.hk/feed/` | RSS，機票相關內容；主來源 403 時改用 Google RSS 備用來源 |
| MeetHK | 旅遊 | `https://www.meethk.com/category/flight/` | 機票相關內容 |

## 抓取順序

Artificial Analysis 的兩個榜單各佔一行，點開即可查看排名。Intelligence Index 使用官方完整模型資料，Coding Agent Index 使用頁面完整代理／模型組合資料並排除 Router models。取消預設模型篩選，保留不同推理設定；只有該指數有官方分數的項目才列入，沒有分數的模型不會當成零分。按原始分數排序並顯示至小數一位；原始分數相同時使用相同名次，顯示值相同但原始分數不同時仍會有先後。

更新失敗時保留該榜單上次成功資料及原擷取時間，並顯示提示；首次讀取失敗時顯示暫時無法取得排名。官方頁面格式變更可能需要調整解析器。

Coding Agent 的舊資料必須同樣排除 Router models 才可保留；若只有先前包含 Router models 的快取，更新失敗時會顯示暫時無法取得排名。

抓取順序由 `scraper.py` 內的 `FETCHERS` 控制。

```python
FETCHERS = {
    'Now Sports': NowSportsFetcher(),
    '點新聞': DotDotNewsFetcher(),
    '經濟一週': EdigestRSSFetcher(),
    'Artificial Analysis': ArtificialAnalysisFetcher(),
    'E-zone': EzoneFetcher(),
    'NewMobileLife': NewMobileLifeFetcher(),
    'Unwire.hk': UnwireFetcher(),
    'FlyDayhk': FlyDayRSSFetcher(),
    'MeetHK': ConfigFetcher(ScraperConfig(...))
}
```

程式會由上至下執行。要改順序，只需要調整 `FETCHERS` 內來源的排列。

`點新聞` 是一個總抓取器，內部會再依序抓取：

```text
點新聞-港聞
點新聞-兩岸
點新聞-國際
點新聞-財經
```

## 輸出格式

`news.json` 格式如下：

```json
{
  "update_time": "2026-05-17 10:00:00",
  "total": 190,
  "news": [
    {
      "title": "新聞標題",
      "link": "https://example.com/article",
      "source": "點新聞-港聞",
      "category": "新聞",
      "scraped_at": "2026-05-17 10:00:00"
    }
  ]
}
```

| 欄位 | 說明 |
|---|---|
| `update_time` | 本次更新時間 |
| `total` | 新聞總數 |
| `news[].title` | 新聞標題 |
| `news[].link` | 原文連結 |
| `news[].source` | 來源名稱 |
| `news[].category` | 分類 |
| `news[].scraped_at` | 抓取時間 |

## 網頁功能

`index.html` 是純靜態頁面，會讀取同目錄的 `news.json`。

主要功能：

- 顯示新聞列表
- 顯示更新時間和總文章數
- 搜尋新聞標題
- 按分類篩選
- 按來源篩選
- 分類改變後，來源按鈕會動態更新
- 清除所有篩選
- 返回頂部按鈕
- 手機和桌面響應式顯示

例如選擇「科技」後，來源只會顯示：

```text
E-zone
NewMobileLife
Unwire.hk
Artificial Analysis
```

## 重要設定

可在 `scraper.py` 調整：

| 設定 | 說明 |
|---|---|
| `FETCHERS` | 來源清單和抓取順序 |
| `MAX_NEWS_PER_SOURCE` | 每個通用來源最多抓取數量 |
| `REQUEST_TIMEOUT` | 網路請求逾時秒數 |
| `MAX_RETRIES` | 通用 HTML 抓取器重試次數 |
| `RETRY_DELAY` | 重試間隔 |
| `TIMEZONE_OFFSET` | 香港時區，預設 UTC+8 |

## 新增來源

如果新來源是一般 HTML 頁面，可用 `ConfigFetcher(ScraperConfig(...))` 加入 `FETCHERS`。

如果新來源有特殊日期、分頁、RSS 或過濾邏輯，建議新增一個專用 Fetcher class，並實作：

```python
def fetch(self) -> List[Article]:
    ...
```

完成後把它加入 `FETCHERS` 即可。

## 更多技術說明

請看 [[news-aggregator_TECHNICAL_DOCUMENTATION | Technical Documentation]]。

## Now Sports 足球新聞及精華

分類固定為「足球」，來源固定為「Now Sports」，不按聯賽細分。
只顯示新聞／精華標題、發布時間及官方原文／觀看連結；不下載、嵌入或重新託管影片。

GitHub Actions 沿用每小時第 17 分鐘的排程，執行 `scraper.py`，
將全部來源統一寫入 `news.json`。排程可能延遲，Mac 關機不影響雲端執行。
六個足球分類為英格蘭、西班牙、歐聯、歐霸／歐協、世界盃及其他足球。
文字新聞來自官方足球新聞列表，與六個影片分類分別收集。
新聞主分類或多重分類 `sportTypes` 包含足球（`sportTypeId=112`）即可通過分類驗證。
以官方 `publishDate` 判斷 24 小時期限，按內容類型及新聞／影片 ID 去重，再依發布時間排序。
新聞或影片請求、格式或分頁檢查失敗時，只保留舊 `news.json` 中該類型仍在 24 小時內且通過驗證的資料；
另一類型與其他來源仍可更新。某類型成功但沒有近期項目時，不沿用該類型的舊資料。
前端只讀取 `news.json`，載入時也會剔除超過 24 小時的足球資料。

分類設定、資料流程及驗證限制見 [技術文件](TECHNICAL_DOCUMENTATION.md#now-sports-雲端足球新聞及精華)。
