# Technical Documentation

本文說明新聞聚合器的程式結構、資料流程、抓取器設計和擴充方式。

## 系統概覽

專案由兩部分組成：

| 檔案 | 角色 |
|---|---|
| `scraper.py` | 抓取新聞、過濾、去重、輸出 `news.json` |
| `index.html` | 讀取 `news.json`，提供搜尋和篩選介面 |

整體流程：

```text
scraper.py
  -> FETCHERS 依序執行
  -> 每個 Fetcher 回傳 Article list
  -> ScraperManager 去重
  -> DataStorage 寫入 news.json
  -> index.html 讀取 news.json
  -> 使用者在網頁搜尋和篩選
```

## 後端入口

`scraper.py` 的入口是：

```python
if __name__ == '__main__':
    main()
```

`main()` 執行步驟：

1. 記錄「開始抓取新聞」
2. 建立 `ScraperManager(FETCHERS)`
3. 執行 `scrape_all()`
4. 記錄總篇數
5. 用 `DataStorage.save()` 寫入 `news.json`

## 核心資料結構

### Artificial Analysis 排行榜

`ArtificialAnalysisFetcher` 讀取官方 Intelligence Index 與 Coding Agent Index 頁面。解析 `<script>` 中 Next.js Flight 的 JSON 字串，依傳輸順序串接，再解析資料記錄及跨記錄參照；不執行頁面 JavaScript。

- Intelligence：讀取頁面 `manifest` 的官方 `/data/<hex>.txt` 檔案及公開解碼參數，依官方前端格式使用 AES-256-GCM 解碼（nonce 為 key 的 SHA-256 前 12 bytes），再 gzip 解壓及解析 JSON。使用完整 `models` 的 `intelligenceIndex`，不使用只有預設項目的 `initialModels` 作為成功結果。資料路徑固定在官方網域並驗證格式。
- Coding Agent：使用完整 `benchmarkRows`，僅納入 `isRouter == false` 的項目，再以 `indexScore × 100` 排序；不依 `isDefault` 過濾，保留 `displayLabel` 的代理名稱、模型名稱與設定。Router 標記缺失時判為解析失敗。
- 保留官方原始分數精度排序；原始分數相同時同名次，下一名跳號。介面顯示一位小數，所以顯示值相同不一定同名次。
- 不套用新聞當天／24 小時篩選、每來源 15 篇上限或預設模型篩選。納入所有有該指數官方分數的項目；缺少分數的模型不列入，也不當作零分。
- `RankingArticle` 繼承 `Article`，額外輸出 `rankings`（`rank`、`name`、`score`）、`ranking_scope`、`stale`、`ranking_status`（`ok`／`stale`／`unavailable`）。不變更一般新聞資料結構。
- 每個榜單分開處理失敗（含完整資料下載或解碼失敗），保留該榜單舊資料、原 `scraped_at` 及原 `ranking_scope`，並標記 `stale`。不把舊的部分排名誤標為完整排名。沒有舊資料時輸出空榜單及 `unavailable`。
- Coding Agent 快取僅接受 `ranking_scope` 與目前排除 Router models 的範圍一致者；舊的包含 Router models 或未確認範圍資料不作降級備援，避免更新失敗後重新顯示 Router models。

現有 Actions 執行 `scraper.py` 時會一併更新這兩個榜單，依賴套件增加 `cryptography`（完整 Intelligence 資料解碼），不需要新增排程。官方未提供這兩個圖表的公開 API；頁面結構或資料格式改變時可能需要維護解析器。

前端 `renderRanking()` 使用原生 `<details>` 建立兩個整行、可鍵盤展開的項目，表格支援水平捲動；名稱與時間經 HTML escaping，官方連結使用現有 URL 驗證。來源、分類及標題搜尋沿用原有流程。

2026-11-07 驗證：Intelligence Index 維持 109 項；Coding Agent Index 排除 4 個 Router 組合後為 29 項，保留不同推理設定。數量隨官方資料改變，不作固定上限。Router 篩選、排序及快取範圍檢查通過。尚未完成實際瀏覽器版面及互動驗證，也未執行整輪新聞抓取。

### Article

`Article` 是每篇新聞的標準格式。

```python
@dataclass
class Article:
    title: str
    link: str
    source: str
    category: str
    scraped_at: str = None
```

如果沒有傳入 `scraped_at`，會自動使用香港時間。

