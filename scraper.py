"""
新聞爬蟲系統 - 優化版本
支援多網站並行爬取，具備完善的錯誤處理和配置管理
"""

import requests
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
# 配置日誌
# ============================================================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('scraper.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

# ============================================================================
# 常量定義
# ============================================================================
USER_AGENT = (
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
    'AppleWebKit/537.36 (KHTML, like Gecko) '
    'Chrome/120.0.0.0 Safari/537.36'
)
MAX_NEWS_PER_SOURCE = 15
REQUEST_TIMEOUT = 10
MAX_WORKERS = 3
MAX_RETRIES = 3
RETRY_DELAY = 1  # 秒
TIMEZONE_OFFSET = 8  # UTC+8


# ============================================================================
# 數據類別
# ============================================================================
@dataclass
class Article:
    """文章數據類"""
    title: str
    link: str
    source: str
    category: str
    scraped_at: str = None
    
    def __post_init__(self):
        if self.scraped_at is None:
            self.scraped_at = datetime.now(
                timezone(timedelta(hours=TIMEZONE_OFFSET))
            ).strftime('%Y-%m-%d %H:%M:%S')
    
    def to_dict(self) -> Dict:
        """轉換為字典"""
        return asdict(self)


@dataclass
class ScraperConfig:
    """爬蟲配置類"""
    url: str
    source: str
    category: str
    min_title_length: int
    domain_check: Optional[str] = None
    url_pattern: Optional[str] = None
    exclude_titles: Optional[List[str]] = None
    base_url: Optional[str] = None
    fallback_url: Optional[str] = None  # 備用 URL
    
    def __post_init__(self):
        if self.exclude_titles is None:
            self.exclude_titles = []


# ============================================================================
# 網站配置，來源順序定義在這裏
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
        domain_check='newmobilelife.com/20',
        exclude_titles=['Read More', '更多'],
        fallback_url='https://www.newmobilelife.com/最新文章/'  # 備用最新文章頁面
    ),
    'holidaysmart': ScraperConfig(
        url='https://holidaysmart.io/hk',
        source='HolidaySmart',
        category='旅遊',
        min_title_length=12,
        url_pattern='/hk/article/',
        exclude_titles=[
            'HolidaySmart 假期日常', 'HolidaySmart', '更多', '詳情',
            '了解更多', '查看更多', 'Read More'
        ],
        base_url='https://holidaysmart.io'
    )
}


# ============================================================================
# 工具函數
# ============================================================================
class URLValidator:
    """URL 驗證工具類"""
    
    @staticmethod
    def is_valid_url(url: str) -> bool:
        """檢查 URL 是否有效"""
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except Exception:
            return False
    
    @staticmethod
    def normalize_url(href: str, base_url: Optional[str] = None) -> str:
        """
        標準化 URL（處理相對路徑）
        
        Args:
            href: 原始連結
            base_url: 基礎 URL
        
        Returns:
            完整 URL
        """
        if not href:
            return ''
        
        # 如果已經是完整 URL，直接返回
        if href.startswith(('http://', 'https://')):
            return href
        
        # 處理相對路徑
        if base_url:
            return urljoin(base_url, href)
        
        return href


class ArticleValidator:
    """文章驗證工具類"""
    
    @staticmethod
    def validate(title: str, href: str, config: ScraperConfig) -> bool:
        """
        驗證文章是否符合抓取條件
        
        Args:
            title: 文章標題
            href: 文章連結
            config: 網站配置
        
        Returns:
            是否符合條件
        """
        # 檢查標題長度
        if not title or len(title) < config.min_title_length:
            return False
        
        # 檢查要排除的文字
        if any(exclude in title for exclude in config.exclude_titles):
            return False
        
        # 檢查 URL 必須滿足的條件
        if config.domain_check and config.domain_check not in href:
            return False
        
        if config.url_pattern and config.url_pattern not in href:
            return False
        
        # 檢查 URL 有效性
        if not URLValidator.is_valid_url(href):
            return False
        
        return True


