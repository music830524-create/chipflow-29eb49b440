# 籌碼流向（手機網頁）

靜態網站（GitHub Pages）：族群 → 個股 的外資／投信 1/5/10/20 日買賣超、近20日K線（含量與5MA/20MA），加上重點股的 ToAlpha 券商評等、新聞、財報、法說會。
籌碼與價格來自證交所／櫃買中心公開資料；族群＝`baskets.json`（自訂 26 個主題）＋`baskets_ext.json`（新增 34 個族群，參考外部分類）＋證交所官方產業別。
**不要把 token、API key 放進這個 repo。** `toalpha_in/`（ToAlpha 原始回傳）已被 .gitignore 排除，不會上傳。

## 每日重建流程（交易日 17:30 之後；由 agent 執行）

需要：box 上有 `/workspace/backtest-chip`（含 raw/ 與 live.py）、`gh` 已登入、ToAlpha MCP（`user-toalpha`）。

1. 補資料並判斷是否交易日
   ```
   cd /workspace/chipflow_site
   python3 build.py fetch      # 補抓 TWSE/TPEx 今日資料
   python3 build.py check      # exit 3 = 今天沒資料（假日/休市）→ 整個流程停止，不 publish
   python3 build.py select     # 印出 data date、流入/流出族群、重點股清單（約39檔），寫 data/selected.json
   ```
2. 用 ToAlpha MCP 查詢重點股（以下每個呼叫都帶 `write_to_file: true`，把回傳存成檔；每分鐘約 60 次上限內，分批平行呼叫）
   - `calendar(kind="法說會", days=45, limit=300)` ×1
   - `news(stock_ids="<≤20檔逗號分隔>", days=14, limit=100)` ×2 → 熱門股會吃光額度，所以**再補**：新聞少於3則或沒有的股票，每 4 檔一組 `news(days=30, limit=40)`
   - 每檔各一次 `broker_ratings(stock_id, days=60, limit=6)` 與 `financials(stock_id, period="quarter", n=2)`
3. 把存檔分類到 `toalpha_in/`
   ```
   rm -f toalpha_in/*     # 先清掉前一天的
   python3 ingest.py /workspace/agent-tools --since-minutes 30   # broker_ratings / financials / news / calendar 依內容自動歸檔
   ```
   （write_to_file 的檔案都在 `/workspace/agent-tools/`；ingest 只認內容，不需手動對應檔名。）
4. 產生並上線
   ```
   python3 build.py build      # 產生 data/flows.json、data/detail.json、data/k/<代號>.json（每檔近20日K線＋逐日籌碼，約1,960檔）與 index.html
   python3 build.py publish    # git add/commit/push origin main → GitHub Pages 約 1 分鐘更新
   curl -sI https://<帳號>.github.io/<repo>/ | head -1   # 驗證 200
   ```

流程與 v1 完全相同（fetch → check → select → ToAlpha → ingest → build → publish）；新增的 `data/k/` 由 build 自動產生並隨 publish 一起提交，不需另外步驟。
需要 ≥40 個交易日的 raw 資料（mi/t86/tpq/tpinst；20日籌碼 + 20MA 暖機），box 上目前已有約 240 個交易日，fetch 每次會回頭補近30個交易日缺的端點；若不足 build 會報錯並提示先 fetch。

缺資料時（ToAlpha 沒回、少某檔）頁面會顯示「無資料」，不會編造。

## 檔案
- `build.py` fetch|check|select|build|publish — 計算與產生資料
- `parse_toalpha.py` — 把 ToAlpha 原始 JSON 轉為頁面資料
- `ingest.py` — 依內容把 MCP 存檔歸檔到 `toalpha_in/`
- `index.src.html` → `index.html`（`__VER__` 會被換成日期時間，避免手機快取）
- `baskets.json` — 主題族群成分（26 個；僅代號）。來源：`/workspace/strong_daily/20261030/baskets.json`（強勢族群日報 pipeline 的 `basket.py` 裡手寫的 B 字典，由當時的 agent 人工挑選，非 ToAlpha、非交易所分類；10/21 起 13→20→23→26 個，10/28 起成分不變）。本站是 2026-10-30 的快照，不會每日自動同步；要增減題材請直接改本檔後重新 build。官方產業＝`/workspace/backtest-chip/raw/twse_company.json` 的「產業別」代碼對照 `build.py` 的 IND（僅上市、≥3檔）。
- `baskets_ext.json` — 新增族群（參考外部分類，2026-10-30 新增 34 個；BBU、探針卡/測試座、ATE、檢測驗證、廠務工程、半導體設備、CoWoS設備、液冷、HVDC、矽光子/CPO、低軌衛星、軍工、儲能、生技、觀光等）。格式 `{族群: {ids:[代號], label, source}}`；每族群的參考來源寫在 `source`，顯示在族群頁。成分股由人工比對公司業務與 FinLab／MoneyDJ／經濟日報／工商時報／財報狗／口袋學堂等清單後列入，代號與簡稱皆對過證交所/櫃買資料；未上市櫃或興櫃股不收。`build.py` 的 `ext_sectors()` 自己讀此檔（每次 build 都會算 1/5/10/20 日籌碼與 20 日指數），輸出到 flows.json 的 `ext`，前端第三個分頁「新增族群」顯示。**不參與 `pick()`**：重點股／個股詳情仍只由原 26 個籃子決定，所以 18:00 每日流程與排程提示詞不用改；要增減族群改本檔後 build 即可。
- `data/k/<代號>.json` — 每檔個股近20日 OHLC（已還原除權息）、量(張)、5MA/20MA、逐日外資/投信(億)，點進個股頁才載入
- `data/` — 前端讀取的 json

## 注意
- ToAlpha 條款可能限制資料再散布；本站為個人使用，repo 名稱不可猜、頁面 `noindex`，請勿公開分享連結。
- 評等/目標價為轉述公開報導，以原連結為準；不構成投資建議。
