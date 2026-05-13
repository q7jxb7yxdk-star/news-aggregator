# ============================================================================
# 這個Python 腳本的主要功能：
# 自動抓取新聞 - 從 5 個網站抓取科技和旅遊新聞
# 智慧過濾 - 排除廣告、優惠碼等不相關內容
# 去除重複 - 自動刪除重複的新聞
# 存成檔案 - 最後輸出成 news.json 檔案
# 執行後會產生一個包含所有新聞的 JSON 檔案，可以用在網站或 App 上顯示最新資訊！
# ============================================================================

# ============================================================================
# 匯入需要的工具包（像是借用別人寫好的工具）
# ============================================================================
import requests                                     # 用來訪問網頁，就像打開瀏覽器
import feedparser                                   # 用來讀取 RSS 新聞源（一種新聞格式）
from bs4 import BeautifulSoup                       # 用來解析網頁內容，找出我們要的資訊
import json                                         # 用來儲存資料成 JSON 格式（一種常見的資料格式）
from datetime import datetime, timedelta, timezone  # 處理時間日期
from typing import Dict, List, Optional, Set        # 用來標註變數類型，讓程式更清楚
from dataclasses import dataclass, asdict           # 用來建立資料結構
from pathlib import Path                            # 處理檔案路徑
import logging                                      # 記錄程式執行過程
from concurrent.futures import ThreadPoolExecutor, as_completed # 同時做多件事（多線程）
from urllib.parse import urljoin, urlparse          # 處理網址
import time                                         # 處理時間延遲
import re                                           # 用來比對文字格式

# ============================================================================
# 設定日誌系統（像是程式的日記本，記錄發生什麼事）
# ============================================================================
logging.basicConfig(
    level=logging.INFO,  # 記錄的詳細程度（INFO 是一般訊息）
    format='%(asctime)s - %(levelname)s - %(message)s' # 日誌格式：時間 - 等級 - 訊息
)
logger = logging.getLogger(__name__)  # 建立一個日誌記錄器

# ============================================================================
# 常數設定（整個程式會用到的固定數值）
# ============================================================================
# 假裝我們是 Chrome 瀏覽器（有些網站會檢查）
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'

MAX_NEWS_PER_SOURCE = 15  # 每個網站最多抓 15 篇新聞
REQUEST_TIMEOUT = 10      # 等待網站回應的時間上限（10 秒）
MAX_WORKERS = 3           # 同時處理 3 個網站（加快速度）
MAX_RETRIES = 3           # 如果失敗，最多重試 3 次
RETRY_DELAY = 1           # 重試之間等待 1 秒
TIMEZONE_OFFSET = 8       # 時區偏移（香港是 UTC+8）

# ============================================================================
# 資料類別定義（用來儲存新聞文章的資訊）
# ============================================================================
@dataclass
class Article:
    """
    儲存單篇新聞文章的資料結構
    就像一張表格，每一列是一篇新聞的資訊
    """
    title: str              # 新聞標題
    link: str               # 新聞連結
    source: str             # 新聞來源（例如：Unwire.hk）
    category: str           # 新聞分類（例如：科技、旅遊）
    scraped_at: str = None  # 抓取時間（預設是空的）

    def __post_init__(self):
        """
        初始化後自動執行的函數
        如果沒有設定抓取時間，就自動填入現在的時間
        """
        if not self.scraped_at:
            # 取得現在時間（香港時區），格式：2025-02-09 14:30:00
            self.scraped_at = datetime.now(
                timezone(timedelta(hours=TIMEZONE_OFFSET))
            ).strftime('%Y-%m-%d %H:%M:%S')

    def to_dict(self):
        """
        把新聞資料轉換成字典格式（方便存成 JSON）
        """
        return asdict(self)


