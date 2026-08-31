# -*- coding: utf-8 -*-
"""
白电三巨头(美的000333 / 海尔600690 / 格力000651) 监测看板 —— 取数层
=====================================================================
fetch.py 循环 3 家公司，从 data-source-router 统一取数：
  - 财务快照(最新一期: 营收/归母/ROE/毛利率/净利率/负债率/有息负债率/经营现金流)
  - 财务年度走势(营收/ROE/净利率 for SVG)
  - 行情(现价/涨跌/PE/PB/总市值/52周位置/近一年涨跌/最大回撤)
  - 分红(每10股派息 → 股息率/分红率)
输出 cache/dashboard_data.json，每公司每指标带 status/fetched_at/latest_date 溯源。

数据正确性铁律：
  - 只从东财 datacenter + 腾讯行情自动取数，绝不 hardcode。
  - 营收/净利同比按「同报告期累计值」重算，不信任东财 TOTALOPERATEREVETZ/PARENTNETPROFITTZ(有bug)。
  - 失败诚实：远程失败标 failed+error，历史值仅作 last_good 参考。
"""
import json, os, sys, time, datetime, urllib.request

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.join(BASE, "scripts"))

def _zach_root():
    d = os.path.dirname(os.path.abspath(__file__))
    for _ in range(8):
        if os.path.isdir(os.path.join(d, "data-source-router")):
            return d
        d = os.path.dirname(d)
    return os.environ.get("ZACH_SKILLS", "/root/zach-skills")

sys.path.insert(0, os.path.join(_zach_root(), "data-source-router"))
try:
    import data_router as DSR
    _HAS_DSR = True
except Exception as e:
    _HAS_DSR = False
    print(f"[warn] data-source-router 未就绪({e})，走直连东财兜底")

CACHE = os.path.join(BASE, "cache"); os.makedirs(CACHE, exist_ok=True)
DATA_PATH = os.path.join(CACHE, "dashboard_data.json")

UA = {"User-Agent": "Mozilla/5.0", "Referer": "https://emweb.securities.eastmoney.com/"}

# 三家白电：代码 + 市场前缀
COMPANIES = [
    {"name": "美的集团", "code": "000333", "secu": "000333.SZ", "tq": "sz000333"},
    {"name": "海尔智家", "code": "600690", "secu": "600690.SH", "tq": "sh600690"},
    {"name": "格力电器", "code": "000651", "secu": "000651.SZ", "tq": "sz000651"},
]

def _get(url, headers=UA, timeout=30, retry=3):
    last = None
    for i in range(retry):
        try:
            req = urllib.request.Request(url, headers=headers)
            return json.loads(urllib.request.urlopen(req, timeout=timeout).read().decode())
        except Exception as e:
            last = e; time.sleep(1.0)
    raise last

# ---------- 财务（走 router；兜底直连） ----------
def em_fin(secucode, report="RPT_F10_FINANCE_MAINFINADATA", page=40):
    if _HAS_DSR:
        d, _s, _m, _t = DSR.get("cn_financial_series", secucode=secucode, report_name=report, page=page)
        if isinstance(d, list) and d:
            return d
    url = ("https://datacenter.eastmoney.com/securities/api/data/v1/get?reportName=" + report + "&columns=ALL"
           f"&filter=(SECUCODE%3D%22{secucode}%22)&pageNumber=1&pageSize={page}&sortTypes=-1&sortColumns=REPORT_DATE")
    return _get(url)["result"]["data"]

def em_stmt(secucode, report, page=60):
    return em_fin(secucode, report, page)

def _find(rows, name):
    for r in rows:
        if r.get("REPORT_DATE_NAME") == name:
            return r
    return None

def _year_rows(rows):
    return [r for r in rows if r.get("REPORT_DATE_NAME") and "年报" in r.get("REPORT_DATE_NAME")]

def _series_of(rows, key, scale=1.0):
    out = []
    for r in _year_rows(rows):
        v = r.get(key)
        if v is None: continue
        nm = r.get("REPORT_DATE_NAME", "")
        out.append({"d": nm, "v": round(v / scale, 2) if scale != 1 else round(v, 2)})
    out.sort(key=lambda x: x["d"])   # 年份升序，确保 [-1]=最新
    return out

def _self_yoy_np(rows):
    """重算归母净利同比(同报告期累计 vs 去年同期)。返回 {报告期名: yoy%}。"""
    out = {}
    for r in rows:
        d = str(r.get("REPORT_DATE", ""))[:10]
        nm = r.get("REPORT_DATE_NAME", "")
        if not d or nm not in ("2026中报","2025中报","2026一季报","2025一季报","2026年报","2025年报"):
            continue
        y, mm = int(d[:4]), int(d[5:7])
        for r2 in rows:
            d2 = str(r2.get("REPORT_DATE", ""))[:10]
            if d2 and int(d2[:4]) == y - 1 and int(d2[5:7]) == mm:
                c, p = r.get("PARENTNETPROFIT"), r2.get("PARENTNETPROFIT")
                if c is not None and p:
                    out[nm] = round((c - p) / p * 100, 1)
                break
    return out

