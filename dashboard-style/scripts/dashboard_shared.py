# -*- coding: utf-8 -*-
"""
dashboard-style 共享工具库 —— 各行业/个股看板复用（消除跨看板重复）
====================================================================
所有看板实例(cement/etf/renfu/whitegoods)共用的：
  1. trend_svg()        多线 SVG 趋势图 + 图例（自包含，可挂 Astro 博客）
  2. 财务序列处理       _find/_year_rows/_series_of/_self_yoy
  3. esc/fnum/pct        HTML 转义 + 数字格式化
  4. 取数入口调 router  em_fin(经 cn_financial_series) / 股息(经 cn_stock_dividend)
                      / 行情(经 cn_stock_quote) / K线位置(基于 cn_stock_kline)

设计（2026-08 定稿，消除重复）：
  - **取数统一走 data-source-router.get()**，本库不直连东财/腾讯（router 是唯一取数入口，
    含缓存/重试/Tier；直连逻辑全部下沉在 router adapters）。
  - market_position 是基于 kline 数据算的 derivative 算法（52周位置/回撤/动量），
    属于「渲染前处理」，留在本库；它从 router 拿 kline 原始数据后再算。

数据正确性铁律（用户强要求）仅在共享层实现一次：
  - 正确性 > 及时性；远程失败诚实标 failed+error，绝不拿旧值冒充当前值。
"""
import json, os, sys, time, html, urllib.request

# ---------- HTML 格式化 ----------
def esc(x):
    return html.escape(str(x)) if x is not None else "—"

def fnum(x, nd=1):
    return f"{x:,.{nd}f}" if isinstance(x, (int, float)) else "—"

def pct(x, nd=1):
    if x is None: return "—"
    return f"{x:,.{nd}f}%"


# ---------- 共享趋势图 ----------
def trend_svg(charts, w=640, h=120):
    """charts=[{name,color,points:[{d,v}]}] → 共用 x 轴(日期升序, 按字符串排序)的多线 SVG + 图例。

    - 各线 points 的 d 需同一年份序列(如都含 '2023年报')，否则按并集 xd 对齐(缺点多就画短线)。
    - 返回自包含 SVG 字符串；少于2点回空串。
    """
    if not charts:
        return ""
    pts = [(str(p["d"]), float(p["v"])) for ch in charts for p in ch.get("points", []) if p.get("v") is not None]
    if len(pts) < 2:
        return ""
    xd = sorted(set(d for d, _ in pts))   # 并集 x 轴(升序)
    mn = min(v for _, v in pts); mx = max(v for _, v in pts); yspan = (mx - mn) or 1
    pad = 8; n = max(1, len(xd) - 1)
    X = lambda i: pad + i / n * (w - 2 * pad)
    Y = lambda v: h - 14 - (v - mn) / yspan * (h - 28)
    svg = f'<svg viewBox="0 0 {w} {h}" width="100%" height="{h}" preserveAspectRatio="none" class="tsvg">'
    svg += f'<line x1="{pad}" y1="{Y(mn):.1f}" x2="{w-pad}" y2="{Y(mn):.1f}" stroke="#eef1f4"/>'
    svg += f'<line x1="{pad}" y1="{Y(mx):.1f}" x2="{w-pad}" y2="{Y(mx):.1f}" stroke="#eef1f4"/>'
    for ch in charts:
        coords = []
        for p in ch.get("points", []):
            if p.get("v") is None: continue
            d = str(p["d"])
            if d in xd:
                idx = xd.index(d)
                coords.append(f"{X(idx):.1f},{Y(float(p['v'])):.1f}")
        if coords:
            svg += f'<polyline points="{" ".join(coords)}" fill="none" stroke="{ch.get("color","#2563eb")}" stroke-width="2"/>'
            lx, ly = coords[-1].split(",")
            svg += f'<circle cx="{lx}" cy="{ly}" r="3" fill="{ch.get("color","#2563eb")}"/>'
    if len(xd) >= 2:
        svg += f'<text x="{pad}" y="{h-2}" font-size="9" fill="#9ca3af">{esc(xd[0])}</text>'
        svg += f'<text x="{w-pad}" y="{h-2}" font-size="9" fill="#9ca3af" text-anchor="end">{esc(xd[-1])}</text>'
    svg += "</svg>"
    if len(charts) > 1:
        leg = '<div class="chleg">' + "".join(
            f'<span><span class="cl" style="background:{ch.get("color","#2563eb")}"></span>{esc(ch.get("name"))}</span>'
            for ch in charts) + '</div>'
        return svg + leg
    return svg


# ---------- 路径定位 + router 单例 ----------
def _zach_root():
    """自动定位 zach-skills 根（含 data-source-router），迁移可用。"""
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
    DSR = None
    _HAS_DSR = False
    print(f"[warn] data-source-router 未就绪({e})，共享库取数不可用")


def _router_get(kind, **params):
    """统一取数入口。DSR 不可用抛异常（调用方 catch）。"""
    if DSR is None:
        raise RuntimeError("data-source-router 不可用")
    d, _s, _m, _t = DSR.get(kind, **params)
    return d