@dataclass
class ScraperConfig:
    """
    爬蟲設定的資料結構
    定義每個網站要怎麼抓取
    """
    url: str                                    # 要抓取的網站網址
    source: str                                 # 網站名稱
    category: str                               # 新聞分類
    min_title_length: int                       # 標題最短長度（太短的可能不是新聞）
    selector: str = 'a'                         # CSS 選擇器（用來找網頁中的連結，預設抓所有 <a> 標籤）
    domain_check: Optional[str] = None          # 檢查網址是否包含特定文字
    url_pattern: Optional[str] = None           # 網址必須包含的特定模式
    exclude_titles: Optional[List[str]] = None  # 要排除的標題關鍵字
    base_url: Optional[str] = None              # 基礎網址（用來拼接相對路徑）
    fallback_url: Optional[str] = None          # 備用網址（主網址失敗時使用）

    def __post_init__(self):
        """
        如果沒有設定排除關鍵字，就建立空清單
        """
        if self.exclude_titles is None:
            self.exclude_titles = []

# ============================================================================
# HTML 爬蟲設定（定義要抓取哪些網站）
# 注意：Unwire.hk 已改由首頁專用抓取器負責（見下方 UnwireFetcher），
#       因此這裡不再包含 unwire 的設定
# ============================================================================
SCRAPERS_CONFIG = {
    # MeetHK - 旅遊網站（專注機票資訊）
    'meethk': ScraperConfig(
        url='https://www.meethk.com/category/flight/',
        source='MeetHK',
        category='旅遊',
        min_title_length=12,
        # 使用更精確的選擇器，只抓標題中的連結
        selector='h2.post-title a, h3.post-title a, .post-title a',
        domain_check='meethk.com',
        url_pattern='/1',  # 網址包含 /1（可能是文章編號）
        # 排除不想要的標題（酒店、優惠碼等）
        exclude_titles=[
            '酒店', 'Staycation', 'Hotel', '信用卡',
            '優惠碼', 'discount code', 'Club Med',
            'KKday', 'Klook', '套票', 'HopeGoo',
            '每日更新', 'Hotels.com', 'Trip.com',
            'Expedia', 'Agoda', 'Booking.com',
            '閱讀全文', 'Read More'
        ]
    )
}

# ============================================================================
# 工具類別（用來驗證和處理網址、文章）
# ============================================================================
class URLValidator:
    """
    網址驗證器 - 檢查網址是否有效
    """
    @staticmethod
    def is_valid(url: str) -> bool:
        """
        檢查網址格式是否正確
        例如：https://example.com 是正確的，example 是不正確的
        """
        try:
            r = urlparse(url)  # 解析網址
            # 檢查是否有協定（http/https）和網域名稱
            return r.scheme and r.netloc
        except Exception:
            return False  # 如果出錯就回傳 False

    @staticmethod
    def normalize(href: str, base_url: Optional[str]):
        """
        把相對路徑轉換成完整網址
        例如：/news/123 + https://example.com = https://example.com/news/123
        """
        if not href:
            return ""  # 如果沒有連結，回傳空字串
        if href.startswith('http'):
            return href  # 已經是完整網址，直接回傳
        if base_url:
            return urljoin(base_url, href)  # 拼接成完整網址
        return href


class ArticleValidator:
    """
    文章驗證器 - 檢查文章是否符合條件
    """
    @staticmethod
    def validate(title: str, href: str, config: ScraperConfig) -> bool:
        """
        檢查這篇文章是否要保留
        """
        # 標題不存在或太短 → 不要
        if not title or len(title) < config.min_title_length:
            return False

        # 標題包含排除關鍵字 → 不要
        if any(x.lower() in title.lower() for x in config.exclude_titles):
            return False

        # 網址不包含指定的網域 → 不要
        if config.domain_check and config.domain_check not in href:
            return False

        # 網址不包含指定的模式 → 不要
        if config.url_pattern and config.url_pattern not in href:
            return False

        # 檢查網址格式是否正確
        return URLValidator.is_valid(href)

