"""Read visible posts in a dedicated, signed-in Chrome profile (no Facebook API)."""

import argparse
from datetime import datetime
import json
import logging
from pathlib import Path
import re
import signal
import time

from now_sports import HK, PAGE_URL, canonical_link, is_football


# Keep actual DOM handles: Facebook virtualizes cards, so numeric indexes are unsafe.
FIND_HEADER = r"""message => {
  for (let scope = message, depth = 0; scope && depth < 12;
       scope = scope.parentElement, depth++) {
    if (scope.querySelectorAll('[data-ad-preview="message"]').length > 1) break;
    const owner = [...scope.querySelectorAll('h2,h3')].find(h =>
      [...h.querySelectorAll('a')].some(a => {
        const u = new URL(a.href);
        return ['facebook.com', 'www.facebook.com'].includes(u.hostname) &&
          u.pathname.replace(/\/$/, '').toLowerCase() === '/now.comsports' &&
          a.innerText.trim() === 'Now Sports';
      }));
    if (!owner) continue;
    const before = [...scope.querySelectorAll('a')].filter(a =>
      (message.compareDocumentPosition(a) & Node.DOCUMENT_POSITION_PRECEDING) &&
      !a.href.includes('/stories/') && a.innerText.trim() !== 'Now Sports');
    return before.at(-1) || null;
  }
  return null;
}"""


def tooltip_time(text):
    """Parse complete visible dates; never substitute collection time."""
    text = re.sub(r'\s+', ' ', text).strip()
    english = re.search(r'(\d{1,2} [A-Za-z]+ \d{4}) at (\d{1,2}:\d{2})(?:\s*(AM|PM))?', text, re.I)
    if english:
        date, clock, ampm = english.groups()
        pattern = '%d %B %Y %I:%M %p' if ampm else '%d %B %Y %H:%M'
        return datetime.strptime(date + ' ' + clock + (' ' + ampm.upper() if ampm else ''), pattern).replace(tzinfo=HK)
    chinese = re.search(r'(\d{4})年\s*(\d{1,2})月\s*(\d{1,2})日.*?(上午|下午)?\s*(\d{1,2}):(\d{2})', text)
    if chinese:
        year, month, day, period, hour, minute = chinese.groups()
        hour = int(hour)
        if period:
            hour = hour % 12 + (12 if period == '下午' else 0)
        return datetime(int(year), int(month), int(day), hour, int(minute), tzinfo=HK)
    raise ValueError('完整發布日期無法解析')


def read_card(page, message):
    original = message.inner_text().strip()
    if not is_football(original):
        return None
    header_handle = message.evaluate_handle(FIND_HEADER)
    try:
        anchor = header_handle.as_element()
        if anchor is None:
            raise ValueError('無法確認 Now Sports 作者及時間連結')
        # Clear a previous tooltip, then hover this exact post's timestamp.
        page.mouse.move(0, 0)
        page.wait_for_function("""() => [...document.querySelectorAll('[role="tooltip"]')]
          .every(e => e.getClientRects().length === 0 || getComputedStyle(e).visibility === 'hidden')""",
                               timeout=4000)
        anchor.hover(timeout=4000)
        tip = page.locator('[role="tooltip"]:visible')
        tip.wait_for(state='visible', timeout=4000)
        described = anchor.get_attribute('aria-describedby')
        if described and tip.get_attribute('id') not in described.split():
            raise ValueError('日期提示不屬於目前貼文')
        published = tooltip_time(tip.inner_text())
        # Hover lazily resolves the timestamp permalink. Wait without clicking.
        deadline = time.monotonic() + 4
        while True:
            try:
                link = canonical_link(anchor.get_attribute('href'))
                break
            except ValueError:
                if time.monotonic() >= deadline:
                    raise
                page.wait_for_timeout(200)
        if not message.evaluate('(m, a) => m.isConnected && a.isConnected', anchor):
            raise ValueError('貼文已被重新載入')
        current = message.inner_text().strip()
        if original != current:
            raise ValueError('貼文在讀取期間改變，略過以免錯配')
        return {'text': current, 'link': link, 'published_at': published.isoformat(),
                'observed_at': datetime.now(HK).isoformat()}
    finally:
        header_handle.dispose()


