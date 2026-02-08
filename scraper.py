import requests
import feedparser
from bs4 import BeautifulSoup
import json
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, asdict
from pathlib import Path
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin, urlparse
import time

# ============================================================================
# Logging
# ============================================================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================================================
# Constants
# ============================================================================
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
MAX_NEWS_PER_SOURCE = 15
REQUEST_TIMEOUT = 10
MAX_WORKERS = 3
MAX_RETRIES = 3
RETRY_DELAY = 1
TIMEZONE_OFFSET = 8

# ============================================================================
# Data Classes
# ============================================================================
@dataclass
class Article:
    title: str
    link: str
    source: str
    category: str
    scraped_at: str = None

    def __post_init__(self):
        if not self.scraped_at:
            self.scraped_at = datetime.now(
                timezone(timedelta(hours=TIMEZONE_OFFSET))
            ).strftime('%Y-%m-%d %H:%M:%S')

    def to_dict(self):
        return asdict(self)


@dataclass
class ScraperConfig:
    url: str
    source: str
    category: str
    min_title_length: int
    selector: str = 'a'  # 預設抓取所有 a，但 MeetHK 會覆蓋此設定
    domain_check: Optional[str] = None
    url_pattern: Optional[str] = None
    exclude_titles: Optional[List[str]] = None
    base_url: Optional[str] = None
    fallback_url: Optional[str] = None

    def __post_init__(self):
        if self.exclude_titles is None:
            self.exclude_titles = []

