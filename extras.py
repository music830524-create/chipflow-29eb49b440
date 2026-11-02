"""擴充分頁資料（A 起漲偵測 / B 族群輪動 RRG / C 工具箱）。純規則運算、不用 LLM、不用付費金鑰。
輸入：hist/（TWSE/TPEx 每日收盤＋法人）、除權息因子、baskets*.json、公開資料（營收/估值/集保/期交所/新聞）
輸出：data/rise.json、data/rrg.json、data/c_*.json、data/heat/<日期>.json
C 分頁的型態辨識沿用 tw-trading-dashboard（MIT）的 patterns.mjs，見 vendor/ 與 THIRD_PARTY_LICENSES。"""
import os, sys, json, csv, math, glob, time, subprocess, statistics as st, datetime as dt, urllib.request, urllib.parse
import pubdata
from pubdata import H, TZ, log

DATA = H + "/data"
NMAX = 150
IND = {'01':'水泥','02':'食品','03':'塑膠','04':'紡織','05':'電機機械','06':'電器電纜','08':'玻璃陶瓷','09':'造紙','10':'鋼鐵','11':'橡膠','12':'汽車','14':'建材營造','15':'航運','16':'觀光餐旅','17':'金融保險','18':'貿易百貨','20':'其他','21':'化學','22':'生技醫療','23':'油電燃氣','24':'半導體','25':'電腦週邊','26':'光電','27':'通信網路','28':'電子零組件','29':'電子通路','30':'資訊服務','31':'其他電子','35':'綠能環保','36':'數位雲端','37':'運動休閒','38':'居家生活'}
OFFICIAL_OK = set(IND.values())
STAMP = None

def jdump(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(obj, open(path, "w"), ensure_ascii=False, separators=(",", ":"))
def jload(path, default=None):
    try: return json.load(open(path))
    except Exception: return default
def r2(x, n=2): return None if x is None else round(x, n)
def sma(a, n, k):
    if k - n + 1 < 0: return None
    w = a[k - n + 1:k + 1]
    return None if any(x is None for x in w) else sum(w) / n
def fetch_text(url, data=None, enc="utf-8", tries=2):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, data=(urllib.parse.urlencode(data).encode() if data else None), headers=pubdata.UA)
            return urllib.request.urlopen(req, timeout=40).read().decode(enc, "replace")
        except Exception as e:
            log("  extras retry", i + 1, url[:80], repr(e)[:70]); time.sleep(3)
    return None
def fetch_json(url, **kw):
    t = fetch_text(url, **kw)
    try: return json.loads(t) if t else None
    except Exception: return None

# ------------------------------------------------------------------ 載入
class DB: pass

def load():
    ds = pubdata.hist_dates(complete_only=True)[-NMAX:]
    db = DB(); db.dates = ds; N = len(ds); db.N = N
    raw = [pubdata.read_hist(d) for d in ds]
    ex = {}
    for r in csv.DictReader(open(H + "/src/exright.csv")): ex[(r["date"], r["sid"])] = float(r["factor"])
    db.mkt = [(x.get("mkt") or {}) for x in raw]
    last = raw[-1]["stocks"]
    S = {}
    for sid, v in last.items():
        A = [1.0] * N
        for i in range(N - 2, -1, -1): A[i] = A[i + 1] * ex.get((ds[i + 1], sid), 1.0)
        s = dict(name=v[0], mk=v[1], o=[None] * N, h=[None] * N, l=[None] * N, c=[None] * N, rc=[None] * N, v=[None] * N, amt=[None] * N, f=[0.0] * N, t=[0.0] * N)
        for i in range(N):
            x = raw[i]["stocks"].get(sid)
            if not x: continue
            s["o"][i], s["h"][i], s["l"][i], s["c"][i] = x[2] * A[i], x[3] * A[i], x[4] * A[i], x[5] * A[i]
            s["rc"][i] = x[5]; s["v"][i] = x[6]; s["f"][i] = x[7]; s["t"][i] = x[8]
            s["amt"][i] = x[9] if len(x) > 9 else None
        S[sid] = s
    db.S = S
    db.have_amt = sum(1 for r in raw if any(len(v) > 9 for v in list(r["stocks"].values())[:3]))
    # 產業（官方）：先用營收檔的產業別（上市＋上櫃），退而求其次 company.json
    rev = jload(H + "/src/rev.json", {})
    co = jload(H + "/src/company.json", {})
    ind = {}
    for sid in S:
        nm = (rev.get(sid) or [None])[0]
        if nm: ind[sid] = nm
        elif sid in co and IND.get(co[sid]): ind[sid] = IND[co[sid]]
        else: ind[sid] = "其他"
    db.ind = ind; db.rev = rev
    # 族群
    G = {"theme": {}, "ext": {}, "official": {}}
    for k, v in jload(H + "/baskets.json", {}).items():
        ids = [i for i in v if i in S]
        if len(ids) >= 3: G["theme"][k] = ids
    for k, v in jload(H + "/baskets_ext.json", {}).items():
        ids = [i for i in v["ids"] if i in S]
        if len(ids) >= 3: G["ext"][k] = ids
    off = {}
    for sid, c in co.items():
        if sid in S and S[sid]["mk"] == "上市" and IND.get(c): off.setdefault(IND[c], []).append(sid)
    G["official"] = {k: v for k, v in off.items() if len(v) >= 3 and k in OFFICIAL_OK}
    db.G = G
    db.twr = [m.get("twr") for m in db.mkt]; db.twii = [m.get("twii") for m in db.mkt]
    # 各股 MA20 之上旗標
    for sid, s in S.items():
        s["ma20"] = [sma(s["c"], 20, i) for i in range(N)]
        s["above20"] = [(s["c"][i] > s["ma20"][i]) if (s["c"][i] is not None and s["ma20"][i] is not None) else None for i in range(N)]
    return db

