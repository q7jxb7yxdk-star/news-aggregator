"""
MeetHK 爬蟲測試腳本
專門測試是否能正確抓取長標題
"""

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

# 測試配置
TEST_URL = 'https://www.meethk.com/category/flight/'
USER_AGENT = 'Mozilla/5.0 RSSAggregator/1.0'

def test_meethk_scraper():
    """測試 MeetHK 爬蟲能否正確抓取標題"""
    
    print("=" * 80)
    print("測試 MeetHK.com 機票優惠爬蟲")
    print("=" * 80)
    
    # 發送請求
    print(f"\n1. 正在抓取: {TEST_URL}")
    try:
        headers = {'User-Agent': USER_AGENT}
        response = requests.get(TEST_URL, headers=headers, timeout=10)
        response.raise_for_status()
        print(f"   ✓ 狀態碼: {response.status_code}")
    except Exception as e:
        print(f"   ✗ 請求失敗: {e}")
        return
    
    # 解析 HTML
    print("\n2. 解析 HTML...")
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # 尋找所有連結
    print("\n3. 分析所有連結:")
    all_links = soup.find_all('a', href=True)
    print(f"   總共找到 {len(all_links)} 個連結")
    
    # 過濾機票文章
    print("\n4. 過濾機票優惠文章:")
    print("-" * 80)
    
    flight_articles = []
    exclude_keywords = [
        'Hotels.com', 'Trip.com', 'Expedia', 'Agoda', 
        'Booking.com', 'Klook', 'KKday', 'Staycation',
        'Club Med', '酒店優惠代碼', '每日更新',
        '一定要bookmark', 'HopeGoo', '信用卡'
    ]
    
    for link in all_links[:50]:  # 只檢查前 50 個連結
        href = link.get('href', '')
        title = link.text.strip()
        
        # 檢查是否為文章連結
        if not href or 'meethk.com' not in href:
            continue
        if '/1' not in href:  # URL 模式檢查
            continue
        if len(title) < 20:  # 標題長度檢查
            continue
        
        # 排除關鍵字檢查
        if any(keyword in title for keyword in exclude_keywords):
            print(f"\n   ✗ 排除: {title[:60]}...")
            print(f"     URL: {href}")
            continue
        
        # 符合條件的文章
        flight_articles.append({
            'title': title,
            'url': href,
            'length': len(title)
        })
        
        print(f"\n   ✓ 抓取成功:")
        print(f"     標題: {title}")
        print(f"     URL: {href}")
        print(f"     長度: {len(title)} 字符")
    
    # 顯示結果統計
    print("\n" + "=" * 80)
    print("測試結果統計")
    print("=" * 80)
    print(f"成功抓取: {len(flight_articles)} 篇機票優惠")
    
    if flight_articles:
        print("\n標題長度分佈:")
        lengths = [a['length'] for a in flight_articles]
        print(f"  最短: {min(lengths)} 字符")
        print(f"  最長: {max(lengths)} 字符")
        print(f"  平均: {sum(lengths)//len(lengths)} 字符")
    
    # 顯示抓取的文章列表
    print("\n抓取到的文章:")
    print("-" * 80)
    for i, article in enumerate(flight_articles[:10], 1):
        print(f"{i}. {article['title'][:70]}...")
        print(f"   {article['url']}")
        print()
    
    return flight_articles

def test_specific_article():
    """測試特定文章的標題抓取"""
    
    print("\n" + "=" * 80)
    print("測試特定文章: /157709/")
    print("=" * 80)
    
    test_url = 'https://www.meethk.com/157709/'
    
    try:
        headers = {'User-Agent': USER_AGENT}
        response = requests.get(test_url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 方法 1: 從 <h1> 標籤抓取
        h1 = soup.find('h1')
        if h1:
            h1_title = h1.text.strip()
            print(f"\n從 <h1> 標籤抓取:")
            print(f"  {h1_title}")
            print(f"  長度: {len(h1_title)} 字符")
        
        # 方法 2: 從 <title> 標籤抓取
        title_tag = soup.find('title')
        if title_tag:
            page_title = title_tag.text.strip()
            # 移除網站名稱部分
            if ' - MeetHK.com' in page_title:
                page_title = page_title.split(' - MeetHK.com')[0]
            print(f"\n從 <title> 標籤抓取:")
            print(f"  {page_title}")
            print(f"  長度: {len(page_title)} 字符")
        
        # 預期標題
        expected_title = "抵呀！連稅千三飛東京/大阪！6月30日前出發！香港飛大阪來回連稅$1,346起、東京$1,392起 – 大灣區航空 (優惠至2月5日)"
        
        print(f"\n預期標題:")
        print(f"  {expected_title}")
        print(f"  長度: {len(expected_title)} 字符")
        
        # 比對結果
        if h1 and h1_title == expected_title:
            print("\n✓ 標題完全匹配!")
        else:
            print("\n⚠ 標題可能有差異")
        
    except Exception as e:
        print(f"✗ 測試失敗: {e}")

if __name__ == '__main__':
    # 測試列表頁抓取
    articles = test_meethk_scraper()
    
    # 測試特定文章頁
    test_specific_article()
    
    print("\n" + "=" * 80)
    print("測試完成")
    print("=" * 80)