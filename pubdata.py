"""公開資料（證交所／櫃買中心）自給自足：抓取 → 壓縮成 hist/<日期>.json（只留普通股）→ build.py 讀取。
不依賴任何本機路徑；GitHub Actions 每天直接執行。
hist/<date>.json = {"complete": bool, "stocks": {代號: [名稱, 市場, 開, 高, 低, 收, 量(張), 外資(張), 投信(張)]}}
complete = 四個端點（mi、t86、tpq、tpinst）都抓到；不完整的日子下次會回頭補。"""
import os, sys, re, json, csv, time, glob, datetime as dt, urllib.request

H = os.path.dirname(os.path.abspath(__file__))
HIST, SRC = H + "/hist", H + "/src"
TZ = dt.timezone(dt.timedelta(hours=8))
UA = {"User-Agent": "Mozilla/5.0 (chipflow daily build)"}
KEEP_DAYS = 60          # hist 保留的交易日數（build 只需 40）
LOOKBACK = 7            # 每次回頭檢查幾個日曆天內缺漏/不完整的日子
SLEEP = 2.5             # 對 TWSE/TPEx 的請求間隔（秒）

def log(*a): print(*a, file=sys.stderr, flush=True)
def now_tw(): return dt.datetime.now(TZ)
def num(x):
    try: return float(str(x).replace(",", "").strip())
    except Exception: return None
def common(s): return re.fullmatch(r"[1-9]\d{3}", s) is not None

def http(url, tries=4):
    for i in range(tries):
        try:
            return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40).read().decode("utf-8")
        except Exception as e:
            log("  retry", i + 1, url[:90], repr(e)[:80]); time.sleep(6 * (i + 1))
    return None

def urls(d):
    s, t = d.strftime("%Y%m%d"), d.strftime("%Y/%m/%d")
    return {"mi": f"https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX?date={s}&type=ALLBUT0999&response=json",
            "t86": f"https://www.twse.com.tw/rwd/zh/fund/T86?date={s}&selectType=ALLBUT0999&response=json",
            "tpq": f"https://www.tpex.org.tw/www/zh-tw/afterTrading/otc?date={t}&type=EW&response=json",
            "tpinst": f"https://www.tpex.org.tw/www/zh-tw/insti/dailyTrade?type=Daily&sect=EW&date={t}&response=json"}

def compact(mi, t86, tpq, tpinst):
    """四個端點的原始 JSON → {sid: [name, mk, o,h,l,c,v,f,t]}（單位：張）；與舊版 build.py load_days 完全同一套欄位對應。"""
    px = {}
    for tb in (mi or {}).get("tables", []):
        if "每日收盤行情" in (tb.get("title") or ""):
            for r in tb["data"]:
                sid = r[0].strip()
                if common(sid) and num(r[8]):
                    px[sid] = [r[1].strip(), "上市", num(r[5]), num(r[6]), num(r[7]), num(r[8]), (num(r[2]) or 0) / 1000, 0.0, 0.0]
    for r in (t86 or {}).get("data", []):
        sid = r[0].strip()
        if sid in px:
            px[sid][7] = ((num(r[4]) or 0) + (num(r[7]) or 0)) / 1000; px[sid][8] = (num(r[10]) or 0) / 1000
    if tpq and tpq.get("tables"):
        for r in tpq["tables"][0]["data"]:
            sid = r[0].strip()
            if common(sid) and num(r[2]):
                px[sid] = [r[1].strip(), "上櫃", num(r[4]), num(r[5]), num(r[6]), num(r[2]), (num(r[7]) or 0) / 1000, 0.0, 0.0]
    if tpinst and tpinst.get("tables"):
        for r in tpinst["tables"][0]["data"]:
            sid = r[0].strip()
            if sid in px and px[sid][1] == "上櫃":
                px[sid][7] = (num(r[10]) or 0) / 1000; px[sid][8] = (num(r[13]) or 0) / 1000
    return {k: [v[0], v[1]] + [None if x is None else round(x, 3) for x in v[2:]] for k, v in px.items()}

def read_hist(d):
    p = f"{HIST}/{d}.json"
    return json.load(open(p)) if os.path.exists(p) else None
def write_hist(d, complete, stocks):
    os.makedirs(HIST, exist_ok=True)
    json.dump(dict(complete=complete, stocks=stocks), open(f"{HIST}/{d}.json", "w"), ensure_ascii=False, separators=(",", ":"))

def hist_dates(complete_only=True):
    out = []
    for p in sorted(glob.glob(HIST + "/*.json")):
        d = os.path.basename(p)[:-5]
        if not complete_only or json.load(open(p)).get("complete"): out.append(d)
    return out