### ScraperConfig

`ScraperConfig` 用於通用 HTML 抓取器。

```python
@dataclass
class ScraperConfig:
    url: str
    source: str
    category: str
    min_title_length: int
    selector: str = 'a'
    domain_check: Optional[str] = None
    url_pattern: Optional[str] = None
    exclude_titles: Optional[List[str]] = None
    base_url: Optional[str] = None
    fallback_url: Optional[str] = None
```

適合 HTML 結構簡單、只需要 CSS selector 和基本過濾的來源。

## 抓取器介面

所有抓取器都統一提供：

```python
def fetch(self) -> List[Article]:
    ...
```

這樣 `ScraperManager` 不需要知道每個來源是 HTML、RSS 還是特殊解析，只需要依序呼叫 `fetch()`。

## FETCHERS

`FETCHERS` 是目前最重要的來源設定。

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

特點：

- 順序就是實際抓取順序
- 順序也是 Terminal 顯示順序
- 新增來源後必須加入這裡
- 不再需要獨立的 `FETCH_ORDER`

## 抓取器類型

### WebScraper

通用 HTML 抓取器。

主要職責：

- 建立 `requests.Session`
- 下載 HTML
- 失敗時重試
- 用 BeautifulSoup 和 CSS selector 找出連結
- 套用 `ArticleValidator`
- 回傳 `Article` 清單

目前 `MeetHK` 透過 `ConfigFetcher(ScraperConfig(...))` 使用這個流程。

### ConfigFetcher

`ConfigFetcher` 是包裝器，讓通用 HTML 設定也能符合統一 `fetch()` 介面。

```python
class ConfigFetcher:
    def __init__(self, config: ScraperConfig):
        self.config = config
        self.source = config.source

    def fetch(self) -> List[Article]:
        return WebScraper(self.config).scrape()
```

### BaseRSSFetcher

RSS 抓取器基礎類別。

主要流程：

- 依序下載主 RSS feed 和備用 RSS feed
- 用 `feedparser.parse()` 解析
- 讀取 `title` 和 `link`
- 回傳最多 `MAX_NEWS_PER_SOURCE` 篇

如果主 RSS feed 失敗，`BaseRSSFetcher` 會自動改試 `fallback_feed_urls`。`FlyDayRSSFetcher` 繼承它後再做機票內容過濾。

### 專用 Fetcher

以下來源使用專用 Fetcher，因為它們需要日期判斷、特殊 HTML 結構、分頁或額外過濾。

| Fetcher | 來源 | 特點 |
|---|---|---|
| `NowSportsFetcher` | Now Sports | 官方足球新聞及精華，24 小時、按類型與 ID 去重、各類型獨立回退 |
| `DotDotNewsFetcher` | 點新聞 | 多分類、分頁、按日期範圍抓取 |
| `EdigestRSSFetcher` | 經濟一週 | RSS 抓取當天即時財經；當天沒有內容時抓最新發布日期 |
| `EzoneFetcher` | E-zone | 只保留當天科技焦點 |
| `NewMobileLifeFetcher` | NewMobileLife | 只保留當天最新文章 |
| `UnwireFetcher` | Unwire.hk | 首頁文章，只保留當天或 24 小時內 |
| `FlyDayRSSFetcher` | FlyDayhk | 先抓官方 RSS，失敗時改用 Google RSS 備用來源，再過濾機票優惠 |

## 來源規則

| 來源 | 類別 | 日期規則 |
|---|---|---|
| 點新聞-港聞 | 新聞 | 當天 |
| 點新聞-兩岸 | 新聞 | 今天和昨天 |
| 點新聞-國際 | 新聞 | 當天 |
| 點新聞-財經 | 新聞 | 當天；當天沒有內容時抓最近一天 |
| 經濟一週 | 新聞 | RSS 即時財經當天；當天沒有內容時抓最近一天 |
| E-zone | 科技 | 當天 |
| NewMobileLife | 科技 | 當天 |
| Unwire.hk | 科技 | 當天或 24 小時內 |
| FlyDayhk | 旅遊 | RSS 最新內容，並過濾機票相關；主來源不可用時使用 Google RSS 備用來源 |
| MeetHK | 旅遊 | 通用 HTML 規則，並排除酒店、優惠碼等內容 |

## 去重邏輯

