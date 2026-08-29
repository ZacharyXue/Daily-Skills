# -*- coding: utf-8 -*-
"""
取数脚本：拉取人福药业(600079)四大财务走势 + 降本拆解 → cache/dashboard_data.json
设计：远程优先(东财 datacenter 免费公开源) + 失败诚实(stale 标记) + 每指标带 fetched_at/source 溯源。
正确性 > 及时性；绝不拿旧值冒充当前值。
"""
import json, os, sys, time, datetime, urllib.request

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "scripts"))

def _zach_root():
    """自动定位 zach-skills 根（含 data-source-router），迁移可用。"""
    d = os.path.dirname(os.path.abspath(__file__))
    for _ in range(8):
        if os.path.isdir(os.path.join(d, "data-source-router")):
            return d
        d = os.path.dirname(d)
    return os.environ.get("ZACH_SKILLS", "/root/zach-skills")

# 统一走 data-source-router 取数（数据源/缓存/重试/Tier 全在 router，勿自建重复抓取）
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

def _get(url, headers=UA, timeout=35, retry=2):
    last = None
    for i in range(retry):
        try:
            req = urllib.request.Request(url, headers=headers)
            return json.loads(urllib.request.urlopen(req, timeout=timeout).read().decode())
        except Exception as e:
            last = e; time.sleep(1.2)
    raise last

# ---------- 东财主财务数据（含有息负债率） ----------
def em_fin(secucode, page=40):
    """主财务序列(含 INTEREST_DEBT_RATIO 有息负债率)。优先走 router；DSR 不可用才直连。"""
    if _HAS_DSR:
        d, _s, _m, _t = DSR.get("cn_financial_series", secucode=secucode,
                                 report_name="RPT_F10_FINANCE_MAINFINADATA", page=page)
        if isinstance(d, list):
            return d
    url = ("https://datacenter.eastmoney.com/securities/api/data/v1/get?reportName=RPT_F10_FINANCE_MAINFINADATA&columns=ALL"
           f"&filter=(SECUCODE%3D%22{secucode}%22)&pageNumber=1&pageSize={page}&sortTypes=-1&sortColumns=REPORT_DATE")
    return _get(url)["result"]["data"]

# ---------- 东财利润表（费用拆解） ----------
def em_stmt(secucode, report_arg, page=40):
    """利润表(费用拆解)。优先走 router；DSR 不可用才直连。"""
    if _HAS_DSR:
        d, _s, _m, _t = DSR.get("cn_financial_series", secucode=secucode,
                                 report_name=report_arg, page=page)
        if isinstance(d, list):
            return d
    url = ("https://datacenter.eastmoney.com/securities/api/data/v1/get?reportName=" + report_arg + "&columns=ALL"
           f"&filter=(SECUCODE%3D%22{secucode}%22)&pageNumber=1&pageSize={page}&sortTypes=-1&sortColumns=REPORT_DATE")
    return _get(url)["result"]["data"]

def _find(rows, name):
    for r in rows:
        if r.get("REPORT_DATE_NAME") == name:
            return r
    return None

def _series(rows, key, filt=None, scale=1):
    """把报告期序列转成 {d(name), v(value)}，按报告期升序；可过滤(默认只取年报/中报的「累计」)。"""
    out = []
    for r in rows:
        v = r.get(key)
        if v is None:
            continue
        if filt and filt(r):
            continue
        nm = r.get("REPORT_DATE_NAME", "")
        out.append({"d": nm, "v": round(v/scale, 2) if scale != 1 else round(v, 2)})
    # 升序按 REPORT_DATE 更可靠，但名称也能排序；直接用原始 rows 顺序是倒序，这里反转
    out = out[::-1]
    return out

# ========== 四大财务走势（年度） ==========
def get_trend_rev():
    rows = em_fin("600079.SH")
    r = _find(rows, "2025年报") or {}
    rev = r.get("TOTALOPERATEREVE")
    rev_yoy = r.get("TOTALOPERATEREVETZ")
    pts = [{"d": t["d"], "v": t["v"]} for t in _series(rows, "TOTALOPERATEREVE", scale=1e8)]
    # 只保留年报点，剔季报/中报，避免半年轴抖动
    annual = [p for p in pts if "年报" in p["d"]]
    cy = r.get("REPORT_DATE_NAME", "")
    return {"latest": round(rev/1e8, 1) if rev else None, "latest_date": cy,
            "rev_yoy": round(rev_yoy, 1) if rev_yoy is not None else None,
            "charts": [{"name": "营收(亿)", "color": "#2563eb", "points": annual}], "stale": False}

