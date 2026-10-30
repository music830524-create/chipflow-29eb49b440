#!/usr/bin/env python3
"""籌碼流向手機網頁 build 腳本。

流程（每個交易日 17:30 後）：
  python3 build.py fetch            # 補抓 TWSE/TPEx 當日資料（沿用 /workspace/backtest-chip/live.py 的抓取）
  python3 build.py select           # 算完籌碼後，印出需要查 ToAlpha 的股票清單（寫 data/selected.json）
  ... agent 依 README 用 ToAlpha MCP 查詢，結果存 toalpha_in/<tool>_<id>.json ...
  python3 build.py build            # 產生 data/flows.json、data/detail.json、data/k/<代號>.json（近20日K線）、index.html
  python3 build.py publish          # git commit + push（GitHub Pages）
  python3 build.py all              # fetch + select + build（假設 toalpha_in 已備好）+ 不含 publish

視窗：1/5/10/20 個交易日；K線 20 根（OHLC 取自 mi 每日收盤行情與 tpq，經 exright.csv 因子還原；MA20 需 40 個交易日 raw）。
資料：籌碼與價格＝證交所／櫃買中心公開資料；族群＝baskets.json（自訂主題族群）與證交所官方產業別（上市）；
      個股詳情＝ToAlpha MCP（券商評等、新聞、財報、法說會）。
"""
import os, sys, json, glob, re, subprocess, datetime as dt
H = os.path.dirname(os.path.abspath(__file__))
CHIP = "/workspace/backtest-chip"
RAW = CHIP + "/raw"
TZ = dt.timezone(dt.timedelta(hours=8))
N_IN, N_OUT = 10, 5          # 詳情頁：流入前 N_IN 個族群、流出前 N_OUT 個族群
K_IN, K_OUT = 3, 2           # 每個族群取幾檔（依 5 日合計買/賣超金額）
IND = {'01':'水泥','02':'食品','03':'塑膠','04':'紡織','05':'電機機械','06':'電器電纜','08':'玻璃陶瓷','09':'造紙','10':'鋼鐵','11':'橡膠','12':'汽車','14':'建材營造','15':'航運','16':'觀光餐旅','17':'金融保險','18':'貿易百貨','20':'其他','21':'化學','22':'生技醫療','23':'油電燃氣','24':'半導體','25':'電腦週邊','26':'光電','27':'通信網路','28':'電子零組件','29':'電子通路','30':'資訊服務','31':'其他電子','35':'綠能環保','36':'數位雲端','37':'運動休閒','38':'居家生活'}

def num(x):
    try: return float(str(x).replace(",", "").strip())
    except Exception: return None
def common(s): return re.fullmatch(r"[1-9]\d{3}", s) is not None
def valid(p): return os.path.exists(p) and os.path.getsize(p) > 2000
def jl(k, d):
    p = f"{RAW}/{k}/{d}.json"
    return json.load(open(p)) if valid(p) else None

def fetch():
    sys.path.insert(0, CHIP)
    import live
    asof = dt.datetime.now(TZ).date()
    live.fetch_incremental(asof)

def cmd_check():
    """fetch 之後呼叫：今天沒有 TWSE 資料（假日/休市）就以 exit 3 結束，routine 應直接跳過。"""
    today = dt.datetime.now(TZ).date().isoformat(); last = trading_dates()[-1]
    if last != today:
        print("SKIP: 今天(%s)沒有交易資料，最新為 %s（休市或資料尚未公布）" % (today, last)); sys.exit(3)
    print("OK data date", last)

def trading_dates():
    return sorted(os.path.basename(p)[:-5] for p in glob.glob(f"{RAW}/mi/*.json") if valid(p))

NDAY = 20      # 籌碼視窗 / K線根數
NHIST = 40     # 需要的交易日數：K線20根 + MA20 暖機19天 + 1（約需 40）

