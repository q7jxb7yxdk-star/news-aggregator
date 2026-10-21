# Now Sports 本機 Chrome → GitHub Pages

分類固定「足球」，來源固定「Now Sports」。只到專頁讀取過去 24 小時的足球資訊，
包含不同聯賽、新聞、精華和直播賽程；不使用搜尋。網站顯示標題、發布時間及原站影片／貼文連結。
不下載影片。FB 可能要求登入或有地區限制，網頁不保證可直接嵌入播放。

## 程式分工

- `collect_now_sports.py`：Playwright 開啟專用、已登入的 Google Chrome，讀取可見貼文與日期 tooltip。
- `now_sports.py`：足球分類、來源／網址／發布時間驗證、24 小時過濾、去重及 JSON 原子替換。
- `run_now_sports.py`：鎖定工作、收集、更新獨立 checkout、只 commit／push `now_sports_posts.json`。
- `setup_now_sports.py`：預覽或安裝每日 13:00 的使用者 LaunchAgent。
- `scraper.py`／GitHub Actions：維持其他來源，只寫 `news.json`。
- `index.html`：合併兩份 JSON；其中一份無法載入不會隱藏另一份；忽略舊 news.json 中的 Now Sports 列。

專頁有置頂、延遲載入和虛擬化。預設最多 35 次捲動、420 秒遍歷，
結果標記 `coverage: partial`，**不能證明已讀齊 24 小時全部貼文**。
讀不到可信時間或來源的貼文不加入；未能驗證任何足球貼文、登入過期或需要驗證時不更新遠端。
有效舊貼文會保留至超過 24 小時。抓到的已驗證貼文本身可以已過期，最後仍由匯入器排除。

## 本機準備及預覽

使用 Python 3.10+、已安裝的 Google Chrome 及 `requirements-now-sports.txt`。
目前測試環境為 Playwright 1.63.0，不需要下載 Playwright Chromium。
若缺少套件，先在準備用的 Python 環境執行：

```bash
python3 -m pip install -r requirements-now-sports.txt
```

只用本工作專用的 Chrome profile，**不要使用日常 Chrome 的 User Data 目錄**。
未有專用登入時：

```bash
python3 -B collect_now_sports.py --profile "$HOME/Library/Application Support/NewsAggregator/chrome-profile" --login
```

登入後只收集／驗證，不執行 Git、不改專案資料：

```bash
python3 -B run_now_sports.py --capture-only
```

結果位於 `~/Library/Application Support/NewsAggregator/preview.json`。
可加 `--max-scrolls 3` 作短測，但此結果更不完整。
在 VS Code 用 Terminal 執行以上命令即可；不要使用 GitHub Pages 瀏覽器連接本機 Chrome。

## 每日 13:00 LaunchAgent

先預覽設定（不寫入、不啟用）：

```bash
python3 -B setup_now_sports.py
```

安裝、複製固定 runtime、保留已登入的本工作測試 profile 並載入排程：

```bash
python3 -B setup_now_sports.py --install --profile-source /path/to/dedicated-test-profile
```

如果目的 `chrome-profile` 已經登入，省略 `--profile-source`。
測試 Chrome 必須已關閉，目的 profile 存在時不覆寫。
安裝器沒有安裝套件、修改 GitHub 設定或立即收集／推送。已載入時會停止，需先手動 bootout 再更新。
程式的後續修改不會自動套用至已安裝 runtime；需重新安裝。

安裝位置：

- `~/Library/LaunchAgents/com.sunnyyu.news-aggregator.now-sports.plist`
- `~/Library/Application Support/NewsAggregator/runtime/`：固定程式副本
- 同目錄的 `chrome-profile/`、`checkout/`、`logs/`、`job.lock`、`last_success.json`

`StartCalendarInterval` 設為 13:00，使用 **Mac 系統時區**；目前系統是香港 UTC+8。
若改系統時區，排程會跟隨改變。需要 Mac 開機、使用者登入並可開啟圖形 Chrome；
睡眠期間不會準時執行，日曆工作可能在喚醒後補跑，關機／登出不能依賴準時補跑。
`RunAtLoad=false`，安裝時不立即執行。同一香港日期已成功完成會略過。

檢查／停止：

```bash
launchctl print "gui/$(id -u)/com.sunnyyu.news-aggregator.now-sports"
tail -n 40 "$HOME/Library/Application Support/NewsAggregator/logs/stderr.log"
launchctl bootout "gui/$(id -u)" "$HOME/Library/LaunchAgents/com.sunnyyu.news-aggregator.now-sports.plist"
```

## 發布及故障處理

首次必須先將新版程式、網頁及初始收集檔提交到 main，網頁才會讀取獨立足球資料。
之後排程才只需發布 `now_sports_posts.json`。首次啟用前應另做一次獲批准的實際發布及 Pages 驗證。
遠端固定 `https://github.com/q7jxb7yxdk-star/news-aggregator.git`、分支 main。
獨立 checkout 初次建立時只讀取 Git 遠端，之後會使用本機 Git 的 Keychain 憑證非互動推送；
不會使用瀏覽器內的 GitHub 登入，也不讀取或輸出 Git 憑證。

開發目錄的未提交變更不受排程修改。發布只 stage 指定 JSON，從不 stash、reset 或 force-push。
若 Git 競爭則最多三次 fetch／rebase／push；同檔衝突或推送失敗保留本機提交／資料，排程停止。
下次若發現 checkout 不乾淨或有未推送提交，亦會停止，需人工確認並處理，避免覆蓋未發布內容。
請在獨立 checkout 檢查 status／log，再決定提交、推送或修復；不要刪掉 checkout 當作重試。

GitHub Pages 必須維持從 main、根目錄發布。這個工具不修改 Pages 設定。
本機一般帳戶 push 與 GitHub Actions 的 GITHUB_TOKEN 行為不同，不能單憑 Actions 綠燈認定 Pages 已部署；
應檢查實際網頁與其 `now_sports_posts.json`。Chrome 登入長期有效、launchd 圖形環境與無人值守 Keychain
仍需運行驗證，不能由靜態檢查或一次手動測試證明。

## 手動資料匯入（保留相容）

```bash
python3 -B now_sports.py /path/to/capture.json --snapshot /path/to/now_sports_posts.json
```

capture 契約：`page_url` 為 Now Sports 專頁、`status: ok`、帶時區 `collected_at`，
`posts` 中每列有 `text`、`link`、帶時區 `observed_at` 與 `published_at`。
舊流程可用 `published_label`，但只接受明確分鐘／小時或剛剛，使用最早可能時間保守過濾。
`--news news.json` 只供舊流程相容；每日排程不使用。