# ---------- 财务取数（统一走 router） ----------
def em_fin(secucode, report="RPT_F10_FINANCE_MAINFINADATA", page=40):
    """主财务序列(含 INTEREST_DEBT_RATIO 有息负债率)。经 router cn_financial_series。"""
    rows = _router_get("cn_financial_series", secucode=secucode, report_name=report, page=page)
    return rows if isinstance(rows, list) else []

def em_stmt(secucode, report, page=60):
    return em_fin(secucode, report, page)

def stock_quote(symbol):
    """现价/PE/PB/市值。经 router cn_stock_quote。symbol=sh600519/sz000333。"""
    q = _router_get("cn_stock_quote", symbol=symbol)
    return q if isinstance(q, dict) else {}

def cn_kline(symbol, count=120):
    """前复权日K({date,open,close,high,low,volume}[])。经 router cn_stock_kline。"""
    rows = _router_get("cn_stock_kline", symbol=symbol, count=count)
    return rows if isinstance(rows, list) else []

def stock_dividend(secucode, page=12):
    """分红原始 rows(每10股税前派息)。经 router cn_stock_dividend。"""
    rows = _router_get("cn_stock_dividend", secucode=secucode, page=page)
    return rows if isinstance(rows, list) else []


# ---------- 财务序列工具 ----------
def _find(rows, name):
    for r in rows:
        if r.get("REPORT_DATE_NAME") == name:
            return r
    return None

def _year_rows(rows):
    return [r for r in rows if r.get("REPORT_DATE_NAME") and "年报" in r.get("REPORT_DATE_NAME")]

def _series_of(rows, key, scale=1.0):
    """把「年报」序列转成 {d(报告期名), v(value)} 按年份升序；允许 scale 换算单位。"""
    out = []
    for r in _year_rows(rows):
        v = r.get(key)
        if v is None: continue
        nm = r.get("REPORT_DATE_NAME", "")
        out.append({"d": nm, "v": round(v / scale, 2) if scale != 1 else round(v, 2)})
    out.sort(key=lambda x: x["d"])
    return out

def _self_yoy(rows, key="PARENTNETPROFIT", periods=None):
    """按「同报告期累计值 vs 去年同期」重算同比(不信任东财 XXTZ 字段有 bug)。返回 {报告期名: yoy%}。"""
    if periods is None:
        periods = ("2026中报", "2025中报", "2026一季报", "2025一季报", "2026年报", "2025年报")
    out = {}
    for r in rows:
        d = str(r.get("REPORT_DATE", ""))[:10]
        nm = r.get("REPORT_DATE_NAME", "")
        if not d or nm not in periods:
            continue
        y, mm = int(d[:4]), int(d[5:7])
        for r2 in rows:
            d2 = str(r2.get("REPORT_DATE", ""))[:10]
            if d2 and int(d2[:4]) == y - 1 and int(d2[5:7]) == mm:
                c, p = r.get(key), r2.get(key)
                if c is not None and p:
                    out[nm] = round((c - p) / p * 100, 1)
                break
    return out


# ---------- 市场位置（基于 cn_stock_kline 的 derivative 算法，保留在渲染层） ----------
def market_position(symbol, window=400):
    """腾讯前复权K线(经 router) → 52周区间位置 + 最大回撤 + 近一年涨跌。"""
    d = cn_kline(symbol, window)
    if not isinstance(d, list) or len(d) < 2:
        return {"stale": True, "error": "K线数据不足"}
    kl = [(str(r.get("date")), float(r.get("close"))) for r in d if r.get("close") is not None]
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
    return {"stale": False, "pos52": round(pos52, 1), "maxdd": round(maxdd, 1),
            "mdd_date": mdd_date, "ret1y": round((px / y_ago - 1) * 100, 1)}


# ---------- 分红年度口径（基于 cn_stock_dividend 的 derivative） ----------
def annual_dividend(secucode, years=("2025", "2024", "2023", "2022", "2021")):
    """返回 {'years':[{year,d10}], 'latest_year', 'd10'}：取最近年报(12-31期)派息为股息率基准。
    绝不取最近一期(中报预案)——否则像美的会算错股息率。"""
    rows = stock_dividend(secucode)
    annual = [r for r in rows if str(r.get("REPORT_DATE", "")).endswith("12-31 00:00:00") and r.get("PRETAX_BONUS_RMB")]
    seen = {}
    for r in annual:
        yr = str(r.get("REPORT_DATE", ""))[:4]
        if yr not in seen:
            seen[yr] = r
    latest = next((v for v in [seen.get(y) for y in years if y in seen] if v), None)
    out_years = [{"year": y, "d10": seen[y].get("PRETAX_BONUS_RMB")} for y in years if y in seen]
    return {"years": out_years,
            "latest_year": str(latest.get("REPORT_DATE", ""))[:4] if latest else None,
            "d10": latest.get("PRETAX_BONUS_RMB") if latest else None}