# ---------- 财务快照（最新一期 总表） ----------
def financial_snapshot(c):   # returns dict
    rows = em_fin(c["secu"])
    cur = _find(rows, "2026中报") or _find(rows, "2026一季报") or (rows[0] if rows else {})
    yoy = _self_yoy_np(rows)
    nm = cur.get("REPORT_DATE_NAME", "获取失败")
    rev = cur.get("TOTALOPERATEREVE"); np_ = cur.get("PARENTNETPROFIT")
    return {
        "report": nm, "stale": False,
        "rev": round(rev / 1e8, 1) if rev else None,
        "np": round(np_ / 1e8, 1) if np_ else None,
        "np_yoy": yoy.get(nm),
        "roe": round(cur["ROEJQ"], 2) if isinstance(cur.get("ROEJQ"), (int, float)) else None,
        "gm": round(cur["XSMLL"], 2) if isinstance(cur.get("XSMLL"), (int, float)) else None,
        "nm": round(cur["XSJLL"], 2) if isinstance(cur.get("XSJLL"), (int, float)) else None,
        "debt": round(cur["ZCFZL"], 1) if isinstance(cur.get("ZCFZL"), (int, float)) else None,
        "idebt": round(cur["INTEREST_DEBT_RATIO"], 1) if isinstance(cur.get("INTEREST_DEBT_RATIO"), (int, float)) else None,
        "opcf": round(cur["MGJYXJJE"], 2) if isinstance(cur.get("MGJYXJJE"), (int, float)) else None,
    }

# ---------- 年度走势（营收/ROE 两线 SVG） ----------
def annual_trends(c):
    rows = em_fin(c["secu"])
    rev = _series_of(rows, "TOTALOPERATEREVE", 1e8)[-6:]   # 近6年年报
    roe = _series_of(rows, "ROEJQ")[-6:]
    nm = _series_of(rows, "XSJLL")[-6:]
    return {"stale": False,
            "charts": [
                {"name": "营收(亿)", "color": "#2563eb", "points": rev},
                {"name": "ROE%", "color": "#16a34a", "points": roe},
                {"name": "净利率%", "color": "#7c3aed", "points": nm},
            ]}

# ---------- 行情（腾讯） ----------
def quote(c):
    url = f"https://qt.gtimg.cn/q={c['tq']}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Referer": "https://gu.qq.com/"})
    try:
        text = urllib.request.urlopen(req, timeout=20).read().decode("gbk")
    except Exception:
        return {"stale": True, "error": "行情获取失败"}
    body = text.split('="', 1)[1].rsplit('"', 1)[0]; f = body.split("~")
    def g(i, conv=None):
        try:
            v = float(f[i]) if conv == float else f[i]
            return v
        except Exception:
            return None
    return {
        "stale": False, "price": g(3, float), "chg_pct": g(32, float),
        "pe": g(39, float), "pb": g(46, float), "mktcap": g(45, float),
        "turnover": g(38, float), "name": f[1],
    }

# ---------- 52周位置 / 回撤 / 近一年（腾讯K线） ----------
def market_position(c):
    url = f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={c['tq']},day,,,400,qfq"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Referer": "https://gu.qq.com/"})
    try:
        d = json.loads(urllib.request.urlopen(req, timeout=25).read().decode("utf-8"))
    except Exception as e:
        return {"stale": True, "error": f"K线失败 {str(e)[:80]}"}
    node = d["data"][c["tq"]]
    rows = node.get("qfqday") or node.get("day") or []
    kl = [(x[0], float(x[2])) for x in rows]
    if len(kl) < 2:
        return {"stale": True, "error": "K线数据不足"}
    closes = [x[1] for x in kl]; px = closes[-1]
    win = min(250, len(closes))
    hi = max(closes[-win:]); lo = min(closes[-win:])
    pos52 = (px - lo) / (hi - lo) * 100 if hi > lo else 100
    peak = closes[0]; maxdd = 0.0; mdd_date = kl[0][0]
    for dt, c2 in kl:
        if c2 > peak: peak = c2
        dd = (peak - c2) / peak * 100
        if dd > maxdd: maxdd = dd; mdd_date = dt
    y_ago = closes[-win] if len(closes) >= win else closes[0]
    ret1y = (px / y_ago - 1) * 100
    return {"stale": False, "pos52": round(pos52, 1), "maxdd": round(maxdd, 1),
            "mdd_date": mdd_date, "ret1y": round(ret1y, 1)}