# ============================================================================
# HTML Scraper Configs
# ============================================================================
SCRAPERS_CONFIG = {
    'unwire': ScraperConfig(
        url='https://unwire.hk/',
        source='Unwire.hk',
        category='科技',
        min_title_length=12,
        domain_check='unwire.hk',
        url_pattern='/20'
    ),
    'newmobilelife': ScraperConfig(
        url='https://www.newmobilelife.com/',
        source='NewMobileLife',
        category='科技',
        min_title_length=12,
        domain_check='newmobilelife.com/20'
    ),
    'holidaysmart': ScraperConfig(
        url='https://holidaysmart.io/hk',
        source='HolidaySmart',
        category='旅遊',
        min_title_length=12,
        url_pattern='/hk/article/',
        base_url='https://holidaysmart.io'
    ),
    'meethk': ScraperConfig(
        url='https://www.meethk.com/category/flight/',
        source='MeetHK.com',
        category='旅遊',
        min_title_length=12,  # 提高長度，因為機票標題通常很長
        selector='h2.post-title a, h3.post-title a, .post-title a', # 精確定位標題連結
        domain_check='meethk.com',
        url_pattern='/1', 
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
# Utils
# ============================================================================
class URLValidator:
    @staticmethod
    def is_valid(url: str) -> bool:
        try:
            r = urlparse(url)
            return r.scheme and r.netloc
        except Exception:
            return False

    @staticmethod
    def normalize(href: str, base_url: Optional[str]):
        if not href: return ""
        if href.startswith('http'):
            return href
        if base_url:
            return urljoin(base_url, href)
        return href


class ArticleValidator:
    @staticmethod
    def validate(title: str, href: str, config: ScraperConfig) -> bool:
        if not title or len(title) < config.min_title_length:
            return False
        if any(x.lower() in title.lower() for x in config.exclude_titles):
            return False
        if config.domain_check and config.domain_check not in href:
            return False
        if config.url_pattern and config.url_pattern not in href:
            return False
        return URLValidator.is_valid(href)

# ============================================================================
# HTML Web Scraper
# ============================================================================
class WebScraper:
    def __init__(self, config: ScraperConfig):
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': USER_AGENT})

    def scrape(self) -> List[Article]:
        try:
            html = self._fetch(self.config.url)
            if not html and self.config.fallback_url:
                html = self._fetch(self.config.fallback_url)
            if not html:
                return []
            return self._parse(html)
        finally:
            self.session.close()

    def _fetch(self, url: str) -> Optional[str]:
        for i in range(MAX_RETRIES):
            try:
                r = self.session.get(url, timeout=REQUEST_TIMEOUT)
                r.raise_for_status()
                # 解決中文編碼問題
                r.encoding = r.apparent_encoding
                return r.text
            except Exception as e:
                logger.warning(f"重試 {i+1}/{MAX_RETRIES}: {url} - {e}")
                time.sleep(RETRY_DELAY)
        return None

    def _parse(self, html: str) -> List[Article]:
        soup = BeautifulSoup(html, 'html.parser')
        seen = set()
        articles = []

        # 使用 CSS Selector 定位，避免抓到雜亂的 <a> 標籤
        targets = soup.select(self.config.selector)

        for a in targets:
            if len(articles) >= MAX_NEWS_PER_SOURCE:
                break

            # get_text(strip=True) 能確保抓到 <a> 內部的完整文字，不論是否有 <span> 或其他標籤
            title = a.get_text(strip=True)
            href = URLValidator.normalize(a.get('href'), self.config.base_url)

            if not ArticleValidator.validate(title, href, self.config):
                continue
            if href in seen:
                continue

            seen.add(href)
            articles.append(Article(
                title=title,
                link=href,
                source=self.config.source,
                category=self.config.category
            ))

        logger.info(f"✓ {self.config.source} HTML 抓取 {len(articles)} 篇")
        return articles

# ============================================================================
# RSS Base Fetcher
# ============================================================================
class BaseRSSFetcher:
    feed_url = ''
    source = ''
    category = ''

    def fetch(self) -> List[Article]:
        try:
            r = requests.get(self.feed_url, timeout=REQUEST_TIMEOUT)
            r.raise_for_status()
            feed = feedparser.parse(r.content)

            if feed.bozo:
                logger.warning(f"RSS 解析警告: {self.source}")
                return []

            articles = []
            for e in feed.entries[:MAX_NEWS_PER_SOURCE]:
                if not e.get('title') or not e.get('link'):
                    continue
                articles.append(Article(
                    title=e.title.strip(),
                    link=e.link.strip(),
                    source=self.source,
                    category=self.category
                ))

            logger.info(f"✓ {self.source} RSS 抓取 {len(articles)} 篇")
            return articles
        except Exception as e:
            logger.error(f"✗ {self.source} RSS 失敗: {e}")
            return []

# ============================================================================
# FlyDay RSS
# ============================================================================
class FlyDayRSSFetcher(BaseRSSFetcher):
    feed_url = 'https://flyday.hk/feed/'
    source = 'FlyDay.hk'
    category = '旅遊'

    AIRLINE_KEYWORDS = ['航空', 'hkexpress', 'air', '飛', '航線']
    DEAL_HINTS = ['優惠', '折', '快閃', '減', '連稅', '起', '出發']
    EXCLUDE_KEYWORDS = ['酒店', '住宿', '攻略', '教學', '信用卡', '里數']

    def fetch(self) -> List[Article]:
        articles = super().fetch()
        filtered = []
        for a in articles:
            title = a.title.lower()
            if any(k in title for k in self.EXCLUDE_KEYWORDS):
                continue
            airline_hit = any(k in title for k in self.AIRLINE_KEYWORDS)
            deal_hit = any(k in title for k in self.DEAL_HINTS)
            if airline_hit or deal_hit:
                filtered.append(a)
        logger.info(f"✓ FlyDay.hk 機票過濾後 {len(filtered)} 篇")
        return filtered

RSS_FETCHERS = [FlyDayRSSFetcher()]

# ============================================================================
# Manager
# ============================================================================
class ScraperManager:
    def __init__(self, configs):
        self.configs = configs

    def scrape_all(self) -> List[Article]:
        articles = []
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
            futures = {
                ex.submit(WebScraper(cfg).scrape): k
                for k, cfg in self.configs.items()
            }
            for f in as_completed(futures):
                try:
                    articles.extend(f.result())
                except Exception as e:
                    logger.error(f"抓取失敗: {e}")

        for rss in RSS_FETCHERS:
            try:
                articles.extend(rss.fetch())
            except Exception as e:
                logger.error(f"RSS 抓取失敗: {e}")

        return self._deduplicate(articles)

    @staticmethod
    def _deduplicate(articles: List[Article]) -> List[Article]:
        seen = set()
        unique = []
        for a in articles:
            if a.link in seen:
                continue
            seen.add(a.link)
            unique.append(a)
        return unique

# ============================================================================
# Storage
# ============================================================================
class DataStorage:
    @staticmethod
    def save(articles: List[Article], filename='news.json'):
        data = {
            'update_time': datetime.now(
                timezone(timedelta(hours=TIMEZONE_OFFSET))
            ).strftime('%Y-%m-%d %H:%M:%S'),
            'total': len(articles),
            'news': [a.to_dict() for a in articles]
        }
        Path(filename).write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding='utf-8'
        )
        logger.info(f"✓ 已輸出 {filename}")

# ============================================================================
# Main
# ============================================================================
def main():
    logger.info("開始抓取新聞")
    mgr = ScraperManager(SCRAPERS_CONFIG)
    articles = mgr.scrape_all()
    logger.info(f"完成，共 {len(articles)} 篇")
    DataStorage.save(articles)

if __name__ == '__main__':
    main()