# ============================================================================
# HTML 網頁爬蟲（從網頁中抓取新聞）
# ============================================================================
class WebScraper:
    """
    網頁爬蟲 - 負責訪問網站並抓取新聞
    """
    def __init__(self, config: ScraperConfig):
        """
        初始化爬蟲，建立一個連線會話
        """
        self.config = config  # 儲存設定
        self.session = requests.Session()  # 建立 HTTP 連線會話
        # 設定瀏覽器身份（User-Agent）
        self.session.headers.update({'User-Agent': USER_AGENT})

    def scrape(self) -> List[Article]:
        """
        執行抓取流程
        """
        try:
            # 1. 先嘗試從主網址抓取
            html = self._fetch(self.config.url)

            # 2. 如果失敗且有備用網址，就用備用網址
            if not html and self.config.fallback_url:
                html = self._fetch(self.config.fallback_url)

            # 3. 如果還是失敗，回傳空清單
            if not html:
                return []

            # 4. 解析網頁內容，找出新聞
            return self._parse(html)
        finally:
            # 5. 無論成功失敗，最後都要關閉連線
            self.session.close()

    def _fetch(self, url: str) -> Optional[str]:
        """
        訪問網站並取得網頁內容
        如果失敗會重試最多 3 次
        """
        for i in range(MAX_RETRIES):  # 最多重試 3 次
            try:
                # 發送請求，取得網頁
                r = self.session.get(url, timeout=REQUEST_TIMEOUT)
                r.raise_for_status()  # 檢查是否成功（如 404, 500 會拋出錯誤）

                # 解決中文編碼問題（自動偵測正確的編碼）
                r.encoding = r.apparent_encoding
                return r.text  # 回傳網頁 HTML 原始碼

            except Exception as e:
                # 記錄錯誤訊息
                logger.warning(f"重試 {i+1}/{MAX_RETRIES}: {url} - {e}")
                time.sleep(RETRY_DELAY)  # 等待 1 秒後再重試

        return None  # 重試 3 次都失敗，回傳 None

    def _parse(self, html: str) -> List[Article]:
        """
        解析網頁 HTML，找出所有新聞連結
        """
        soup = BeautifulSoup(html, 'html.parser')  # 用 BeautifulSoup 解析 HTML
        seen = set()   # 用來記錄已經看過的連結（避免重複）
        articles = []  # 儲存找到的新聞

        # 使用 CSS 選擇器找出所有符合條件的標籤
        targets = soup.select(self.config.selector)

        for tag in targets:
            # 如果已經抓夠數量，就停止
            if len(articles) >= MAX_NEWS_PER_SOURCE:
                break

            # 取得標籤內的文字（標題）
            title = tag.get_text(strip=True)

            # 判斷找到的標籤是否為 <a>（連結標籤）
            # 一般情況：selector 直接選到 <a>，可以直接取 href
            # eZone 特殊情況：selector 選到 <h3>，本身沒有 href
            #   → 需要往上尋找包住它的父層 <a> 標籤來取得連結
            # 例如 ezone 的 HTML 結構：
            #   <a href="/article/123/...">   ← 連結在外層 <a>
            #     <h3 class="title">文章標題</h3>  ← selector 選到這裡
            #   </a>
            if tag.name != 'a':
                # 不是 <a> 標籤，往上找最近的父層 <a>
                parent_a = tag.find_parent('a')
                href = URLValidator.normalize(
                    parent_a.get('href') if parent_a else '',
                    self.config.base_url
                )
            else:
                # 本身就是 <a> 標籤，直接取 href
                href = URLValidator.normalize(tag.get('href'), self.config.base_url)

            # 檢查這篇文章是否符合條件（標題長度、排除關鍵字、網址格式等）
            if not ArticleValidator.validate(title, href, self.config):
                continue  # 不符合就跳過

            # 檢查是否已經看過這個連結
            if href in seen:
                continue  # 重複就跳過

            # 記錄這個連結，避免重複
            seen.add(href)

            # 建立新聞物件並加入清單
            articles.append(Article(
                title=title,
                link=href,
                source=self.config.source,
                category=self.config.category
            ))

        # 記錄抓取結果
        logger.info(f"✓ {self.config.source} HTML 抓取 {len(articles)} 篇")
        return articles

