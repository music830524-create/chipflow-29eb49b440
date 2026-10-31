"""用 Python 直接呼叫 ToAlpha 公開 MCP 端點（streamable-http / JSON-RPC：initialize → tools/call），
取得重點股的券商評等、財報、新聞、法說會，存成 toalpha_in/（與舊流程同檔名，parse_toalpha.py 直接讀）。
- 預設不帶金鑰；若環境變數 TOALPHA_API_KEY 存在（例如 GitHub Secrets）才帶 Authorization: Bearer。金鑰絕不寫進檔案或 log。
- 節流：呼叫間隔 ≥ 1.3 秒（≈0.77 次/秒、約 46 次/分，低於公開額度 60/分）；HTTP 429 依 Retry-After 或指數退避重試。
- 單一呼叫失敗（逾時、5xx、重試用盡）只記進 toalpha_in/_status.json，不拋例外；build 會對失敗的股票沿用上次資料並標註日期。
- 範圍＝baskets.json＋baskets_ext.json 全部成分（約 379 檔）。每天約 600 次呼叫：calendar 1、news 約 50–70、broker_ratings 379、financials：重點股 39 檔每天＋其餘每 3 天輪抓（約 110）。上限 1500 次／45 分鐘。
用法：python3 toalpha_fetch.py        （讀 data/selected.json）"""
import os, sys, json, time, shutil, urllib.request, urllib.error

H = os.path.dirname(os.path.abspath(__file__))
URL = "https://toalpha.tw/mcp"
OUT = H + "/toalpha_in"
MIN_GAP = 1.3          # 秒
MAX_TRIES = 5
TIMEOUT = 40