def get_trend_roe():
    rows = em_fin("600079.SH")
    r = _find(rows, "2025年报") or {}
    pts = [{"d": t["d"], "v": t["v"]} for t in _series(rows, "ROEJQ")]
    annual = [p for p in pts if "年报" in p["d"]]
    return {"latest": r.get("ROEJQ"), "latest_date": r.get("REPORT_DATE_NAME", ""),
            "charts": [{"name": "ROE%", "color": "#16a34a", "points": annual}], "stale": False}

def get_trend_debt():
    rows = em_fin("600079.SH")
    r = _find(rows, "2025年报") or {}
    pts = [{"d": t["d"], "v": t["v"]} for t in _series(rows, "ZCFZL")]
    annual = [p for p in pts if "年报" in p["d"]]
    return {"latest": round(r.get("ZCFZL"), 1), "latest_date": r.get("REPORT_DATE_NAME", ""),
            "charts": [{"name": "资产负债率%", "color": "#d97706", "points": annual}], "stale": False}

def get_trend_idebt():
    rows = em_fin("600079.SH")
    r = _find(rows, "2025年报") or {}
    pts = [{"d": t["d"], "v": t["v"]} for t in _series(rows, "INTEREST_DEBT_RATIO")]
    annual = [p for p in pts if "年报" in p["d"]]
    return {"latest": round(r.get("INTEREST_DEBT_RATIO"), 1) if r.get("INTEREST_DEBT_RATIO") is not None else None,
            "latest_date": r.get("REPORT_DATE_NAME", ""),
            "charts": [{"name": "有息负债率%", "color": "#dc2626", "points": annual}], "stale": False}

# ========== 最新一期快照 ==========
def get_snap():
    rows = em_fin("600079.SH")
    r = rows[0] if rows else {}  # 最新一期(倒序=第一)
    nm = r.get("REPORT_DATE_NAME", "")
    return {"report": nm,
            "rev": round(r.get("TOTALOPERATEREVE", 0)/1e8, 1),
            "rev_yoy": r.get("TOTALOPERATEREVETZ"),
            "np": round(r.get("PARENTNETPROFIT", 0)/1e8, 1),
            "np_yoy": r.get("PARENTNETPROFITTZ"),
            "roe": r.get("ROEJQ"), "debt": round(r.get("ZCFZL", 0), 1),
            "idebt": round(r.get("INTEREST_DEBT_RATIO", 0), 1) if r.get("INTEREST_DEBT_RATIO") is not None else None,
            "stale": False}

# ========== 费用结构占比（最新一期 + 两年对比） ==========
def get_cost_struct():
    rows = em_stmt("600079.SH", "RPT_F10_FINANCE_GINCOME")
    cur = rows[0] if rows else {}   # 最新一期
    prev = _find(rows, "2025年报") or rows[1] if len(rows) > 1 else {}
    def ratio(r, k, inc):
        return round(r.get(k, 0)/inc*100, 1) if r.get(k) and inc else None
    inc_cur = cur.get("TOTAL_OPERATE_INCOME") or 1
    return {"report": cur.get("REPORT_DATE_NAME", ""),
            "sale": ratio(cur, "SALE_EXPENSE", inc_cur),
            "manage": ratio(cur, "MANAGE_EXPENSE", inc_cur),
            "research": ratio(cur, "RESEARCH_EXPENSE", inc_cur),
            "finance": ratio(cur, "FINANCE_EXPENSE", inc_cur),
            "oper_cost": ratio(cur, "OPERATE_COST", inc_cur),
            "prev_report": prev.get("REPORT_DATE_NAME", ""),
            "prev_sale": ratio(prev, "SALE_EXPENSE", (prev.get("TOTAL_OPERATE_INCOME") or 1)) if prev else None,
            "prev_manage": ratio(prev, "MANAGE_EXPENSE", (prev.get("TOTAL_OPERATE_INCOME") or 1)) if prev else None,
            "prev_research": ratio(prev, "RESEARCH_EXPENSE", (prev.get("TOTAL_OPERATE_INCOME") or 1)) if prev else None,
            "prev_finance": ratio(prev, "FINANCE_EXPENSE", (prev.get("TOTAL_OPERATE_INCOME") or 1)) if prev else None,
            "stale": False}