# ============================================================================
# HolidaySmart 抓取器（只抓取 7 天內文章）
# ============================================================================
class HolidaySmartFetcher:
    URL = 'https://holidaysmart.io/hk'
    source = 'HolidaySmart'
    category = '旅遊'

    @staticmethod
    def _today_hk_date():
        return datetime.now(
            timezone(timedelta(hours=TIMEZONE_OFFSET))
        ).date()

    @staticmethod
    def _article_date_from_html(html: str):
        date_match = re.search(
            r'(?:datePublished|published_at|publishedAt)["\']?\s*[:=]\s*["\']([^"\']+)',
            html
        )
        if not date_match:
            date_match = re.search(r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:Z|[+-]\d{2}:\d{2}))', html)

        if not date_match:
            return None

        date_text = date_match.group(1).replace('Z', '+00:00')

        try:
            return datetime.fromisoformat(date_text).astimezone(
                timezone(timedelta(hours=TIMEZONE_OFFSET))
            ).date()
        except ValueError:
            return None

    def fetch(self) -> List[Article]:
        articles = []
        seen = set()
        today = self._today_hk_date()
        earliest_date = today - timedelta(days=6)

        try:
            r = requests.get(self.URL, headers={'User-Agent': USER_AGENT}, timeout=REQUEST_TIMEOUT)
            r.raise_for_status()
            r.encoding = r.apparent_encoding
            soup = BeautifulSoup(r.text, 'html.parser')
            candidates = []

            for tag in soup.select('a[href*="/hk/article/"]'):
                if len(candidates) >= MAX_NEWS_PER_SOURCE:
                    break

                href = URLValidator.normalize(tag.get('href'), 'https://holidaysmart.io')
                title = tag.get_text(strip=True)

                if not title or len(title) < 12 or href in seen:
                    continue

                candidates.append((title, href))
                seen.add(href)

            def fetch_article(candidate):
                title, href = candidate

                try:
                    article_response = requests.get(
                        href,
                        headers={'User-Agent': USER_AGENT},
                        timeout=REQUEST_TIMEOUT
                    )
                    article_response.raise_for_status()
                    article_response.encoding = article_response.apparent_encoding
                    article_date = self._article_date_from_html(article_response.text)
                except Exception as e:
                    logger.warning(f"HolidaySmart 文章日期讀取失敗: {href} - {e}")
                    return None

                if not article_date or article_date < earliest_date or article_date > today:
                    return None

                return Article(
                    title=title,
                    link=href,
                    source=self.source,
                    category=self.category
                )

            with ThreadPoolExecutor(max_workers=5) as ex:
                futures = [ex.submit(fetch_article, candidate) for candidate in candidates]

                for f in as_completed(futures):
                    article = f.result()

                    if article:
                        articles.append(article)

            logger.info(f"✓ HolidaySmart 7 天內抓取 {len(articles)} 篇")
            return articles

        except Exception as e:
            logger.error(f"✗ HolidaySmart 抓取失敗: {e}")
            return []

# ============================================================================
# eZone 抓取器（科技焦點，只抓取當天新聞）
# ============================================================================
class EzoneFetcher:
    URL = 'https://ezone.hk/srae001/科技焦點/'
    source = 'E-zone'
    category = '科技'

    @staticmethod
    def _today_hk_date():
        return datetime.now(
            timezone(timedelta(hours=TIMEZONE_OFFSET))
        ).date()

    @staticmethod
    def _article_date_from_text(text: str):
        date_match = re.search(r'(\d{2})-(\d{2})-(\d{4})\s+\d{2}:\d{2}', text)
        if not date_match:
            return None

        try:
            return datetime.strptime('-'.join(date_match.groups()), '%d-%m-%Y').date()
        except ValueError:
            return None

    def fetch(self) -> List[Article]:
        articles = []
        seen = set()
        today = self._today_hk_date()

        try:
            r = requests.get(self.URL, headers={'User-Agent': USER_AGENT}, timeout=REQUEST_TIMEOUT)
            r.raise_for_status()
            r.encoding = r.apparent_encoding
            soup = BeautifulSoup(r.text, 'html.parser')

            for tag in soup.select('a[href*="/article/"]'):
                href = URLValidator.normalize(tag.get('href'), 'https://ezone.hk')
                title_tag = tag.select_one('h3.title')
                title = title_tag.get_text(strip=True) if title_tag else ''
                item_date = self._article_date_from_text(tag.get_text(' ', strip=True))

                if not title or len(title) < 8 or not item_date:
                    continue

                if item_date < today:
                    break

                if item_date != today or href in seen:
                    continue

                articles.append(Article(
                    title=title,
                    link=href,
                    source=self.source,
                    category=self.category
                ))
                seen.add(href)

            logger.info(f"✓ E-zone 科技焦點當天抓取 {len(articles)} 篇")
            return articles

        except Exception as e:
            logger.error(f"✗ E-zone 科技焦點抓取失敗: {e}")
            return []