def load_days(dates):
    """回傳 {date: {sid: dict(name, mk, o,h,l,close, v, f, t)}}；f/t/v 單位＝張。"""
    days = {}
    for d in dates:
        px = {}
        m = jl("mi", d)
        for tb in m["tables"]:
            if "每日收盤行情" in (tb.get("title") or ""):
                for r in tb["data"]:
                    sid = r[0].strip()
                    if common(sid) and num(r[8]):
                        px[sid] = dict(name=r[1].strip(), mk="上市", o=num(r[5]), h=num(r[6]), l=num(r[7]), close=num(r[8]), v=(num(r[2]) or 0) / 1000, f=0.0, t=0.0)
        t = jl("t86", d)
        for r in (t or {}).get("data", []):
            sid = r[0].strip()
            if sid in px: px[sid]["f"] = ((num(r[4]) or 0) + (num(r[7]) or 0)) / 1000; px[sid]["t"] = (num(r[10]) or 0) / 1000
        q = jl("tpq", d)
        if q and q.get("tables"):
            for r in q["tables"][0]["data"]:
                sid = r[0].strip()
                if common(sid) and num(r[2]):
                    px[sid] = dict(name=r[1].strip(), mk="上櫃", o=num(r[4]), h=num(r[5]), l=num(r[6]), close=num(r[2]), v=(num(r[7]) or 0) / 1000, f=0.0, t=0.0)
        ti = jl("tpinst", d)
        if ti and ti.get("tables"):
            for r in ti["tables"][0]["data"]:
                sid = r[0].strip()
                if sid in px and px[sid]["mk"] == "上櫃": px[sid]["f"] = (num(r[10]) or 0) / 1000; px[sid]["t"] = (num(r[13]) or 0) / 1000
        days[d] = px
    return days

def exfactors():
    import csv
    f = {}
    for r in csv.DictReader(open(CHIP + "/data/exright.csv")): f[(r["date"], r["sid"])] = float(r["factor"])
    return f

def sma(a, n, k):
    """a[0..k] 中以 k 為尾的 n 日均；視窗內有缺值就回 None。"""
    if k - n + 1 < 0: return None
    w = a[k - n + 1:k + 1]
    return None if any(x is None for x in w) else sum(w) / n

def compute():
    """回傳 (dates40, w20, stocks, kl, idxbase)。
    stocks[sid]：n, mk, c, r1/r5/r10/r20, fa/ta/f/t（20 日逐日）
    kl[sid]：近20日 K線（已還原除權息）、量(張)、MA5/MA20、逐日外資投信(億)"""
    dates = trading_dates()[-NHIST:]
    assert len(dates) == NHIST, "need %d trading days of raw data (有 mi/t86/tpq/tpinst)，請先 fetch 補齊" % NHIST
    days = load_days(dates); ex = exfactors()
    last = dates[-1]; w = dates[-NDAY:]; wi = len(dates) - NDAY
    stocks, kl = {}, {}
    for sid, v in days[last].items():
        # 還原因子：A[i] = 第 i 日之後所有除權息因子乘積
        A = [1.0] * len(dates)
        for i in range(len(dates) - 2, -1, -1): A[i] = A[i + 1] * ex.get((dates[i + 1], sid), 1.0)
        X = [days[d].get(sid) for d in dates]
        adj = lambda key, i: (X[i][key] * A[i] if X[i] and X[i].get(key) is not None else None)
        C = [adj("close", i) for i in range(len(dates))]
        def ret(n):
            if C[-1] is None or C[-1 - n] is None: return None
            return C[-1] / C[-1 - n] - 1
        ser = [(X[i]["f"], X[i]["t"], X[i]["close"]) if X[i] else (0.0, 0.0, None) for i in range(wi, len(dates))]
        s = dict(n=v["name"], mk=v["mk"], c=v["close"], r1=ret(1), r5=ret(5), r10=ret(10), r20=ret(20))
        s["f"] = [round(a[0], 1) for a in ser]; s["t"] = [round(a[1], 1) for a in ser]
        s["fa"] = [round(a[0] * (a[2] or 0) / 1e5, 4) for a in ser]   # 億元（張×收盤÷1e5）
        s["ta"] = [round(a[1] * (a[2] or 0) / 1e5, 4) for a in ser]
        stocks[sid] = s
        rd = lambda x: None if x is None else round(x, 2)
        kl[sid] = dict(d=[x[5:] for x in w],
                       o=[rd(adj("o", i)) for i in range(wi, len(dates))], h=[rd(adj("h", i)) for i in range(wi, len(dates))],
                       l=[rd(adj("l", i)) for i in range(wi, len(dates))], c=[rd(C[i]) for i in range(wi, len(dates))],
                       v=[round(X[i]["v"]) if X[i] else None for i in range(wi, len(dates))],
                       m5=[rd(sma(C, 5, i)) for i in range(wi, len(dates))], m20=[rd(sma(C, 20, i)) for i in range(wi, len(dates))],
                       fa=[round(x, 2) for x in s["fa"]], ta=[round(x, 2) for x in s["ta"]], adj=bool(any(A[i] != 1.0 for i in range(len(dates)))))
        # 供族群等權指數用：逐日還原收盤報酬
        s["_C"] = C[wi - 1:]
    return dates, w, stocks, kl

