import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime, timedelta, timezone

# 常量定義
USER_AGENT = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
MAX_NEWS_PER_SOURCE = 15
REQUEST_TIMEOUT = 10

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


def scrape_website(config_key):
    """通用的網站爬蟲函數，提高代碼效率"""
    config = SCRAPERS_CONFIG[config_key]
    source_name = config['source']
    print(f"正在抓取 {source_name}...")
    
    try:
        response = requests.get(
            config['url'],
            headers={'User-Agent': USER_AGENT},
            timeout=REQUEST_TIMEOUT
        )
        
        if response.status_code != 200:
            print(f"✗ {source_name} HTTP 錯誤: {response.status_code}")
            return []
        
        soup = BeautifulSoup(response.content, 'html.parser')
        all_links = soup.find_all('a', href=True)
        
        news = []
        seen_links = set()  # 使用 set 提升查找效率到 O(1)
        filters = config['filters']
        
        for link in all_links:
            href = link.get('href', '')
            title = link.text.strip()
            
            # 檢查標題長度
            if not title or len(title) < config['min_title_length']:
                continue
            
            # 檢查要排除的文字
            if any(exclude in title for exclude in filters.get('exclude_titles', [])):
                continue
            
            # 檢查 URL 必須滿足的條件
            if filters.get('domain_check') and filters['domain_check'] not in href:
                continue
            if filters.get('url_pattern') and filters['url_pattern'] not in href:
                continue
            
            # 處理相對路徑
            if filters.get('base_url') and href.startswith('/'):
                href = filters['base_url'] + href
            
            # 避免重複（使用 set 提升效率）
            if href in seen_links:
                continue
            
            seen_links.add(href)
            news.append({
                'title': title,
                'link': href,
                'source': source_name,
                'category': config['category']
            })
            
            if len(news) >= MAX_NEWS_PER_SOURCE:
                break
        
        print(f"✓ 成功抓取 {len(news)} 篇文章")
        return news
        
    except requests.RequestException as e:
        print(f"✗ {source_name} 抓取失敗: {e}")
        return []
    except Exception as e:
        print(f"✗ {source_name} 發生錯誤: {e}")
        return []

def main():
    print("=" * 60)
    print("開始抓取新聞...")
    print("=" * 60)
    
    all_news = []
    
    # 抓取各個網站
    for config_key in SCRAPERS_CONFIG.keys():
        all_news.extend(scrape_website(config_key))
    
    # 添加抓取時間（香港時區 UTC+8）
    data = {
        'update_time': datetime.now(timezone(timedelta(hours=8))).strftime('%Y-%m-%d %H:%M:%S'),
        'total_count': len(all_news),
        'news': all_news
    }
    
    # 保存為 JSON 文件
    try:
        with open('news.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        print("\n" + "=" * 60)
        print(f"✓ 完成！共抓取 {len(all_news)} 篇新聞")
        print(f"✓ 已保存到 news.json")
        print("=" * 60)
    except IOError as e:
        print(f"✗ 保存 JSON 文件失敗: {e}")


if __name__ == '__main__':
    main()
