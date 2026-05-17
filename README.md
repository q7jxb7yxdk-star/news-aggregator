# 香港新聞聚合器

這個專案會自動抓取香港新聞、科技資訊和旅遊優惠，輸出成 `news.json`，再由 `index.html` 以靜態網頁方式顯示。

## 功能

- 抓取新聞、科技和旅遊來源
- 點新聞分拆為港聞、兩岸、國際、財經
- 支援 HTML、RSS 和專用網站解析器
- 可自訂來源抓取順序
- 自動過濾不相關內容
- 同一來源內按連結去重
- 輸出 UTF-8 JSON
- 網頁支援搜尋、分類篩選和來源篩選
- 選擇分類後，來源會自動只顯示該分類可用來源

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
pip install requests feedparser beautifulsoup4
```

## 執行抓取

在專案目錄執行：

```bash
python scraper.py
```

完成後會更新 `news.json`。

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

抓取順序由 `scraper.py` 內的 `FETCHERS` 控制。

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

請看 `TECHNICAL_DOCUMENTATION.md`。