def agg(ids, stocks):
    """ids 的族群彙總：外資/投信 1/5/10/20 日、均漲跌、20日等權指數（日報酬等權平均，起點=100）。"""
    ms = [stocks[i] for i in ids if i in stocks]
    n = NDAY
    f = [sum(s["f"][k] for s in ms) for k in range(n)]; t = [sum(s["t"][k] for s in ms) for k in range(n)]
    fa = [sum(s["fa"][k] for s in ms) for k in range(n)]; ta = [sum(s["ta"][k] for s in ms) for k in range(n)]
    win = lambda a, k: sum(a[n - k:])
    out = dict(n=len(ms))
    for k in (1, 5, 10, 20):
        out[f"f{k}"] = round(win(f, k)); out[f"t{k}"] = round(win(t, k))
        out[f"fa{k}"] = round(win(fa, k), 2); out[f"ta{k}"] = round(win(ta, k), 2); out[f"a{k}"] = round(win(fa, k) + win(ta, k), 2)
        rs = [s[f"r{k}"] for s in ms if s[f"r{k}"] is not None]
        out[f"r{k}"] = sum(rs) / len(rs) if rs else None
    out["daily"] = [round(fa[k] + ta[k], 2) for k in range(n)]        # 合計金額（億）逐日（20日）
    prev5 = sum(fa[n - 10:n - 5]) + sum(ta[n - 10:n - 5]); cur5 = sum(fa[n - 5:]) + sum(ta[n - 5:])
    out["a5prev"] = round(prev5, 2)
    out["flag"] = flag(cur5, prev5)
    # 20日等權指數（每日報酬為成分股當日還原報酬的平均；缺價者當日不計）
    idx = [100.0]
    for k in range(1, n + 1):
        rs = [s["_C"][k] / s["_C"][k - 1] - 1 for s in ms if s["_C"][k] is not None and s["_C"][k - 1] is not None]
        idx.append(idx[-1] * (1 + (sum(rs) / len(rs) if rs else 0)))
    out["idx"] = [round(x, 2) for x in idx]           # 21點：基準日 + 20 日
    return out

def flag(a, b, eps=0.5):
    """a=近5日合計(億)、b=前5日(第6–10日)。回傳 (標籤, 方向 up/down/flat)。"""
    if abs(a) < eps and abs(b) < eps: return ["持平", "flat"]
    if a > 0 and b <= 0: return ["由賣轉買", "up"]
    if a < 0 and b >= 0: return ["由買轉賣", "down"]
    if a > 0 and b > 0:
        return ["買超加速", "up"] if a >= 1.5 * b else (["買超降溫", "flat"] if a <= 0.5 * b else ["續買", "up"])
    # 兩段都賣
    return ["賣超擴大", "down"] if a <= 1.5 * b else (["賣超收斂", "flat"] if a >= 0.5 * b else ["續賣", "down"])

def sectors(stocks):
    B = json.load(open(H + "/baskets.json"))
    theme = {k: dict(ids=v, **agg(v, stocks)) for k, v in B.items()}
    co = json.load(open(RAW + "/twse_company.json"))
    off = {}
    for r in co:
        sid = r["公司代號"].strip()
        if sid in stocks and stocks[sid]["mk"] == "上市":
            off.setdefault(IND.get(r["產業別"], r["產業別"]), []).append(sid)
    official = {k: dict(ids=v, **agg(v, stocks)) for k, v in off.items() if len(v) >= 3 and k in IND.values()}
    return theme, official

def pick(theme, stocks):
    ranked = sorted(theme.items(), key=lambda kv: -kv[1]["a5"])
    ins = [k for k, v in ranked[:N_IN]]; outs = [k for k, v in ranked[::-1][:N_OUT] if k not in ins]
    sel = {}
    for k in ins:
        ids = sorted(theme[k]["ids"], key=lambda i: -(sum(stocks[i]["fa"][-5:]) + sum(stocks[i]["ta"][-5:])) if i in stocks else 0)
        for i in ids[:K_IN]: sel.setdefault(i, k)
    for k in outs:
        ids = sorted(theme[k]["ids"], key=lambda i: (sum(stocks[i]["fa"][-5:]) + sum(stocks[i]["ta"][-5:])) if i in stocks else 0)
        for i in ids[:K_OUT]: sel.setdefault(i, k)
    return sel, ins, outs

