# -*- coding: utf-8 -*-
"""
伊利股份(600887) 监测看板 —— 渲染层
读 cache/dashboard_data.json → output/yili_dashboard.html（自包含单文件 HTML）
复用 dashboard-style 骨架样式，指标按 6 组核心指标线展示。
"""
import json, os, sys, html

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(BASE, "cache", "dashboard_data.json")
OUT = os.path.join(BASE, "output", "yili_dashboard.html")

def _ds_dir():
    d = os.path.dirname(os.path.abspath(__file__))
    for _ in range(8):
        if os.path.isdir(os.path.join(d, "dashboard-style", "scripts")):
            return os.path.join(d, "dashboard-style", "scripts")
        d = os.path.dirname(d)
    return os.path.join(os.environ.get("ZACH_SKILLS", "/root/zach-skills"), "dashboard-style", "scripts")
sys.path.insert(0, _ds_dir())
from dashboard_shared import esc, fnum, trend_svg  # noqa: E402

def badge(st):
    if st == "failed": return ("err", "获取失败")
    if st == "ok": return ("ok", "正常")
    if st == "manual": return ("gray", "人工/研报口径")
    return ("err", "异常")

def build():
    data = json.load(open(DATA, encoding="utf-8"))
    # 读取 indicators 元数据
    ind_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "indicators.py")
    inds = []
    ns = {}
    try:
        exec(open(ind_file, encoding="utf-8").read(), ns)
        inds = ns.get("INDICATORS", [])
    except Exception as e:
        print("indicators load err:", e)
    by_id = {i["id"]: i for i in inds}
    groups = ns.get("GROUPS", [])

    def v(id_): 
        it = by_id.get(id_) or {}
        return data.get(it.get("getter")) or {}
    def ind(id_): return by_id.get(id_) or {}
    def gv(getter): return data.get(getter) or {}

    fetched = max((gv(i.get("getter")).get("fetched_at", "") for i in inds), default="")

    # ---- 击球点决策条（核心） ----
    q = gv("quote"); fv = gv("fair_value"); adj = gv("adj_roe"); d_ = gv("dividend")
    price = q.get("price"); pe = q.get("pe"); pos = q.get("pos_52w")
    fps = (fv.get("prices") or {}); fps_adj = (fv.get("prices_adj") or {})
    price_txt = f"{fnum(price)} 元" if price else "—"
    # 击球点判定
    hit = ""
    if isinstance(price, (int, float)):
        if price <= 20: hit = "⚡ 已进入击球区(价格<20,股息接近6%)"
        elif price <= 22.5: hit = "🟡 接近击球区(20-22.5,正常化合理价附近)"
        else: hit = "🔴 未到击球区(>22.5,继续等)"
    else:
        hit = "🔴 数据未取到，无法判定"

    verdict_cards = "".join([
        _scard("现价", price_txt, f"52周位置 {pos}%" if pos is not None else "—",
               "neg" if (pos is not None and pos >= 70) else ""),
        _scard("PE(TTM)", fnum(pe, 1), "隐含增速4.8%>实际" if pe else "—"),
        _scard("股息率(2025口径)", f"{d_.get('dps_2025',1.38)/price*100:.2f}%" if price else "—",
               "击球位>6%" if price else ""),
        _scard("合理价 r=8%", f"{fps.get('r8','—')} 元", f"正常化ROE口径: {fps_adj.get('adj_r8','—')}",
               "neg" if (isinstance(fps.get('r8'), (int,float)) and isinstance(price,(int,float)) and fps['r8'] < price) else ""),
    ])

    # ---- 仪表盘信号条 ----（用 gv() 按 getter 名取数）
    b = gv("growth"); roe = gv("roe"); nc = gv("net_cash"); cp = gv("core_profit")
    pills = []
    # ① 营收同比
    if b.get("rev_yoy") is not None:
        rev = b["rev_yoy"]
        pills.append(f'<span class="sus-pill {"ok" if rev>=4 else "warn" if rev>=0 else "bad"}">营收同比 {rev:+.1f}%</span>')
    # ② ROE 锚
    adj_roe = adj.get("roe_adj")
    if adj_roe:
        pills.append(f'<span class="sus-pill {"ok" if adj_roe>=17 else "warn" if adj_roe>=15 else "bad"}">正常化ROE ~{fnum(adj_roe,1)}%</span>')
    # ③ 净头寸
    if nc.get("net_cash") is not None:
        ncs = nc["net_cash"]
        pills.append(f'<span class="sus-pill {"ok" if ncs>=0 else "bad"}">净头寸 {fnum(ncs)}亿</span>')
    # ④ 核心利润增速
    if cp.get("core_yoy") is not None:
        cy = cp["core_yoy"]
        pills.append(f'<span class="sus-pill {"ok" if cy>=10 else "warn" if cy>=0 else "bad"}">核心利润 {cy:+.1f}%</span>')
    # ⑤ 商誉
    imp = gv("impairment")
    pills.append(f'<span class="sus-pill {"ok" if imp.get("goodwill_left",99)<=10 else "warn"}">商誉剩 {fnum(imp.get("goodwill_left"))}亿</span>')
    pills_html = "".join(pills)

    # ---- 组卡片 ----
    group_html = ""
    for g in groups:
        g_inds = [i for i in inds if i.get("group") == g]
        if not g_inds: continue
        cards = []
        for it in g_inds:
            val = v(it["id"])
            bcls, btxt = badge(val.get("status"))
            main, sub = _main_value(it, val, price)
            cards.append(
                f'<div class="tcard">'
                f'<div class="thead"><span class="cname">{esc(it.get("name"))}</span>'
                f'<span class="tval">{esc(main)}</span>'
                f'<span class="badge {bcls}">{btxt}</span></div>'
                f'<div class="theader2">为什么关注：<span class="tw">{esc(it.get("meaning",""))}</span></div>'
                f'<div class="theader2">信号：<span class="tw">{esc(it.get("signal",""))}</span></div>'
                + _extra_html(it["id"], val)
                + f'<div class="meta">来源：{esc(val.get("source", it.get("source","")))} · 报告期：{esc(val.get("latest_date",""))}'
                  + (f' · 更新：{esc(val.get("fetched_at",""))}' if val.get("fetched_at") else "") + f'</div>'
                + (f'<div class="errnote">⚠️ {esc(str(val.get("reason","")))}</div>' if val.get("status")=="failed" else "")
                + '</div>')
        group_html += f'<section class="grp"><h2 class="gtitle">{esc(g)}</h2><div class="tgrid">{"".join(cards)}</div></section>'

    html_doc = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>伊利股份 · 监测看板（等击球点/验证ROE锚）</title>