# ========== 降本贡献度拆解（2026中报 vs 2025中报） ==========
def get_contrib_breakdown():
    rows = em_stmt("600079.SH", "RPT_F10_FINANCE_GINCOME")
    rm = {r.get("REPORT_DATE_NAME"): r for r in rows}
    cur = rm.get("2026中报") or {}; prev = rm.get("2025中报") or {}
    def b(k):
        c, p = cur.get(k), prev.get(k)
        if c is None or p is None: return None
        return float(c)/1e8, float(p)/1e8
    def v(k):
        x = b(k)
        return x if x else (0, 0)
    np_c, np_p = v("PARENT_NETPROFIT")
    np_delta = np_c - np_p
    items = []
    def add(label, key, kind):
        x = b(key)
        if x is None: return
        c, p = x; delta = c - p
        pc = -delta if kind in ("cost", "expense") else delta  # 成本/费用降=+贡献
        pct = pc / np_delta * 100 if np_delta else 0
        items.append({"label": label, "delta": round(delta, 2), "pc": round(pc, 2), "pct": round(pct, 0)})
    add("营业成本", "OPERATE_COST", "cost")
    add("销售费用", "SALE_EXPENSE", "expense")
    add("管理费用", "MANAGE_EXPENSE", "expense")
    add("研发费用", "RESEARCH_EXPENSE", "expense")
    add("财务费用", "FINANCE_EXPENSE", "expense")
    cost_total = sum(i["pc"] for i in items if i["pc"] > 0)
    exp_total = sum(abs(i["pc"]) for i in items if i["pc"] < 0)
    return {"report": cur.get("REPORT_DATE_NAME", ""), "prev_report": prev.get("REPORT_DATE_NAME", ""),
            "np_c": round(np_c, 2), "np_p": round(np_p, 2), "np_delta": round(np_delta, 2),
            "np_pct": round(np_delta / np_p * 100, 2) if np_p else 0,
            "items": items, "cost_total": round(cost_total, 2), "exp_total": round(exp_total, 2),
            "stale": False}

# ========== 财务费用年度趋势（去杠杆红利验证） ==========
def get_trend_fin_exp():
    rows = em_stmt("600079.SH", "RPT_F10_FINANCE_GINCOME")
    pts = [{"d": t["d"], "v": t["v"]} for t in _series(rows, "FINANCE_EXPENSE", scale=1e8)]
    annual = [p for p in pts if "年报" in p["d"]]
    return {"latest": annual[-1]["v"] if annual else None,
            "latest_date": annual[-1]["d"] if annual else "",
            "charts": [{"name": "财务费用(亿)", "color": "#7c3aed", "points": annual}], "stale": False}

def get_trend_idebt_fin():
    fin = em_stmt("600079.SH", "RPT_F10_FINANCE_GINCOME")
    rows = em_fin("600079.SH")
    # 年度有息负债率
    idebt = [{"d": t["d"], "v": t["v"]} for t in _series(rows, "INTEREST_DEBT_RATIO")]
    idebt_annual = [p for p in idebt if "年报" in p["d"]]
    finpts = [{"d": t["d"], "v": t["v"]} for t in _series(fin, "FINANCE_EXPENSE", scale=1e8)]
    fin_annual = [p for p in finpts if "年报" in p["d"]]
    return {"latest": idebt_annual[-1]["v"] if idebt_annual else None,
            "latest_date": idebt_annual[-1]["d"] if idebt_annual else "",
            "charts": [
                {"name": "有息负债率%", "color": "#dc2626", "points": idebt_annual},
                {"name": "财务费用(亿)", "color": "#7c3aed", "points": fin_annual}],
            "stale": False}

GETTER_MAP = {
    "snap": get_snap,
    "trend_rev": get_trend_rev, "trend_roe": get_trend_roe,
    "trend_debt": get_trend_debt, "trend_idebt": get_trend_idebt,
    "cost_struct": get_cost_struct, "trend_fin_exp": get_trend_fin_exp,
    "trend_idebt_fin": get_trend_idebt_fin,
    "contrib_breakdown": get_contrib_breakdown,
}

def fetch_all():
    import urllib.request  # noqa
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    prev = None
    if os.path.exists(DATA_PATH):
        try: prev = json.load(open(DATA_PATH, encoding="utf-8"))
        except Exception: prev = None
    prev_map = {i["id"]: i for i in (prev["indicators"] if prev else [])}
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
                    rec["last_good"] = old.get("last_good"); rec["last_good_at"] = old.get("last_good_at")
                rec["value"] = None; rec["status"] = "failed"; rec["error"] = str(e)[:120]
        else:
            rec["status"] = "pending"; rec["note"] = "待接入"
        rec["fetched_at"] = now
        out["indicators"].append(rec)
    with open(DATA_PATH, "w") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("saved", DATA_PATH)
    return out

if __name__ == "__main__":
    from indicators import INDICATORS
    fetch_all()
