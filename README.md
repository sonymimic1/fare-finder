# Fare Finder

為 Flight Price Notifier（機票降價通知）建立一個 SaaS 產品的 Landing Page 加上需登入的應用程式外殼（app shell）。這個產品會監控從台北出發的熱門航線，當最低票價降到使用者設定的目標價（含）以下時，以 email 通知使用者——目標客群是預算導向的旅客：他們不在乎確切的出發時間，只想買到預算內的機票。 網站必須包含： 一個公開的 Landing Page（路徑 `/`），內容如下： - Hero 區塊：醒目地顯示產品名稱 "Flight Price Notifier"，價值主張為「設定航線與目標價，機票降價就通知你」（英文副標題："Set a route and a target price — we email you when the fare drops."），並在頁首右上角放一個主要 CTA 按鈕，文字為 "Sign in / 登入"。 - Features 區塊，恰好包含 3 張功能卡片： - 卡片 1：「盯緊熱門航線 (Always-on route watching)」— 持續監控台北出發的熱門航線（東京、首爾），自動抓最低票價。 - 卡片 2：「達標自動通知 (Target-price email alerts)」— 低於你設定的目標價，就寄 email 提醒你，附上立即訂購連結。 - 卡片 3：「隨時取消 (Cancel anytime)」— 月訂閱制，不想用隨時停，沒有綁約。 - Footer，顯示版權文字「© 2026 Flight Price Notifier」。 身分驗證：使用 Lovable 內建的 Supabase 式驗證（使用 Lovable 預設提供的任何驗證後端即可——這個 v1 版本用 Lovable Cloud 沒問題；我們會在之後的步驟換成使用者自有的 Supabase 專案）： - 註冊（Sign Up）頁面：email + 密碼 - 登入（Sign In）頁面：email + 密碼 - 登出（Sign Out）功能 - 為求簡化，v1 可以停用 email 確認 一個需登入的應用程式外殼，路徑為 `/app`，使用者登入後會導向這裡： - 以 email 向已登入的使用者打招呼：「Hi {user.email}」 - 一段佔位訊息：「你的航線追蹤儀表板即將上線 — 下一個里程碑會加上訂閱航線的功能。」（英文："Your dashboard is coming soon. Route-subscription will be added in the next milestone."） - 頁首有一個登出（Sign Out）按鈕 設計需求： - 現代、專業的深色主題（近黑色背景，搭配紫色 / 紫羅蘭色的強調色） - 使用 Inter 或類似的無襯線字體 - 支援行動裝置的響應式設計 - 適度、低調的動畫（捲動時淡入即可；不要過度） v1 不在範圍內的項目：航線訂閱表單、目標價輸入、票價顯示、付款功能、自訂資料庫資料表（**不要**建立 subscriptions 或 profiles 資料表——只使用 Supabase 預設的 auth.users）。這些會在之後的里程碑加入。請只做 Landing Page + 身分驗證 + 佔位用的儀表板。

This project was built with [Lovable](https://lovable.dev).

## Build with Lovable

Continue developing this project in the [Lovable editor](https://lovable.dev/projects/bba58699-65f7-47ab-8123-ff5b810ea052).

- **Ship faster**: describe what you want to build and Lovable handles the code.
- **Stay in sync**: every change made in Lovable is committed straight to this repository.
- **Full ownership**: this code is yours. Push to `main` on GitHub and your changes sync back into Lovable, ready for your next prompt.

## Development

Prefer working locally? You need Node.js and npm — [install with nvm](https://github.com/nvm-sh/nvm#installing-and-updating).

```sh
git clone <this-repository-url>
cd <repository-name>
npm i
npm run dev
```
