"""Local scheduled collector; publish only now_sports_posts.json from its own clone."""

import argparse
import fcntl
import json
import os
import signal
from pathlib import Path
import subprocess
import sys
import tempfile

from now_sports import HK, atomic_json, import_capture
from datetime import datetime

REMOTE = 'https://github.com/q7jxb7yxdk-star/news-aggregator.git'
BRANCH = 'main'
TARGET = 'now_sports_posts.json'
DEFAULT_STATE = Path.home() / 'Library/Application Support/NewsAggregator'


def collector_groups(root_pid):
    """Remember descendant groups before parents exit (Chrome may detach)."""
    result = subprocess.run(['/bin/ps', '-axo', 'pid=,ppid=,pgid='],
                            capture_output=True, text=True, check=True, timeout=5)
    rows = [tuple(map(int, line.split())) for line in result.stdout.splitlines() if line.strip()]
    descendants = {root_pid}
    while True:
        found = {pid for pid, parent, _ in rows if parent in descendants}
        if found <= descendants:
            break
        descendants.update(found)
    # Only signal groups led by our own descendants, never the invoking shell.
    return {root_pid} | {group for pid, _, group in rows
                         if pid in descendants and group in descendants and group != os.getpgrp()}


def run_collector(command):
    process = subprocess.Popen(command, start_new_session=True)
    try:
        status = process.wait(timeout=600)
        if status:
            raise RuntimeError(f'Chrome 收集未完成（exit {status}）；未發布')
    except BaseException:
        if process.poll() is None:
            try:
                groups = collector_groups(process.pid)
            except (OSError, subprocess.SubprocessError):
                groups = {process.pid}
            # First allow the collector's finally block to close persistent Chrome.
            try:
                process.terminate()
                try:
                    process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    pass
            finally:
                for group in groups:
                    try:
                        os.killpg(group, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                process.wait(timeout=10)
        raise


def git(repo, *arguments, check=True):
    env = {**os.environ, 'GIT_TERMINAL_PROMPT': '0', 'GIT_ASKPASS': '/usr/bin/false',
           'SSH_ASKPASS': '/usr/bin/false', 'GIT_EDITOR': '/usr/bin/true',
           'GIT_SEQUENCE_EDITOR': '/usr/bin/true'}
    result = subprocess.run(['/usr/bin/git', '-c', 'credential.interactive=false', *arguments],
                            cwd=repo, env=env, capture_output=True, text=True, timeout=90)
    if check and result.returncode:
        # Do not log credential helper responses, embedded URLs or browser data.
        raise RuntimeError('Git ' + arguments[0] + ' 失敗；請檢查網絡、Git 憑證及獨立 checkout')
    return result


def prepare_checkout(state):
    repo = state / 'checkout'
    if not repo.exists():
        git(state, 'clone', '--single-branch', '--branch', BRANCH, REMOTE, str(repo))
        git(repo, 'config', 'user.name', 'Now Sports Local Collector')
        git(repo, 'config', 'user.email', 'q7jxb7yxdk-star@users.noreply.github.com')
    if git(repo, 'remote', 'get-url', 'origin').stdout.strip() != REMOTE:
        raise RuntimeError('獨立 checkout 遠端不符；停止發布')
    if git(repo, 'branch', '--show-current').stdout.strip() != BRANCH:
        raise RuntimeError('獨立 checkout 分支不符；停止發布')
    if git(repo, 'status', '--porcelain', '--untracked-files=all').stdout.strip():
        raise RuntimeError('獨立 checkout 有未提交內容；保留現場，請人工檢查')
    git(repo, 'fetch', 'origin', BRANCH)
    ahead = git(repo, 'rev-list', '--count', f'origin/{BRANCH}..HEAD').stdout.strip()
    if ahead != '0':
        raise RuntimeError('獨立 checkout 有未推送提交；保留現場，請人工處理後重試')
    git(repo, 'merge', '--ff-only', f'origin/{BRANCH}')
    return repo


def publish(repo):
    git(repo, 'add', '--', TARGET)
    paths = git(repo, 'diff', '--cached', '--name-only').stdout.splitlines()
    if paths != [TARGET]:
        if not paths:
            return False
        raise RuntimeError('暫存區包含其他檔案；停止提交')
    git(repo, 'commit', '-m', 'Update Now Sports football ' + datetime.now(HK).isoformat(timespec='seconds'))
    for attempt in range(3):
        result = git(repo, 'push', 'origin', f'HEAD:refs/heads/{BRANCH}', check=False)
        if result.returncode == 0:
            return True
        # Retry only a verified non-fast-forward race. Auth/network failures stop.
        if not any(marker in result.stderr.lower() for marker in ('fetch first', 'non-fast-forward', 'rejected')):
            raise RuntimeError('Git push 失敗；提交保留在獨立 checkout')
        if attempt == 2:
            break
        git(repo, 'fetch', 'origin', BRANCH)
        rebased = git(repo, 'rebase', f'origin/{BRANCH}', check=False)
        if rebased.returncode:
            git(repo, 'rebase', '--abort', check=False)
            raise RuntimeError('遠端有同檔案衝突；保留本機提交，請人工處理')
    raise RuntimeError('遠端持續更新；提交已保留，未強制推送')


def run(state, capture_only=False, profile=None, max_scrolls=35):
    os.umask(0o077)
    state.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (state / 'job.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print('已有收集／發布工作執行中；略過')
            return
        stamp = state / 'last_success.json'
        today = datetime.now(HK).date().isoformat()
        if not capture_only and stamp.exists():
            if json.loads(stamp.read_text())['date'] == today:
                print('今天已成功完成；略過')
                return
        with tempfile.TemporaryDirectory(prefix='capture-', dir=state) as temporary:
            capture = Path(temporary) / 'capture.json'
            command = [sys.executable, '-B', str(Path(__file__).with_name('collect_now_sports.py')),
                       '--profile', str(profile or state / 'chrome-profile'), '--output', str(capture),
                       '--max-scrolls', str(max_scrolls)]
            run_collector(command)
            if capture_only:
                destination = state / 'preview.json'
                import_capture(capture, destination)
                print('僅預覽，未執行 Git：' + str(destination))
                return
            repo = prepare_checkout(state)
            count, rejected = import_capture(capture, repo / TARGET)
            changed = publish(repo)
            atomic_json(stamp, {'date': today, 'completed_at': datetime.now(HK).isoformat()})
            print(f'完成：{count} 篇，略過 {rejected} 篇，已推送={changed}', flush=True)


def main():
    def terminate(*_):
        raise SystemExit(143)
    signal.signal(signal.SIGTERM, terminate)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state-dir', type=Path, default=DEFAULT_STATE)
    parser.add_argument('--capture-only', action='store_true', help='只收集及預覽；不執行任何 Git')
    parser.add_argument('--profile', type=Path, help='只供 capture-only 指定測試專用 profile')
    parser.add_argument('--max-scrolls', type=int, default=35)
    args = parser.parse_args()
    if args.profile and not args.capture_only:
        parser.error('--profile 只適用於 --capture-only')
    if not 1 <= args.max_scrolls <= 60:
        parser.error('max-scrolls 必須介乎 1 至 60')
    try:
        run(args.state_dir.expanduser(), args.capture_only, args.profile, args.max_scrolls)
    except Exception as error:
        print(f'Now Sports 工作失敗：{error}', file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
