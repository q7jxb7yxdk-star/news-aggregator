"""Import public Now Sports posts collected from the signed-in Chrome page.

This module never reads browser credentials or calls Facebook. The browser
operator supplies only post text, its permalink and its visible publication time.
"""

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
import json
import logging
import os
from pathlib import Path
import re
import tempfile
from urllib.parse import parse_qs, urlparse


ROOT = Path(__file__).resolve().parent
PAGE_URL = 'https://www.facebook.com/now.comSports'
SNAPSHOT_PATH = ROOT / 'now_sports_posts.json'
HK = timezone(timedelta(hours=8))
WINDOW = timedelta(hours=24)
logger = logging.getLogger(__name__)


def atomic_json(path, payload):
    """Replace a complete JSON file on the same filesystem."""
    path = Path(path)
    descriptor, name = tempfile.mkstemp(prefix='.' + path.name, dir=path.parent)
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)

# Broad football subjects, not a restriction to particular leagues.
FOOTBALL = re.compile(
    r'足球|英超|西甲|意甲|法甲|德甲|歐聯|歐霸|歐協|港超|中超|日職|韓職|'
    r'亞冠|世冠盃|世界盃|歐洲國家盃|美洲國家盃|亞洲盃|非洲國家盃|'
    r'足總盃|英足盃|聯賽盃|國王盃|國際賽|女足|五人足球|門將|十二碼|越位|'
    r'補時|頭槌|頭鎚|紅牌|黃牌|美斯|C朗|安巴比|摩連奴|哥迪奧拿|'
    r'曼聯|曼城|利物浦|阿仙奴|車路士|熱刺|皇家馬德里|皇馬|巴塞隆拿|'
    r'國際米蘭|AC米蘭|祖雲達斯|拿玻里|巴黎聖日耳門|拜仁|多蒙特|'
    r'阿士東維拉|維拉利爾|利華古遜|羅馬|拉素|馬體會|畢爾包|里昂|馬賽|'
    r'\b(?:football|soccer|premier\s*league|laliga|serie\s*a|ligue\s*1|'
    r'bundesliga|champions\s*league|europa\s*league|UCL|UEL|FIFA|UEFA)\b',
    re.IGNORECASE,
)
OTHER_SPORTS = re.compile(
    r'NBA|WNBA|籃球|羽毛球|網球|乒乓球|高爾夫|高球|排球|棒球|美式足球|'
    r'美式橄欖球|F1|一級方程式|桌球|游泳|田徑|欖球|NFL|NHL|MLB', re.IGNORECASE,
)
PROMOTION = re.compile(r'有獎|抽獎|問答遊戲|送波衫|訂購|訂閱|月費|優惠碼|立即登記|續約.*獨家直播')
GIVEAWAY = re.compile(r'有獎|抽獎|問答遊戲|送波衫')


@dataclass
class NowSportsArticle:
    title: str
    link: str
    published_at: str
    content_type: str
    scraped_at: str
    observed_at: str = ''
    published_at_precision: str = 'exact'
    source: str = 'Now Sports'
    category: str = '足球'

    def to_dict(self):
        return asdict(self)


def parse_instant(value):
    """Require an explicit offset so a runner's local timezone cannot change it."""
    if not isinstance(value, str):
        raise ValueError('時間必須是含時區的 ISO 8601 字串')
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if result.tzinfo is None:
        raise ValueError('時間缺少時區')
    return result.astimezone(HK)


def canonical_link(value):
    """Accept individual Facebook posts/videos; remove tracking and comments."""
    if not isinstance(value, str):
        raise ValueError('缺少貼文連結')
    url = urlparse(value)
    if url.scheme != 'https' or url.netloc.lower() not in ('www.facebook.com', 'facebook.com'):
        raise ValueError('只接受 Facebook HTTPS 貼文連結')
    path = url.path.rstrip('/')
    if re.fullmatch(r'/now\.comSports/posts/(?:pfbid[A-Za-z0-9]+|\d+)', path, re.IGNORECASE):
        return PAGE_URL + '/posts/' + path.rsplit('/', 1)[1]
    match = re.fullmatch(r'/(?:now\.comSports/videos|reel)/(\d+)', path, re.IGNORECASE)
    if match:
        # Preserve the observed route rather than assuming every old video has
        # a usable Reel page. Identity-based deduplication is handled separately.
        route = 'now.comSports/videos' if '/videos/' in path.lower() else 'reel'
        return 'https://www.facebook.com/' + route + '/' + match.group(1) + '/'
    if path == '/watch':
        video_id = parse_qs(url.query).get('v', [''])[0]
        if video_id.isdigit():
            return 'https://www.facebook.com/watch/?v=' + video_id
    raise ValueError('連結不是獨立貼文或影片，請先點開貼文時間取得連結')


