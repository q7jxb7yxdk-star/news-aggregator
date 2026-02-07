import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

# 配置日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 常量定義
USER_AGENT = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
MAX_NEWS_PER_SOURCE = 15
REQUEST_TIMEOUT = 10
MAX_WORKERS = 3  # 並行抓取的線程數

# 網站配置
SCRAPERS_CONFIG = {
    'unwire': {
        'url': 'https://unwire.hk/',
        'source': 'Unwire.hk',
        'category': '科技',
        'min_title_length': 10,
        'filters': {
            'domain_check': 'unwire.hk',
            'url_pattern': '/20',
        }
    },
    'newmobilelife': {
        'url': 'https://www.newmobilelife.com/',
        'source': 'New MobileLife',
        'category': '科技',
        'min_title_length': 15,
        'filters': {
            'domain_check': 'newmobilelife.com/20',
            'exclude_titles': ['Read More', '更多']
        }
    },
    'holidaysmart': {
        'url': 'https://holidaysmart.io/hk',
        'source': 'HolidaySmart',
        'category': '旅遊',
        'min_title_length': 20,
        'filters': {
            'url_pattern': '/hk/article/',
            'exclude_titles': [
                'HolidaySmart 假期日常', 'HolidaySmart', '更多', '詳情',
                '了解更多', '查看更多', 'Read More', 'an hour ago',
                'hours ago', 'a day ago', 'days ago'
            ],
            'base_url': 'https://holidaysmart.io'
        }
    }
}


def validate_article(title: str, href: str, config: Dict) -> bool:
    """
    驗證文章是否符合抓取條件
    
    Args:
        title: 文章標題
        href: 文章連結
        config: 網站配置
    
    Returns:
        是否符合條件
    """
    filters = config['filters']
    
    # 檢查標題長度
    if not title or len(title) < config['min_title_length']:
        return False
    
    # 檢查要排除的文字
    exclude_titles = filters.get('exclude_titles', [])
    if any(exclude in title for exclude in exclude_titles):
        return False
    
    # 檢查 URL 必須滿足的條件
    domain_check = filters.get('domain_check')
    if domain_check and domain_check not in href:
        return False
    
    url_pattern = filters.get('url_pattern')
    if url_pattern and url_pattern not in href:
        return False
    
    return True


def normalize_url(href: str, base_url: Optional[str]) -> str:
    """
    標準化 URL（處理相對路徑）
    
    Args:
        href: 原始連結
        base_url: 基礎 URL
    
    Returns:
        完整 URL
    """
    if base_url and href.startswith('/'):
        return base_url + href
    return href


def scrape_website(config_key: str) -> List[Dict]:
    """
    通用的網站爬蟲函數
    
    Args:
        config_key: 配置鍵名
    
    Returns:
        新聞列表
    """
    config = SCRAPERS_CONFIG[config_key]
    source_name = config['source']
    logger.info(f"正在抓取 {source_name}...")
    
    try:
        # 發送請求
        response = requests.get(
            config['url'],
            headers={'User-Agent': USER_AGENT},
            timeout=REQUEST_TIMEOUT
        )
        response.raise_for_status()  # 自動處理 HTTP 錯誤
        
        # 解析 HTML
        soup = BeautifulSoup(response.content, 'html.parser')
        all_links = soup.find_all('a', href=True)
        
        news = []
        seen_links = set()
        base_url = config['filters'].get('base_url')
        
        for link in all_links:
            # 達到上限則停止
            if len(news) >= MAX_NEWS_PER_SOURCE:
                break
            
            href = link.get('href', '').strip()
            title = link.text.strip()
            
            # 驗證文章
            if not validate_article(title, href, config):
                continue
            
            # 標準化 URL
            href = normalize_url(href, base_url)
            
            # 避免重複
            if href in seen_links:
                continue
            
            seen_links.add(href)
            news.append({
                'title': title,
                'link': href,
                'source': source_name,
                'category': config['category']
            })
        
        logger.info(f"✓ {source_name} 成功抓取 {len(news)} 篇文章")
        return news
        
    except requests.HTTPError as e:
        logger.error(f"✗ {source_name} HTTP 錯誤: {e}")
        return []
    except requests.RequestException as e:
        logger.error(f"✗ {source_name} 請求失敗: {e}")
        return []
    except Exception as e:
        logger.exception(f"✗ {source_name} 發生未預期錯誤: {e}")
        return []


def scrape_all_websites_parallel() -> List[Dict]:
    """
    並行抓取所有網站
    
    Returns:
        所有新聞列表
    """
    all_news = []
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # 提交所有任務
        future_to_config = {
            executor.submit(scrape_website, config_key): config_key 
            for config_key in SCRAPERS_CONFIG.keys()
        }
        
        # 收集結果
        for future in as_completed(future_to_config):
            config_key = future_to_config[future]
            try:
                news = future.result()
                all_news.extend(news)
            except Exception as e:
                logger.exception(f"✗ {config_key} 任務執行失敗: {e}")
    
    return all_news


def save_to_json(data: Dict, filename: str = 'news.json') -> bool:
    """
    保存數據為 JSON 文件
    
    Args:
        data: 要保存的數據
        filename: 文件名
    
    Returns:
        是否保存成功
    """
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"✓ 已保存到 {filename}")
        return True
    except IOError as e:
        logger.error(f"✗ 保存 JSON 文件失敗: {e}")
        return False


def main():
    """主函數"""
    logger.info("=" * 60)
    logger.info("開始抓取新聞...")
    logger.info("=" * 60)
    
    # 並行抓取所有網站
    all_news = scrape_all_websites_parallel()
    
    # 準備數據
    data = {
        'update_time': datetime.now(
            timezone(timedelta(hours=8))
        ).strftime('%Y-%m-%d %H:%M:%S'),
        'total_count': len(all_news),
        'news': all_news
    }
    
    # 保存結果
    logger.info("=" * 60)
    logger.info(f"✓ 完成！共抓取 {len(all_news)} 篇新聞")
    save_to_json(data)
    logger.info("=" * 60)


if __name__ == '__main__':
    main()