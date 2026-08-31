# -*- coding: utf-8 -*-
"""
取数脚本：拉取人福药业(600079)四大财务走势 + 降本拆解 → cache/dashboard_data.json
设计：远程优先(东财 datacenter 免费公开源) + 失败诚实(stale 标记) + 每指标带 fetched_at/source 溯源。
正确性 > 及时性；绝不拿旧值冒充当前值。

⚠️ 数据正确性关键点：
  - 营收同比(NP/REV 同比)一律按「同报告期累计值」重算，不信任东财 TOTALOPERATEREVETZ(有 bug)。
  - 所有数值只来自东财 datacenter 自动取数，禁止 hardcode 明细。
  - 统一走 data-source-router.get('cn_financial_series')，DSR 不可用才直连兜底。
"""
import json, os, sys, time, datetime

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "scripts"))

# 复用 dashboard-style 共享工具库（_find/_year_rows/_series_of/_get 同构，消除跨看板重复）
def _ds_dir():
    d = os.path.dirname(os.path.abspath(__file__))
    for _ in range(8):
        if os.path.isdir(os.path.join(d, "dashboard-style", "scripts")):
            return os.path.join(d, "dashboard-style", "scripts")
        d = os.path.dirname(d)
    return os.path.join(os.environ.get("ZACH_SKILLS", "/root/zach-skills"), "dashboard-style", "scripts")
sys.path.insert(0, _ds_dir())
from dashboard_shared import _find, _year_rows, _series_of, _get  # noqa: E402

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

def _get(url, headers=UA, timeout=35, retry=2):
    import urllib.request
    last = None
    for i in range(retry):
        try:
            req = urllib.request.Request(url, headers=headers)
            return json.loads(urllib.request.urlopen(req, timeout=timeout).read().decode())
        except Exception as e:
            last = e; time.sleep(1.2)
    raise last

# ---------- 东财取数（统一走 router） ----------
def em_fin(secucode, report_arg="RPT_F10_FINANCE_MAINFINADATA", page=40):
    """主财务序列(含 INTEREST_DEBT_RATIO 有息负债率)。优先走 router；DSR 不可用才直连。"""
    if _HAS_DSR:
        d, _s, _m, _t = DSR.get("cn_financial_series", secucode=secucode,
                                 report_name=report_arg, page=page)
        if isinstance(d, list):
            return d
    url = ("https://datacenter.eastmoney.com/securities/api/data/v1/get?reportName=" + report_arg + "&columns=ALL"
           f"&filter=(SECUCODE%3D%22{secucode}%22)&pageNumber=1&pageSize={page}&sortTypes=-1&sortColumns=REPORT_DATE")
    return _get(url)["result"]["data"]

def em_fin_direct(secucode, report_arg, page=40):
    return em_fin(secucode, report_arg, page)

# ---------- 工具 ----------
# _find/_year_rows/_series_of/_get 复用 dashboard-style 共享库(dashboard_shared)，不在此重复定义
def _rev_yoy_by_self(rows):
    """按同报告期累计值重算营收同比。返回 {报告期名: yoy%}。"""
    by_period = {}
    for r in rows:
        d = str(r.get("REPORT_DATE"))[:10]          # YYYY-MM-DD
        pname = r.get("REPORT_DATE_NAME") or ""
        by_period.setdefault(lag_key(pname), (r, d))
    out = {}
    for pname, (cur, d) in by_period.items():
        y, mm = int(d[:4]), int(d[5:7])
        # 找去年同 month 段
        lag = None
        for pname2, (r2, d2) in by_period.items():
            if int(d2[:4]) == y - 1 and int(d2[5:7]) == mm:
                lag = r2; break
        rev_c = cur.get("TOTALOPERATEREVE")
        if lag is None or rev_c is None: continue
        rev_l = lag.get("TOTALOPERATEREVE")
        if not rev_l: continue
        out[cur.get("REPORT_DATE_NAME")] = round((rev_c - rev_l) / rev_l * 100, 1)
    return out

def lag_key(name):
    return name  # 占位：用 REPORT_DATE_NAME 做 key(去重)

def _series_of(rows, key, scale=1):
    """把「年报」序列转成 {d(report期名), v(value)}，按年份升序。scale 统一换算单位。"""
    out = []
    for r in _year_rows(rows):
        v = r.get(key)
        if v is None: continue
        nm = r.get("REPORT_DATE_NAME", "")
        out.append({"d": nm, "v": round(v / scale, 2) if scale != 1 else round(v, 2)})
    # 东财返回是报告期倒序(最新在前)；按报告期名里的年份升序，确保 [-1]=最新
    out.sort(key=lambda x: x["d"])
    return out

