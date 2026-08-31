# -*- coding: utf-8 -*-
"""
白电三巨头(美的000333 / 海尔600690 / 格力000651) 监测看板 —— 取数层
=====================================================================
fetch.py 循环 3 家公司取数。**取数工具复用 dashboard-style/scripts/dashboard_shared.py**
(共享财务序列/行情/K线/分红工具), 不再各自复制。数据统一走 data-source-router。

新增 ROIC(经济性核心, 复用 stock-analysis/scripts/roic.py 同名逻辑内嵌简版):
  - market 隐含回报 = ROE/PB (市场给的质量溢价)
  - ROIC = NOPAT/投入资本

数据正确性铁律：只从东财+腾讯自动取数，绝不 hardcode；同比重算不信任东财 XXTZ 字段。
"""
import json, os, sys, time, datetime

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

# 定位 dashboard-style 共享库（向上找到 dashboard-style/scripts）
def _shared_dir():
    d = os.path.dirname(os.path.abspath(__file__))
    for _ in range(8):
        if os.path.isdir(os.path.join(d, "dashboard-style", "scripts")):
            return os.path.join(d, "dashboard-style", "scripts")
        d = os.path.dirname(d)
    return os.path.join(os.environ.get("ZACH_SKILLS", "/root/zach-skills"), "dashboard-style", "scripts")
sys.path.insert(0, _shared_dir())

import dashboard_shared as DSH
from dashboard_shared import em_fin, em_stmt, _find, stock_quote, market_position, annual_dividend

CACHE = os.path.join(BASE, "cache"); os.makedirs(CACHE, exist_ok=True)
DATA_PATH = os.path.join(CACHE, "dashboard_data.json")

COMPANIES = [
    {"name": "美的集团", "code": "000333", "secu": "000333.SZ", "tq": "sz000333"},
    {"name": "海尔智家", "code": "600690", "secu": "600690.SH", "tq": "sh600690"},
    {"name": "格力电器", "code": "000651", "secu": "000651.SZ", "tq": "sz000651"},
]


# ---------- 财务快照（最新一期） ----------
def financial_snapshot(c):
    rows = em_fin(c["secu"])
    cur = _find(rows, "2026中报") or _find(rows, "2026一季报") or (rows[0] if rows else {})
    np_yoy = DSH._self_yoy(rows, "PARENTNETPROFIT").get(cur.get("REPORT_DATE_NAME", ""))
    rev = cur.get("TOTALOPERATEREVE"); np_ = cur.get("PARENTNETPROFIT")
    return {"report": cur.get("REPORT_DATE_NAME", "获取失败"), "stale": False,
            "rev": round(rev / 1e8, 1) if rev else None,
            "np": round(np_ / 1e8, 1) if np_ else None, "np_yoy": np_yoy,
            "roe": round(cur["ROEJQ"], 2) if isinstance(cur.get("ROEJQ"), (int, float)) else None,
            "gm": round(cur["XSMLL"], 2) if isinstance(cur.get("XSMLL"), (int, float)) else None,
            "nm": round(cur["XSJLL"], 2) if isinstance(cur.get("XSJLL"), (int, float)) else None,
            "debt": round(cur["ZCFZL"], 1) if isinstance(cur.get("ZCFZL"), (int, float)) else None,
            "idebt": round(cur["INTEREST_DEBT_RATIO"], 1) if isinstance(cur.get("INTEREST_DEBT_RATIO"), (int, float)) else None,
            "opcf": round(cur["MGJYXJJE"], 2) if isinstance(cur.get("MGJYXJJE"), (int, float)) else None}


# ---------- 年度走势（营收/ROE/净利率 三线 for 三家对比） ----------
def annual_trends(c):
    rows = em_fin(c["secu"])
    return {"stale": False,
            "charts": [
                {"name": "营收(亿)", "color": "#2563eb", "points": DSH._series_of(rows, "TOTALOPERATEREVE", 1e8)[-6:]},
                {"name": "ROE%", "color": "#16a34a", "points": DSH._series_of(rows, "ROEJQ")[-6:]},
                {"name": "净利率%", "color": "#7c3aed", "points": DSH._series_of(rows, "XSJLL")[-6:]},
            ]}


# ---------- 行情 + 市场位置 ----------
def get_position(c):
    try:
        return market_position(c["tq"])
    except Exception as e:
        return {"stale": True, "error": f"K线失败 {str(e)[:80]}"}


