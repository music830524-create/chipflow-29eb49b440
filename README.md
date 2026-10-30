# 籌碼流向（手機網頁）

靜態網站（GitHub Pages）：族群 → 個股 的外資／投信 1/5/10 日買賣超，加上重點股的 ToAlpha 券商評等、新聞、財報、法說會。
籌碼與價格來自證交所／櫃買中心公開資料；族群＝`baskets.json`（自訂 25 個主題）＋證交所官方產業別。
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
   python3 build.py build      # 產生 data/*.json 與 index.html
   python3 build.py publish    # git add/commit/push origin main → GitHub Pages 約 1 分鐘更新
   curl -sI https://<帳號>.github.io/<repo>/ | head -1   # 驗證 200
   ```

缺資料時（ToAlpha 沒回、少某檔）頁面會顯示「無資料」，不會編造。

## 檔案
- `build.py` fetch|check|select|build|publish — 計算與產生資料
- `parse_toalpha.py` — 把 ToAlpha 原始 JSON 轉為頁面資料
- `ingest.py` — 依內容把 MCP 存檔歸檔到 `toalpha_in/`
- `index.src.html` → `index.html`（`__VER__` 會被換成日期時間，避免手機快取）
- `baskets.json` — 主題族群成分（來源：`/workspace/strong_daily/<date>/baskets.json`）
- `data/` — 前端讀取的 json

## 注意
- ToAlpha 條款可能限制資料再散布；本站為個人使用，repo 名稱不可猜、頁面 `noindex`，請勿公開分享連結。
- 評等/目標價為轉述公開報導，以原連結為準；不構成投資建議。
