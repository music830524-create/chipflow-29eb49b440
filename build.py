#!/usr/bin/env python3
"""籌碼流向手機網頁 build 腳本。

流程（每個交易日 17:30 後）：
  python3 build.py fetch            # 補抓 TWSE/TPEx 當日資料（沿用 /workspace/backtest-chip/live.py 的抓取）
  python3 build.py select           # 算完籌碼後，印出需要查 ToAlpha 的股票清單（寫 data/selected.json）
  ... agent 依 README 用 ToAlpha MCP 查詢，結果存 toalpha_in/<tool>_<id>.json ...
  python3 build.py build            # 產生 data/flows.json、data/detail.json、index.html 用的資料
  python3 build.py publish          # git commit + push（GitHub Pages）
  python3 build.py all              # fetch + select + build（假設 toalpha_in 已備好）+ 不含 publish

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

def load_days(dates):
    """回傳 {date: {sid: dict(name, mk, close, f, t)}}；f/t 單位＝張。"""
    days = {}
    for d in dates:
        px = {}
        m = jl("mi", d)
        for tb in m["tables"]:
            if "每日收盤行情" in (tb.get("title") or ""):
                for r in tb["data"]:
                    sid = r[0].strip()
                    if common(sid) and num(r[8]): px[sid] = dict(name=r[1].strip(), mk="上市", close=num(r[8]), f=0.0, t=0.0)
        t = jl("t86", d)
        for r in (t or {}).get("data", []):
            sid = r[0].strip()
            if sid in px: px[sid]["f"] = ((num(r[4]) or 0) + (num(r[7]) or 0)) / 1000; px[sid]["t"] = (num(r[10]) or 0) / 1000
        q = jl("tpq", d)
        if q and q.get("tables"):
            for r in q["tables"][0]["data"]:
                sid = r[0].strip()
                if common(sid) and num(r[2]): px[sid] = dict(name=r[1].strip(), mk="上櫃", close=num(r[2]), f=0.0, t=0.0)
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

def compute():
    dates = trading_dates()[-11:]          # 10 日 + 1 個基準日（算漲跌用）
    assert len(dates) == 11, "need 11 trading days of raw data"
    days = load_days(dates); ex = exfactors()
    last = dates[-1]; w = dates[1:]       # 10 個交易日
    stocks = {}
    for sid, v in days[last].items():
        ser = []
        for d in w:
            x = days[d].get(sid)
            ser.append((x["f"], x["t"], x["close"]) if x else (0.0, 0.0, None))
        def ret(n):
            c0 = days[last][sid]["close"]; base = days[dates[-1 - n]].get(sid)
            if not base: return None
            fac = 1.0
            for d in dates[len(dates) - n:]: fac *= ex.get((d, sid), 1.0)
            return c0 / base["close"] / fac - 1
        s = dict(n=v["name"], mk=v["mk"], c=v["close"], r1=ret(1), r5=ret(5), r10=ret(10))
        s["f"] = [round(a[0], 1) for a in ser]; s["t"] = [round(a[1], 1) for a in ser]
        s["fa"] = [round(a[0] * (a[2] or 0) / 1e5, 4) for a in ser]   # 億元（張×收盤÷1e5）
        s["ta"] = [round(a[1] * (a[2] or 0) / 1e5, 4) for a in ser]
        stocks[sid] = s
    return dates, w, stocks

def agg(ids, stocks):
    """ids 的族群彙總。序列以『新→舊』無關，這裡 f/t 為舊→新 10 日。"""
    ms = [stocks[i] for i in ids if i in stocks]
    n = 10
    f = [sum(s["f"][k] for s in ms) for k in range(n)]; t = [sum(s["t"][k] for s in ms) for k in range(n)]
    fa = [sum(s["fa"][k] for s in ms) for k in range(n)]; ta = [sum(s["ta"][k] for s in ms) for k in range(n)]
    win = lambda a, k: sum(a[n - k:])
    out = dict(n=len(ms))
    for k in (1, 5, 10):
        out[f"f{k}"] = round(win(f, k)); out[f"t{k}"] = round(win(t, k))
        out[f"fa{k}"] = round(win(fa, k), 2); out[f"ta{k}"] = round(win(ta, k), 2); out[f"a{k}"] = round(win(fa, k) + win(ta, k), 2)
        rs = [s[f"r{k}"] for s in ms if s[f"r{k}"] is not None]
        out[f"r{k}"] = sum(rs) / len(rs) if rs else None
    out["daily"] = [round(fa[k] + ta[k], 2) for k in range(n)]        # 合計金額（億）逐日
    prev5 = sum(fa[:5]) + sum(ta[:5]); cur5 = sum(fa[5:]) + sum(ta[5:])
    out["a5prev"] = round(prev5, 2)
    out["flag"] = flag(cur5, prev5)
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
        ids = sorted(theme[k]["ids"], key=lambda i: -(sum(stocks[i]["fa"][5:]) + sum(stocks[i]["ta"][5:])) if i in stocks else 0)
        for i in ids[:K_IN]: sel.setdefault(i, k)
    for k in outs:
        ids = sorted(theme[k]["ids"], key=lambda i: (sum(stocks[i]["fa"][5:]) + sum(stocks[i]["ta"][5:])) if i in stocks else 0)
        for i in ids[:K_OUT]: sel.setdefault(i, k)
    return sel, ins, outs

def cmd_select():
    dates, w, stocks = compute(); theme, _ = sectors(stocks); sel, ins, outs = pick(theme, stocks)
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
    dates, w, stocks = compute(); theme, official = sectors(stocks); sel, ins, outs = pick(theme, stocks)
    date = dates[-1]
    allf = agg(list(stocks), stocks)
    flows = dict(date=date, dates=w, generated=dt.datetime.now(TZ).strftime("%Y-%m-%d %H:%M"), market=allf,
                 theme=theme, official=official, stocks=stocks, inflow=ins, outflow=outs)
    for sid, x in stocks.items():   # 瘦身：每檔只留 1/5/10 日合計與近10日逐日(億)
        for w_ in (1, 5, 10):
            x["f%d" % w_] = sum(x["f"][-w_:]); x["t%d" % w_] = sum(x["t"][-w_:])
        del x["f"], x["t"]
    json.dump(flows, open(H + "/data/flows.json", "w"), ensure_ascii=False, separators=(",", ":"))
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
    print("built", date, "stocks", len(stocks), "detail", len(detail), "ver", ver)

def cmd_publish():
    msg = "update " + json.load(open(H + "/data/flows.json"))["date"]
    sh = lambda c: subprocess.run(c, cwd=H, check=True, shell=True)
    sh("git add -A && (git diff --cached --quiet || git commit -m '%s') && git push origin main" % msg)

if __name__ == "__main__":
    c = sys.argv[1] if len(sys.argv) > 1 else "build"
    {"check": cmd_check, "fetch": fetch, "select": cmd_select, "build": cmd_build, "publish": cmd_publish}[c]() if c != "all" else (fetch(), cmd_select(), cmd_build())