def ret(s, i, n=1):
    a, b = s["c"][i], s["c"][i - n] if i - n >= 0 else None
    return None if a is None or b is None or b == 0 else a / b - 1

# ------------------------------------------------------------------ 族群等權指數
def group_index(db, ids):
    N = db.N; idx = [100.0]
    for i in range(1, N):
        rs = [ret(db.S[s], i) for s in ids]; rs = [x for x in rs if x is not None]
        idx.append(idx[-1] * (1 + (sum(rs) / len(rs) if rs else 0.0)))
    return idx

# ------------------------------------------------------------------ A 起漲偵測
def rise_status(score, c1, c2, below):
    if score >= 5: return "起漲"
    if score >= 3 and c1 and c2: return "候選"
    if below: return "轉弱"
    return "盤整"

def conds_at(db, idx, rs, ids, t):
    """回傳 (c1..c5, 資訊)。需要 t>=25。"""
    ma = lambda k: sma(idx, 20, k)
    m, m5 = ma(t), ma(t - 5)
    c1 = m is not None and idx[t] > m
    c2 = m is not None and m5 is not None and (m - m5) / 5 > 0
    w = [x for x in rs[t - 19:t + 1]] if t >= 19 else []
    c3 = bool(w) and all(x is not None for x in w) and rs[t] >= max(w) - 1e-12
    ab = [db.S[s]["above20"][t] for s in ids]; ab = [x for x in ab if x is not None]
    pa = sum(ab) / len(ab) if ab else 0
    c4 = pa >= 0.5
    r5 = idx[t] / idx[t - 5] - 1
    c5 = r5 >= 0.03
    return [c1, c2, c3, c4, c5], dict(pa=pa, r5=r5, below=(m is not None and idx[t] < m))

def build_rise(db):
    N = db.N; res = []
    bench = db.twr
    for typ, gs in db.G.items():
        for name, ids in gs.items():
            idx = group_index(db, ids)
            rs = [(idx[i] / bench[i]) if bench[i] else None for i in range(N)]
            hist = []
            for t in range(N - 8, N):
                cs, inf = conds_at(db, idx, rs, ids, t)
                sc = sum(cs); hist.append((rise_status(sc, cs[0], cs[1], inf["below"]), sc, cs, inf))
            stt, sc, cs, inf = hist[-1]
            prev = hist[-2][0]
            rn = 0
            for h in reversed(hist):
                if h[0] == "起漲": rn += 1
                else: break
            n_high = 0
            for s in ids:
                c = db.S[s]["c"]; w = [x for x in c[-20:] if x is not None]
                if len(w) >= 15 and c[-1] is not None and c[-1] >= max(w) - 1e-9: n_high += 1
            lead = sorted([s for s in ids if ret(db.S[s], N - 1, 5) is not None], key=lambda s: -ret(db.S[s], N - 1, 5))[:3]
            res.append(dict(type=typ, name=name, n=len(ids), status=stt, prev=prev, new=(stt in ("起漲", "候選") and prev not in ("起漲", "候選")),
                            score=sc, conds=[int(bool(x)) for x in cs], rising_day_n=rn, pct_above_ma20=r2(inf["pa"], 3), n_high20=n_high,
                            r5=r2(inf["r5"], 4), r20=r2(idx[-1] / idx[-21] - 1, 4), idx=r2(idx[-1], 2),
                            hist=[h[0] for h in hist], spark=[r2(x, 2) for x in idx[-30:]],
                            lead=[[s, db.S[s]["name"], r2(ret(db.S[s], N - 1, 5), 4)] for s in lead]))
    # 大盤背景
    tw = [x for x in db.twii]
    ok = tw[-1] is not None and all(x is not None for x in tw[-26:])
    mk = dict(ok=False)
    if ok:
        m20 = sum(tw[-20:]) / 20; m20b = sum(tw[-25:-5]) / 20
        mk = dict(ok=True, twii=tw[-1], ma20=r2(m20, 1), above=tw[-1] > m20, slope=r2((m20 - m20b) / 5, 2), r5=r2(tw[-1] / tw[-6] - 1, 4), r1=r2(tw[-1] / tw[-2] - 1, 4))
    order = {"起漲": 0, "候選": 1, "盤整": 2, "轉弱": 3}
    res.sort(key=lambda x: (order[x["status"]], -x["score"], -(x["r5"] or 0)))
    out = dict(date=db.dates[-1], market=mk, bench="發行量加權股價報酬指數（TWSE）", items=res)
    jdump(DATA + "/rise.json", out)
    return out