`ScraperManager._deduplicate()` 使用以下 key 判斷重複：

```python
key = (a.source, a.link)
```

也就是同一來源內相同連結只保留一次。不同來源即使連結相同，也會視為不同新聞。

## 輸出

`DataStorage.save()` 會把資料寫入 `news.json`。

```json
{
  "update_time": "2026-05-17 10:00:00",
  "total": 190,
  "news": []
}
```

注意：前端目前會讀取 `data.total_count || allNews.length` 顯示總數；後端輸出欄位是 `total`。因為有 `allNews.length` fallback，所以畫面仍可正確顯示。

## 前端資料流程

`index.html` 的主要流程：

1. `DOMContentLoaded` 後執行 `loadNews()`
2. `fetch('news.json')`
3. 將 `data.news` 存入 `allNews`
4. `initializeFilters()` 產生分類按鈕
5. `renderSourceFilters()` 根據目前分類產生來源按鈕
6. `displayNews(allNews)` 顯示新聞卡片

## 前端篩選邏輯

篩選狀態保存在：

```javascript
let currentFilters = {
    category: 'all',
    source: 'all',
    search: ''
};
```

`filterNews()` 依序處理：

1. 如果目前來源不屬於目前分類，自動重置來源為 `all`
2. 按分類過濾
3. 按來源過濾
4. 按標題關鍵字過濾
5. 重新顯示新聞
6. 更新「清除篩選」按鈕

## 動態來源篩選

`renderSourceFilters()` 會根據目前分類重新產生來源按鈕。

例如分類選擇「科技」時，只會從科技新聞中收集來源，所以來源會顯示：

```text
E-zone
NewMobileLife
Unwire.hk
```

這個邏輯不需要手動維護來源列表，會直接根據 `news.json` 內容更新。

## 新增通用 HTML 來源

適合頁面結構簡單的來源。

範例：

```python
FETCHERS = {
    ...
    'Example': ConfigFetcher(ScraperConfig(
        url='https://example.com/news',
        source='Example',
        category='科技',
        min_title_length=8,
        selector='h2 a',
        domain_check='example.com',
        base_url='https://example.com',
        exclude_titles=['廣告', '優惠碼']
    ))
}
```

## 新增專用來源

如果來源需要特殊邏輯，新增 class：

```python
class ExampleFetcher:
    source = 'Example'
    category = '科技'

    def fetch(self) -> List[Article]:
        articles = []
        ...
        return articles
```

然後加入：

```python
FETCHERS = {
    ...
    'Example': ExampleFetcher()
}
```

## 常見維護位置

| 需求 | 修改位置 |
|---|---|
| 改抓取順序 | `FETCHERS` |
| 改來源網址 | 對應 Fetcher 的 `URL` 或 `ScraperConfig.url` |
| 改日期範圍 | 對應 Fetcher 的日期判斷 |
| 改每個來源最多數量 | `MAX_NEWS_PER_SOURCE` |
| 改逾時 | `REQUEST_TIMEOUT` |
| 改前端來源圖標 | `index.html` 的 `sourceIcons` |
| 改前端分類順序 | `index.html` 的 `categoryOrder` |

## 注意事項

- Unwire.hk 使用首頁，不使用 fallback。
- 點新聞財經目前使用 `https://www.dotdotnews.com/finance`，優先保留香港時間當天文章；如果當天沒有內容，會改抓最近一天的文章。
- 經濟一週使用即時財經分類 RSS：`https://www.edigest.hk/category/投資/news/feed/`，優先保留香港時間當天文章；如果 RSS 當天沒有內容，會改抓最近一天的文章。
- FlyDayhk 優先使用 `https://flyday.hk/feed/`，不使用首頁，因為首頁有 Cloudflare 保護；如果官方 RSS 回 403，會改用 Google RSS 備用來源。
- 所有時間判斷以香港時間 UTC+8 為準。

## 建議測試

修改抓取邏輯後建議檢查：

```bash
python scraper.py
```

再確認：

- Terminal 每個來源篇數是否合理
- `news.json` 是否成功更新
- `index.html` 能否正常顯示
- 分類和來源篩選是否正確

## Now Sports 雲端足球新聞及精華

