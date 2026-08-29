# -*- coding: utf-8 -*-
"""
取数脚本：拉取看板全部可自动获取的数据 → cache/dashboard_data.json
设计：远程优先(免费公开源) + 失败回退本地种子缓存(标记 stale) + TTL 分级。
正确性 > 及时性；每个指标带 fetched_at / source_ts / stale 便于溯源。
"""
import json, os, sys, time, datetime, urllib.request, statistics

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "scripts"))

def _zach_root():
    """自动定位 zach-skills 根（含 data-source-router），迁移可用的关键：不写死绝对路径。"""
    d = os.path.dirname(os.path.abspath(__file__))
    for _ in range(8):
        if os.path.isdir(os.path.join(d, "data-source-router")):
            return d
        d = os.path.dirname(d)
    return os.environ.get("ZACH_SKILLS", "/root/zach-skills")

sys.path.insert(0, os.path.join(_zach_root(), "data-source-router"))
import data_router as DSR
from indicators import INDICATORS

CACHE = os.path.join(BASE, "cache"); SEED = os.path.join(CACHE, "seed")
os.makedirs(CACHE, exist_ok=True); os.makedirs(SEED, exist_ok=True)
DATA_PATH = os.path.join(CACHE, "dashboard_data.json")
MANUAL_PATH = os.path.join(BASE, "cache", "manual.json")

def load_manual():
    try:
        return json.load(open(MANUAL_PATH, encoding="utf-8"))
    except Exception:
        return {}

UA = {"User-Agent": "Mozilla/5.0", "Referer": "https://index.ccement.com/"}
TQ = {"User-Agent": "Mozilla/5.0"}

def _get(url, headers=UA, timeout=35, retry=2):
    last = None
    for i in range(retry):
        try:
            req = urllib.request.Request(url, headers=headers)
            return json.loads(urllib.request.urlopen(req, timeout=timeout).read().decode())
        except Exception as e:
            last = e; time.sleep(1.5)
    raise last

def _cget(url, timeout=14, retry=3):
    """ccement 源：已知偶发单次丢包，短超时+多次重试(丢包重试即恢复)；仍失败则报错(不拿旧值冒充)"""
    last = None
    for i in range(retry+1):
        try:
            req = urllib.request.Request(url, headers=UA)
            return json.loads(urllib.request.urlopen(req, timeout=timeout).read().decode())
        except Exception as e:
            last = e
            if i < retry: time.sleep(0.8)
    raise last

def _gettxt(url, headers=TQ, timeout=30):
    req = urllib.request.Request(url, headers=headers)
    return urllib.request.urlopen(req, timeout=timeout).read().decode("utf-8", "ignore")

# ---------- 中国水泥网：远程优先 + 种子回退 ----------
_c = {}
def ccement_priceindex():
    if "gpi" not in _c:
        _c["gpi"] = _cget("https://index.ccement.com/index/priceindex/getPriceIndex")["Data"]
    return _c["gpi"]
def ccement_series(ep):
    key = "s_" + ep.replace("/", "_")
    if key not in _c:
        _c[key] = _cget("https://index.ccement.com/index/priceindex/" + ep)["Data"]
    return _c[key]

