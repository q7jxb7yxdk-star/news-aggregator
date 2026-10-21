"""Plan or install the user's daily 13:00 Now Sports LaunchAgent."""

import argparse
from importlib.metadata import version
import json
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys

from run_now_sports import DEFAULT_STATE

LABEL = 'com.sunnyyu.news-aggregator.now-sports'
FILES = ('now_sports.py', 'collect_now_sports.py', 'run_now_sports.py')


def make_plist(state=DEFAULT_STATE, python=None):
    state = state.resolve()
    return {
        'Label': LABEL,
        'ProgramArguments': [python or sys.executable, '-B', str(state / 'runtime/run_now_sports.py'),
                             '--state-dir', str(state)],
        'WorkingDirectory': str(state),
        'StartCalendarInterval': {'Hour': 13, 'Minute': 0},
        'RunAtLoad': False,
        'ExitTimeOut': 30,
        'ProcessType': 'Interactive',
        'EnvironmentVariables': {'PATH': '/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin',
                                 'TZ': 'Asia/Hong_Kong', 'PYTHONUNBUFFERED': '1'},
        'StandardOutPath': str(state / 'logs/stdout.log'),
        'StandardErrorPath': str(state / 'logs/stderr.log'),
    }


def install(profile_source=None):
    if sys.platform != 'darwin':
        raise RuntimeError('LaunchAgent 只適用於 macOS')
    if version('playwright') != '1.63.0':
        raise RuntimeError('請先安裝 requirements-now-sports.txt 指定版本')
    timezone = subprocess.run(['/bin/date', '+%z'], check=True, capture_output=True, text=True).stdout.strip()
    if timezone != '+0800':
        raise RuntimeError('系統時區並非香港 UTC+8；StartCalendarInterval 使用系統時區，請先確認')
    if not Path('/Applications/Google Chrome.app').exists():
        raise RuntimeError('找不到 Google Chrome')
    state = DEFAULT_STATE
    plist_path = Path.home() / 'Library/LaunchAgents' / (LABEL + '.plist')
    service = f'gui/{os.getuid()}/{LABEL}'
    loaded = subprocess.run(['/bin/launchctl', 'print', service], capture_output=True).returncode == 0
    if loaded:
        raise RuntimeError('排程已載入；請先手動 bootout，再重新安裝')
    profile = state / 'chrome-profile'
    if profile_source:
        profile_source = profile_source.expanduser().resolve()
        # Never import the user's everyday Chrome profile.
        normal = Path.home() / 'Library/Application Support/Google/Chrome'
        if profile_source == normal or normal in profile_source.parents:
            raise RuntimeError('只接受本工作的專用測試 profile，不接受日常 Chrome profile')
        if not (profile_source / 'Local State').is_file() or profile.exists():
            raise RuntimeError('測試 profile 無效，或目的 profile 已存在；未覆寫')
        if any((profile_source / item).exists() or (profile_source / item).is_symlink()
               for item in ('SingletonLock', 'SingletonSocket', 'SingletonCookie')):
            raise RuntimeError('測試 Chrome 可能仍在執行；請先關閉')
    elif not (profile / 'Local State').is_file():
        raise RuntimeError('需要 --profile-source 專用測試 profile，或先建立 chrome-profile 並登入')
    os.umask(0o077)
    state.mkdir(parents=True, exist_ok=True, mode=0o700)
    (state / 'runtime').mkdir(exist_ok=True, mode=0o700)
    (state / 'logs').mkdir(exist_ok=True, mode=0o700)
    if profile_source:
        shutil.copytree(profile_source, profile, ignore=shutil.ignore_patterns(
            'Singleton*', 'DevToolsActivePort', 'Cache', 'Code Cache', 'GPUCache',
            '*.py', '*.png', '*.log'))
        profile.chmod(0o700)
    for name in FILES:
        shutil.copy2(Path(__file__).with_name(name), state / 'runtime' / name)
    plist_path.parent.mkdir(parents=True, exist_ok=True)
    with plist_path.open('wb') as output:
        plistlib.dump(make_plist(), output)
    plist_path.chmod(0o600)
    subprocess.run(['/usr/bin/plutil', '-lint', str(plist_path)], check=True)
    subprocess.run(['/bin/launchctl', 'bootstrap', f'gui/{os.getuid()}', str(plist_path)], check=True)
    subprocess.run(['/bin/launchctl', 'print', service], check=True)
    print('已啟用每日 13:00 排程；RunAtLoad=false，安裝時不執行收集或推送。')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--install', action='store_true', help='複製程式／專用 profile，寫入並載入 LaunchAgent')
    parser.add_argument('--profile-source', type=Path)
    parser.add_argument('--write-plist', type=Path, help='只產生 plist 供檢查，不啟用')
    args = parser.parse_args()
    if args.install:
        install(args.profile_source)
    elif args.write_plist:
        with args.write_plist.open('wb') as output:
            plistlib.dump(make_plist(), output)
    else:
        print(json.dumps(make_plist(), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
