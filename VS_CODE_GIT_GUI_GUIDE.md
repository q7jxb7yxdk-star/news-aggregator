# 🖥️ VS Code Git GUI 操作完整指南

无需打命令，全部用鼠标点击操作！

---

## 📍 準備工作

### 開啟 Source Control 面板
1. VS Code 左邊欄 → 點擊 **分支圖標**（Source Control）
   
   ![image]
   或用快捷鍵：<kbd>Ctrl</kbd> + <kbd>Shift</kbd> + <kbd>G</kbd>（Windows/Linux）
           <kbd>Cmd</kbd> + <kbd>Shift</kbd> + <kbd>G</kbd>（Mac）

---

## 📝 Step 1: 修改文件並暫存

### 1a️⃣ 修改文件
- 在 VS Code 編輯器中修改 `scraper.py`
- 你會看到文件名旁邊有 **白點** 或 **M** 標記（表示已修改）

### 1b️⃣ 在 Source Control 面板中查看修改
- 打開 Source Control 面板
- 在 **"Changes"** 區域可以看到所有修改的文件

### 1c️⃣ 暫存（Add）文件
**方式一**：暫存所有文件
- 在 "Changes" 上方，點擊 **加號 (+)** 按鈕
- 所有修改會移到 "Staged Changes"

**方式二**：暫存單個文件
- 右鍵點擊要暫存的文件
- 選擇 **"Stage Changes"**

---

## 💾 Step 2: 提交（Commit）修改

### 2a️⃣ 在提交訊息欄輸入描述
- 在 Source Control 面板頂部，有一個輸入框
- 輸入提交訊息，例如：`重構 scraper.py：提高效率`

### 2b️⃣ 點擊 Commit
- 點擊輸入框下方的 **勾選圖標** 或 **"Commit"** 按鈕
- 本地提交完成！

---

## 🔄 Step 3: 拉取遠程更新（Pull）

### 3a️⃣ 點擊同步按鈕
- 在 Source Control 面板頂部右側，有一個 **圓形箭頭** 圖標（Sync）
- 直接點擊它

**或者**

- 底部狀態欄 → 點擊 **"拉取/推送"** 的同步圖標

### 3b️⃣ 如果有衝突
VS Code 會提示：
- ❌ "Merge conflict in news.json"
- 點擊 **"Resolve in Merge Editor"** 或在文件中查看衝突

---

## 🆘 Step 4: 解決衝突（GUI 方式）

### 4a️⃣ 查看衝突
- 有衝突的文件會在 Source Control 顯示為 **"U"**（Unresolved）
- 點擊文件名，在編輯器中可以看到衝突標記：

```
<<<<<<< HEAD
  本地內容
=======
  遠程內容
>>>>>>> 遠程分支名
```

### 4b️⃣ 使用合併編輯器（推薦）
- 右鍵衝突文件 → **"Open Merge Editor"**
- 你會看到三個面板：
  - **Current**（本地）
  - **Incoming**（遠程）
  - **Result**（結果）
- 點擊 **"Accept Current"** 或 **"Accept Incoming"** 或 **"Accept Both"**

### 4c️⃣ 手動編輯（進階）
- 直接刪除 `<<<<<<<`、`=======`、`>>>>>>>` 標記
- 保留要的內容
- 編輯完成後，VS Code 自動標記為已解決

### 4d️⃣ 暫存解決後的文件
- 衝突解決後，右鍵文件 → **"Stage Changes"**

### 4e️⃣ 提交合併結果
- 在提交訊息欄輸入：`Resolve merge conflict`
- 點擊 Commit 按鈕

---

## 🚀 Step 5: 推送到遠程（Push）

### 5a️⃣ 點擊推送按鈕
- 底部狀態欄 → 點擊 **推送 (Push)** 圖標
- 或在 Source Control 面板找 **"Publish"** 或 **"Push"** 按鈕

### 5b️⃣ 確認推送
- VS Code 會跳出確認提示
- 點擊 **"Yes"** 推送