# ------------------------------------------------------------------ B RRG
def zs(a, n, k):
    w = a[k - n + 1:k + 1]
    if len(w) < n or any(x is None for x in w): return None
    m = sum(w) / n; sd = (sum((x - m) ** 2 for x in w) / n) ** .5
    return None if sd == 0 else (a[k] - m) / sd

def build_rrg(db):
    N = db.N; bench = db.twr; items = []
    TAIL = 21
    for typ, gs in db.G.items():
        for name, ids in gs.items():
            idx = group_index(db, ids)
            rs = [(idx[i] / bench[i] * 100) if bench[i] else None for i in range(N)]
            ratio = [None] * N
            for k in range(19, N): ratio[k] = (lambda z: None if z is None else 100 + z)(zs(rs, 20, k))
            mom = [None] * N
            for k in range(24, N):
                if ratio[k] is not None and ratio[k - 5] is not None: mom[k] = 100 + (ratio[k] - ratio[k - 5])
            pts = [[r2(ratio[k], 2), r2(mom[k], 2)] for k in range(N - TAIL, N) if ratio[k] is not None and mom[k] is not None]
            if len(pts) < 5: continue
            x, y = pts[-1]
            q = ("領先" if y >= 100 else "轉弱") if x >= 100 else ("改善" if y >= 100 else "落後")
            items.append(dict(type=typ, name=name, n=len(ids), q=q, pts=pts, r5=r2(idx[-1] / idx[-6] - 1, 4)))
    out = dict(date=db.dates[-1], bench="發行量加權股價報酬指數（TWSE，含股利再投入）", items=items)
    jdump(DATA + "/rrg.json", out)
    return out

# ------------------------------------------------------------------ 公開資料補抓（失敗就沿用 src/ 內舊檔）
def norm_ind(s):
    s = (s or "").strip()
    for suf in ("工業", "業"):
        if s.endswith(suf) and len(s) > 2: s = s[:-len(suf)]; break
    return {"紡織纖維": "紡織", "電腦及週邊設備": "電腦週邊", "其他電子": "其他電子", "文化創意": "文化創意"}.get(s, s)

def fetch_rev():
    """月營收（上市＋上櫃，政府 OpenAPI）→ src/rev.json: {sid: [產業, 去年同月增減%, 上月比較增減%, 資料年月, 當月營收(千元)]}"""
    old = jload(H + "/src/rev.json", {}); out = dict(old); n = 0
    for u in ("https://openapi.twse.com.tw/v1/opendata/t187ap05_L", "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap05_O"):
        j = fetch_json(u)
        if not isinstance(j, list): continue
        for r in j:
            sid = str(r.get("公司代號", "")).strip()
            if not pubdata.common(sid): continue
            f = lambda k: pubdata.num(r.get(k))
            out[sid] = [norm_ind(r.get("產業別")), f("營業收入-去年同月增減(%)"), f("營業收入-上月比較增減(%)"), r.get("資料年月"), f("營業收入-當月營收")]; n += 1
    if n: jdump(H + "/src/rev.json", out)
    log("  rev rows", n)
    return out

def fetch_val(date):
    """本益比/股價淨值比/殖利率（TWSE BWIBBU_d＋TPEx peratio）→ src/val.json: {sid: [PE, PB, yield]}"""
    out = {}
    d = date.replace("-", "")
    j = fetch_json(f"https://www.twse.com.tw/rwd/zh/afterTrading/BWIBBU_d?date={d}&selectType=ALL&response=json")
    for r in (j or {}).get("data", []):
        out[r[0].strip()] = [pubdata.num(r[5]), pubdata.num(r[6]), pubdata.num(r[3])]
    j = fetch_json("https://www.tpex.org.tw/openapi/v1/tpex_mainboard_peratio_analysis")
    for r in (j if isinstance(j, list) else []):
        out[str(r.get("SecuritiesCompanyCode", "")).strip()] = [pubdata.num(r.get("PriceEarningRatio")), pubdata.num(r.get("PriceBookRatio")), pubdata.num(r.get("YieldRatio"))]
    if out: jdump(H + "/src/val.json", out)
    return out or jload(H + "/src/val.json", {})

