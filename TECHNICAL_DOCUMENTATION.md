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
    '點新聞': DotDotNewsFetcher(),
    'E-zone': EzoneFetcher(),
    'NewMobileLife': NewMobileLifeFetcher(),
    'Unwire.hk': UnwireFetcher(),
    'FlyDayhk': FlyDayRSSFetcher(),
    'HolidaySmart': HolidaySmartFetcher(),
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

- 下載 RSS feed
- 用 `feedparser.parse()` 解析
- 讀取 `title` 和 `link`
- 回傳最多 `MAX_NEWS_PER_SOURCE` 篇

`FlyDayRSSFetcher` 繼承它後再做機票內容過濾。

### 專用 Fetcher

以下來源使用專用 Fetcher，因為它們需要日期判斷、特殊 HTML 結構、分頁或額外過濾。

| Fetcher | 來源 | 特點 |
|---|---|---|
| `DotDotNewsFetcher` | 點新聞 | 多分類、分頁、按日期範圍抓取 |
| `EzoneFetcher` | E-zone | 只保留當天科技焦點 |
| `NewMobileLifeFetcher` | NewMobileLife | 只保留當天最新文章 |
| `UnwireFetcher` | Unwire.hk | 首頁文章，只保留當天或 24 小時內 |
| `FlyDayRSSFetcher` | FlyDayhk | RSS 後再過濾機票優惠 |
| `HolidaySmartFetcher` | HolidaySmart | 首頁找候選文章，再平行讀文章日期，只保留 7 天內 |

## 來源規則

| 來源 | 類別 | 日期規則 |
|---|---|---|
| 點新聞-港聞 | 新聞 | 當天 |
| 點新聞-兩岸 | 新聞 | 今天和昨天 |
| 點新聞-國際 | 新聞 | 當天 |
| 點新聞-財經 | 新聞 | 今天和昨天 |
| E-zone | 科技 | 當天 |
| NewMobileLife | 科技 | 當天 |
| Unwire.hk | 科技 | 當天或 24 小時內 |
| FlyDayhk | 旅遊 | RSS 最新內容，並過濾機票相關 |
| HolidaySmart | 旅遊 | 7 天內 |
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
- FlyDayhk 使用 `https://flyday.hk/feed/`，不使用首頁，因為首頁有 Cloudflare 保護。
- HolidaySmart 需要進入文章頁讀日期，因此比一般首頁解析慢；目前用 `ThreadPoolExecutor(max_workers=5)` 平行加速。
- 點新聞財經目前使用 `https://www.dotdotnews.com/finance`。
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
