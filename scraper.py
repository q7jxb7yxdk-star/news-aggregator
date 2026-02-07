import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime, timedelta, timezone

# temp
def scrape_unwire():
    """抓取 Unwire.hk 科技新聞"""
    print("正在抓取 Unwire.hk...")
    url = 'https://unwire.hk/'
    
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            all_links = soup.find_all('a', href=True)
            
            news = []
            for link in all_links:
                href = link.get('href', '')
                title = link.text.strip()
                
                # 如果有標題，而且標題長度多過 10 個字，同時連結係 unwire.hk，而且 URL 入面包含 /20
                if title and len(title) > 10 and 'unwire.hk' in href and '/20' in href:
                    if not any(item['link'] == href for item in news):
                        news.append({
                            'title': title,
                            'link': href,
                            'source': 'Unwire.hk',
                            'category': '科技'
                        })
                        if len(news) >= 15: # 當新聞數量已經收集到 15 篇，就停止再搵落去。
                            break
            
            print(f"✓ 成功抓取 {len(news)} 篇文章")
            return news
    except Exception as e:
        print(f"✗ Unwire.hk 抓取失敗: {e}")
        return []

def scrape_newmobilelife():
    """抓取 New MobileLife 科技新聞"""
    print("正在抓取 New MobileLife...")
    url = 'https://www.newmobilelife.com/'
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            all_links = soup.find_all('a', href=True)
            
            news = []
            for link in all_links:
                href = link.get('href', '')
                title = link.text.strip()
                
                # 篩選文章鏈接（包含日期格式 /2026/ 等）
                if (title and len(title) > 15 and 
                    'newmobilelife.com/20' in href and
                    title not in ['Read More', '更多']):
                    
                    if not any(item['link'] == href for item in news):
                        news.append({
                            'title': title,
                            'link': href,
                            'source': 'New MobileLife',
                            'category': '科技'
                        })
                        
                        if len(news) >= 15:
                            break
            
            print(f"✓ 成功抓取 {len(news)} 篇文章")
            return news
            
    except Exception as e:
        print(f"✗ New MobileLife 抓取失敗: {e}")
        return []

def scrape_holidaysmart():
    """抓取 HolidaySmart 假期日常旅遊資訊"""
    print("正在抓取 HolidaySmart...")
    url = 'https://holidaysmart.io/hk'
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # 先檢查網頁結構
            all_links = soup.find_all('a', href=True)
            
            news = []
            # 需要排除的文字
            exclude_texts = [
                'HolidaySmart 假期日常', 'HolidaySmart', '更多', '詳情', 
                '了解更多', '查看更多', 'Read More', 'an hour ago', 
                'hours ago', 'a day ago', 'days ago'
            ]
            
            for link in all_links:
                href = link.get('href', '')
                title = link.text.strip()
                
                # 必須包含 /hk/article/ 才是真正的文章
                if (title and len(title) > 20 and 
                    '/hk/article/' in href and
                    not any(exclude in title for exclude in exclude_texts)):

                    # 處理相對路徑
                    if href.startswith('/'):
                        href = 'https://holidaysmart.io' + href
                    
                    # 避免重複
                    if not any(item['link'] == href for item in news):
                        news.append({
                            'title': title,
                            'link': href,
                            'source': 'HolidaySmart',
                            'category': '旅遊'
                        })
                        
                        if len(news) >= 15:
                            break
            
            print(f"✓ 成功抓取 {len(news)} 篇文章")
            return news
            
    except Exception as e:
        print(f"✗ HolidaySmart 抓取失敗: {e}")
        return []

def main():
    print("=" * 60)
    print("開始抓取新聞...")
    print("=" * 60)
    
    all_news = []
    
    # 抓取各個網站
    all_news.extend(scrape_unwire())
    all_news.extend(scrape_newmobilelife())
    all_news.extend(scrape_holidaysmart())
    
    # 添加抓取時間
    data = {
        # 香港時區
        'update_time': datetime.now(timezone(timedelta(hours=8))).strftime('%Y-%m-%d %H:%M:%S'),
        'total_count': len(all_news),
        'news': all_news
    }
    
    # 保存為 JSON 文件
    with open('news.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print("\n" + "=" * 60)
    print(f"✓ 完成！共抓取 {len(all_news)} 篇新聞")
    print(f"✓ 已保存到 news.json")
    print("=" * 60)

if __name__ == '__main__':
    main()