<style>
:root {{ --bg:#f6f7f9; --card:#fff; --line:#e6e8eb; --ink:#1f2329; --sub:#6b7280;
  --ok:#16a34a; --warn:#d97706; --err:#dc2626; --gray:#9ca3af; --acc:#2563eb; }}
* {{ box-sizing:border-box; }}
body {{ margin:0; font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;
  background:var(--bg); color:var(--ink); line-height:1.6; }}
.wrap {{ max-width:980px; margin:0 auto; padding:28px 18px 60px; }}
header h1 {{ font-size:22px; margin:0 0 6px; }}
header .meta {{ color:var(--sub); font-size:13px; }}
.verdictbar {{ background:#1f2937; color:#f9fafb; border-radius:12px; padding:16px 18px; margin:14px 0; font-size:14px; line-height:1.9; }}
.verdictbar b {{ color:#fda4af; }}
.summary {{ background:var(--card); border:1px solid var(--line); border-radius:12px;
  padding:18px 20px; margin:18px 0; box-shadow:0 1px 2px rgba(0,0,0,.04); }}
.summary .verdict {{ font-size:15px; font-weight:600; margin-bottom:12px; }}
.scards {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(165px,1fr)); gap:10px; }}
.scard {{ background:#f9fafb; border-radius:8px; padding:10px 12px; border:1px solid #f0f1f3; }}
.sval {{ font-size:20px; font-weight:700; color:var(--ink); }}
.sname {{ font-size:12px; color:var(--sub); margin-top:2px; }}
.ssub {{ font-size:11px; margin-top:2px; }}
.ssub.pos {{ color:var(--ok); }} .ssub.neg {{ color:var(--err); }} .ssub.warn {{ color:var(--warn); }}
.gtitle {{ font-size:16px; margin:26px 0 10px; padding-left:10px; border-left:4px solid var(--acc); }}
.tgrid {{ display:grid; grid-template-columns:1fr; gap:12px; width:100%; }}
.tcard {{ background:var(--card); border:1px solid var(--line); border-radius:10px; padding:14px 16px; width:100%; }}
.thead {{ display:flex; align-items:center; gap:10px; flex-wrap:wrap; }}
.cname {{ font-weight:600; }}
.tval {{ font-size:16px; font-weight:700; color:var(--acc); margin-left:auto; }}
.theader2 {{ font-size:12px; color:var(--sub); margin-top:6px; }}
.tw {{ color:var(--ink); }}
.badge {{ padding:2px 8px; border-radius:12px; font-size:12px; font-weight:600; }}
.badge.ok {{ background:#e9f8ef; color:var(--ok); }} .badge.err {{ background:#fef2f2; color:var(--err); }}
.badge.gray {{ background:#f1f2f4; color:var(--sub); }}
.tsvg {{ margin-top:8px; background:#fafbfc; border-radius:6px; }}
.meta {{ margin-top:8px; font-size:12px; color:var(--sub); }}
.errnote {{ margin-top:8px; font-size:12px; color:var(--err); background:#fef2f2; padding:6px 10px; border-radius:6px; }}
.sus-pills {{ display:flex; gap:8px; flex-wrap:wrap; margin-bottom:12px; }}
.sus-pill {{ display:inline-block; padding:5px 14px; border-radius:20px; font-size:13px; font-weight:700; }}
.sus-pill.ok {{ background:#e9f8ef; color:#16a34a; border:1px solid #bbf0cc; }}
.sus-pill.warn {{ background:#fef6e5; color:#d97706; border:1px solid #fbe3b0; }}
.sus-pill.bad {{ background:#fef2f2; color:#dc2626; border:1px solid #fbd0d0; }}
table.mini {{ width:100%; border-collapse:collapse; font-size:12px; margin-top:8px; }}
table.mini th, table.mini td {{ padding:6px 8px; border-bottom:1px solid var(--line); text-align:right; }}
table.mini th {{ background:#f1f2f4; color:var(--sub); text-align:center; font-size:11px; }}
table.mini td.pn {{ text-align:left; font-weight:600; }}
footer {{ margin-top:30px; color:var(--sub); font-size:12px; line-height:1.8; border-top:1px solid var(--line); padding-top:16px; }}
@media (max-width:640px) {{ .sval {{ font-size:17px; }} }}
</style>
</head>
<body>
<div class="wrap">
<header><h1>伊利股份 (600887) · 监测看板</h1>
<div class="meta">更新：{esc(fetched)} · 逻辑：不赚成长钱，只等极端低估(股息>6%≈20元)赚均值回归 · 正确性优先 · 免费公开源</div></header>

<div class="verdictbar">🎯 <b>击球点判定</b>：{esc(hit)}<br>
💡 <b>当前逻辑</b>：好公司差价格。等两件事——① 原奶成本红利退潮后 <b>正常化 ROE 仍稳 17-18%</b>(锚不塌)；② 营收端出现<b>真实量价驱动</b>(管我财信号)。任一不满足，20 元都不是底。</div>

<div class="summary">
  <div class="verdict">📊 关键信号（每季对照）</div>
  <div class="sus-pills">{pills_html}</div>
  <div class="scards">{verdict_cards}</div>
</div>

{group_html}

<footer>
  <b>数据源</b>：东方财富 datacenter（MAINFINADATA/GINCOME/GBALANCE）+ 腾讯行情，统一经 data-source-router 取数；研报口径指标标「人工/研报」并注明出处。<br>
  <b>原则</b>：正确性 &gt; 及时性；远程失败即标「获取失败」+ 原因，绝不使用旧值冒充当前值。<br>
  <b>口径</b>：营收/净利为报告期累计；ROE 为加权；净头寸 = (货币资金+其他流动+其他非流动) − (短借+1年内到期+长借)；正常化 ROE = 账面 − 成本红利修正(简化模型)。<br>
  <b>说明</b>：本看板仅监测指标，不构成投资建议。
</footer>
</div>
</body>
</html>"""
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(html_doc)
    print("saved", OUT, len(html_doc), "bytes")

def _scard(name, val, sub, subcls=""):
    return (f'<div class="scard"><div class="sval">{esc(val)}</div>'
            f'<div class="sname">{esc(name)}</div>'
            f'<div class="ssub {subcls}">{esc(sub)}</div></div>')

def _main_value(it, val, price):
    """指标主值展示"""
    g = it.get("group", "")
    if it["id"] == "a_price":
        return f"{fnum(val.get('price'))}元 / {fnum(val.get('pos_52w'))}%", "现价/52周位置"
    if it["id"] == "a_div":
        dps = val.get("dps_2025")
        if dps and price:
            return f"{dps/price*100:.2f}%", "2025口径股息率"
        return f"{fnum(dps)} 元/股", "每股分红"
    if it["id"] == "a_pe":
        return f"{fnum(val.get('pe'),1)} 倍", "PE(TTM)"
    if it["id"] == "a_fair":
        p = val.get("prices") or {}
        return f"{p.get('r8','—')} / {p.get('r10','—')} / {p.get('r12','—')}", "r8%/r10%/r12% 合理价"
    if it["id"] == "b_rev":
        yoy = val.get("rev_yoy")
        return f"{fnum(val.get('rev'))}亿 ({yoy:+.1f}%)" if yoy is not None else f"{fnum(val.get('rev'))}亿", "营收同比"
    if it["id"] == "b_milk":
        return f"{val.get('milk_q2_yoy'):+.2f}%" if isinstance(val.get('milk_q2_yoy'), (int,float)) else "—", "液体乳Q2同比"
    if it["id"] == "b_contrib":
        return "四拆", "量/价/结构(亿元)"
    if it["id"] == "b_gm":
        return f"{fnum(val.get('gm'),1)}%", "毛利率"
    if it["id"] == "c_milk_price":
        return esc(val.get("trend","—")), "生鲜乳价格趋势"
    if it["id"] == "c_adjroe":
        return f"{fnum(val.get('roe_adj'),1)}%", "正常化ROE(剔成本红利)"
    if it["id"] == "d_roe":
        return f"{fnum(val.get('roe_2025'),1)}%", "2025年报ROE"
    if it["id"] == "d_core":
        yoy = val.get("core_yoy")
        return f"{fnum(val.get('core_h1'))}亿 ({yoy:+.1f}%)" if yoy is not None else f"{fnum(val.get('core_h1'))}亿", "核心经营利润(剔减值)"
    if it["id"] == "d_impair":
        return f"减值{fnum(val.get('impairment_h1_2026'))}亿 / 商誉{fnum(val.get('goodwill_left'))}亿", "2026H1/现存"
    if it["id"] == "e_netcash":
        return f"{fnum(val.get('net_cash'))}亿", "净头寸(类现金-有息负债)"
    if it["id"] == "e_liq":
        return f"{fnum(val.get('ld'),2)} / {fnum(val.get('idebt'))}%", "流动比率/有息负债率"
    if it["id"] == "e_fin":
        return f"{fnum(val.get('fin_h1'),2)}亿", "财务费用(负=净收益)"
    if it["id"] == "f_peer":
        return f"{fnum(val.get('yili_rev_yoy'))}% vs {fnum(val.get('mengniu_rev_yoy'))}%", "伊利 vs 蒙牛营收同比"
    if it["id"] == "f_div":
        dps = val.get("dps_2025")
        return f"{fnum(dps)} 元/股", "2025每股分红"
    return "", ""

def _extra_html(id_, val):
    """补充区块（表格/SVG）"""
    parts = []
    if id_ == "b_contrib":
        parts.append(f"""<table class="mini"><thead><tr><th>项目</th><th>2025液体乳贡献(亿元)</th></tr></thead><tbody>
<tr><td class="pn">销量</td><td class="neg">{fnum(val.get('liquid_qty'))}</td></tr>
<tr><td class="pn">价格</td><td class="neg">{fnum(val.get('liquid_price'))}</td></tr>
<tr><td class="pn">结构</td><td class="neg">{fnum(val.get('liquid_mix'))}</td></tr>
</tbody></table>""")
    if id_ == "a_fair":
        p = val.get("prices") or {}; pa = val.get("prices_adj") or {}
        parts.append(f"""<table class="mini"><thead><tr><th>口径</th><th>r=8%</th><th>r=10%</th><th>r=12%</th></tr></thead><tbody>
<tr><td class="pn">账面ROE {fnum(val.get('roe'),1)}%</td><td>{fnum(p.get('r8'))}</td><td>{fnum(p.get('r10'))}</td><td>{fnum(p.get('r12'))}</td></tr>
<tr><td class="pn">正常化ROE 17.5%</td><td>{fnum(pa.get('adj_r8'))}</td><td>{fnum(pa.get('adj_r10'))}</td><td>—</td></tr>
</tbody></table>""")
    if id_ == "d_roe":
        h = val.get("hist") or {}
        points = [{"x": k, "y": v} for k, v in sorted(h.items())]
        if len(points) >= 2:
            svg = trend_svg([{"name": "ROE(%)", "color": "#2563eb", "points": points}])
            parts.append(svg)
    if id_ == "e_fin":
        h = val.get("hist") or {}
        points = [{"x": k, "y": v} for k, v in sorted(h.items())]
        if len(points) >= 2:
            svg = trend_svg([{"name": "财务费用(亿)", "color": "#d97706", "points": points}])
            parts.append(svg)
    if id_ == "d_impair":
        h = val.get("hist") or {}
        rows = "".join(f"<tr><td class='pn'>{k}</td><td class='neg'>{v}亿</td></tr>" for k, v in h.items())
        parts.append(f"""<table class="mini"><thead><tr><th>报告期</th><th>资产减值(亿元)</th></tr></thead><tbody>{rows}</tbody></table>""")
    return "".join(parts)

if __name__ == "__main__":
    build()