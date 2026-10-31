# 籌碼流向（手機網頁）

靜態網站（GitHub Pages）：族群 → 個股 的外資／投信 1/5/10/20 日買賣超、近20日K線（含量與5MA/20MA），加上重點股的 ToAlpha 券商評等、新聞、財報、法說會。
籌碼與價格來自證交所／櫃買中心公開資料；族群＝`baskets.json`（自訂 26 個主題）＋`baskets_ext.json`（新增 34 個族群，參考外部分類）＋證交所官方產業別。
**不要把 token、API key 放進這個 repo。** `toalpha_in/`（ToAlpha 原始回傳，每次執行重新產生）已被 .gitignore 排除，不會上傳。

## 每日更新流程（完全由 GitHub Actions 執行，不需要 LLM／agent／排程）

`.github/workflows/daily-update.yml`：
- **排程**：`cron: '0 10 * * 1-5'`（UTC 10:00＝台北平日 18:00；GitHub 可能延遲數分鐘到數十分鐘）。也能到 Actions 頁手動「Run workflow」（`force` 勾選＝略過「今天是否交易日」檢查，用最新完整交易日重建，測試或補跑用）。
- **權限**：`permissions: contents: write, pages: write`，只用內建 `GITHUB_TOKEN` 推回 `main`；repo 內沒有任何 token。
- **步驟**：`python3 daily.py`
  1. `fetch`：`pubdata.py` 直接抓證交所／櫃買中心公開資料（收盤行情 MI_INDEX、三大法人 T86、上櫃 otc、上櫃法人 dailyTrade，皆 JSON；另有除權息 TWT49U／exDailyQ、上市公司產業別），壓縮成 `hist/<日期>.json`（只留普通股，保留近 60 個交易日）與 `src/`。近 7 天缺漏或不完整的日子會回頭補。
  2. `check`：今天 TWSE 無行情＝休市 → 直接結束、不 commit；行情已出但法人/上櫃資料未齊 → 每 5 分鐘重試（最多 30 分鐘），仍未齊就用最新完整交易日重建，隔天補上。
  3. `select`：**純程式規則**挑重點股（`build.py` 的 `pick()`）：原 26 個主題籃子依近 5 日外資＋投信合計排序，流入前 10 名各取買超最多 3 檔、流出前 5 名各取賣超最多 2 檔，約 39 檔（寫 `data/selected.json`）。
  4. `toalpha_fetch.py`：用 Python 直接呼叫 ToAlpha 公開 MCP 端點 `https://toalpha.tw/mcp`（JSON-RPC：`initialize` → `tools/call`）。每天約 **88 次**：`calendar` 1、`news` 2＋補查約 5、`broker_ratings` 39、`financials` 39。呼叫間隔 ≥1.3 秒（約 46 次/分，低於公開額度 60 次/分、5,000 次/日），429 依 `Retry-After` 或指數退避重試；單一呼叫失敗不會讓 build 失敗——該檔該類資料沿用上次 `detail.json`，頁面標「本次抓取失敗，沿用 YYYY-MM-DD 的資料」。
  5. `build`：產生 `data/flows.json`、`data/detail.json`、`data/k/*.json`、`index.html`。
  6. 有變更才 `git commit`＋`git push`（訊息 `update <資料日> (actions)`），並呼叫 Pages API 要求重新建置（GitHub Pages 約 1 分鐘更新）。
- **選用金鑰**：到 repo Settings → Secrets and variables → Actions 新增 `TOALPHA_API_KEY`，程式就會帶 `Authorization: Bearer`；沒設就不帶（公開額度，照 IP 計算；GitHub 的 runner IP 是共用的，若常被 429 再考慮設金鑰）。金鑰只存在 Secrets，不寫進檔案或 log。

本機也能跑同一支：`python3 daily.py [--force] [--no-toalpha]`（只需 Python 3 標準庫，無需安裝套件；`python3 build.py publish` 仍可手動 commit/push）。

需要 ≥40 個交易日的 `hist/`（K線20根＋20MA暖機）；repo 內已附近 50 日，之後每天增量。若不足，build 會報錯並提示。

缺資料時（ToAlpha 沒回、少某檔）頁面會顯示「無資料」或沿用舊資料並標日期，不會編造。

## 檔案
- `build.py` fetch|check|select|build|publish — 計算與產生資料
- `daily.py` — 每日流程總入口（Actions 與本機共用）
- `pubdata.py` — 證交所／櫃買中心公開資料抓取與壓縮（`hist/`、`src/`）
- `toalpha_fetch.py` — 直接呼叫 ToAlpha MCP 取重點股評等／新聞／財報／法說（寫 `toalpha_in/`）
- `parse_toalpha.py` — 把 ToAlpha 原始 JSON 轉為頁面資料
- `hist/<日期>.json` — 每日行情＋外資／投信（張）壓縮檔；`src/exright.csv` 除權息還原因子、`src/company.json` 上市公司產業別、`src/holidays.json` 已確認休市日
- `index.src.html` → `index.html`（`__VER__` 會被換成日期時間，避免手機快取）
- `baskets.json` — 主題族群成分（26 個；僅代號）。來源：`/workspace/strong_daily/20261030/baskets.json`（強勢族群日報 pipeline 的 `basket.py` 裡手寫的 B 字典，由當時的 agent 人工挑選，非 ToAlpha、非交易所分類；10/21 起 13→20→23→26 個，10/28 起成分不變）。族群設定留在 repo，Actions 每天直接讀取；要增減題材請直接改本檔後重新 build。官方產業＝`src/company.json`（證交所 openapi t187ap03_L 的「產業別」）代碼對照 `build.py` 的 IND（僅上市、≥3檔）。
- `baskets_ext.json` — 新增族群（參考外部分類，2026-10-30 新增 34 個；BBU、探針卡/測試座、ATE、檢測驗證、廠務工程、半導體設備、CoWoS設備、液冷、HVDC、矽光子/CPO、低軌衛星、軍工、儲能、生技、觀光等）。格式 `{族群: {ids:[代號], label, source}}`；每族群的參考來源寫在 `source`，顯示在族群頁。成分股由人工比對公司業務與 FinLab／MoneyDJ／經濟日報／工商時報／財報狗／口袋學堂等清單後列入，代號與簡稱皆對過證交所/櫃買資料；未上市櫃或興櫃股不收。`build.py` 的 `ext_sectors()` 自己讀此檔（每次 build 都會算 1/5/10/20 日籌碼與 20 日指數），輸出到 flows.json 的 `ext`，前端第三個分頁「新增族群」顯示。**不參與 `pick()`**：重點股／個股詳情仍只由原 26 個籃子決定，所以不影響每日重點股流程；要增減族群改本檔後 build 即可。
- `data/k/<代號>.json` — 每檔個股近20日 OHLC（已還原除權息）、量(張)、5MA/20MA、逐日外資/投信(億)，點進個股頁才載入
- `data/` — 前端讀取的 json

## 注意
- ToAlpha 條款可能限制資料再散布；本站為個人使用，repo 名稱不可猜、頁面 `noindex`，請勿公開分享連結。
- 評等/目標價為轉述公開報導，以原連結為準；不構成投資建議。