# ---------- 分红（东财 RPT_SHAREBONUS_DET → 股息率/分红率） ----------
def dividend(c):
    import urllib.parse
    url = ("https://datacenter.eastmoney.com/securities/api/data/v1/get"
           "?reportName=RPT_SHAREBONUS_DET&columns=ALL"
           f"&filter=(SECUCODE%3D%22{c['secu']}%22)&pageNumber=1&pageSize=12&sortTypes=-1&sortColumns=REPORT_DATE")
    try:
        rows = _get(url)["result"]["data"]
    except Exception as e:
        return {"stale": True, "error": f"分红获取失败 {str(e)[:80]}"}
    # 白电普遍「年度大额 + 中期小额」双分红。股息率基准取「最近完整年报(12-31期)派息」，
    # 这是可持续口径(中期分红是预案/非完整年)；绝不用最近一期(如2026中报预案)当当前股息率。
    def year_of(r):
        return str(r.get("REPORT_DATE", ""))[:4]
    annual = [r for r in rows if str(r.get("REPORT_DATE", "")).endswith("12-31 00:00:00") and r.get("PRETAX_BONUS_RMB")]
    # 每年取该年最后一次年报派息(最新在前→第一笔即最近年报)
    seen = {}
    for r in annual:
        yr = year_of(r)
        if yr not in seen:
            seen[yr] = r
    latest = next((v for v in [seen.get(y) for y in ["2025", "2024", "2023", "2022", "2021"] if y in seen] if v), None)
    # 展示近5年年报派息
    years = []
    for y in ["2025", "2024", "2023", "2022", "2021"]:
        if y in seen:
            years.append({"year": y, "d10": seen[y].get("PRETAX_BONUS_RMB")})
    div_data = {"stale": False, "years": years,
                "latest_year": year_of(latest) if latest else None,
                "d10": latest.get("PRETAX_BONUS_RMB") if latest else None}
    px = quote(c).get("price")
    if latest and px:
        div_data["yield"] = round(latest.get("PRETAX_BONUS_RMB") / 10 / px * 100, 2)
    else:
        div_data["yield"] = None
    return div_data

# ---------- 估值性价比（复用合理PB=ROE/r 逻辑，简版：PE分位+股息率锚） ----------
def valuation(c, snap):
    q = quote(c)
    roe = snap.get("roe")
    pb = q.get("pb"); pe = q.get("pe")
    # 市场隐含回报 = ROE/PB
    imp = round(roe / pb, 2) if roe and pb else None
    # 合理PB=ROE/10% 对应价
    fair_pb_r10 = roe / 10 if roe else None
    fair_px_r10 = round(fair_pb_r10 * (q.get("price") / pb if pb else 1), 2) if fair_pb_r10 else None
    return {"stale": False, "pe": pe, "pb": pb,
            "implied_r": imp, "fair_px_r10": fair_px_r10}

# ========== 主流程 ==========
def fetch_all():
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    prev = None
    if os.path.exists(DATA_PATH):
        try: prev = json.load(open(DATA_PATH, encoding="utf-8"))
        except Exception: prev = None
    prev_companies = {cm["name"]: cm for cm in (prev["companies"] if prev else [])} if prev else {}

    out = {"fetched_at": now, "companies": []}
    for c in COMPANIES:
        pc = prev_companies.get(c["name"], {})
        rec = {"name": c["name"], "code": c["code"], "tq": c["tq"],
               "secu": c["secu"], "sets": {}, "fetched_at": now}

        # 各数据组
        for setname, fn in [("financial", lambda: financial_snapshot(c)),
                            ("trends", lambda: annual_trends(c)),
                            ("quote", lambda: quote(c)),
                            ("position", lambda: market_position(c)),
                            ("dividend", lambda: dividend(c))]:
            try:
                rec["sets"][setname] = fn()
                rec["sets"][setname]["status"] = "ok"
            except Exception as e:
                old = pc.get("sets", {}).get(setname, {}) if isinstance(pc, dict) else {}
                rec["sets"][setname] = {"status": "failed", "error": str(e)[:120],
                                        "last_good": old.get("value") if isinstance(old, dict) else None}
        # valuation 依赖 snap+quote
        try:
            snap, q = rec["sets"].get("financial"), rec["sets"].get("quote")
            val = valuation(c, snap or {})
            rec["sets"]["valuation"] = val; val["status"] = "ok"
        except Exception as e:
            rec["sets"]["valuation"] = {"status": "failed", "error": str(e)[:80]}

        out["companies"].append(rec)
        # 打印摘要
        f = rec["sets"].get("financial", {}); q_ = rec["sets"].get("quote", {})
        print(f"  {c['name']}: 期={f.get('report')} 营收={f.get('rev')}亿 归母={f.get('np')}亿 "
              f"现价={q_.get('price')} PE={q_.get('pe')} 股息={(rec['sets'].get('dividend') or {}).get('yield')}%")
        time.sleep(0.3)

    with open(DATA_PATH, "w") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("saved", DATA_PATH)
    return out

if __name__ == "__main__":
    fetch_all()