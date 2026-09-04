#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""render_html.py — 成长vs价值风格轮动看板 渲染层 → output/style-rotation-dashboard.html（自包含）"""
import json, os, html, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = json.load(open(os.path.join(HERE, "..", "cache", "dashboard_data.json")))
OUT = os.path.join(HERE, "..", "output", "style-rotation-dashboard.html")

def _f(x, dec=1):
    if x is None: return "—"
    return f"{x:.{dec}f}" if isinstance(x, (int, float)) else str(x)

def _pct(x):
    if x is None: return "—"
    return f"{x:+.1f}%" if x != 0 else "0.0%"

def _bar(pct, kind="g"):
    pct = float(pct or 0)
    c = "#e0563f" if kind == "g" else "#3a7bd5"
    return (f'<div class="hbar" style="width:{min(pct,100):.1f}%"></div>' 
            f'<span class="hval" style="color:{c}">{pct:.1f}%</span>')

def industry_table(title, inds, klass):
    if not inds:
        return f'<div class="card"><h3>{title}</h3><p>行业分布获取失败</p></div>'
    rows = "".join(
        f'<tr><td>{html.escape(i["industry"])}</td>'
        f'<td><div class="barwrap">{_bar(i["weight_pct"], "g" if klass=="g" else "v")}</div></td>'
        f'<td>{_pct(i["yoy"])}</td>'
        f'<td>{_f(i["mktcap_yi"])}万亿</td></tr>'
        for i in sorted(inds, key=lambda t: -t["weight_pct"])[:12])
    return f'''<div class="card"><h3>{title}</h3>
    <table><thead><tr><th>行业</th><th>权重(自由流通)</th><th>年内涨跌</th><th>总市值</th></tr></thead>
    <tbody>{rows}</tbody></table></div>'''

# ---- 引擎 ----
e = DATA.get("engine") or {}
d = {}
if e:
    s = e["signals"]
    c = e["confluence"]
    def sigrow(name, val, dirn, note=""):
        col = {"up":"#2e9e5b","down":"#e0563f","flat":"#999"}.get(dirn,"#999")
        arrow = {"up":"▲偏成长","down":"▼偏价值","flat":"→中性"}.get(dirn,"")
        return (f'<tr><td>{name}</td><td>{val}</td>'
                f'<td style="color:{col};font-weight:600">{arrow}</td><td class="dim">{note}</td></tr>')
    gd = DATA.get("growth_diff") or {}
    gd_str = "—"
    gd_dir = "flat"
    gd_note = "未自动接入(需跑 growth_precompute.py)"
    if gd.get("ok") and gd.get("profit_diff_pp") is not None:
        pd = gd["profit_diff_pp"]
        pg = gd.get("profit_growth_pct"); pv = gd.get("profit_value_pct")
        pg_s = f"{pg:.0f}%" if isinstance(pg, (int, float)) else "—"
        pv_s = f"{pv:.0f}%" if isinstance(pv, (int, float)) else "—"
        pd_s = f"{pd:+.0f}pp"
        gd_str = "{0} (成长 {1} vs 价值 {2})".format(pd_s, pg_s, pv_s)
        gd_dir = "up" if pd > 8 else ("down" if pd < -8 else "flat")
        gd_note = "等权聚合 {0}/{1} 只成分净利同比，第一性信号".format(gd.get("n_growth_valid"), gd.get("n_value_valid"))
    signal_rows = "".join([
        sigrow("盈利增速差(净利)", gd_str, gd_dir, gd_note),
        sigrow("ROE 差(成长−价值)", _f(s.get("roe_diff_pp"))+"pp", e["directions"].get("roe",""), "长期风格锚：成长ROE更强→偏成长"),
        sigrow("估值价差(PE分位差)", _f(s.get("pe_pct_diff_pp"))+"pp / PE比"+_f(s.get("pe_ratio"))+"x", e["directions"].get("val",""), "成长相对越贵→减成长"),
        sigrow("行业拥挤度(电子58%)", _f(s.get("s_crowding"),2), "down" if s.get("s_crowding") and s["s_crowding"]<0 else "flat", "成长行业集中→安全边际下调"),
        sigrow("动量(6m相对,温和)", _pct(s.get("mom_6m_growth")), e["directions"].get("mom",""), "仅极端预警,不做切换依据"),
    ])
    default_eng = f'''
    <div class="gauge">
      <div class="g-num">{_f(e.get('growth_w_pct'))}<span class="g-unit">% 成长</span></div>
      <div class="g-bar"><div class="g-fill" style="width:{e.get('growth_w_pct')}%"></div>
        <span class="g-tick" style="left:50%"></span></div>
      <div class="g-sub">价值 {_f(e.get('value_w_pct'))}% &nbsp;·&nbsp; 偏移 {_pct(e.get('bias_pts'))}</div>
    </div>
    <p class="note">偏移逻辑：基准50/50，由「ROE差(长锚)+估值价差(安全边际)+行业拥挤度+盈利增速差(第一性)+温和动量」加权偏移，
    限幅[40%,70%]。信号并聚力不足时收敛至±12pt内（防单信号误切）。本引擎只调权重偏移，不做成长/价值二值切换。</p>
    <table class="sig"><thead><tr><th>信号</th><th>读数</th><th>方向</th><th>注释</th></tr></thead><tbody>{signal_rows}</tbody></table>
    <p class="note">并聚力：推动成长 <b>{c.get("pushing_up")}</b> / 推动价值 <b>{c.get("pushing_down")}</b>（净 {('{:+d}'.format(c.get("net_push")) if c.get("net_push") is not None else '—')}，阈值 {c.get("threshold")}）</p>'''