# ============================================================================
# NewMobileLife 抓取器（最新文章，只抓取當天新聞）
# ============================================================================
class NewMobileLifeFetcher:
    URL = 'https://www.newmobilelife.com/最新文章/'
    source = 'NewMobileLife'
    category = '科技'

    @staticmethod
    def _today_hk_date():
        return datetime.now(
            timezone(timedelta(hours=TIMEZONE_OFFSET))
        ).date()

    @staticmethod
    def _article_date_from_text(text: str):
        try:
            return datetime.strptime(text.strip(), '%Y-%m-%d').date()
        except ValueError:
            return None

    def fetch(self) -> List[Article]:
        articles = []
        seen = set()
        today = self._today_hk_date()

        try:
            r = requests.get(self.URL, headers={'User-Agent': USER_AGENT}, timeout=REQUEST_TIMEOUT)
            r.raise_for_status()
            r.encoding = r.apparent_encoding
            soup = BeautifulSoup(r.text, 'html.parser')

            for item in soup.select('article'):
                title_tag = item.select_one('h2 a')
                date_tag = item.select_one('.cs-meta-date')

                if not title_tag or not date_tag:
                    continue

                title = title_tag.get_text(strip=True)
                href = URLValidator.normalize(title_tag.get('href'), 'https://www.newmobilelife.com')
                item_date = self._article_date_from_text(date_tag.get_text(strip=True))

                if not title or len(title) < 12 or not item_date:
                    continue

                if item_date < today:
                    break

                if item_date != today or href in seen:
                    continue

                articles.append(Article(
                    title=title,
                    link=href,
                    source=self.source,
                    category=self.category
                ))
                seen.add(href)

            logger.info(f"✓ NewMobileLife 最新文章當天抓取 {len(articles)} 篇")
            return articles

        except Exception as e:
            logger.error(f"✗ NewMobileLife 最新文章抓取失敗: {e}")
            return []

# ============================================================================
# RSS 基礎類別（用來抓取 RSS 格式的新聞源）
# ============================================================================
class BaseRSSFetcher:
    """
    RSS 抓取器基礎類別
    RSS 是一種標準化的新聞格式，很多網站都有提供
    """
    feed_url = ''   # RSS 網址（子類別會覆蓋）
    source = ''     # 來源名稱
    category = ''   # 分類

    def fetch(self) -> List[Article]:
        """
        從 RSS 源抓取新聞
        """
        try:
            # 1. 訪問 RSS 網址
            r = requests.get(self.feed_url, timeout=REQUEST_TIMEOUT)
            r.raise_for_status()  # 檢查是否成功

            # 2. 解析 RSS 內容
            feed = feedparser.parse(r.content)

            # 3. 檢查是否有解析錯誤
            if feed.bozo:  # bozo 表示格式有問題
                logger.warning(f"RSS 解析警告: {self.source}")
                return []

            articles = []
            # 4. 遍歷每一則新聞（最多 15 則）
            for e in feed.entries[:MAX_NEWS_PER_SOURCE]:
                # 檢查標題和連結是否存在
                if not e.get('title') or not e.get('link'):
                    continue

                # 建立新聞物件
                articles.append(Article(
                    title=e.title.strip(),   # 去除前後空白
                    link=e.link.strip(),
                    source=self.source,
                    category=self.category
                ))

            # 記錄抓取結果
            logger.info(f"✓ {self.source} RSS 抓取 {len(articles)} 篇")
            return articles

        except Exception as e:
            logger.error(f"✗ {self.source} RSS 失敗: {e}")
            return []

