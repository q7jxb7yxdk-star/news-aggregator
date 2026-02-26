# 📰 香港新聞聚合器

自動抓取香港科技及旅遊新聞，輸出 JSON 資料，並透過靜態網頁呈現最新資訊。

![Python](https://img.shields.io/badge/Python-3.8+-blue?logo=python) ![License](https://img.shields.io/badge/License-MIT-green) ![News Sources](https://img.shields.io/badge/新聞來源-6個-orange)

---

## 📋 目錄

- [功能特色](#功能特色)
- [專案結構](#專案結構)
- [新聞來源](#新聞來源)
- [安裝與使用](#安裝與使用)
- [輸出格式](#輸出格式)
- [網頁介面](#網頁介面)
- [技術架構](#技術架構)
- [設定說明](#設定說明)

---

## ✨ 功能特色

- 🔄 **自動抓取** — 同時從 6 個香港新聞網站抓取科技與旅遊新聞
- ⚡ **多線程執行** — 使用 `ThreadPoolExecutor` 並行處理，大幅縮短抓取時間
- 📡 **雙模式支援** — HTML 爬蟲 + RSS 解析，根據各網站特性選擇最佳方式
- 🧹 **智慧過濾** — 自動排除廣告、優惠碼、酒店、信用卡等不相關內容
- 🔁 **自動重試** — 網路錯誤時自動重試最多 3 次
- 🗑️ **去除重複** — 以文章連結為基礎，自動刪除重複新聞
- 💾 **JSON 輸出** — 結果儲存為結構化 JSON，方便整合至任何平台
- 🌐 **靜態網頁** — 提供美觀的前端介面，支援搜尋、篩選與響應式設計

---

## 📁 專案結構

```
.
├── scraper.py    # 主爬蟲程式（Python）
├── news.json     # 抓取結果輸出（自動生成）
└── index.html    # 新聞展示網頁（靜態前端）
```

---

## 📰 新聞來源

| 來源 | 分類 | 抓取方式 |
|------|------|----------|
| [Unwire.hk](https://unwire.hk) | 科技 | RSS |
| [E-zone](https://ezone.hk) | 科技 | HTML 爬蟲 |
| [NewMobileLife](https://www.newmobilelife.com) | 科技 | HTML 爬蟲 |
| [HolidaySmart](https://holidaysmart.io/hk) | 旅遊 | HTML 爬蟲 |
| [MeetHK](https://www.meethk.com/category/flight/) | 旅遊 | HTML 爬蟲 |
| [FlyDay.hk](https://flyday.hk) | 旅遊 | RSS（機票專項過濾）|

---

## 🚀 安裝與使用

### 1. 安裝依賴套件

```bash
pip install requests feedparser beautifulsoup4
```

### 2. 執行爬蟲

```bash
python scraper.py
```

執行完成後，會在同目錄生成 `news.json` 檔案。

### 3. 查看網頁

直接用瀏覽器開啟 `index.html`，即可瀏覽最新新聞。

> **注意：** `index.html` 會自動讀取同目錄下的 `news.json`，請確保兩個檔案放在同一個資料夾內。

### 自動化排程（選用）

可搭配排程工具定期自動執行，例如每小時更新一次：

```bash
# Linux / macOS（crontab）
0 * * * * cd /path/to/project && python scraper.py

# Windows（工作排程器）
schtasks /create /tn "NewsScraper" /tr "python C:\path\to\scraper.py" /sc hourly
```

---

## 📄 輸出格式

`news.json` 的結構如下：

```json
{
  "update_time": "2026-02-26 11:56:58",
  "total": 71,
  "news": [
    {
      "title": "Samsung 發佈 Galaxy S26 系列　首創隱私螢幕與深度 AI 整合功能",
      "link": "https://www.newmobilelife.com/2026/02/26/samsung-galaxy-s26-whatsnew/",
      "source": "NewMobileLife",
      "category": "科技",
      "scraped_at": "2026-02-26 11:56:55"
    }
  ]
}
```

| 欄位 | 說明 |
|------|------|
| `update_time` | 本次抓取的完成時間（香港時間 UTC+8）|
| `total` | 本次共抓取的新聞總數 |
| `news[].title` | 新聞標題 |
| `news[].link` | 新聞原文連結 |
| `news[].source` | 新聞來源網站名稱 |
| `news[].category` | 分類（科技 / 旅遊）|
| `news[].scraped_at` | 該篇文章的抓取時間 |

---

## 🌐 網頁介面

`index.html` 為純靜態網頁，無需伺服器，直接以瀏覽器開啟即可使用。

**主要功能：**

- 🔍 **即時搜尋** — 輸入關鍵字即時過濾新聞標題
- 📂 **分類篩選** — 按「科技」或「旅遊」分類顯示
- 🏷️ **來源篩選** — 可單獨查看特定網站的新聞
- 📊 **統計資訊** — 顯示新聞總數、更新時間等摘要
- 📱 **響應式設計** — 手機、平板、桌機均可正常顯示
- ⬆️ **返回頂部** — 捲動頁面後可快速回到頁首

---

## 🏗️ 技術架構

```
scraper.py
├── Article            # 資料類別：儲存單篇新聞
├── ScraperConfig      # 設定類別：定義各網站爬取規則
├── URLValidator       # 網址驗證與正規化
├── ArticleValidator   # 文章內容驗證（標題長度、關鍵字過濾）
├── WebScraper         # HTML 網頁爬蟲
├── BaseRSSFetcher     # RSS 抓取器基礎類別
│   ├── UnwireRSSFetcher   # Unwire.hk 專用
│   └── FlyDayRSSFetcher   # FlyDay.hk 專用（含機票關鍵字過濾）
├── ScraperManager     # 統一管理所有爬蟲（多線程調度、去重）
└── DataStorage        # JSON 檔案輸出
```

---

## ⚙️ 設定說明

可在 `scraper.py` 頂部調整以下常數：

| 常數 | 預設值 | 說明 |
|------|--------|------|
| `MAX_NEWS_PER_SOURCE` | `15` | 每個來源最多抓取幾篇 |
| `REQUEST_TIMEOUT` | `10` | 網路請求逾時秒數 |
| `MAX_WORKERS` | `3` | 並行執行的爬蟲數量 |
| `MAX_RETRIES` | `3` | 失敗時的最大重試次數 |
| `RETRY_DELAY` | `1` | 重試間隔秒數 |
| `TIMEZONE_OFFSET` | `8` | 時區偏移（UTC+8，香港時間）|

如需新增新聞來源，可在 `SCRAPERS_CONFIG` 字典中加入新的 `ScraperConfig`，或繼承 `BaseRSSFetcher` 建立新的 RSS 抓取器。