def content_key(link):
    url = urlparse(canonical_link(link))
    if '/posts/' in url.path:
        return ('post', url.path.rstrip('/').rsplit('/', 1)[1])
    video_id = (parse_qs(url.query)['v'][0] if url.path.rstrip('/') == '/watch'
                else url.path.rstrip('/').rsplit('/', 1)[1])
    return ('video', video_id)


def is_football(text):
    if not isinstance(text, str) or GIVEAWAY.search(text):
        return False
    # A basketball post can mention football in its body; inspect the lead first.
    lead = text.strip().split('\n', 1)[0][:180]
    if OTHER_SPORTS.search(lead) or PROMOTION.search(lead):
        return False
    if re.search(r'續約.*獨家直播', text) and not re.search(r'賽程|精華|戰報|分析', lead):
        return False
    return bool(FOOTBALL.search(text))


def publication_time(post, observed):
    if post.get('published_at'):
        precision = post.get('published_at_precision', 'exact')
        if precision not in ('exact', 'relative'):
            raise ValueError('無效的時間精度')
        return parse_instant(post['published_at']), precision
    label = post.get('published_label', '').strip().lower()
    # Relative labels are rounded. Use the OLDEST possible time, so a post
    # labelled 23 hours never stays eligible for an extra rounded hour.
    match = re.fullmatch(r'(\d+)\s*(minutes?|mins?|m|小時|分鐘|hours?|hrs?|h)(?:\s*ago|前)?', label)
    if match:
        amount = int(match.group(1))
        unit = match.group(2)
        interval = timedelta(minutes=amount + 1) if unit.startswith(('m', '分鐘')) else timedelta(hours=amount + 1)
        return observed - interval, 'relative'
    if label in ('just now', '剛剛', '剛才'):
        return observed - timedelta(minutes=1), 'relative'
    raise ValueError('發布時間無法確認；不使用擷取時間代替')


def normalize_post(post, observed, now, curated=False):
    if not isinstance(post, dict):
        raise ValueError('無效的貼文資料')
    if curated:
        if post.get('source') != 'Now Sports' or post.get('category') != '足球':
            raise ValueError('來源或分類不符')
        text = post.get('title', '')
    else:
        text = post.get('text', '')
        if not is_football(text):
            return None
    if not isinstance(text, str) or not text.strip():
        raise ValueError('缺少貼文文字')
    published, precision = publication_time(post, observed)
    if published > observed or not now - WINDOW <= published <= now:
        return None
    link = canonical_link(post.get('link'))
    title = re.sub(r'\s*(?:…\s*)?(?:See more|查看更多|顯示更多)\s*$', '', text.strip().split('\n', 1)[0]).strip()
    if len(title) < 4:
        raise ValueError('標題太短')
    # Aggregate a headline only, not the complete Facebook post or its comments.
    title = title[:180].rstrip()
    content_type = post.get('content_type', 'post')
    if content_key(link)[0] == 'video':
        content_type = 'video'
    if content_type not in ('video', 'post'):
        raise ValueError('無效的內容類型')
    return NowSportsArticle(
        title=title, link=link, published_at=published.isoformat(),
        published_at_precision=precision, content_type=content_type,
        observed_at=observed.isoformat(),
        scraped_at=observed.strftime('%Y-%m-%d %H:%M:%S'),
    )


def read_snapshot(path, now=None):
    now = now or datetime.now(HK)
    payload = json.loads(Path(path).read_text(encoding='utf-8'))
    if payload.get('page_url') != PAGE_URL or payload.get('status') != 'ok':
        raise ValueError('不是成功的 Now Sports 專頁擷取資料')
    collected = parse_instant(payload.get('collected_at'))
    if collected > now or not isinstance(payload.get('posts'), list):
        raise ValueError('擷取時間或貼文清單無效')
    result = {}
    invalid = 0
    for post in payload['posts']:
        try:
            observed = parse_instant(post.get('observed_at', payload['collected_at']))
            if observed > collected:
                raise ValueError('貼文觀察時間晚於擷取完成時間')
            article = normalize_post(post, observed, now, curated=True)
            if article:
                result.setdefault(content_key(article.link), article)
        except (ValueError, TypeError, AttributeError) as error:
            invalid += 1
            logger.warning('略過無效的 Now Sports 資料：%s', error)
    if invalid:
        raise ValueError('收集檔包含無效資料，改用上次輸出')
    return sorted(result.values(), key=lambda article: article.published_at, reverse=True)