# ============================================================================
# Unwire 抓取器（首頁最新文章，只抓取當天新聞）
# ============================================================================
class UnwireFetcher:
    URL = 'https://unwire.hk'
    source = 'Unwire.hk'
    category = '科技'

    @staticmethod
    def _today_hk_date():
        return datetime.now(
            timezone(timedelta(hours=TIMEZONE_OFFSET))
        ).date()

    @staticmethod
    def _article_date_from_link(link: str):
        date_match = re.search(r'/(\d{4})/(\d{2})/(\d{2})/', link)
        if not date_match:
            return None

        try:
            return datetime.strptime('-'.join(date_match.groups()), '%Y-%m-%d').date()
        except ValueError:
            return None

    @staticmethod
    def _is_within_24_hours(text: str) -> bool:
        if re.search(r'\d+\s*秒前|\d+\s*分鐘前', text):
            return True

        hour_match = re.search(r'(\d+)\s*小時前', text)
        return bool(hour_match and int(hour_match.group(1)) < 24)

    def fetch(self) -> List[Article]:
        articles = []
        seen = set()
        today = self._today_hk_date()

        try:
            r = requests.get(self.URL, headers={'User-Agent': USER_AGENT}, timeout=REQUEST_TIMEOUT)
            r.raise_for_status()
            r.encoding = r.apparent_encoding
            soup = BeautifulSoup(r.text, 'html.parser')

            for tag in soup.select('.post-content .title a'):
                href = URLValidator.normalize(tag.get('href'), 'https://unwire.hk')
                title = tag.get_text(strip=True)
                item_date = self._article_date_from_link(href)
                parent = tag.find_parent(class_='post-content')
                item_text = parent.get_text(' ', strip=True) if parent else ''

                if not title or len(title) < 8 or not item_date:
                    continue

                if item_date != today and not self._is_within_24_hours(item_text):
                    continue

                if href in seen:
                    continue

                articles.append(Article(
                    title=title,
                    link=href,
                    source=self.source,
                    category=self.category
                ))
                seen.add(href)

            logger.info(f"✓ Unwire.hk 首頁當天抓取 {len(articles)} 篇")
            return articles

        except Exception as e:
            logger.error(f"✗ Unwire.hk 首頁抓取失敗: {e}")
            return []

# ============================================================================
# FlyDay RSS 抓取器（專門抓取機票優惠新聞）
# ============================================================================
class FlyDayRSSFetcher(BaseRSSFetcher):
    """
    FlyDay.hk 的 RSS 抓取器
    只抓取機票相關的新聞，過濾掉酒店、攻略等
    """
    feed_url = 'https://flyday.hk/feed/'
    source = 'FlyDayhk'
    category = '旅遊'

    # 航空公司關鍵字
    AIRLINE_KEYWORDS = ['航空', 'hkexpress', 'air', '飛', '航線']

    # 優惠訊息關鍵字
    DEAL_HINTS = ['優惠', '折', '快閃', '減', '連稅', '起', '出發']

    # 要排除的關鍵字
    EXCLUDE_KEYWORDS = ['酒店', '住宿', '攻略', '教學', '信用卡', '里數']

    def fetch(self) -> List[Article]:
        """
        抓取並過濾新聞
        """
        # 1. 先用父類別的方法抓取所有新聞
        articles = super().fetch()

        filtered = []
        # 2. 逐一檢查每篇新聞
        for a in articles:
            title = a.title.lower()  # 轉成小寫方便比對

            # 如果包含排除關鍵字，跳過
            if any(k in title for k in self.EXCLUDE_KEYWORDS):
                continue

            # 檢查是否包含航空公司或優惠關鍵字
            airline_hit = any(k in title for k in self.AIRLINE_KEYWORDS)
            deal_hit = any(k in title for k in self.DEAL_HINTS)

            # 如果有符合任一條件，就保留
            if airline_hit or deal_hit:
                filtered.append(a)

        # 記錄過濾結果
        logger.info(f"✓ FlyDay.hk 機票過濾後 {len(filtered)} 篇")
        return filtered