# ---------- 分红 ----------
def dividend(c):
    try:
        d = annual_dividend(c["secu"])
        px = stock_quote(c["tq"]).get("price")
        if d.get("d10") and px:
            d["yield"] = round(d["d10"] / 10 / px * 100, 2)
        else:
            d["yield"] = None
        return d
    except Exception as e:
        return {"stale": True, "error": f"分红失败 {str(e)[:80]}"}


# ---------- ROIC + 估值性价比 ----------
def roic_of(c):
    """复用财务序列算 ROIC = NOPAT/投入资本；ROE=归母/净资产。"""
    bal = em_stmt(c["secu"], "RPT_F10_FINANCE_GBALANCE")
    inc = em_stmt(c["secu"], "RPT_F10_FINANCE_GINCOME")
    for period in ["2025年报", "2026中报"]:
        b = _find(bal, period); i = _find(inc, period)
        if not b or not i: continue
        Y = 1e8
        eq = b.get("TOTAL_EQUITY")
        if not isinstance(eq, (int, float)): continue
        debt = sum(b.get(k, 0) for k in ["SHORT_LOAN", "NONCURRENT_LIABILITIES_1YEAR", "LONG_LOAN", "BOND_PAYABLE"] if isinstance(b.get(k), (int, float)))
        invested = eq + debt
        op = i.get("OPERATE_PROFIT"); tax = i.get("INCOME_TAX"); tp = i.get("TOTAL_PROFIT")
        if not all(isinstance(v, (int, float)) for v in [op, tax, tp]) or tp == 0: continue
        nopat = op * (1 - tax / tp)
        peq = b.get("TOTAL_PARENT_EQUITY"); np_ = i.get("PARENT_NETPROFIT")
        roe = np_ / peq * 100 if (isinstance(peq, (int, float)) and peq and isinstance(np_, (int, float))) else None
        return {"period": period, "roic": round(nopat / invested * 100, 1) if invested else None, "roe": round(roe, 1) if roe else None}
    return {"period": None, "roic": None, "roe": None}


def valuation(c, snap):
    q = stock_quote(c["tq"])
    roe = snap.get("roe"); pb = q.get("pb")
    imp = round(roe / pb, 2) if roe and pb else None
    fair_pb_r10 = roe / 10 if roe else None
    fair_px = None
    if fair_pb_r10 and pb and q.get("price"):
        fair_px = round(fair_pb_r10 * q["price"] / pb, 2)
    roic = roic_of(c)
    return {"stale": False, "pe": q.get("pe"), "pb": pb, "implied_r": imp,
            "fair_px_r10": fair_px, "roic": roic.get("roic"), "roic_period": roic.get("period")}


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
        rec = {"name": c["name"], "code": c["code"], "tq": c["tq"], "secu": c["secu"],
               "sets": {}, "fetched_at": now}
        for setname, fn in [("financial", lambda: financial_snapshot(c)),
                            ("trends", lambda: annual_trends(c)),
                            ("quote", lambda: stock_quote(c["tq"])),
                            ("position", lambda: get_position(c)),
                            ("dividend", lambda: dividend(c))]:
            try:
                rec["sets"][setname] = fn(); rec["sets"][setname]["status"] = "ok"
            except Exception as e:
                old = pc.get("sets", {}).get(setname, {}) if isinstance(pc, dict) else {}
                rec["sets"][setname] = {"status": "failed", "error": str(e)[:120]}
        try:
            val = valuation(c, rec["sets"].get("financial") or {})
            rec["sets"]["valuation"] = val; val["status"] = "ok"
        except Exception as e:
            rec["sets"]["valuation"] = {"status": "failed", "error": str(e)[:80]}
        out["companies"].append(rec)
        f = rec["sets"].get("financial", {}); q_ = rec["sets"].get("quote", {}); va = rec["sets"].get("valuation", {})
        print(f"  {c['name']}: 期={f.get('report')} 营收={f.get('rev')}亿 归母={f.get('np')}亿 "
              f"现价={q_.get('price')} PE={q_.get('pe')} 股息={(rec['sets'].get('dividend') or {}).get('yield')}% "
              f"ROIC={va.get('roic')}%")
        time.sleep(0.4)

    with open(DATA_PATH, "w") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("saved", DATA_PATH)
    return out

if __name__ == "__main__":
    fetch_all()