# ========== 快照（最新一期） ==========
def get_snap():
    rows = em_fin("600079.SH")
    r = rows[0] if rows else {}   # 最新一期(倒序=第一)
    yoy_map = _rev_yoy_by_self(rows)
    nm = r.get("REPORT_DATE_NAME", "")
    rev = r.get("TOTALOPERATEREVE")
    np_ = r.get("PARENTNETPROFIT")
    # 归母净利同比也重算
    np_yoy = None
    d = str(r.get("REPORT_DATE"))[:10]; y, mm = int(d[:4]), int(d[5:7])
    for r2 in rows:
        d2 = str(r2.get("REPORT_DATE"))[:10]
        if int(d2[:4]) == y - 1 and int(d2[5:7]) == mm:
            np_l = r2.get("PARENTNETPROFIT")
            if np_ is not None and np_l:
                np_yoy = round((np_ - np_l) / np_l * 100, 1)
            break
    rev_yoy = yoy_map.get(nm)
    return {"report": nm,
            "rev": round(rev / 1e8, 1) if rev else None,
            "rev_yoy": rev_yoy,
            "np": round(np_ / 1e8, 1) if np_ else None,
            "np_yoy": np_yoy,
            "roe": r.get("ROEJQ"),
            "debt": round(r.get("ZCFZL"), 1) if r.get("ZCFZL") is not None else None,
            "idebt": round(r.get("INTEREST_DEBT_RATIO"), 1) if r.get("INTEREST_DEBT_RATIO") is not None else None,
            "stale": False}

# ========== 四大财务走势（年度） ==========
def get_trend_rev():
    rows = em_fin("600079.SH")
    r = _find(rows, "2025年报") or rows[0] or {}
    annual = _series_of(rows, "TOTALOPERATEREVE", scale=1e8)
    return {"latest": round((r.get("TOTALOPERATEREVE") or 0) / 1e8, 1),
            "latest_date": r.get("REPORT_DATE_NAME", ""),
            "charts": [{"name": "营收(亿)", "color": "#2563eb", "points": annual}], "stale": False}

def get_trend_roe():
    rows = em_fin("600079.SH")
    r = _find(rows, "2025年报") or rows[0] or {}
    annual = _series_of(rows, "ROEJQ")
    return {"latest": r.get("ROEJQ"), "latest_date": r.get("REPORT_DATE_NAME", ""),
            "charts": [{"name": "ROE%", "color": "#16a34a", "points": annual}], "stale": False}

def get_trend_debt():
    rows = em_fin("600079.SH")
    r = _find(rows, "2025年报") or rows[0] or {}
    annual = _series_of(rows, "ZCFZL")
    return {"latest": round(r.get("ZCFZL"), 1) if r.get("ZCFZL") is not None else None,
            "latest_date": r.get("REPORT_DATE_NAME", ""),
            "charts": [{"name": "资产负债率%", "color": "#d97706", "points": annual}], "stale": False}

def get_trend_idebt():
    rows = em_fin("600079.SH")
    r = _find(rows, "2025年报") or rows[0] or {}
    annual = _series_of(rows, "INTEREST_DEBT_RATIO")
    return {"latest": round(r.get("INTEREST_DEBT_RATIO"), 1) if r.get("INTEREST_DEBT_RATIO") is not None else None,
            "latest_date": r.get("REPORT_DATE_NAME", ""),
            "charts": [{"name": "有息负债率%", "color": "#dc2626", "points": annual}], "stale": False}

# ========== 费用结构占比（最新一期 + 去年年报） ==========
def get_cost_struct():
    rows = em_stmt("600079.SH", "RPT_F10_FINANCE_GINCOME", page=60)
    cur = rows[0] if rows else {}
    prev = _find(rows, "2025年报") or (rows[1] if len(rows) > 1 else {})
    def ratio(r, k, inc):
        return round(r.get(k, 0) / inc * 100, 1) if r.get(k) and inc else None
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

def em_stmt(secucode, report_arg, page=60):
    return em_fin(secucode, report_arg, page)