class Client:
    def __init__(self):
        self.key = os.environ.get("TOALPHA_API_KEY", "").strip()
        self.last = 0.0; self.n = 0; self.rid = 0; self.n429 = 0; self.sid = None
    def _post(self, method, params):
        gap = MIN_GAP - (time.time() - self.last)
        if gap > 0: time.sleep(gap)
        self.rid += 1
        h = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
        if self.key: h["Authorization"] = "Bearer " + self.key
        if self.sid: h["Mcp-Session-Id"] = self.sid
        req = urllib.request.Request(URL, data=json.dumps({"jsonrpc": "2.0", "id": self.rid, "method": method, "params": params}).encode(), headers=h)
        self.last = time.time(); self.n += 1
        r = urllib.request.urlopen(req, timeout=TIMEOUT)
        self.sid = r.headers.get("Mcp-Session-Id") or self.sid
        body = r.read().decode("utf-8")
        ct = r.headers.get("Content-Type", "")
        if "text/event-stream" in ct:       # SSE：取最後一個 data: 行
            datas = [l[5:].strip() for l in body.splitlines() if l.startswith("data:")]
            body = datas[-1] if datas else "{}"
        return json.loads(body)
    def rpc(self, method, params):
        err = None
        for i in range(MAX_TRIES):
            try:
                return self._post(method, params)
            except urllib.error.HTTPError as e:
                err = "HTTP %s" % e.code
                if e.code == 429:
                    self.n429 += 1
                    ra = e.headers.get("Retry-After")
                    wait = float(ra) if ra and ra.replace(".", "", 1).isdigit() else 15 * (2 ** i)
                    print("  429，等 %.0f 秒後重試" % min(wait, 120), file=sys.stderr, flush=True); time.sleep(min(wait, 120))
                elif e.code >= 500: time.sleep(5 * (i + 1))
                else: break                  # 4xx（非429）重試無意義
            except Exception as e:
                err = repr(e)[:80]; time.sleep(5 * (i + 1))
        raise RuntimeError(err or "failed")
    def init(self):
        self.rpc("initialize", {"protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {"name": "chipflow-daily", "version": "1"}})
    def tool(self, name, args):
        """回傳工具結果（解析後的 JSON dict）；失敗回傳 None。"""
        try:
            j = self.rpc("tools/call", {"name": name, "arguments": args})
            res = j.get("result") or {}
            if "error" in j or res.get("isError"): return None
            txt = "".join(c.get("text", "") for c in res.get("content", []) if c.get("type") == "text")
            return json.loads(txt)
        except Exception as e:
            print("  失敗 %s %s：%s" % (name, args.get("stock_id") or args.get("stock_ids", ""), str(e)[:60]), file=sys.stderr, flush=True)
            return None

def dump(name, j): json.dump(j, open(f"{OUT}/{name}", "w", encoding="utf-8"), ensure_ascii=False)

MAX_CALLS = 1500       # 單次執行呼叫上限（安全閥；正常約 600）
MAX_SECONDS = 45 * 60  # 單次執行時間上限；超過就停手，沒抓到的沿用舊資料
FIN_EVERY = 3          # 非重點股財報每 3 天輪抓一次（財報一季才變一次）

def fin_due(sid, key, ordinal, prev):
    """重點股每天抓財報；其他股每 FIN_EVERY 天輪到一次；從沒抓過財報的一律先抓。"""
    if sid in key or not (prev.get(sid) or {}).get("fin"): return True
    return (int(sid) + ordinal) % FIN_EVERY == 0 if sid.isdigit() else True

def run():
    import datetime as dt
    j0 = json.load(open(H + "/data/selected.json")); sel = j0["stocks"]; key = set(j0.get("key") or sel)
    # 重點股排前面：萬一達到上限／時間限制，被犧牲的是非重點股（沿用舊資料並標日期）
    ids = sorted(sel, key=lambda i: (i not in key,)) 
    try: prev = json.load(open(H + "/data/detail.json")).get("detail", {})
    except Exception: prev = {}
    ordinal = dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).date().toordinal()
    shutil.rmtree(OUT, ignore_errors=True); os.makedirs(OUT)
    c = Client(); st = dict(broker_ratings=[], financials=[], news=[], calendar=False, fin_skip=[])
    t0 = time.time()
    def over(): return c.n >= MAX_CALLS or time.time() - t0 > MAX_SECONDS
    try: c.init()
    except Exception as e:
        print("ToAlpha initialize 失敗：", e); st = dict(broker_ratings=ids, financials=ids, news=ids, calendar=True, fin_skip=[], fatal=str(e)[:80])
        json.dump(st, open(OUT + "/_status.json", "w")); return st
    # 法說會
    j = c.tool("calendar", dict(kind="法說會", days=45, limit=500))
    if j and "events" in j: dump("calendar_conf.txt", j)
    else: st["calendar"] = True
    # 新聞：每 20 檔一批（14 天）；新聞少於 3 則的再每 8 檔一組補查 30 天。回傳筆數達 limit 視為被截斷 → 對半拆開重查
    got = {}; nfail = set(); nfile = [0]
    def add_news(j):
        for i in j.get("items", []): got.setdefault(i["id"], {})[i.get("url") or i["title"]] = i
    def news(b, days, limit, tag):
        if over(): nfail.update(b); return
        j = c.tool("news", dict(stock_ids=",".join(b), days=days, limit=limit))
        if not (j and "items" in j): nfail.update(b); return
        if len(j["items"]) >= limit and len(b) > 1:
            h = len(b) // 2; news(b[:h], days, limit, tag); news(b[h:], days, limit, tag); return
        nfile[0] += 1; dump(f"news_{tag}{nfile[0]:03d}.txt", j); add_news(j)
    for k in range(0, len(ids), 20): news(ids[k:k + 20], 14, 300, "")
    thin = [i for i in ids if len(got.get(i, {})) < 3 and i not in nfail]
    for k in range(0, len(thin), 8): news(thin[k:k + 8], 30, 300, "x")
    st["news"] = sorted(nfail)
    # 每檔券商評等；財報依輪抓規則
    for sid in ids:
        if over():
            st["broker_ratings"].append(sid)
            if fin_due(sid, key, ordinal, prev): st["financials"].append(sid)
            else: st["fin_skip"].append(sid)
            continue
        j = c.tool("broker_ratings", dict(stock_id=sid, days=60, limit=6))
        if j and "ratings" in j: dump(f"broker_ratings_{sid}.json", j)
        else: st["broker_ratings"].append(sid)
        if not fin_due(sid, key, ordinal, prev): st["fin_skip"].append(sid); continue
        j = c.tool("financials", dict(stock_id=sid, period="quarter", n=2))
        if j and "rows" in j: dump(f"financials_{sid}.json", j)
        else: st["financials"].append(sid)
    st["calls"] = c.n; st["n429"] = c.n429; st["secs"] = round(time.time() - t0); st["capped"] = over()
    json.dump(st, open(OUT + "/_status.json", "w"))
    print("ToAlpha 呼叫 %d 次（429 共 %d 次）、耗時 %d 秒；涵蓋 %d 檔（重點 %d）；失敗：評等%d 財報%d（輪休略過 %d）新聞%d 法說%s%s" % (
        c.n, c.n429, st["secs"], len(ids), len(key), len(st["broker_ratings"]), len(st["financials"]), len(st["fin_skip"]), len(st["news"]), "是" if st["calendar"] else "否",
        "；已達上限／時間限制，部分沿用舊資料" if st["capped"] else ""))
    return st

if __name__ == "__main__":
    run()