def holidays():
    p = SRC + "/holidays.json"
    return set(json.load(open(p))) if os.path.exists(p) else set()

def fetch_day(d):
    """抓一天的四個端點。回傳 (state, stocks)：state = 'holiday'（TWSE 當天無資料）/'ok'/'partial'/'fail'"""
    raw = {}; u = urls(d); empty_mi = False
    for k, url in u.items():
        txt = http(url); time.sleep(SLEEP)
        if txt is None: continue
        try: j = json.loads(txt)
        except Exception: continue
        bad = ("stat" in j and str(j.get("stat")).upper() != "OK") or (k.startswith("tp") and not (j.get("tables") and j["tables"][0].get("data")))
        if bad:
            if k == "mi": empty_mi = True; break      # 沒有收盤行情＝休市或尚未公布，其他端點不用抓
            continue
        raw[k] = j
    if "mi" not in raw:
        return ("holiday" if empty_mi else "fail"), None
    st = compact(raw.get("mi"), raw.get("t86"), raw.get("tpq"), raw.get("tpinst"))
    return ("ok" if all(k in raw for k in u) else "partial"), st

def fetch_incremental(asof=None):
    """補抓缺漏或不完整的交易日（含今天）。回傳抓了幾個端點的天數。"""
    asof = asof or now_tw().date()
    hol = holidays(); n = 0
    for i in range(LOOKBACK, -1, -1):
        d = asof - dt.timedelta(days=i)
        if d.weekday() >= 5 or d.isoformat() in hol: continue
        h = read_hist(d.isoformat())
        if h and h.get("complete"): continue
        st, stocks = fetch_day(d); n += 1
        log(f"  fetched {d} → {st}")
        if st == "holiday":
            if d < now_tw().date(): hol.add(d.isoformat())
        elif stocks:
            write_hist(d.isoformat(), st == "ok", stocks)
    os.makedirs(SRC, exist_ok=True)
    json.dump(sorted(hol), open(SRC + "/holidays.json", "w"))
    prune()
    return n

def prune():
    ds = hist_dates(complete_only=False)
    for d in ds[:-KEEP_DAYS]: os.remove(f"{HIST}/{d}.json")

# ---- 除權息還原因子（TWSE TWT49U + TPEx exDailyQ）
def roc2iso(s):
    s = s.replace("年", "/").replace("月", "/").replace("日", "")
    y, m, d = [int(x) for x in s.split("/")]; return f"{y+1911:04d}-{m:02d}-{d:02d}"

def refresh_exrights(asof=None):
    asof = asof or now_tw().date(); s = asof - dt.timedelta(days=120); rows = {}
    p = SRC + "/exright.csv"
    if os.path.exists(p):
        for r in csv.DictReader(open(p)): rows[(r["date"], r["sid"])] = float(r["factor"])
    new = {}
    t = http(f"https://www.twse.com.tw/rwd/zh/exRight/TWT49U?startDate={s:%Y%m%d}&endDate={asof:%Y%m%d}&response=json")
    try:
        for r in json.loads(t).get("data", []):
            k = (roc2iso(r[0]), r[1].strip()); f = num(r[4]) / num(r[3]); new[k] = new.get(k, 1.0) * f
    except Exception as e: log("  TWSE 除權息抓取失敗", repr(e)[:80])
    q = http(f"https://www.tpex.org.tw/www/zh-tw/bulletin/exDailyQ?startDate={s:%Y/%m/%d}&endDate={asof:%Y/%m/%d}&response=json")
    try:
        for r in json.loads(q)["tables"][0]["data"]:
            k = (roc2iso(r[0]), r[1].strip()); f = num(r[4]) / num(r[3]); new[k] = new.get(k, 1.0) * f
    except Exception as e: log("  TPEx 除權息抓取失敗", repr(e)[:80])
    rows.update(new)
    cut = (asof - dt.timedelta(days=240)).isoformat()
    os.makedirs(SRC, exist_ok=True)
    with open(p, "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(["date", "sid", "factor"])
        for (d, sid), f in sorted(rows.items()):
            if d >= cut: w.writerow([d, sid, repr(f)])

# ---- 上市公司產業別（官方產業分頁用）
def refresh_company():
    t = http("https://openapi.twse.com.tw/v1/opendata/t187ap03_L")
    if t and t.strip().startswith("["):
        co = {r["公司代號"].strip(): r["產業別"] for r in json.loads(t)}
        if len(co) > 500:
            os.makedirs(SRC, exist_ok=True); json.dump(co, open(SRC + "/company.json", "w"), ensure_ascii=False, separators=(",", ":"))

def fetch_all():
    n = fetch_incremental()
    refresh_exrights(); refresh_company()
    return n
