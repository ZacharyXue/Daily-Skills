# -*- coding: utf-8 -*-
"""
dashboard-style 共享工具库 —— 各行业/个股看板复用（消除跨看板重复）
====================================================================
所有看板实例(cement/etf/renfu/whitegoods)共用的：
  1. trend_svg()        多线 SVG 趋势图 + 图例（自包含，可挂 Astro 博客）
  2. 财务取数工具        _find/_year_rows/_series_of/_self_yoy + 东财直连
  3. esc/fnum/pct        HTML 转义 + 数字格式化

用法（在实例 render_html.py / fetch.py 顶部）：
    import sys, os
    BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, os.path.join(os.path.dirname(BASE), "scripts"))
    # 或直接定位 dashboards-index: 见下方 _shared_dir()

设计目的：
  - 数据正确性铁律仅在共享层实现一次，各看板不再各自复制。
  - 取数统一走 data-source-router（_zach_root 自动定位），DSR 不可用才直连兜底。
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


# ---------- 路径定位 ----------
def _zach_root():
    """自动定位 zach-skills 根（含 data-source-router + dashboard-style），迁移可用。"""
    d = os.path.dirname(os.path.abspath(__file__))
    for _ in range(8):
        if os.path.isdir(os.path.join(d, "data-source-router")):
            return d
        d = os.path.dirname(d)
    return os.environ.get("ZACH_SKILLS", "/root/zach-skills")

def _dsr():
    """复用单一 DSR import（防各脚本重复 sys.path 注入）。"""
    sys.path.insert(0, os.path.join(_zach_root(), "data-source-router"))
    try:
        import data_router as DSR
        return DSR, True
    except Exception:
        return None, False

DSR, _HAS_DSR = _dsr()

UA = {"User-Agent": "Mozilla/5.0", "Referer": "https://emweb.securities.eastmoney.com/"}

def _get(url, headers=UA, timeout=30, retry=3):
    last = None
    for i in range(retry):
        try:
            req = urllib.request.Request(url, headers=headers)
            return json.loads(urllib.request.urlopen(req, timeout=timeout).read().decode())
        except Exception as e:
            last = e; time.sleep(1.0)
    raise last

# ---------- 财务取数（统一走 router；兜底直连东财） ----------
def em_fin(secucode, report="RPT_F10_FINANCE_MAINFINADATA", page=40):
    """主财务序列(含 INTEREST_DEBT_RATIO 有息负债率)。优先 router；DSR 不可用才直连。"""
    if DSR is not None:
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

# ---------- 股票行情（腾讯） ----------
def stock_quote(tq):
    """腾讯实时行情。tq = sh600519/sz000333。返回 dict(price/pe/pb/mktcap/chg_pct/turnover/name)。"""
    url = f"https://qt.gtimg.cn/q={tq}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Referer": "https://gu.qq.com/"})
    text = urllib.request.urlopen(req, timeout=20).read().decode("gbk")
    body = text.split('="', 1)[1].rsplit('"', 1)[0]; f = body.split("~")
    def g(i, conv=None):
        try: return float(f[i]) if conv == float else f[i]
        except Exception: return None
    return {"name": f[1], "price": g(3, float), "chg_pct": g(32, float), "pe": g(39, float),
            "pb": g(46, float), "mktcap": g(45, float), "turnover": g(38, float)}

def market_position(tq, window=400):
    """腾讯前复权K线 → 52周区间位置 + 最大回撤 + 近一年涨跌。"""
    url = f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={tq},day,,,{window},qfq"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Referer": "https://gu.qq.com/"})
    d = json.loads(urllib.request.urlopen(req, timeout=25).read().decode("utf-8"))
    node = d["data"][tq]
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
    return {"stale": False, "pos52": round(pos52, 1), "maxdd": round(maxdd, 1),
            "mdd_date": mdd_date, "ret1y": round((px / y_ago - 1) * 100, 1)}

# ---------- 分红（年度口径，白电等「年度+中期」双分红公司必用） ----------
def annual_dividend(secucode, years=("2025", "2024", "2023", "2022", "2021")):
    """返回 {'years':[{year,d10}], 'latest_year', 'd10'}：取最近年报(12-31期)派息为股息率基准。
    绝不取最近一期(中报预案)——否则像美的会算错股息率。"""
    url = ("https://datacenter.eastmoney.com/securities/api/data/v1/get"
           "?reportName=RPT_SHAREBONUS_DET&columns=ALL"
           f"&filter=(SECUCODE%3D%22{secucode}%22)&pageNumber=1&pageSize=12&sortTypes=-1&sortColumns=REPORT_DATE")
    rows = _get(url)["result"]["data"]
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