def series_stats(dates, vals):
    import datetime as dt
    pairs = sorted(zip(dates, vals), key=lambda t: t[0])
    d = [p[0] for p in pairs]; v = [float(p[1]) for p in pairs]
    if not d: return {"latest": None}
    hi = max(v); lo = min(v)
    latest, latest_date = v[-1], d[-1]
    target = str(dt.date.fromisoformat(d[-1]) - dt.timedelta(days=365))
    idx = next((i for i, x in enumerate(d) if x >= target), 0)
    yoy = (latest - v[idx]) / v[idx] * 100 if v[idx] else None
    step = max(1, len(d)//200)
    return {"latest": round(latest, 2), "latest_date": latest_date,
            "yoy_1y": round(yoy, 1) if yoy is not None else None,
            "hi": round(hi,2), "hi_date": d[v.index(hi)], "lo": round(lo,2), "lo_date": d[v.index(lo)],
            "trend": [{"d": d[i], "v": v[i]} for i in range(0, len(d), step)],
            "full_len": len(d)}

def seed_series(name):
    """历史备份序列（仅存档参考，不作为当前值）"""
    p = os.path.join(SEED, name + ".json")
    if os.path.exists(p):
        d = json.load(open(p, encoding="utf-8"))
        return series_stats(d["date"], d["val"])
    return None

def _with_chart(res, name, color="#2563eb"):
    """给 series_stats 结果附加单序列趋势图数据 (render 用 charts 画)"""
    if res.get("trend"):
        res["charts"] = [{"name": name, "color": color, "points": res["trend"]}]
    return res

def _adapt_cement(d, name, color):
    """router cn_cement_index 输出 → 看板 value + charts 单序列。"""
    if not (d and d.get("ok")):
        raise RuntimeError("router ccement 不可用: " + str(d)[:60])
    series = d.get("series") or []
    return {"latest": d.get("latest"), "latest_date": d.get("latest_date"),
            "yoy_1y": d.get("yoy_1y"), "hi": d.get("hi"), "hi_date": d.get("hi_date"),
            "lo": d.get("lo"), "lo_date": d.get("lo_date"),
            "charts": [{"name": name, "color": color, "points": series}], "stale": False}

def get_cempi():
    d,s,m,t = DSR.get('cn_cement_index', index_type='cempi')
    return _adapt_cement(d, "CEMPI", "#2563eb")
def get_coal():
    d,s,m,t = DSR.get('cn_cement_index', index_type='coal')
    return _adapt_cement(d, "煤价", "#16a34a")
def get_po425():
    d,s,m,t = DSR.get('cn_cement_index', index_type='po425')
    return _adapt_cement(d, "P.O42.5", "#d97706")
def get_clinker():
    d,s,m,t = DSR.get('cn_cement_index', index_type='clinker')
    return _adapt_cement(d, "熟料", "#7c3aed")
def get_concrete():
    d,s,m,t = DSR.get('cn_cement_index', index_type='concrete')
    return _adapt_cement(d, "混凝土", "#0891b2")
def get_spread():
    pos,_,_,_ = DSR.get('cn_cement_index', index_type='po425')
    cls,_,_,_ = DSR.get('cn_cement_index', index_type='clinker')
    cod = {x['d']: x['v'] for x in (pos.get('series') or [])}
    cld = {x['d']: x['v'] for x in (cls.get('series') or [])}
    common = sorted(set(cod) & set(cld))
    pts = [{"d": d, "v": round(cod[d]-cld[d], 1)} for d in common]
    recent = [p['v'] for p in pts[-7:]]
    return {"latest": round(statistics.mean(recent), 1) if recent else None, "latest_date": "近一周均值",
            "note": "水泥-熟料价差(周均)",
            "charts": [{"name": "水泥-熟料价差", "color": "#dc2626", "points": pts}], "stale": False}

# ---------- 东财财务（海螺/华新/同行） ----------
def em_fin(secucode, page=30):
    url = ("https://datacenter.eastmoney.com/securities/api/data/v1/get?reportName=RPT_F10_FINANCE_MAINFINADATA&columns=ALL"
           f"&filter=(SECUCODE%3D%22{secucode}%22)&pageNumber=1&pageSize={page}&sortTypes=-1&sortColumns=REPORT_DATE")
    return _get(url, headers={"User-Agent": "Mozilla/5.0", "Referer": "https://emweb.securities.eastmoney.com/"})["result"]["data"]
def em_find(rows, key):
    for r in rows:
        if r.get("REPORT_DATE_NAME") == key: return r
    return None

def get_helluo_np():
    rows = em_fin("600585.SH"); r = em_find(rows, "2026中报")
    hist = sorted([{"d": str(x.get("REPORT_DATE",""))[:10], "v": round(x.get("PARENTNETPROFIT",0)/1e8,1)}
                   for x in rows if x.get("PARENTNETPROFIT") is not None], key=lambda t:t["d"])
    return {"np": round(r.get("PARENTNETPROFIT", 0)/1e8, 1), "np_yoy": round(r.get("PARENTNETPROFITTZ"), 1),
            "rev": round(r.get("TOTALOPERATEREVE", 0)/1e8, 1), "rev_yoy": round(r.get("TOTALOPERATEREVETZ"), 1),
            "gm": r.get("XSMLL"), "nm": r.get("XSJLL"), "report": "2026中报",
            "charts": [{"name": "归母净利(累计·亿)", "color": "#dc2626", "points": hist}], "stale": False}
def get_cashflow_ratio():
    rows = em_fin("600585.SH"); r = em_find(rows, "2026中报")
    eps = r.get("EPSJB") or 0; cf = r.get("MGJYXJJE") or 0
    hist = sorted([{"d": str(x.get("REPORT_DATE",""))[:10],
                    "v": round((x.get("MGJYXJJE") or 0)/(x.get("EPSJB") or 1), 2)}
                   for x in rows if x.get("MGJYXJJE") is not None and x.get("EPSJB")], key=lambda t:t["d"])
    return {"latest": round(cf/eps, 2) if eps else None, "eps": eps, "cf_ps": cf, "report": "2026中报",
            "charts": [{"name": "经营现金流/净利", "color": "#2563eb", "points": hist}], "stale": False}
def get_debt_ratio():
    rows = em_fin("600585.SH"); r = em_find(rows, "2026中报")
    hist = sorted([{"d": str(x.get("REPORT_DATE",""))[:10], "v": x.get("ZCFZL")}
                   for x in rows if x.get("ZCFZL") is not None], key=lambda t:t["d"])
    return {"latest": round(r.get("ZCFZL", 0), 1), "latest_date": "2026中报",
            "charts": [{"name": "资产负债率%", "color": "#2563eb", "points": hist}], "stale": False}

# ---------- 同行对比（头部五家） ----------
PEERS = [("海螺水泥","600585.SH"),("华新水泥","600801.SH"),("天山股份","000877.SZ"),
         ("冀东水泥","000401.SZ"),("塔牌集团","002233.SZ")]
def get_peers(report="2026中报"):
    rows = []
    for name, code in PEERS:
        try:
            d = em_fin(code); r = em_find(d, report)
            r25 = em_find(d, "2025年报")
            if not r: raise RuntimeError("无报告期")
            p = lambda rr: rr or {}
            rows.append({"name": name, "code": code,
                "rev": round(p(r).get("TOTALOPERATEREVE",0)/1e8, 1) if r else None,
                "np": round(p(r).get("PARENTNETPROFIT",0)/1e8, 1) if r else None,
                "np_yoy": round(p(r).get("PARENTNETPROFITTZ",0), 1) if r else None,
                "gm": p(r).get("XSMLL"), "nm": p(r).get("XSJLL"),
                "roe": p(r).get("ROEJQ"), "zcfz": p(r).get("ZCFZL"),
                "cf_ps": p(r).get("MGJYXJJE"), "np25": round(p(r25).get("PARENTNETPROFIT",0)/1e8,1) if r25 else None,
                "report": report})
        except Exception as e:
            rows.append({"name": name, "code": code, "err": str(e)[:40], "report": report})
    return rows

# ---------- 财务细项（资产负债表/现金流量表） ----------
def em_stmt(secucode, report_arg):
    url = ("https://datacenter.eastmoney.com/securities/api/data/v1/get?reportName=" + report_arg + "&columns=ALL"
           f"&filter=(SECUCODE%3D%22{secucode}%22)&pageNumber=1&pageSize=8&sortTypes=-1&sortColumns=REPORT_DATE")
    return _get(url, headers={"User-Agent":"Mozilla/5.0","Referer":"https://emweb.securities.eastmoney.com/"})["result"]["data"]
def em_balance():
    return em_find(em_stmt("600585.SH","RPT_F10_FINANCE_GBALANCE"), "2026中报")
def em_cashflow():
    return em_find(em_stmt("600585.SH","RPT_F10_FINANCE_GCASHFLOW"), "2026中报")
def get_money():
    r = em_balance() or {}; g = lambda k: (r.get(k) or 0)
    return {"latest": round(g("MONETARYFUNDS")/1e8, 1), "latest_date": "2026中报", "stale": False}
def get_idebt():
    r = em_balance() or {}; g = lambda k: (r.get(k) or 0)
    ib = g("SHORT_LOAN")+g("LONG_LOAN")+g("BOND_PAYABLE")+g("SHORT_BOND_PAYABLE")
    ta = r.get("TOTAL_ASSETS") or 1
    return {"latest": round(ib/ta*100, 1), "latest_date": "2026中报",
            "note": f"短借{g('SHORT_LOAN')/1e8:.1f}+长借{g('LONG_LOAN')/1e8:.1f}+债券{g('BOND_PAYABLE')/1e8:.1f}亿 / 总资产{ta/1e8:.0f}亿", "stale": False}
def get_fcf():
    r = em_cashflow() or {}; g = lambda k: (r.get(k) or 0)
    op = g("NETCASH_OPERATE"); cap = g("CONSTRUCT_LONG_ASSET")
    return {"latest": round((op-cap)/1e8, 1), "latest_date": "2026中报",
            "note": f"经营现金{op/1e8:.1f}亿 - 资本开支{cap/1e8:.1f}亿", "stale": False}

def tencent_quote(code):
    import re
    raw = _gettxt(f"https://qt.gtimg.cn/q={code}", headers=TQ)
    m = re.search(r'="(.*)"', raw); f = m.group(1).split("~")
    return {"name": f[1], "price": float(f[3]) if f[3] else None,
            "pe": float(f[39]) if f[39] else None, "pb": float(f[46]) if f[46] else None}
def get_pb():
    rows = em_fin("600585.SH"); r = em_find(rows, "2026中报")
    q = tencent_quote("sh600585"); bps = r.get("BPS") if r else None
    if not bps:
        return {"latest": None, "note": "缺每股净资产", "stale": False}
    k = get_kline(qfq=False)  # 不复权价(市值口径)
    dates = [x[0] for x in k]; closes = [x[2] for x in k]
    pb_s = [round(c/bps, 3) for c in closes]
    cur = round(closes[-1]/bps, 3)
    last250 = pb_s[-250:] if len(pb_s) >= 250 else pb_s
    pct = round(sum(1 for p in last250 if p <= cur)/len(last250)*100, 1)
    step = max(1, len(pb_s)//150)
    pts = [{"d": dates[i], "v": pb_s[i]} for i in range(0, len(pb_s), step)]
    return {"latest": cur, "pb_percentile": pct, "bps": round(bps, 2),
            "price": q.get("price"), "pe": q.get("pe"),
            "note": "PB=不复权收盘价/每股净资产(26中报)；分位=近250日所处百分位",
            "charts": [{"name": "PB", "color": "#dc2626", "points": pts}], "stale": False}
def get_dividend_yield():
    d = _report()
    dy = d.get("dividend_yield"); dps = d.get("dps"); price = d.get("price")
    if dy is None:
        return {"latest": None, "note": "未提取分红", "stale": False}
    return {"latest": dy, "latest_date": d.get("fetched_at", ""), "report": d.get("ar_report", ""),
            "note": f"全年每股派息 {dps} 元，现价 {price} 元（10年国债对比待补）", "stale": False}

# ---------- 技术面（腾讯ifzq前复权K线） ----------
def get_kline(code="sh600585", beg="2024-01-01", end="2026-08-29", cnt=660, qfq=True):
    fqs = ",qfq" if qfq else ","
    url = f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={code},day,{beg},{end},{cnt}{fqs}"
    d = _get(url, headers={"User-Agent": "Mozilla/5.0", "Referer": "https://gu.qq.com/"})
    key = "qfqday" if qfq else "day"
    k = d["data"][code].get(key) or d["data"][code].get("day", [])
    return [[r[0], float(r[1]), float(r[2]), float(r[3]), float(r[4]), float(r[5])] for r in k]
def get_ma():
    k = get_kline(); dates = [r[0] for r in k]; c = [r[2] for r in k]
    def mser(n):
        return [round(sum(c[max(0, i-n+1):i+1])/min(n, i+1), 2) for i in range(len(c))]
    ma20s, ma60s = mser(20), mser(60)
    step = max(1, len(c)//150)
    pts = lambda s: [{"d": dates[i], "v": s[i]} for i in range(0, len(s), step)]
    return {"latest_date": dates[-1], "close": c[-1],
            "ma20": round(sum(c[-20:])/20, 2) if len(c) >= 20 else None,
            "ma60": round(sum(c[-60:])/60, 2) if len(c) >= 60 else None,
            "ma120": round(sum(c[-120:])/120, 2) if len(c) >= 120 else None,
            "charts": [
                {"name": "收盘价", "color": "#1f2329", "points": pts(c)},
                {"name": "MA20", "color": "#d97706", "points": pts(ma20s)},
                {"name": "MA60", "color": "#2563eb", "points": pts(ma60s)}],
            "stale": False}
def get_macd_rsi():
    k = get_kline(); c = [r[2] for r in k]; n = len(c)
    e12=[c[0]]; e26=[c[0]]
    for x in c[1:]:
        e12.append(x*2/13+e12[-1]*11/13); e26.append(x*2/27+e26[-1]*25/27)
    dif=[a-b for a,b in zip(e12,e26)]
    dea=[dif[0]]
    for a in dif[1:]: dea.append(a*2/10+dea[-1]*8/10)
    macd=[(a-b)*2 for a,b in zip(dif,dea)]
    g=[max(c[i]-c[i-1],0) for i in range(1,n)]; l=[max(c[i-1]-c[i],0) for i in range(1,n)]
    ag=sum(g[:14])/14; al=sum(l[:14])/14
    for i in range(14,len(g)): ag=(ag*13+g[i])/14; al=(al*13+l[i])/14
    rsi=100-100/(1+ag/al) if al else 100
    dates=[r[0] for r in k]; step=max(1,len(dates)//150)
    pts=lambda s:[{"d":dates[i],"v":round(s[i],3)} for i in range(0,len(s),step)]
    return {"latest_date": k[-1][0], "dif": round(dif[-1],3), "dea": round(dea[-1],3),
            "macd": round(macd[-1],3), "rsi14": round(rsi,1),
            "charts":[{"name":"DIF","color":"#2563eb","points":pts(dif)},
                      {"name":"DEA","color":"#d97706","points":pts(dea)},
                      {"name":"MACD","color":"#7c3aed","points":pts(macd)}],
            "stale": False}

def _report():
    try:
        return json.load(open(os.path.join(BASE, "cache", "report_helluo.json"), encoding="utf-8"))
    except Exception:
        return {}
def get_rep_ton_gm():
    d = _report(); v = d.get("ton_gross_margin")
    if not v: return {"latest": None, "note": "财报未提取", "stale": False}
    return {"latest": v, "latest_date": d.get("fetched_at", ""), "report": d.get("report", ""),
            "note": f"自产品吨毛利 {v} 元/吨(收入-营业成本口径)", "stale": False}
def get_rep_ton_cost():
    d = _report(); v = d.get("ton_cost")
    if not v: return {"latest": None, "note": "财报未提取", "stale": False}
    prod = d.get("prod_cost"); fuel = d.get("fuel_power_cost")
    return {"latest": v, "latest_date": d.get("fetched_at", ""), "report": d.get("report", ""),
            "note": f"吨营业成本 {v} 元/吨" + (f"；生产成本 {prod} 元/吨" if prod else "") +
                    (f"；燃料动力 {fuel} 元/吨" if fuel else ""), "stale": False}
def get_rep_sales_yoy():
    d = _report(); v = d.get("sales_yoy")
    if v is None: return {"latest": None, "note": "财报未提取", "stale": False}
    return {"latest": v, "latest_date": d.get("fetched_at", ""), "report": d.get("report", ""),
            "note": f"自产品销量 {d.get('sales_yt')} 亿吨，同比 {v}%", "stale": False}

def get_rep_ton_price():
    d = _report(); v = d.get("ton_price")
    if not v: return {"latest": None, "note": "财报未提取", "stale": False}
    return {"latest": v, "latest_date": d.get("fetched_at", ""), "report": d.get("op_report", ""),
            "note": f"自产品吨售价 {v} 元/吨", "stale": False}
def get_rep_ton_np():
    d = _report(); sy = d.get("sales_yt"); hn = get_helluo_np(); np = hn.get("np")
    if sy and np is not None:
        v = round(np/sy, 1)
        return {"latest": v, "latest_date": d.get("fetched_at", ""), "report": d.get("op_report", ""),
                "note": f"归母净利{np}亿 ÷ 销量{sy}亿吨 = {v} 元/吨（含骨料/混凝土口径近似）", "stale": False}
    return {"latest": None, "note": "缺数据", "stale": False}

GETTER_MAP = {
    "po425_price": get_po425, "cempi_index": get_cempi, "clinker_price": get_clinker,
    "concrete_price": get_concrete, "spread_calc": get_spread, "coal_index": get_coal,
    "helluo_np_yoy": get_helluo_np, "cashflow_ratio": get_cashflow_ratio,
    "debt_ratio": get_debt_ratio, "pb_percentile": get_pb, "ma_calc": get_ma,
    "macd_rsi_calc": get_macd_rsi, "dividend_yield_calc": get_dividend_yield,
    "rep_ton_gm": get_rep_ton_gm, "rep_ton_cost": get_rep_ton_cost, "rep_sales_yoy": get_rep_sales_yoy,
    "monetary": get_money, "idebt": get_idebt, "fcf": get_fcf,
    "rep_ton_price": get_rep_ton_price, "rep_ton_np": get_rep_ton_np,
}

def fetch_all():
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    prev = None
    if os.path.exists(DATA_PATH):
        try: prev = json.load(open(DATA_PATH, encoding="utf-8"))
        except Exception: prev = None
    prev_map = {i["id"]: i for i in (prev["indicators"] if prev else [])}
    manual = load_manual()
    out = {"fetched_at": now, "indicators": []}
    for ind in INDICATORS:
        rec = dict(ind)
        fn = GETTER_MAP.get(ind["getter"])
        if fn:
            try:
                val = fn(); rec["value"] = val; rec["last_good"] = val
                rec["last_good_at"] = now; rec["status"] = "ok"
            except Exception as e:
                old = prev_map.get(ind["id"])
                if old:
                    rec["last_good"] = old.get("last_good")
                    rec["last_good_at"] = old.get("last_good_at")
                rec["value"] = None; rec["status"] = "failed"; rec["error"] = str(e)[:100]
        else:
            rec["status"] = "pending"; rec["note"] = "待接入(财报/公告/换通道)"
        # 人工补录覆盖：用户从别的软件获取后写入 manual.json，优先展示
        if rec["id"] in manual and rec["status"] in ("pending", "failed", "error"):
            m = manual[rec["id"]]
            rec["value"] = m.get("value"); rec["status"] = "manual"
            rec["last_good"] = m.get("value"); rec["last_good_at"] = m.get("date")
            rec["manual_at"] = m.get("date"); rec["manual_note"] = m.get("note", "人工录入")
        rec["fetched_at"] = now
        out["indicators"].append(rec)
    out["peers"] = get_peers()
    with open(DATA_PATH, "w") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("saved", DATA_PATH)
    for ind in out["indicators"]:
        v = ind.get("value")
        if isinstance(v, dict): disp = v.get("latest") or v.get("close") or v.get("np") or v.get("pending") or ""
        elif v is None: disp = ""
        else: disp = v
        stale = " (stale)" if ind.get("stale") else ""
        if ind["status"] == "error": disp = ind.get("error","")
        print(f"  [{ind['status']:6s}] {ind['name']}: {disp}{stale}")
    return out

if __name__ == "__main__":
    fetch_all()
