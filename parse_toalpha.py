"""把 toalpha_in/ 內 MCP 原始 JSON 轉成網頁用的精簡資料。缺資料就留空（頁面顯示「無資料」），絕不補編。"""
import json, os, re
H = os.path.dirname(os.path.abspath(__file__))
ACT = {"raise_tp": "調升目標價", "lower_tp": "調降目標價", "maintain": "維持", "reiterate": "重申",
       "upgrade": "調升評等", "downgrade": "調降評等"}

def _raw(name):
    p = f"{H}/toalpha_in/{name}"
    if not os.path.exists(p): return None
    t = open(p, encoding="utf-8").read()
    try: return json.JSONDecoder().raw_decode(t[t.index("{"):])[0]
    except Exception: return None

_news = None; _cal = None
def news_by_id():
    global _news
    if _news is None:
        _news = {}
        for f in sorted(os.listdir(f"{H}/toalpha_in")):
            if f.startswith("news_"):
                j = _raw(f) or {}
                for i in j.get("items", []): _news.setdefault(i["id"], {})[i.get("url") or i["title"]] = i
    return _news

def cal_by_id():
    global _cal
    if _cal is None:
        _cal = {}
        for e in (_raw("calendar_conf.txt") or {}).get("events", []): _cal.setdefault(e["id"], []).append(e)
    return _cal

def r(x, n=1):
    return None if x is None else round(x, n)

def parse_stock(sid, load_in, date):
    d = {}
    br = load_in("broker_ratings", sid)
    if br:
        s = br.get("summary") or {}
        nm = (br.get("stock") or {}).get("name", "")
        d["name"] = nm; d["ind"] = (br.get("stock") or {}).get("industry")
        d["rt"] = dict(asof=br.get("as_of"), n=s.get("brokers"), pos=s.get("positive"), neu=s.get("neutral"), neg=s.get("negative"),
                       med=s.get("tp_median"), hi=s.get("tp_high"), lo=s.get("tp_low"), up=s.get("upside_vs_close"), close=s.get("close"), link=br.get("link"))
        d["ratings"] = [dict(b=x["broker"], d=x["date"], r=x.get("rating"), a=ACT.get(x.get("action")), tp=x.get("tp"), t=x.get("title"), u=x.get("url"), s=x.get("source"),
                             warn=bool(nm and nm not in (x.get("title") or "")))
                        for x in sorted(br.get("ratings", []), key=lambda x: x["date"], reverse=True)[:6]]
    fi = load_in("financials", sid)
    if fi and fi.get("rows"):
        rows = fi["rows"]; a = rows[0]
        d.setdefault("name", (fi.get("stock") or {}).get("name"))
        d["fin"] = dict(p=a["period"], rev=a.get("revenue"), yoy=a.get("revenue_yoy"), gm=a.get("gross_margin"), om=a.get("op_margin"), nm=a.get("net_margin"),
                        ni=a.get("net_income"), eps=a.get("eps"), epsyoy=a.get("eps_yoy"), epsttm=a.get("eps_ttm"), roe=a.get("roe_ttm"),
                        prev=(dict(p=rows[1]["period"], rev=rows[1].get("revenue"), eps=rows[1].get("eps"), gm=rows[1].get("gross_margin")) if len(rows) > 1 else None),
                        link=fi.get("link"))
    nws = sorted(news_by_id().get(sid, {}).values(), key=lambda i: i["time"], reverse=True)
    seen = set(); out = []
    for i in nws:
        if i["title"] in seen or not i.get("time") or not i.get("url"): continue   # 沒有發佈時間或連結的不收
        seen.add(i["title"]); out.append(dict(t=i["title"], time=i["time"], src=i.get("source"), u=i["url"]))
        if len(out) >= 6: break
    d["news"] = out
    d["cc"] = [dict(date=e["date"], detail=e.get("detail"), inv=e.get("invited")) for e in sorted(cal_by_id().get(sid, []), key=lambda e: e["date"])]
    return d