# ========== 财务费用年度趋势（去杠杆红利验证） ==========
def get_trend_fin_exp():
    rows = em_stmt("600079.SH", "RPT_F10_FINANCE_GINCOME", page=80)
    annual = _series_of(rows, "FINANCE_EXPENSE", scale=1e8)
    # 只保留近5年年报(2021-2025)，与双线验证一致，聚焦去杠杆红利
    annual = annual[-5:]
    latest = annual[-1]["v"] if annual else None
    ldate = annual[-1]["d"] if annual else ""
    return {"latest": latest, "latest_date": ldate,
            "charts": [{"name": "财务费用(亿)", "color": "#7c3aed", "points": annual}], "stale": False}

# ========== 有息负债率 vs 财务费用双线 ==========
def get_trend_idebt_fin():
    fin = em_stmt("600079.SH", "RPT_F10_FINANCE_GINCOME", page=80)
    rows = em_fin("600079.SH")
    idebt_annual = _series_of(rows, "INTEREST_DEBT_RATIO")
    fin_annual = _series_of(fin, "FINANCE_EXPENSE", scale=1e8)
    # 近五年：只保留最后 5 个年报点（2021-2025），让去杠杆红利在最近5期看更聚焦
    idebt_annual = idebt_annual[-5:]
    fin_annual = fin_annual[-5:]
    return {"latest": idebt_annual[-1]["v"] if idebt_annual else None,
            "latest_date": idebt_annual[-1]["d"] if idebt_annual else "",
            "charts": [
                {"name": "有息负债率%", "color": "#dc2626", "points": idebt_annual},
                {"name": "财务费用(亿)", "color": "#7c3aed", "points": fin_annual}],
            "stale": False}

# ========== 降本贡献度拆解（2026中报 vs 2025中报） ==========
def get_contrib_breakdown():
    rows = em_stmt("600079.SH", "RPT_F10_FINANCE_GINCOME", page=80)
    rm = {r.get("REPORT_DATE_NAME"): r for r in rows}
    cur = rm.get("2026中报") or {}; prev = rm.get("2025中报") or {}
    def b(k):
        c, p = cur.get(k), prev.get(k)
        if c is None or p is None: return None
        return float(c) / 1e8, float(p) / 1e8
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
        pc = -delta if kind in ("cost", "expense") else delta   # 成本/费用降=+贡献
        pct = pc / np_delta * 100 if np_delta else 0
        items.append({"label": label, "delta": round(delta, 2), "pc": round(pc, 2), "pct": round(pct, 0)})
    add("营业成本", "OPERATE_COST", "cost")
    add("销售费用", "SALE_EXPENSE", "expense")
    add("管理费用", "MANAGE_EXPENSE", "expense")
    add("研发费用", "RESEARCH_EXPENSE", "expense")
    add("财务费用", "FINANCE_EXPENSE", "expense")
    cost_total = sum(i["pc"] for i in items if i["pc"] > 0)   # 降本/费用下降=正贡献
    issue_total = sum(abs(i["pc"]) for i in items if i["pc"] < 0)  # 费用上升=负贡献
    return {"report": cur.get("REPORT_DATE_NAME", ""), "prev_report": prev.get("REPORT_DATE_NAME", ""),
            "np_c": round(np_c, 2), "np_p": round(np_p, 2), "np_delta": round(np_delta, 2),
            "np_pct": round(np_delta / np_p * 100, 2) if np_p else 0,
            "items": items, "cost_total": round(cost_total, 2), "issue_total": round(issue_total, 2),
            "stale": False}

GETTER_MAP = {
    "snap": get_snap,
    "trend_rev": get_trend_rev, "trend_roe": get_trend_roe,
    "trend_debt": get_trend_debt, "trend_idebt": get_trend_idebt,
    "cost_struct": get_cost_struct,
    "trend_fin_exp": get_trend_fin_exp,
    "trend_idebt_fin": get_trend_idebt_fin,
    "contrib_breakdown": get_contrib_breakdown,
}

def fetch_all():
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
    for ind in out["indicators"]:
        v = ind.get("value") or {}
        disp = v.get("latest") if isinstance(v, dict) else None
        if disp is None and ind["id"] == "snap_rev": disp = v.get("rev")
        if disp is None and ind["id"] == "snap_np": disp = v.get("np")
        if disp is None and ind["id"] == "contrib_breakdown": disp = v.get("np_delta")
        print(f"  [{ind['status']:6s}] {ind['name']}: {disp}")
    return out

if __name__ == "__main__":
    from indicators import INDICATORS
    fetch_all()