def fetch_tdcc(date):
    """集保戶股權分散（週）→ src/tdcc.json: {週資料日: {sid: [400張以上%, 1000張以上%, 總人數]}}，保留 14 週。"""
    hist = jload(H + "/src/tdcc.json", {})
    t = fetch_text("https://opendata.tdcc.com.tw/getOD.ashx?id=1-5")
    if t:
        rows = {}; wk = None
        for ln in t.splitlines()[1:]:
            p = ln.strip().split(",")
            if len(p) < 6: continue
            wk = p[0].lstrip("\ufeff"); sid = p[1].strip()
            if not pubdata.common(sid): continue
            lv = int(p[2]); rows.setdefault(sid, {})[lv] = (pubdata.num(p[3]) or 0, pubdata.num(p[5]) or 0)
        snap = {}
        for sid, v in rows.items():
            if 15 in v and 17 in v:
                snap[sid] = [round(sum(v.get(k, (0, 0))[1] for k in (12, 13, 14, 15)), 2), round(v[15][1], 2), int(v[17][0])]
        if wk and snap:
            hist[wk] = snap
            for k in sorted(hist)[:-14]: del hist[k]
            jdump(H + "/src/tdcc.json", hist)
    return hist

def fetch_taifex(date=None):
    """期交所：臺股期貨三大法人（外資未平倉淨口數）＋臺指選擇權外資 CALL/PUT 未平倉。保留近 90 日 → src/taifex.json"""
    old = jload(H + "/src/taifex.json", {"fut": {}, "opt": {}})
    end = dt.date.fromisoformat(date) if date else dt.date.today() - dt.timedelta(days=1); start = end - dt.timedelta(days=27)
    q = {"queryStartDate": start.strftime("%Y/%m/%d"), "queryEndDate": end.strftime("%Y/%m/%d")}
    t = fetch_text("https://www.taifex.com.tw/cht/3/futContractsDateDown", data=dict(q, commodityId="TXF"), enc="big5")
    if t:
        for ln in t.splitlines()[1:]:
            p = ln.strip().split(",")
            if len(p) >= 14 and p[1] == "臺股期貨":
                d = p[0].replace("/", "-"); old["fut"].setdefault(d, {})[p[2]] = [int(pubdata.num(p[7]) or 0), int(pubdata.num(p[13]) or 0)]
    t = fetch_text("https://www.taifex.com.tw/cht/3/callsAndPutsDateDown", data=dict(q, commodityId="TXO"), enc="big5")
    if t:
        for ln in t.splitlines()[1:]:
            p = ln.strip().split(",")
            if len(p) >= 15 and p[1] == "臺指選擇權":
                d = p[0].replace("/", "-"); old["opt"].setdefault(d, {})[p[2] + "|" + p[3]] = int(pubdata.num(p[14]) or 0)
    for k in ("fut", "opt"):
        for d in sorted(old[k])[:-90]: del old[k][d]
    jdump(H + "/src/taifex.json", old)
    return old

def fetch_news():
    news = []
    j = fetch_json("https://api.cnyes.com/media/api/v1/newslist/category/headline?limit=30")
    for it in ((j or {}).get("items") or {}).get("data", [])[:30]:
        try:
            news.append(dict(t=it["title"], u="https://news.cnyes.com/news/id/%s" % it["newsId"], ts=dt.datetime.fromtimestamp(it["publishAt"], TZ).strftime("%m-%d %H:%M")))
        except Exception: pass
    cal = []
    j = fetch_json("https://nfs.faireconomy.media/ff_calendar_thisweek.json")
    for e in (j if isinstance(j, list) else []):
        if e.get("impact") in ("High",) and e.get("country") in ("USD", "TWD", "CNY", "JPY", "EUR"):
            try:
                tm = dt.datetime.fromisoformat(e["date"]).astimezone(TZ).strftime("%m-%d %H:%M")
            except Exception: tm = str(e.get("date"))[:16]
            cal.append(dict(t=tm, c=e["country"], n=e.get("title"), f=e.get("forecast"), p=e.get("previous")))
    old = jload(DATA + "/c_news_raw.json", {})
    if not news: news = old.get("news", [])
    if not cal: cal = old.get("cal", [])
    jdump(DATA + "/c_news_raw.json", dict(news=news, cal=cal))
    return news, cal

# ------------------------------------------------------------------ C 族群排名（沿用 tw-trading-dashboard grouprank 的加權法）
def stock_rate(db, sid, t):
    s = db.S[sid]; r = ret(s, t)
    a = s["amt"][t]
    return None if r is None or a is None else (r, a * 1e6)

def group_rank_at(db, t):
    out = {}
    mk_amt = sum((s["amt"][t] or 0) * 1e6 for s in db.S.values())
    for typ, gs in db.G.items():
        rows = []
        for name, ids in gs.items():
            st_ = [(sid,) + stock_rate(db, sid, t) for sid in ids if stock_rate(db, sid, t)]
            tot = sum(x[2] for x in st_)
            if not st_ or tot <= 0: continue
            used = [x for x in st_ if x[2] / tot >= 0.005 and x[2] >= 1e7] or st_
            wsum = sum(math.sqrt(x[2]) for x in used)
            score = sum(x[1] * math.sqrt(x[2]) for x in used) / wsum
            amt_used = sum(x[2] for x in used)
            wavg = sum(x[1] * x[2] for x in used) / amt_used
            rs = [x[1] for x in used]
            up = sum(1 for r in rs if r > 0.0005); dn = sum(1 for r in rs if r < -0.0005)
            top = max(used, key=lambda x: x[2])
            rows.append(dict(name=name, n=len(ids), used=len(used), score=score, wavg=wavg, avg=sum(rs) / len(rs), med=st.median(rs),
                             up=up, dn=dn, flat=len(rs) - up - dn, breadth=up / len(rs), amt=tot / 1e8, share=tot / mk_amt if mk_amt else 0,
                             top=[top[0], db.S[top[0]]["name"], r2(top[1], 4)]))
        rows.sort(key=lambda r: (-r["score"], -r["breadth"], r["name"]))
        for i, r in enumerate(rows): r["rank"] = i + 1
        out[typ] = rows
    return out