def collect(profile, max_scrolls=35, max_seconds=420):
    from playwright.sync_api import sync_playwright

    if not (profile / 'Local State').is_file():
        raise ValueError('專用 Chrome 尚未登入；先執行 --login')
    rows, attempted, errors = {}, set(), []
    started = time.monotonic()
    with sync_playwright() as playwright:
        context = playwright.chromium.launch_persistent_context(
            str(profile), channel='chrome', headless=False, accept_downloads=False,
            locale='en-GB', timezone_id='Asia/Hong_Kong', no_viewport=True)
        try:
            context.set_default_timeout(5000)
            page = context.pages[0] if context.pages else context.new_page()
            page.goto(PAGE_URL, wait_until='domcontentloaded', timeout=60000)
            page.locator('[data-ad-preview="message"]').first.wait_for(state='attached', timeout=20000)
            if page.locator('input[name="email"]:visible').count() or '/checkpoint' in page.url or '/login' in page.url:
                raise ValueError('Facebook 登入失效或需要驗證；保留上次資料')
            if not page.get_by_role('button', name=re.compile(r'^(Your profile|你的個人檔案|您的個人檔案)$')).count():
                raise ValueError('無法確認 Facebook 登入狀態；請重新登入專用 Chrome')
            for _ in range(max_scrolls):
                if time.monotonic() - started > max_seconds:
                    break
                for message in page.locator('[data-ad-preview="message"]').element_handles():
                    try:
                        text = message.inner_text().strip()
                        if not is_football(text) or text in attempted:
                            continue
                        # Only mark successful cards, so detached/late cards can retry.
                        row = read_card(page, message)
                        if row:
                            rows[row['link']] = row
                            attempted.add(text)
                    except Exception as error:
                        errors.append(type(error).__name__)
                        logging.warning('略過未驗證貼文：%s: %s', type(error).__name__, str(error).split('\n')[0])
                    finally:
                        message.dispose()
                    if time.monotonic() - started > max_seconds:
                        break
                page.mouse.move(0, 0)
                page.mouse.wheel(0, 1000)
                page.wait_for_timeout(1200)
            # Empty visible results cannot distinguish a broken selector from no news.
            if not rows:
                raise ValueError('未能驗證任何足球貼文；不覆寫上次收集檔')
            return {'page_url': PAGE_URL, 'status': 'ok', 'coverage': 'partial',
                    'collected_at': datetime.now(HK).isoformat(),
                    'diagnostics': {'verified_posts': len(rows), 'read_errors': len(errors)},
                    'posts': list(rows.values())}
        finally:
            context.close()


def login(profile):
    from playwright.sync_api import sync_playwright

    profile.mkdir(parents=True, exist_ok=True, mode=0o700)
    with sync_playwright() as playwright:
        context = playwright.chromium.launch_persistent_context(
            str(profile), channel='chrome', headless=False, locale='en-GB',
            timezone_id='Asia/Hong_Kong', accept_downloads=False)
        try:
            page = context.pages[0] if context.pages else context.new_page()
            page.goto(PAGE_URL, wait_until='domcontentloaded', timeout=60000)
            input('請在專用 Chrome 登入 Facebook，完成後回到終端機按 Enter 關閉：')
        finally:
            context.close()


def main():
    # A runner timeout first requests graceful cleanup of Chrome/profile locks.
    def terminate(*_):
        raise SystemExit(143)
    signal.signal(signal.SIGTERM, terminate)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', type=Path, required=True)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--login', action='store_true')
    parser.add_argument('--max-scrolls', type=int, default=35)
    args = parser.parse_args()
    if args.login:
        login(args.profile)
    else:
        if not args.output or not 1 <= args.max_scrolls <= 60:
            parser.error('需要 --output，max-scrolls 必須介乎 1 至 60')
        payload = collect(args.profile, args.max_scrolls)
        args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        args.output.chmod(0o600)
        print(f"已驗證 {len(payload['posts'])} 篇足球貼文；遍歷範圍：partial")


if __name__ == '__main__':
    main()