class NowSportsFetcher:
    """A local snapshot bridge; GitHub Actions cannot share a Mac Chrome login."""
    source = 'Now Sports'
    category = '足球'

    def __init__(self, path=SNAPSHOT_PATH, fallback_path=ROOT / 'news.json'):
        self.path = Path(path)
        self.fallback_path = Path(fallback_path)

    def fetch(self):
        now = datetime.now(HK)
        try:
            articles = read_snapshot(self.path, now)
            logger.info('✓ Now Sports 匯入 %d 篇（過去 24 小時；Chrome 資料檔）', len(articles))
            return articles
        except (OSError, ValueError, TypeError, AttributeError) as error:
            logger.warning('Now Sports 資料檔不可用：%s；嘗試保留仍在 24 小時內的舊資料', error)
        # An unavailable browser/import must not erase eligible previous results.
        try:
            previous = json.loads(self.fallback_path.read_text(encoding='utf-8'))
            articles = {}
            for post in previous.get('news', []):
                if post.get('source') != self.source:
                    continue
                try:
                    observed = parse_instant(post.get('observed_at'))
                    if observed > now:
                        continue
                    article = normalize_post(post, observed, now, curated=True)
                    if article:
                        articles.setdefault(content_key(article.link), article)
                except (ValueError, TypeError, AttributeError):
                    continue
            return sorted(articles.values(), key=lambda article: article.published_at, reverse=True)
        except (OSError, ValueError, TypeError, AttributeError):
            return []


def import_capture(input_path, snapshot_path=SNAPSHOT_PATH, news_path=None, now=None):
    """Validate a browser capture completely before writing either local file."""
    now = now or datetime.now(HK)
    payload = json.loads(Path(input_path).read_text(encoding='utf-8'))
    if payload.get('page_url') != PAGE_URL or payload.get('status') != 'ok':
        raise ValueError('必須從 Now Sports 專頁成功擷取，不接受搜尋、登入錯誤或其他頁面')
    collected = parse_instant(payload.get('collected_at'))
    if not now - WINDOW <= collected <= now or not isinstance(payload.get('posts'), list):
        raise ValueError('擷取資料已過期，或資料格式無效')
    normalized = {}
    rejected = 0
    for post in payload['posts']:
        try:
            observed = parse_instant(post.get('observed_at', payload['collected_at']))
            if observed > collected:
                raise ValueError('貼文觀察時間晚於擷取完成時間')
            article = normalize_post(post, observed, now)
            if article:
                normalized.setdefault(content_key(article.link), article)
            else:
                rejected += 1
        except (ValueError, TypeError, AttributeError) as error:
            rejected += 1
            logger.warning('略過貼文：%s', error)
    # Preserve eligible posts from a previous, possibly more complete traversal.
    try:
        previous = read_snapshot(snapshot_path, now)
    except (OSError, ValueError, TypeError, AttributeError):
        previous = []
    for article in previous:
        normalized.setdefault(content_key(article.link), article)
    articles = sorted(normalized.values(), key=lambda article: article.published_at, reverse=True)
    snapshot = {
        'page_url': PAGE_URL, 'status': 'ok', 'collected_at': collected.isoformat(),
        'coverage': payload.get('coverage', 'partial'),
        'posts': [article.to_dict() for article in articles],
    }
    news = None
    if news_path:
        news = json.loads(Path(news_path).read_text(encoding='utf-8'))
        if not isinstance(news.get('news'), list):
            raise ValueError('news.json 格式無效；未修改任何檔案')
        news['news'] = [item for item in news['news'] if item.get('source') != 'Now Sports'] + snapshot['posts']
        news['total'] = len(news['news'])
        if 'total_count' in news:
            news['total_count'] = news['total']
        # Existing sources were not re-fetched; do not reset their update time.
    atomic_json(snapshot_path, snapshot)
    if news is not None:
        atomic_json(news_path, news)
    return len(articles), rejected


def main():
    parser = argparse.ArgumentParser(description='匯入已登入 Chrome 的 Now Sports 專頁擷取結果；不會連線 Facebook')
    parser.add_argument('capture', type=Path, help='經瀏覽器讀取的 JSON，格式見 NOW_SPORTS_COLLECTION.md')
    parser.add_argument('--snapshot', type=Path, default=SNAPSHOT_PATH)
    parser.add_argument('--news', type=Path, help='同時更新指定 news.json，保留其他來源')
    args = parser.parse_args()
    try:
        count, rejected = import_capture(args.capture, args.snapshot, args.news)
    except (OSError, ValueError, TypeError, AttributeError) as error:
        parser.exit(1, f'匯入失敗：{error}\n')
    print(f'Now Sports：保留 {count} 篇，略過 {rejected} 篇；分類：足球')


if __name__ == '__main__':
    main()