def build_rank(db):
    N = db.N
    cur, prv = group_rank_at(db, N - 1), group_rank_at(db, N - 2)
    for typ, rows in cur.items():
        pr = {r["name"]: r["rank"] for r in prv.get(typ, [])}
        for r in rows:
            r["move"] = (pr[r["name"]] - r["rank"]) if r["name"] in pr else None
            for k in ("score", "wavg", "avg", "med", "breadth", "share"): r[k] = r2(r[k], 4)
            r["amt"] = r2(r["amt"], 1)
    out = dict(date=db.dates[-1], rows=cur)
    jdump(DATA + "/c_rank.json", out)
    return out

# ------------------------------------------------------------------ C 資金熱浪（treemap 資料；客戶端彙總）
def build_heat(db, keep=15):
    N = db.N; inds = sorted(set(db.ind.values())); iidx = {k: i for i, k in enumerate(inds)}
    os.makedirs(DATA + "/heat", exist_ok=True)
    for f in glob.glob(DATA + "/heat/*.json"): os.remove(f)
    dates = db.dates[-keep:]
    for t in range(N - len(dates), N):
        rows = []
        for sid, s in db.S.items():
            a = s["amt"][t]; r = ret(s, t)
            if not a or r is None: continue
            pa = s["amt"][t - 1] if t > 0 else None
            rows.append([sid, s["name"], 0 if s["mk"] == "上市" else 1, iidx[db.ind[sid]], round(a, 1), round(r * 100, 2), None if pa is None else round(pa, 1)])
        jdump(DATA + "/heat/%s.json" % db.dates[t], dict(date=db.dates[t], ind=inds, rows=rows))
    jdump(DATA + "/c_heat.json", dict(dates=dates))

# ------------------------------------------------------------------ C 型態選股（執行 vendored patterns.mjs）
def build_patterns(db):
    N = db.N
    if N < 90: return None
    items = []
    for sid, s in db.S.items():
        if db.ind[sid] and any(x in db.ind[sid] for x in ("金融", "水泥", "造紙", "紡織", "運動休閒", "貿易百貨", "油電燃氣", "文化創意")): continue
        w = range(N - 90, N)
        if any(s["c"][i] is None or s["rc"][i] is None or s["o"][i] is None for i in w): continue
        v5 = [x for x in s["v"][-5:] if x is not None]
        if len(v5) < 5 or sum(v5) / 5 < 300: continue
        items.append(dict(id=sid, a=[[round(s["o"][i], 4), round(s["h"][i], 4), round(s["l"][i], 4), round(s["c"][i], 4), (s["v"][i] or 0) * 1000] for i in w],
                          p=[[s["rc"][i] * (s["o"][i] / s["c"][i]), s["rc"][i] * (s["h"][i] / s["c"][i]), s["rc"][i] * (s["l"][i] / s["c"][i]), s["rc"][i], (s["v"][i] or 0) * 1000] for i in w]))
    inp = json.dumps(dict(dates=db.dates[-90:], stocks=items))
    try:
        r = subprocess.run(["node", H + "/vendor/tw-trading-dashboard/run_patterns.mjs"], input=inp, capture_output=True, text=True, timeout=600)
    except FileNotFoundError:
        log("  node 不存在，略過型態選股"); return None
    if r.returncode != 0:
        log("  patterns 失敗", r.stderr[:300]); return None
    res = json.loads(r.stdout); hits = []
    for h in res["hits"]:
        s = db.S[h["id"]]
        best = max(h["matches"], key=lambda m: m["score"])
        for m in h["matches"]:
            hits.append(dict(sid=h["id"], name=s["name"], mk=s["mk"], ind=db.ind[h["id"]], close=s["rc"][-1], r1=r2(ret(s, N - 1), 4),
                             pid=m["id"], pname=m["name"], cat=m["category"], score=m["score"], status=m["status"], start=m["start"], end=m["end"], bdate=m["breakoutDate"],
                             res=m["resistance"], sup=m["support"], vr=m["volumeRatio"], plan={k: m["plan"][k] for k in ("entry", "entryMax", "stop", "target", "rr", "chased", "action")},
                             warn=m["warnings"][:2], best=(m is best), lines=[[l["label"], l["from"], l["to"], r2(l["a"]), r2(l["b"])] for l in m["lines"]],
                             c=None))
    hits.sort(key=lambda x: -x["score"])
    hits = hits[:200]
    amap = {it["id"]: [r2(x[3]) for x in it["a"]] for it in items}
    for x in hits: x["c"] = amap[x["sid"]]
    out = dict(date=db.dates[-1], types=[dict(id=t["id"], name=t["name"], category=t.get("category")) for t in res["types"]], scanned=len(items), hits=hits)
    jdump(DATA + "/c_pat.json", out)
    return out