`NowSportsFetcher`、`NowSportsArticle` 與其驗證邏輯均在 `scraper.py`，
由 `FETCHERS` 與其他來源一起執行，統一輸出至 `news.json` 的 `news` 陣列。
足球項目另含 `published_at`、`observed_at`、`content_type=news` 或 `content_type=video` 及
`published_at_precision=exact`；來源為 `Now Sports`，分類為「足球」。
不需要獨立收集程式、驗證模組或足球 JSON 檔案。

文字新聞從 `https://sportsapi.now.com/api/getNewsList` 讀取，tag 為 `soccerAllSearchTags`。
驗證 `newsId`、`headlineChi`、`publishDate`、足球分類及 `deleted`；
主分類 `sportTypeId=112` 或多重分類 `sportTypes` 中包含 `sportTypeId=112` 均接受，
例如主分類為網球但同時列入足球的拿度／皇馬新聞；兩者均不含足球時仍視為分類驗證失敗。
排除已刪除、未來或超過 24 小時的新聞，不保存內文或圖片。
原文連結格式為 `https://sports.now.com/home/news/details?id=<id>`。

從官方影片頁使用的 `https://sportsapi.now.com/api/getSoccerVideoList` 讀取六個足球分類。

| 分類 | area | 官方列表 tag |
|---|---|---|
| 英格蘭 | england | soccerEnglandSearchTags |
| 西班牙 | spain | soccerSpainSearchTags |
| 歐聯 | ucl | soccerUCLSearchTags |
| 歐霸／歐協 | uecl | soccerUECLSearchTags |
| 世界盃 | worldcup2026 | worldcup2026SearchTags |
| 其他足球 | otherSoccer | soccerOtherSearchTags |

每頁 12 筆，逐頁讀至不足一頁；不假設列表依發布日期排序，每類上限 50 頁；文字新聞同樣每頁 12 筆、上限 50 頁。
新聞與影片收集各有 10 分鐘時間預算，請求前檢查剩餘時間；每次請求 timeout 最多 20 秒，網路錯誤最多嘗試三次。
Requests timeout 是連線／讀取等待上限，不是整體執行的精確截止時間。

新聞列表成功後使用本次新聞結果，六個影片分類全部成功後使用本次影片結果，兩者獨立處理。
某類型請求、格式、重複頁或分頁上限檢查失敗，會記錄 warning，
並從寫入前的 `news.json` 保留該類型仍在 24 小時內且通過來源、分類、官方網址、內容類型與時間驗證的舊資料。
同一類型不混入部分完成的新資料；成功但沒有近期項目時不沿用該類型的舊資料。
舊資料的 `observed_at` 保持不變，避免把回退項目表示成新抓取結果。

`publishDate` 為毫秒 Unix 時間，以香港時間檢查過去 24 小時；
`onAirDate`／`offAirDate` 只判斷上架期限，不作發布時間替代值。
只儲存標題、時間與官方原文／觀看連結，不查詢播放串流。
觀看連結格式為 `https://sports.now.com/home/video#tvVideoId=<id>&type=<area>`。
足球收集與回退皆以 `news:<id>`／`video:<id>` 分開去重，然後按發布時間由新至舊排序。

`DataStorage.save()` 以同目錄暫存檔、flush／fsync 及原子替換寫入統一的 `news.json`。
`index.html` 只載入這份檔案，普通新聞依來源／連結去重，足球項目另檢查官方網址、新聞／影片 ID、連結與內容類型一致性、來源、分類、
發布／觀察時間及 24 小時期限。頁首統一以 `news.json.update_time` 顯示「新聞更新」時間，
新聞與影片卡片顯示各自類型標籤；不另列足球收集時間；足球項目的發布時間及有效期限檢查維持不變。

GitHub Actions 沿用每小時第 17 分鐘排程與 concurrency，只執行 `python scraper.py`，
提交清單只允許 `news.json`。push 競爭最多重試三次，每次 fetch／rebase；真正內容衝突會停止，沒有強制推送。
舊本機收集／推送程式、排程安裝器、Playwright 依賴清單及匯入入口已移除。
本機舊 LaunchAgent 已停用並卸載，plist 及整個專用資料目錄（登入資料、日誌、runtime、checkout）已刪除。

本地擷取成功不代表 GitHub Actions 或 GitHub Pages 已部署成功。
提交並推送後，須再核對 Actions 執行結果與線上的 JSON／網頁。
本流程不測試影片實際播放、地區或登入限制；觀看仍受官方網站及影片上架期限限制。