# ============================================================================
# 爬蟲類
# ============================================================================
class WebScraper:
    """網站爬蟲類"""
    
    def __init__(self, config: ScraperConfig):
        """
        初始化爬蟲
        
        Args:
            config: 爬蟲配置
        """
        self.config = config
        self.session = self._create_session()
    
    def _create_session(self) -> requests.Session:
        """創建 requests session"""
        session = requests.Session()
        session.headers.update({'User-Agent': USER_AGENT})
        return session
    
    def _fetch_page(self, url: Optional[str] = None) -> Optional[str]:
        """
        獲取頁面內容（帶重試機制）
        
        Args:
            url: 要獲取的 URL，如果為 None 則使用 config.url
        
        Returns:
            頁面 HTML 內容
        """
        target_url = url or self.config.url
        
        for attempt in range(MAX_RETRIES): # 嘗試獲取頁面內容3次
            try:
                response = self.session.get(
                    target_url,
                    timeout=REQUEST_TIMEOUT
                )
                response.raise_for_status()
                return response.content
                
            except requests.HTTPError as e:
                logger.warning(
                    f"{self.config.source} HTTP 錯誤 (嘗試 {attempt + 1}/{MAX_RETRIES}): {e}"
                )
            except requests.RequestException as e:
                logger.warning(
                    f"{self.config.source} 請求失敗 (嘗試 {attempt + 1}/{MAX_RETRIES}): {e}"
                )
            
            # 重試前等待並遞增等待時間
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY * (attempt + 1))
        
        return None
    
    def _extract_articles(self, html_content: str) -> List[Article]:
        """
        從 HTML 提取文章
        
        Args:
            html_content: HTML 內容
        
        Returns:
            文章列表
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        all_links = soup.find_all('a', href=True)
        
        articles = []
        seen_links: Set[str] = set()
        
        for link in all_links:
            # 達到上限則停止
            if len(articles) >= MAX_NEWS_PER_SOURCE:
                break
            
            href = link.get('href', '').strip()
            title = link.text.strip()
            
            # 標準化 URL
            href = URLValidator.normalize_url(href, self.config.base_url)
            
            # 驗證文章
            if not ArticleValidator.validate(title, href, self.config):
                continue
            
            # 避免重複
            if href in seen_links:
                continue
            
            seen_links.add(href)
            articles.append(Article(
                title=title,
                link=href,
                source=self.config.source,
                category=self.config.category
            ))
        
        return articles
    
    def scrape(self) -> List[Article]:
        """
        執行爬取
        
        Returns:
            文章列表
        """
        logger.info(f"正在抓取 {self.config.source}...")
        
        try:
            # 嘗試獲取主頁面
            html_content = self._fetch_page()
            
            # 如果主頁面失敗且有備用 URL，嘗試備用 URL
            if not html_content and self.config.fallback_url:
                logger.warning(
                    f"{self.config.source} 主頁面無法獲取，嘗試備用頁面: {self.config.fallback_url}"
                )
                html_content = self._fetch_page(self.config.fallback_url)
            
            # 如果還是沒有內容，返回空列表
            if not html_content:
                logger.error(f"✗ {self.config.source} 無法獲取頁面內容")
                return []
            
            # 提取文章
            articles = self._extract_articles(html_content)
            logger.info(f"✓ {self.config.source} 成功抓取 {len(articles)} 篇文章")
            return articles
            
        except Exception as e:
            logger.exception(f"✗ {self.config.source} 發生未預期錯誤: {e}")
            return []
        finally:
            self.session.close()


# ============================================================================
# 爬蟲管理器
# ============================================================================
class ScraperManager:
    """爬蟲管理器 - 負責協調多個爬蟲的執行"""
    
    def __init__(self, configs: Dict[str, ScraperConfig]):
        """
        初始化管理器
        
        Args:
            configs: 爬蟲配置字典
        """
        self.configs = configs
    
    def scrape_all_parallel(self) -> List[Article]:
        """
        並行抓取所有網站（保持配置順序）
        
        Returns:
            所有文章列表
        """
        results = {}  # 使用字典暫存結果
        
        # 並行爬取
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            # 提交所有任務
            future_to_config = {
                executor.submit(self._scrape_single, config_key): config_key
                for config_key in self.configs.keys()
            }
            
            # 收集結果（保存到字典）
            for future in as_completed(future_to_config):
                config_key = future_to_config[future]
                try:
                    articles = future.result()
                    results[config_key] = articles
                except Exception as e:
                    logger.exception(f"✗ {config_key} 任務執行失敗: {e}")
                    results[config_key] = []
        
        # 按 SCRAPERS_CONFIG 的配置順序合併結果
        all_articles = []
        for config_key in self.configs.keys():
            if config_key in results:
                all_articles.extend(results[config_key])
        
        return all_articles
    
    def _scrape_single(self, config_key: str) -> List[Article]:
        """
        抓取單個網站
        
        Args:
            config_key: 配置鍵名
        
        Returns:
            文章列表
        """
        config = self.configs[config_key]
        scraper = WebScraper(config)
        return scraper.scrape()


# ============================================================================
# 數據存儲
# ============================================================================
class DataStorage:
    """數據存儲類"""
    
    @staticmethod
    def save_to_json(
        articles: List[Article],
        filename: str = 'news.json'
    ) -> bool:
        """
        保存數據為 JSON 文件
        
        Args:
            articles: 文章列表
            filename: 文件名
        
        Returns:
            是否保存成功
        """
        try:
            # 準備數據
            data = {
                'update_time': datetime.now(
                    timezone(timedelta(hours=TIMEZONE_OFFSET))
                ).strftime('%Y-%m-%d %H:%M:%S'),
                'total_count': len(articles),
                'sources': list(set(article.source for article in articles)),
                'categories': list(set(article.category for article in articles)),
                'news': [article.to_dict() for article in articles]
            }
            
            # 確保目錄存在
            output_path = Path(filename)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 保存文件
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"✓ 已保存到 {filename}")
            return True
            
        except IOError as e:
            logger.error(f"✗ 保存 JSON 文件失敗: {e}")
            return False
    
    @staticmethod
    def save_summary(
        articles: List[Article],
        filename: str = 'news_summary.txt'
    ) -> bool:
        """
        保存摘要文本
        
        Args:
            articles: 文章列表
            filename: 文件名
        
        Returns:
            是否保存成功
        """
        try:
            output_path = Path(filename)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(f"新聞爬取摘要\n")
                f.write(f"{'=' * 60}\n")
                f.write(f"更新時間: {datetime.now(timezone(timedelta(hours=TIMEZONE_OFFSET))).strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"總文章數: {len(articles)}\n\n")
                
                # 按來源分組
                by_source = {}
                for article in articles:
                    if article.source not in by_source:
                        by_source[article.source] = []
                    by_source[article.source].append(article)
                
                for source, items in by_source.items():
                    f.write(f"\n{source} ({len(items)} 篇)\n")
                    f.write(f"{'-' * 60}\n")
                    for i, article in enumerate(items, 1):
                        f.write(f"{i}. {article.title}\n")
                        f.write(f"   {article.link}\n\n")
            
            logger.info(f"✓ 已保存摘要到 {filename}")
            return True
            
        except IOError as e:
            logger.error(f"✗ 保存摘要失敗: {e}")
            return False


# ============================================================================
# 主程序
# ============================================================================
def main():
    """主函數"""
    logger.info("=" * 60)
    logger.info("開始抓取新聞...")
    logger.info("=" * 60)
    
    start_time = time.time()
    
    # 創建管理器並執行爬取
    manager = ScraperManager(SCRAPERS_CONFIG)
    all_articles = manager.scrape_all_parallel()
    
    # 計算執行時間
    elapsed_time = time.time() - start_time
    
    # 保存結果
    logger.info("=" * 60)
    logger.info(f"✓ 完成！共抓取 {len(all_articles)} 篇新聞")
    logger.info(f"✓ 執行時間: {elapsed_time:.2f} 秒")
    
    # 保存為 JSON
    DataStorage.save_to_json(all_articles)
    
    # 保存摘要
    DataStorage.save_summary(all_articles)
    
    logger.info("=" * 60)


if __name__ == '__main__':
    main()