# ------------------------------------------------------------------ C 研究評分（沿用 tw-trading-dashboard 四因子的公式；話題因子無資料來源→剔除並重新配權）
def clamp(x, a=0, b=100): return max(a, min(b, x))
W = dict(tech=30, chips=30, ind=25)         # 原 30/30/15/25，話題(15)為人工判斷，這裡不做
def rating(sc, full):
    r = "強勢" if sc >= 75 else "中性偏強" if sc >= 55 else "中性偏弱" if sc >= 40 else "弱勢"
    return r if full else "暫評・" + r

def build_score(db, val):
    N = db.N; S = db.S
    # 產業因子：成分站上 MA60 比例、營收 YoY 中位數、60 日報酬中位數
    byind = {}
    for sid, s in S.items(): byind.setdefault(db.ind[sid], []).append(sid)
    indf = {}
    for k, ids in byind.items():
        ab, yoy, r60 = [], [], []
        for sid in ids:
            s = S[sid]; m60 = sma(s["c"], 60, N - 1)
            if m60 and s["c"][-1] is not None: ab.append(s["c"][-1] > m60)
            y = (db.rev.get(sid) or [None, None])[1]
            if y is not None: yoy.append(y)
            if N > 60 and s["c"][-1] and s["c"][-61]: r60.append((s["c"][-1] / s["c"][-61] - 1) * 100)
        if len(ab) >= min(5, len(ids)) and len(ab) >= 0.5 * len(ids) and yoy and r60 and len(yoy) >= 0.5 * len(ids):
            indf[k] = (sum(ab) / len(ab) * 100) * .4 + clamp(50 + st.median(yoy)) * .4 + clamp(50 + st.median(r60) * 2) * .2
    rows = []
    for sid, s in S.items():
        c = s["c"]
        if c[-1] is None: continue
        f = {}
        # 技術面（需 ≥140 根還原 K）
        if N >= 140 and all(x is not None for x in c[-140:]):
            m20, m60, m120 = sma(c, 20, N - 1), sma(c, 60, N - 1), sma(c, 120, N - 1)
            trend = (int(c[-1] > m20) + int(m20 > m60) + int(m60 > m120)) / 3 * 100
            r60 = (c[-1] / c[-61] - 1) * 100; mom = clamp(50 + r60 * 2)
            m60b = sma(c, 60, N - 21); slope = (m60 / m60b - 1) * 100 if m60b else 0; slopes = clamp(50 + slope * 5)
            hi = max(c[-60:]); dd = (c[-1] / hi - 1) * 100; dev = abs(c[-1] / m20 - 1) * 100
            stab = clamp(100 + dd * 4 - max(0, dev - 15) * 3)
            f["tech"] = trend * .4 + mom * .25 + slopes * .2 + stab * .15
        # 籌碼面：外資＋投信 20 日淨買賣 / 20 日成交量
        fl = [s["f"][i] + s["t"][i] for i in range(N - 20, N)]; vols = [x or 0 for x in s["v"][-20:]]
        if sum(1 for x in s["v"][-20:] if x is not None) >= 18 and sum(vols) > 0:
            ratio = sum(fl) / sum(vols) * 100
            posd = sum(1 for x in fl if x > 0) / 20
            f["chips"] = clamp(50 + ratio * 5) * .6 + posd * 100 * .4
        if db.ind[sid] in indf: f["ind"] = indf[db.ind[sid]]
        if not f: continue
        tw = sum(W[k] for k in f); sc = sum(f[k] * W[k] for k in f) / tw
        full = len(f) == 3
        v = val.get(sid) or [None, None, None]; rv = db.rev.get(sid) or [None] * 5
        rows.append([sid, s["name"], 0 if s["mk"] == "上市" else 1, db.ind[sid], round(sc, 1), rating(sc, full), r2(f.get("tech"), 0), r2(f.get("chips"), 0), r2(f.get("ind"), 0),
                     round(tw / sum(W.values()) * 100), v[0], v[1], v[2], r2(rv[1], 1), r2(rv[2], 1), r2(ret(s, N - 1), 4), s["rc"][-1]])
    rows.sort(key=lambda r: -r[4])
    out = dict(date=db.dates[-1], weights=dict(tech=30, chips=30, industry=25, topic="略（人工判斷，無公開資料）"),
               cols=["sid", "name", "mk", "ind", "score", "rating", "tech", "chips", "industry", "w", "pe", "pb", "yield", "yoy", "mom", "r1", "close"], rows=rows)
    jdump(DATA + "/c_score.json", out)
    return out