---

## 👁️ 查看提交歷史

### 方式 1️⃣：在 Source Control 中查看
- Source Control 面板 → 找 **"COMMITS"** 區域
- 展開查看最近的提交列表

### 方式 2️⃣：使用 Git 圖表（擴展功能）
- 安裝擴展：**Git Graph**（by mhutchie）
  1. 打開擴展市場
  2. 搜索 "Git Graph"
  3. 點擊 Install
- 打開後可視化查看所有分支和提交

### 方式 3️⃣：在文件中查看歷史
- 右鍵任何文件 → **"Open Timeline"** 或 **"View History"**
- 查看該文件的修改歷史

---

## 📊 查看分支

### 查看和切換分支
- Source Control 面板頂部 → 點擊 **分支名稱**
- 彈出菜單顯示所有分支
- 點擊想要切換的分支

### 建立新分支
- 點擊分支名稱 → 選擇 **"Create New Branch"**
- 輸入新分支名稱
- 新分支會自動建立並切換

---

## 🎯 完整工作流（GUI 版）

```
1️⃣ 修改文件
   ↓
2️⃣ Source Control → 看到修改的文件
   ↓
3️⃣ 右鍵文件 → "Stage Changes"（或點擊 + 暫存全部）
   ↓
4️⃣ 在提交訊息欄輸入描述
   ↓
5️⃣ 點擊 ✓ Commit 按鈕
   ↓
6️⃣ 底部狀態欄 → 點擊圓形箭頭同步（Pull + Push）
   ↓
7️⃣ 如有衝突 → 在 Merge Editor 中解決
   ↓
✅ 完成！
```

---

## 🔧 常用按鈕位置對照

| 功能 | 位置 | 圖標 |
|------|------|------|
| **暫存全部** | Source Control 頂部 | ➕ (加號) |
| **清除暫存** | Source Control 頂部 | ⊖ (減號) |
| **查看差異** | 右鍵文件 | 📄 |
| **Commit** | 提交訊息欄下 | ✓ |
| **Sync/Pull** | 底部狀態欄 | 🔄 |
| **Push** | 底部狀態欄 | ⬆️ |
| **分支** | Source Control 頂部 | 🌳 |
| **Merge Editor** | 右鍵衝突文件 | 🔀 |

---

## 💡 小貼士

### ✅ 推薦做法
- 修改一個功能 → 立即 Stage + Commit
- 開始工作前先 Sync（同步遠程）
- 完成工作後立即 Push

### ⌨️ 快捷鍵（可自訂）
```
Cmd + Shift + G    : 打開 Source Control (Mac)
Ctrl + Shift + G   : 打開 Source Control (Windows/Linux)
```

### 🎨 VS Code 主題建議
- 安裝 **GitHub Light/Dark Theme** 看 git 更清楚
- 或使用 **One Dark Pro** 獲得更好的對比

---

## 🚀 進階：安裝有用的 Git 擴展

### 推薦擴展
1. **Git Graph** - 可視化提交歷史
2. **GitLens** - 查看每行代碼的作者和修改時間
3. **Git History** - 快速查看文件修改歷史
4. **Merge Conflict Resolver** - 更好地解決衝突

### 安裝步驟
1. VS Code 左側欄 → 點擊 **擴展圖標** (或 Cmd+Shift+X)
2. 搜索擴展名稱
3. 點擊 **Install**

---

## 🆘 遇到問題？

### ❓ "Cannot commit: no staged files"
→ 需要先 Stage 文件（點擊 + 按鈕或右鍵選擇 Stage）

### ❓ 無法 Push
→ 先 Sync（Pull 遠程更新），解決衝突後再 Push

### ❓ 不小心 Commit 了錯誤的內容
→ 右鍵最後一個 commit → "Revert Commit"

### ❓ 想回到某個之前的版本
→ 在 Git Timeline 中找到那個版本 → 點擊 "Revert to This Commit"

---

**祝你使用愉快！🎉**