# DotDotNews 抓取器（專門抓取點新聞的港聞新聞）
# 用 Chrome 打開點新聞網站，使用瀏覽器的開發者工具（F12），切換到 Network 分頁，按 Reload 重新載入頁面，找到 stories.json 的請求，右鍵 Copy URL。
class DotDotNewsFetcher:
    HK_NEWS_URL = "https://www.dotdotnews.com/immed/hknews"
    BOTH_SIDES_URL = "https://www.dotdotnews.com/immed/bothsides"
    INTERNATIONAL_URL = "https://www.dotdotnews.com/immed/inter"
    FINANCE_URL = "https://www.dotdotnews.com/finance"

    @staticmethod
    def _today_hk_date():
        return datetime.now(
            timezone(timedelta(hours=TIMEZONE_OFFSET))
        ).date()

    @staticmethod
    def _article_date_from_link(link: str):
        date_match = re.search(r'/a/(\d{6})/(\d{2})/', link)
        if not date_match:
            return None

        try:
            return datetime.strptime(''.join(date_match.groups()), '%Y%m%d').date()
        except ValueError:
            return None

    def _fetch_column_news(self, base_url: str, source: str, days: int) -> List[Article]:
        articles = []
        seen = set()
        today = self._today_hk_date()
        earliest_date = today - timedelta(days=days - 1)
        page = 1

        while True:
            url = base_url if page == 1 else f"{base_url}/more_{page}.html"
            r = requests.get(url, headers={'User-Agent': USER_AGENT}, timeout=REQUEST_TIMEOUT)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, 'html.parser')

            page_items = soup.select('.Share_Article[data-title][data-href]')
            if not page_items:
                break

            found_today = False
            found_older = False

            for item in page_items:
                link = URLValidator.normalize(item.get('data-href'), 'https://www.dotdotnews.com')
                title = item.get('data-title', '').strip()
                item_date = self._article_date_from_link(link)

                if not title or not item_date or link in seen:
                    continue

                if item_date < earliest_date:
                    found_older = True
                    continue

                if item_date > today:
                    continue

                articles.append(Article(
                    title=title,
                    link=link.strip(),
                    source=source,
                    category='新聞'
                ))
                seen.add(link)
                found_today = True

            if found_older or not found_today:
                break

            page += 1

        return articles

    def _fetch_static_pages_news(self, urls: List[str], source: str, days: int) -> List[Article]:
        articles = []
        seen = set()
        today = self._today_hk_date()
        earliest_date = today - timedelta(days=days - 1)

        for base_url in urls:
            page = 1

            while True:
                url = base_url if page == 1 else f"{base_url}/more_{page}.html"
                r = requests.get(url, headers={'User-Agent': USER_AGENT}, timeout=REQUEST_TIMEOUT)
                r.raise_for_status()
                soup = BeautifulSoup(r.text, 'html.parser')

                page_items = soup.select('.Share_Article[data-title][data-href]')
                if not page_items:
                    break

                found_in_range = False
                found_older = False

                for item in page_items:
                    link = URLValidator.normalize(item.get('data-href'), 'https://www.dotdotnews.com')
                    title = item.get('data-title', '').strip()
                    item_date = self._article_date_from_link(link)

                    if not title or not item_date or link in seen:
                        continue

                    if item_date < earliest_date:
                        found_older = True
                        continue

                    if item_date > today:
                        continue

                    articles.append(Article(
                        title=title,
                        link=link.strip(),
                        source=source,
                        category='新聞'
                    ))
                    seen.add(link)
                    found_in_range = True

                if found_older or not found_in_range:
                    break

                page += 1

        return articles

    def _fetch_hk_news(self) -> List[Article]:
        return self._fetch_column_news(self.HK_NEWS_URL, '點新聞-港聞', days=1)

    def _fetch_both_sides_news(self) -> List[Article]:
        return self._fetch_column_news(self.BOTH_SIDES_URL, '點新聞-兩岸', days=2)

    def _fetch_international_news(self) -> List[Article]:
        return self._fetch_column_news(self.INTERNATIONAL_URL, '點新聞-國際', days=1)

    def _fetch_market_news(self) -> List[Article]:
        return self._fetch_static_pages_news(
            [self.FINANCE_URL],
            '點新聞-財經',
            days=2
        )

    def fetch(self) -> List[Article]:
        articles = []

        try:
            articles.extend(self._fetch_hk_news())
            articles.extend(self._fetch_both_sides_news())
            articles.extend(self._fetch_international_news())
            articles.extend(self._fetch_market_news())

            logger.info(f"✓ 點新聞 分類後 {len(articles)} 篇")
            return articles

        except Exception as e:
            logger.error(f"✗ 點新聞 API 失敗: {e}")
            return []

