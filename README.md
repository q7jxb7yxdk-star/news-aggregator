# 香港新聞聚合器

自動抓取香港新聞、科技資訊和旅遊優惠，輸出 `news.json`，並透過 `index.html` 顯示最新內容。

## 專案檔案

```text
.
├── scraper.py    # 主爬蟲程式
├── news.json     # 抓取結果輸出
├── index.html    # 靜態新聞展示頁
└── README.md     # 專案說明
```

## 主要功能

- 抓取新聞、科技、旅遊相關來源
- 依來源自訂抓取順序
- 點新聞分拆為港聞、兩岸、國際、財經
- 依不同網站使用 HTML、RSS 或專用解析器
- 自動過濾不需要的內容
- 同一來源內根據連結去重
- 輸出 UTF-8 JSON
- 前端支援搜尋、分類篩選和來源篩選
- 選擇分類後，來源選項會按該分類動態顯示

## 新聞來源

| 來源 | 分類 | 網址 | 抓取範圍 |
|---|---|---|---|
| 點新聞-港聞 | 新聞 | `https://www.dotdotnews.com/immed/hknews` | 當天 |
| 點新聞-兩岸 | 新聞 | `https://www.dotdotnews.com/immed/bothsides` | 今天和昨天 |
| 點新聞-國際 | 新聞 | `https://www.dotdotnews.com/immed/inter` | 當天 |
| 點新聞-財經 | 新聞 | `https://www.dotdotnews.com/finance` | 今天和昨天 |
| E-zone | 科技 | `https://ezone.hk/srae001/科技焦點/` | 當天 |
| NewMobileLife | 科技 | `https://www.newmobilelife.com/最新文章/` | 當天 |
| Unwire.hk | 科技 | `https://unwire.hk` | 當天最新文章 |
| FlyDayhk | 旅遊 | `https://flyday.hk/feed/` | RSS，機票相關內容 |
| HolidaySmart | 旅遊 | `https://holidaysmart.io/hk` | 7 天內 |
| MeetHK | 旅遊 | `https://www.meethk.com/category/flight/` | 機票相關內容 |

## 抓取順序

抓取順序由 `scraper.py` 內的 `FETCH_ORDER` 控制。

```python
FETCH_ORDER = [
    '點新聞',
    'E-zone',
    'NewMobileLife',
    'Unwire.hk',
    'FlyDayhk',
    'HolidaySmart',
    'MeetHK'
]
```

程式會由上至下執行。要改順序，只需要調整這個清單，不需要移動 class 或 function 的代碼位置。

其中 `點新聞` 會在內部再依序抓取：

```text
點新聞-港聞
點新聞-兩岸
點新聞-國際
點新聞-財經
```

## 抓取器分類

`MeetHK` 使用通用 HTML 設定，放在 `SCRAPERS_CONFIG`。

```python
SCRAPERS_CONFIG = {
    'meethk': ScraperConfig(...)
}
```

其他來源使用專用抓取器，放在 `RSS_FETCHERS`。

```python
RSS_FETCHERS = {
    '點新聞': DotDotNewsFetcher(),
    'NewMobileLife': NewMobileLifeFetcher(),
    'E-zone': EzoneFetcher(),
    'Unwire.hk': UnwireFetcher(),
    'FlyDayhk': FlyDayRSSFetcher(),
    'HolidaySmart': HolidaySmartFetcher()
}
```

`RSS_FETCHERS` 名字沿用舊代碼，但現在不只包含 RSS，也包含專用 HTML 抓取器。

## 安裝

```bash
pip install requests feedparser beautifulsoup4
```

## 執行

在專案目錄執行：

```bash
python scraper.py
```

執行後會產生或更新：

```text
news.json
```

Terminal 會即時顯示每個來源抓取完成的結果，例如：

```text
2026-05-13 17:02:17,980 - INFO - 開始抓取新聞
2026-05-13 17:02:29,923 - INFO - ✓ 點新聞-港聞 抓取 51 篇
2026-05-13 17:02:29,923 - INFO - ✓ 點新聞-兩岸 抓取 47 篇
2026-05-13 17:02:29,923 - INFO - ✓ 點新聞-國際 抓取 27 篇
2026-05-13 17:02:29,923 - INFO - ✓ 點新聞-財經 抓取 10 篇
2026-05-13 17:02:20,028 - INFO - ✓ E-zone 科技焦點當天抓取 8 篇
2026-05-13 17:02:29,924 - INFO - 完成，共 190 篇
2026-05-13 17:02:29,925 - INFO - ✓ 已輸出 news.json
```

## 查看網頁

直接用瀏覽器開啟：

```text
index.html
```

`index.html` 會讀取同目錄的 `news.json`。

## 輸出格式

`news.json` 格式如下：

```json
{
  "update_time": "2026-05-14 10:00:00",
  "total": 190,
  "news": [
    {
      "title": "新聞標題",
      "link": "https://example.com/article",
      "source": "點新聞-港聞",
      "category": "新聞",
      "scraped_at": "2026-05-14 10:00:00"
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

## 前端功能

`index.html` 是純靜態頁面，主要功能包括：

- 顯示最新新聞
- 關鍵字搜尋
- 按分類篩選
- 按來源篩選
- 來源會根據分類動態顯示
- 顯示新聞統計和更新時間
- 支援桌面和手機瀏覽

例如選擇「科技」分類後，來源只會顯示：

```text
E-zone
NewMobileLife
Unwire.hk
```

## 重要設定

可在 `scraper.py` 調整：

| 設定 | 說明 |
|---|---|
| `FETCH_ORDER` | 自訂抓取順序 |
| `MAX_NEWS_PER_SOURCE` | 每個來源最多抓取數量 |
| `REQUEST_TIMEOUT` | 網路請求逾時秒數 |
| `MAX_RETRIES` | 通用 HTML 抓取器重試次數 |
| `RETRY_DELAY` | 重試間隔 |
| `TIMEZONE_OFFSET` | 香港時間 UTC+8 |

## 新增來源

如果新來源適合通用 HTML 抓取，可以加入 `SCRAPERS_CONFIG`。

如果新來源需要特殊日期、分頁或過濾邏輯，建議新增一個專用 Fetcher class，然後加入 `RSS_FETCHERS` 和 `FETCH_ORDER`。