# ------------------------------------------------------------------ C 異動雷達（收盤後規則版）
def build_radar(db, pat):
    N = db.N; ev = []
    t = N - 1
    bk = {}
    for h in (pat or {}).get("hits", []):
        if h["bdate"] == db.dates[-1] and h["status"] == "量價確認": bk[h["sid"]] = h
    for sid, s in db.S.items():
        a = s["amt"][t]; r = ret(s, t)
        if not a or r is None: continue
        vs = [x for x in s["v"][-21:-1] if x]
        vr = (s["v"][t] / (sum(vs) / len(vs))) if vs and s["v"][t] else None
        tags = []
        if r >= 0.095: tags.append(("漲停", "up"))
        elif r <= -0.095: tags.append(("跌停", "dn"))
        if a >= 100 and r >= 0.07 and not any(x[0] == "漲停" for x in tags): tags.append(("急漲≥7%", "up"))
        if a >= 100 and r <= -0.07 and not any(x[0] == "跌停" for x in tags): tags.append(("急跌≤-7%", "dn"))
        if vr and vr >= 2 and a >= 100: tags.append(("爆量%.1f倍" % vr, "up" if r >= 0 else "dn"))
        if sid in bk: tags.append(("型態突破·" + bk[sid]["pname"], "up"))
        if a < 10 and not any(x[0] in ("漲停", "跌停") for x in tags): continue
        if tags: ev.append(dict(sid=sid, name=s["name"], mk=s["mk"], ind=db.ind[sid], close=s["rc"][t], r1=r2(r, 4), amt=r2(a / 100, 2), vr=r2(vr, 1), tags=[list(x) for x in tags]))
    ev.sort(key=lambda e: -e["amt"])
    out = dict(date=db.dates[-1], items=ev[:200], total=len(ev)); jdump(DATA + "/c_radar.json", out); return out

# ------------------------------------------------------------------ C 法人／期貨籌碼
def build_flow(db, tfx):
    N = db.N; S = db.S
    mk = [dict(d=db.dates[i], f=m.get("f"), t=m.get("t"), dl=m.get("d"), twii=m.get("twii")) for i, m in enumerate(db.mkt) if m.get("f") is not None][-60:]
    def rank(win, key, sign):
        rows = []
        for sid, s in S.items():
            if s["c"][-1] is None: continue
            lots = sum(s[key][N - win:]); amt = lots * s["rc"][-1] / 1e5   # 億元
            rows.append([sid, s["name"], round(lots), round(amt, 2), r2(ret(s, N - 1, min(win, 5)), 4)])
        rows.sort(key=lambda r: -sign * r[3]); return rows[:20]
    stocks = {}
    for win in (1, 5, 20):
        for key, kn in (("f", "外資"), ("t", "投信")):
            stocks["%s%d_buy" % (key, win)] = rank(win, key, 1); stocks["%s%d_sell" % (key, win)] = rank(win, key, -1)
    fut = []
    for d in sorted((tfx or {}).get("fut", {}))[-40:]:
        x = tfx["fut"][d]
        fut.append([d, (x.get("外資及陸資") or [None, None])[1], (x.get("投信") or [None, None])[1], (x.get("自營商") or [None, None])[1]])
    opt = []
    for d in sorted((tfx or {}).get("opt", {}))[-20:]:
        x = tfx["opt"][d]
        opt.append([d, x.get("CALL|外資及陸資"), x.get("PUT|外資及陸資")])
    out = dict(date=db.dates[-1], mkt=mk, stocks=stocks, fut=fut, opt=opt)
    jdump(DATA + "/c_flow.json", out); return out

# ------------------------------------------------------------------ C 大戶集中度（集保週資料；歷史由每週累積）
def build_hold(db, tdcc):
    wks = sorted(tdcc)
    if not wks: return None
    cur = tdcc[wks[-1]]; prv = tdcc[wks[-2]] if len(wks) > 1 else {}
    rows = []
    for sid, v in cur.items():
        if sid not in db.S: continue
        p = prv.get(sid); s = db.S[sid]
        rows.append([sid, s["name"], 0 if s["mk"] == "上市" else 1, v[0], v[1], v[2], None if not p else round(v[1] - p[1], 2), None if not p else round(v[0] - p[0], 2),
                     None if not p or not p[2] else round((v[2] / p[2] - 1) * 100, 2), s["rc"][-1], r2(ret(s, db.N - 1, 5), 4), round(sum(x or 0 for x in s["amt"][-5:]) / 5, 1)])
    out = dict(date=db.dates[-1], week=wks[-1], prev=wks[-2] if prv else None, weeks=len(wks),
               cols=["sid", "name", "mk", "big400", "big1000", "holders", "d1000", "d400", "dholders", "close", "r5", "amt5"], rows=rows)
    jdump(DATA + "/c_hold.json", out); return out