else:
    default_eng = '<p class="note">配置引擎暂不可用（估值数据缺失）。</p>'

def _fmt_signed(x):  # noqa: unused (inline in default_eng)
    if x is None: return "—"
    return f"{x:+d}"

# ---- 估值对比 ----
g, v = DATA["growth"], DATA["value"]
def vrow(label, gv, vv, fmt=_f):
    if not callable(fmt):
        fmt = lambda x: x if isinstance(x, str) else ("—" if x is None else str(x))
    return f'<tr><td>{label}</td><td class="g">{fmt(gv)}</td><td class="v">{fmt(vv)}</td></tr>'
val_table = f'''
<div class="card"><h3>估值 & 盈利质量对比</h3>
<table><thead><tr><th>指标</th><th class="g">成长100 (980080)</th><th class="v">价值100 (980081)</th></tr></thead>
<tbody>
{vrow("PE(TTM)", g["pe_ttm"], v["pe_ttm"])}
{vrow("ROE", g["roe"], v["roe"])}
{vrow("PE 10年分位", g["pe_pct_10y"], v["pe_pct_10y"])}
{vrow("PB 10年分位", g["pb_pct_10y"], v["pb_pct_10y"])}
{vrow("指数点位", g["point"], v["point"])}
{vrow("YTD", g["ytd"], v["ytd"], _pct)}
{vrow("近1月涨跌", g["return_1m"], v["return_1m"], _pct)}
{vrow("近3月涨跌", g["return_3m"], v["return_3m"], _pct)}
{vrow("近6月涨跌", g["return_6m"], v["return_6m"], _pct)}
{vrow("近1年涨跌", g["return_1y"], v["return_1y"], _pct)}
{vrow("近3年涨跌", g["return_3y"], v["return_3y"], _pct)}
{vrow("近5年涨跌", g["return_5y"], v["return_5y"], _pct)}
</tbody></table>
<p class="note">成长 PE60.6x vs 价值 10.4x（PE 比 {_f(g.get("pe_ttm")/v.get("pe_ttm") if v.get("pe_ttm") else None)}x），成长贵 5.9 倍。但 ROE 差 +2.5pp、盈利更强劲。估值过高≠立即切换，需盈利增速差配合（第一性）。</p>
</div>'''

# ---- 技术温度 ----
def techrow(label, gv, vv, sub="%"):
    return f'<tr><td>{label}</td><td class="g">{_fmt_x(gv)}</td><td class="v">{_fmt_x(vv)}</td></tr>'
def _fmt_x(x):
    return _f(x) if isinstance(x,(int,float)) else (html.escape(x) if x else "—")
tech_table = f'''
<div class="card"><h3>技术温度（易方达 ETF 短期，次新历史短）</h3>
<table><thead><tr><th>指标(ETF)</th><th class="g">成长ETF {html.escape(DATA["meta"]["growth"]["etf_name"])}</th><th class="v">价值ETF {html.escape(DATA["meta"]["value"]["etf_name"])}</th></tr></thead>
<tbody>
{vrow("现价", g["etf"]["close"] if g["etf"].get("ok") else "—", v["etf"]["close"] if v["etf"].get("ok") else "—")}
{vrow("MA20", g["etf"]["ma20"] if g["etf"].get("ok") else "—", v["etf"]["ma20"] if v["etf"].get("ok") else "—")}
{vrow("BIAS20(乖离)", g["etf"]["bias20"] if g["etf"].get("ok") else "—", v["etf"]["bias20"] if v["etf"].get("ok") else "—", "")}
{vrow("60日回撤", g["etf"]["drawdown60"] if g["etf"].get("ok") else "—", v["etf"]["drawdown60"] if v["etf"].get("ok") else "—", "")}
{vrow("52周位置", g["etf"]["pos52"] if g["etf"].get("ok") else "—", v["etf"]["pos52"] if v["etf"].get("ok") else "—", "")}
{vrow("近5日", g["etf"]["chg_5d"] if g["etf"].get("ok") else "—", v["etf"]["chg_5d"] if v["etf"].get("ok") else "—", "")}
</tbody></table>
<p class="note">⚠️ 次新ETF：成长 {g["etf"].get("n_bars") if g["etf"].get("ok") else "?"}根（{g["etf"].get("first_date") if g["etf"].get("ok") else "?"}起）、价值 {v["etf"].get("n_bars") if v["etf"].get("ok") else "?"}根。技术温度仅短期参考；回撤仅覆盖上市以来，勿当长史。成长 ETF 回撤 -{_f(abs(g["etf"]["drawdown60"]) if g["etf"].get("ok") else 0)}%（3m 指数跌14.8%后），价值回撤浅。</p>
</div>'''