def cmd_select():
    dates, w, stocks, kl = compute(); theme, _ = sectors(stocks); sel, ins, outs = pick(theme, stocks)
    json.dump(dict(date=dates[-1], stocks=sel, inflow=ins, outflow=outs), open(H + "/data/selected.json", "w"), ensure_ascii=False, indent=1)
    print("data date", dates[-1]); print("流入", ins); print("流出", outs); print(len(sel), "stocks:", ",".join(sel))

# ------------------------------------------------------------- ToAlpha ingest
def load_in(tool, sid):
    """toalpha_in/<tool>_<sid>.json 為 MCP 工具回傳的 JSON 原樣存檔。"""
    p = f"{H}/toalpha_in/{tool}_{sid}.json"
    if not os.path.exists(p): return None
    try: return json.load(open(p))
    except Exception: return None

def build_detail(sel, date):
    # ToAlpha 解析在 parse_toalpha()，由 README 規定檔名；缺檔就留空，不編造
    import parse_toalpha as P
    return {sid: P.parse_stock(sid, load_in, date) for sid in sel}

def cmd_build():
    dates, w, stocks, kl = compute(); theme, official = sectors(stocks); sel, ins, outs = pick(theme, stocks)
    date = dates[-1]
    allf = agg(list(stocks), stocks)
    # 瘦身：每檔只留 1/5/10/20 日合計；逐日序列與 K 線放到 data/k/<sid>.json，點進個股才載入
    comp = {}
    for sid, x in stocks.items():
        c = dict(n=x["n"], mk=x["mk"], c=x["c"])
        for w_ in (1, 5, 10, 20):
            c["r%d" % w_] = None if x["r%d" % w_] is None else round(x["r%d" % w_], 4)
            c["f%d" % w_] = round(sum(x["f"][-w_:])); c["t%d" % w_] = round(sum(x["t"][-w_:]))
            c["fa%d" % w_] = round(sum(x["fa"][-w_:]), 2); c["ta%d" % w_] = round(sum(x["ta"][-w_:]), 2)
        comp[sid] = c
    for d_ in list(theme.values()) + list(official.values()) + [allf]:
        for k_ in ("r1", "r5", "r10", "r20"):
            if d_.get(k_) is not None: d_[k_] = round(d_[k_], 4)
    flows = dict(date=date, dates=w, generated=dt.datetime.now(TZ).strftime("%Y-%m-%d %H:%M"), market=allf,
                 theme=theme, official=official, stocks=comp, inflow=ins, outflow=outs)
    json.dump(flows, open(H + "/data/flows.json", "w"), ensure_ascii=False, separators=(",", ":"))
    kd = H + "/data/k"; os.makedirs(kd, exist_ok=True)
    for p in glob.glob(kd + "/*.json"): os.remove(p)       # 清掉已下市/不在清單的舊檔
    for sid, k in kl.items(): json.dump(k, open(f"{kd}/{sid}.json", "w"), separators=(",", ":"))
    try:
        detail = build_detail(sel, date)
    except ImportError:
        detail = {}
    for sid, d in detail.items(): d["sector"] = sel[sid]
    json.dump(dict(date=date, detail=detail), open(H + "/data/detail.json", "w"), ensure_ascii=False, separators=(",", ":"))
    # index.html 裡的版本號避免手機快取舊資料
    ver = date.replace("-", "") + dt.datetime.now(TZ).strftime("%H%M")
    html = open(H + "/index.src.html").read().replace("__VER__", ver)
    open(H + "/index.html", "w").write(html)
    print("built", date, "stocks", len(stocks), "detail", len(detail), "kfiles", len(kl), "ver", ver)

def cmd_publish():
    msg = "update " + json.load(open(H + "/data/flows.json"))["date"]
    sh = lambda c: subprocess.run(c, cwd=H, check=True, shell=True)
    sh("git add -A && (git diff --cached --quiet || git commit -m '%s') && git push origin main" % msg)

if __name__ == "__main__":
    c = sys.argv[1] if len(sys.argv) > 1 else "build"
    {"check": cmd_check, "fetch": fetch, "select": cmd_select, "build": cmd_build, "publish": cmd_publish}[c]() if c != "all" else (fetch(), cmd_select(), cmd_build())