# ------------------------------------------------------------------ C 今日焦點＋規則版盤後日報
def build_brief(db, rise, rank, radar, pat, news, cal):
    N = db.N; L = []
    tw = db.twii; m = db.mkt[-1]
    if tw[-1] and tw[-2]:
        ch = tw[-1] / tw[-2] - 1
        tot = sum((s["amt"][-1] or 0) for s in db.S.values()) / 100; avg = sum(sum((s["amt"][i] or 0) for s in db.S.values()) for i in range(N - 20, N)) / 20 / 100
        L.append(["大盤", "加權指數 %.2f（%+.2f%%），上市櫃普通股成交金額 %.0f 億，為近20日均量 %.1f 倍。" % (tw[-1], ch * 100, tot, tot / avg if avg else 0), "up" if ch > 0 else "dn"])
    if m.get("f") is not None:
        L.append(["法人", "三大法人買賣超：外資 %+.0f 億、投信 %+.0f 億、自營商 %+.0f 億（證交所 BFI82U，上市）。" % (m["f"], m["t"], m["d"]), "up" if m["f"] > 0 else "dn"])
    top = rank["rows"]["official"][:3] if rank else []
    if top: L.append(["強勢族群", "官方產業加權強度前三：" + "、".join("%s（%+.2f%%）" % (r["name"], r["score"] * 100) for r in top) + "。", "up"])
    bot = rank["rows"]["official"][-2:] if rank else []
    if bot: L.append(["弱勢族群", "官方產業加權強度最後：" + "、".join("%s（%+.2f%%）" % (r["name"], r["score"] * 100) for r in bot) + "。", "dn"])
    if rise:
        ris = [x for x in rise["items"] if x["status"] == "起漲"]; new = [x for x in rise["items"] if x["new"]]
        L.append(["起漲偵測", "規則判定「起漲」的族群 %d 個、「候選」%d 個；今日新轉入 %d 個%s。" % (len(ris), sum(1 for x in rise["items"] if x["status"] == "候選"), len(new), ("（" + "、".join(x["name"] for x in new[:4]) + "）") if new else ""), "up"])
    if radar:
        lu = sum(1 for e in radar["items"] if any(t[0] == "漲停" for t in e["tags"])); ld = sum(1 for e in radar["items"] if any(t[0] == "跌停" for t in e["tags"]))
        L.append(["漲跌停", "漲停 %d 檔、跌停 %d 檔（≥9.5%% 且成交 ≥1000 萬）。" % (lu, ld), "up" if lu >= ld else "dn"])
    if pat:
        bo = [h for h in pat["hits"] if h["bdate"] == db.dates[-1] and h["status"] == "量價確認"]
        L.append(["型態", "掃描 %d 檔，偵測到 %d 組型態，其中今日量價確認突破 %d 組。" % (pat["scanned"], len(pat["hits"]), len(bo)), "fl"])
    jdump(DATA + "/c_news.json", dict(date=db.dates[-1], brief=L, news=news, cal=cal))
    return L

def main(only=None):
    t0 = time.time()
    os.makedirs(DATA, exist_ok=True)
    ds = pubdata.hist_dates(complete_only=True)
    if not ds: return
    date = ds[-1]
    for fn, a in ((fetch_rev, ()),):
        try: fn(*a)
        except Exception as e: log("  fetch fail", fn.__name__, repr(e))
    val, tdcc, tfx, news, cal = {}, {}, {}, [], []
    for name, fn, a in (("val", fetch_val, (date,)), ("tdcc", fetch_tdcc, (date,)), ("tfx", fetch_taifex, (date,)), ("news", fetch_news, ())):
        try:
            r = fn(*a)
            if name == "val": val = r
            elif name == "tdcc": tdcc = r
            elif name == "tfx": tfx = r
            else: news, cal = r
        except Exception as e: log("  fetch fail", name, repr(e))
    db = load(); log("  extras: %d days, %d stocks, amt-days %d" % (db.N, len(db.S), db.have_amt))
    if db.N < 45 or db.twr[-1] is None or any(x is None for x in db.twr[-45:]):
        log("  extras: 歷史不足（需 ≥45 日含報酬指數），略過 A/B"); rise = None
    else:
        rise = build_rise(db); build_rrg(db)
    stage = {}
    def run(name, fn, *a):
        try: stage[name] = fn(*a)
        except Exception as e:
            import traceback; traceback.print_exc(); log("  extras stage fail", name, repr(e)); stage[name] = None
    if any(x is None for x in db.mkt[-1:]) or db.S and all(s["amt"][-1] is None for s in db.S.values()):
        log("  extras: 缺成交金額，C 分頁略過"); return
    run("rank", build_rank, db); run("heat", build_heat, db); run("pat", build_patterns, db)
    run("score", build_score, db, val); run("radar", build_radar, db, stage.get("pat"))
    run("flow", build_flow, db, tfx); run("hold", build_hold, db, tdcc)
    run("brief", build_brief, db, rise, stage.get("rank"), stage.get("radar"), stage.get("pat"), news, cal)
    log("  extras done %.0fs" % (time.time() - t0))

if __name__ == "__main__":
    main()