# 所有額外抓取器的清單（RSS 與專用網站抓取器）
RSS_FETCHERS = [HolidaySmartFetcher(), EzoneFetcher(), NewMobileLifeFetcher(), FlyDayRSSFetcher(), UnwireFetcher(), DotDotNewsFetcher()]

# ============================================================================
# 爬蟲管理器（統一管理所有爬蟲）
# ============================================================================
class ScraperManager:
    """
    爬蟲管理器 - 負責協調所有爬蟲一起工作
    """
    def __init__(self, configs):
        """
        初始化，接收所有爬蟲設定
        """
        self.configs = configs

    def scrape_all(self) -> List[Article]:
        """
        同時執行所有爬蟲，抓取所有新聞
        """
        articles = []

        # 使用多線程同時執行多個爬蟲（加快速度）
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
            # 為每個設定建立一個爬蟲任務
            futures = {
                ex.submit(WebScraper(cfg).scrape): k
                for k, cfg in self.configs.items()
            }

            # 等待所有任務完成，收集結果
            for f in as_completed(futures):
                try:
                    articles.extend(f.result())  # 將結果加入清單
                except Exception as e:
                    logger.error(f"抓取失敗: {e}")

        # 執行所有 RSS 抓取器
        for rss in RSS_FETCHERS:
            try:
                articles.extend(rss.fetch())
            except Exception as e:
                logger.error(f"RSS 抓取失敗: {e}")

        # 去除重複的新聞
        return self._deduplicate(articles)

    @staticmethod
    def _deduplicate(articles: List[Article]) -> List[Article]:
        """
        去除重複的新聞（同一來源內根據連結判斷）
        """
        seen = set()  # 記錄已看過的來源和連結
        unique = []   # 儲存不重複的新聞

        for a in articles:
            key = (a.source, a.link)

            # 如果同一來源的這個連結已經看過，跳過
            if key in seen:
                continue

            # 記錄這個來源和連結
            seen.add(key)
            unique.append(a)

        return unique

# ============================================================================
# 資料儲存（將抓取的新聞存成 JSON 檔案）
# ============================================================================
class DataStorage:
    """
    資料儲存類別 - 負責將新聞寫入檔案
    """
    @staticmethod
    def save(articles: List[Article], filename='news.json'):
        """
        將新聞清單存成 JSON 檔案
        """
        # 建立要儲存的資料結構
        data = {
            'update_time': datetime.now(
                timezone(timedelta(hours=TIMEZONE_OFFSET))
            ).strftime('%Y-%m-%d %H:%M:%S'),            # 更新時間
            'total': len(articles),                     # 總新聞數
            'news': [a.to_dict() for a in articles]     # 所有新聞（轉成字典）
        }

        # 寫入檔案
        Path(filename).write_text(
            json.dumps(data, ensure_ascii=False, indent=2),  # 轉成 JSON，保留中文，縮排 2 格
            encoding='utf-8'  # 使用 UTF-8 編碼
        )

        logger.info(f"✓ 已輸出 {filename}")

# ============================================================================
# 主程式（程式的入口）
# ============================================================================
def main():
    """
    主函數 - 程式從這裡開始執行
    """
    logger.info("開始抓取新聞")

    # 1. 建立爬蟲管理器
    mgr = ScraperManager(SCRAPERS_CONFIG)

    # 2. 執行所有爬蟲，抓取新聞
    articles = mgr.scrape_all()

    # 3. 顯示結果
    logger.info(f"完成，共 {len(articles)} 篇")

    # 4. 儲存成 JSON 檔案
    DataStorage.save(articles)

# 當直接執行這個檔案時，就執行 main() 函數
if __name__ == '__main__':
    main()