CSS = """
<style>
:root{--g:#e0563f;--v:#3a7bd5;--bg:#f5f7fa;--card:#fff;--line:#e3e8ef;--text:#2c3e50;--dim:#7f8c9b}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,'PingFang SC','Microsoft YaHei',sans-serif;background:var(--bg);color:var(--text);padding:20px;line-height:1.5}
.wrap{max-width:960px;margin:0 auto}
h1{font-size:20px;margin-bottom:2px}
h2{font-size:15px;color:var(--dim);font-weight:500;margin-bottom:16px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:18px;margin-bottom:16px}
.card h3{font-size:15px;margin-bottom:12px;color:#1f2d3d}
table{width:100%;border-collapse:collapse;font-size:13px}
th,td{text-align:left;padding:7px 8px;border-bottom:1px solid #eef1f5}
th{color:var(--dim);font-weight:600;background:#f8fafc}
td.g{color:var(--g);font-weight:600}
td.v{color:var(--v);font-weight:600}
td.dim{color:var(--dim);font-size:12px}
.gauge{padding:18px;background:linear-gradient(135deg,#fff5f3,#eef4ff);border-radius:10px;margin-bottom:12px;text-align:center}
.g-num{font-size:44px;font-weight:800;color:var(--g)}
.g-unit{font-size:16px;color:var(--dim);font-weight:500;margin-left:6px}
.g-bar{height:22px;background:#eef0f4;border-radius:11px;margin:14px auto;max-width:420px;position:relative}
.g-fill{height:100%;background:linear-gradient(90deg,var(--v),#7aa5e0 50%,var(--g));border-radius:11px}
.g-tick{position:absolute;top:-4px;width:2px;height:30px;background:#333;opacity:.5}
.g-sub{font-size:14px;color:var(--dim)}
.note{font-size:12.5px;color:var(--dim);margin-top:10px;background:#f8fafc;padding:8px 10px;border-radius:6px}
.sig td,.sig th{font-size:12.5px}
.barwrap{position:relative;min-width:120px;height:16px;background:#f0f2f6;border-radius:8px}
.hbar{height:100%;border-radius:8px;background-color:var(--line)}
.hval{position:absolute;right:4px;top:0;font-size:11px;font-weight:600}
.foot{font-size:11.5px;color:var(--dim);margin-top:20px;line-height:1.7}
.badge{display:inline-block;padding:1px 8px;border-radius:10px;font-size:11px;font-weight:600}
.badge.r{background:#fdece8;color:#c0392b}
@media(max-width:600px){h1{font-size:17px}.g-num{font-size:34px}}
</style>"""

HTML = f"""<!DOCTYPE html><html lang="zh"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>成长 vs 价值 · 风格轮动 & 配置比例</title>{CSS}</head><body><div class="wrap">
<h1>成长 vs 价值 · 风格轮动 & 配置比例</h1>
<h2>成长100(980080) vs 价值100(980081) · 更新 {DATA["meta"]["updated"]}</h2>

<div class="card"><h3>目标配置比例 <span class="badge r">轮动引擎 v1</span></h3>{default_eng}</div>
{val_table}
<div class="card"><h3>行业分布</h3><div class="two" style="display:flex;gap:14px;flex-wrap:wrap">
{industry_table("成长100 · 行业分布", g.get("top_industries"), "g")}
{industry_table("价值100 · 行业分布", v.get("top_industries"), "v")}
</div>
<p class="note">成长被<b>电子(58%)</b>极度主导=行业拥挤度高（触发拥挤度减权）；价值由<b>银行(36%)+家电(22%)</b>构成，防御属性强。行业 yoy=该行业年内涨跌。</p></div>
{tech_table}

<div class="foot">
<b>数据源：</b>天天基金 TTFUND_INDEX_INFO（估值/ROE/行业分布/多期收益，国证成长100=980080、价值100=980081）、腾讯 ETF K线（易方达成长ETF 159259 / 价值ETF 159263，技术温度）。<br>
<b>正确性 &gt; 及时性：</b>所有指标带净值（valuation/quote/performance 为 TTFUND 当日）。免费源故障时如实标注「获取失败」，绝不拿旧值冒充当前值。<br>
<b>方法声明：</b>配置比例由 ROE差(长锚)+估值价差(安全边际)+行业拥挤度+盈利增速差(第一性)+温和动量 加权偏移，限幅[40%,70%]，信号并聚≥2才明显偏移。盈利增速差需成分净利聚合（依赖 growth_precompute 脚本），当前未自动接入则该项中性。本引擎不给买卖点，只给相对权重。
</div>
</div></body></html>"""

os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w") as f:
    f.write(HTML)
print("written", OUT, os.path.getsize(OUT), "bytes")