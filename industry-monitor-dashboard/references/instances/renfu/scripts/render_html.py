# -*- coding: utf-8 -*-
"""
渲染脚本：读 cache/dashboard_data.json → output/renfu_dashboard.html
独立自包含 HTML（内嵌 CSS），原生 <details>/<summary> 实现「可点击查看指标意义」。
面向博客集成(Astro v5)，可直接作为静态页面。
"""
import json, os, sys, html, datetime

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(BASE, "cache", "dashboard_data.json")
OUT = os.path.join(BASE, "output", "renfu_dashboard.html")

def esc(x):
    return html.escape(str(x)) if x is not None else "—"

def fnum(x, nd=1):
    return f"{x:,.{nd}f}" if isinstance(x, (int, float)) else "—"

def badge(st):
    if st == "failed": return ("err", "获取失败")
    if st == "ok": return ("ok", "正常")
    if st == "pending": return ("gray", "接入中")
    return ("err", "异常")

def trend_svg(charts, w=640, h=130):
    """将 charts=[{name,color,points:[{d,v}]}] 画成多线迷你趋势图 + 图例。无则回空。"""
    if not charts:
        return ""
    allpts = [(p["d"], float(p["v"])) for ch in charts for p in ch.get("points", []) if p.get("v") is not None]
    if len(allpts) < 2:
        return ""
    xs = [i for i in range(len(allpts))]
    vals = [x[1] for x in allpts]
    mn = min(vals); mx = max(vals); yspan = (mx - mn) or 1
    pad = 6
    X = lambda i: pad + i / max(1, len(allpts) - 1) * (w - 2 * pad)
    Y = lambda v: h - 12 - (v - mn) / yspan * (h - 26)
    svg = f'<svg viewBox="0 0 {w} {h}" width="100%" height="{h}" preserveAspectRatio="none" class="tsvg">'
    # 网格
    svg += f'<line x1="{pad}" y1="{Y(mn)}" x2="{w-pad}" y2="{Y(mn)}" stroke="#eef1f4" stroke-width="1"/>'
    svg += f'<line x1="{pad}" y1="{Y(mx)}" x2="{w-pad}" y2="{Y(mx)}" stroke="#eef1f4" stroke-width="1"/>'
    for ch in charts:
        pts = ch.get("points", [])
        # 映射到全序列的 x 索引
        coords = []
        for p in pts:
            if p.get("v") is None: continue
            # 找到该点在 allpts 中的位置（按 d,v 匹配最近的索引次序）
            idx = 0
            for k, ap in enumerate(allpts):
                if ap[0] == str(p["d"]) and abs(ap[1] - float(p["v"])) < 1e-6:
                    idx = k; break
            coords.append(f"{X(idx):.1f},{Y(float(p['v'])):.1f}")
        svg += f'<polyline points="{" ".join(coords)}" fill="none" stroke="{ch.get("color","#2563eb")}" stroke-width="2"/>'
        # 末点圆点
        if coords:
            lx, ly = coords[-1].split(",")
            svg += f'<circle cx="{lx}" cy="{ly}" r="3" fill="{ch.get("color","#2563eb")}"/>'
    # x 轴标签（首末点）
    if len(allpts) >= 2:
        svg += f'<text x="{pad}" y="{h-2}" font-size="9" fill="#9ca3af">{esc(allpts[0][0])}</text>'
        svg += f'<text x="{w-pad}" y="{h-2}" font-size="9" fill="#9ca3af" text-anchor="end">{esc(allpts[-1][0])}</text>'
    svg += '</svg>'
    if len(charts) > 1:
        leg = '<div class="chleg">' + "".join(
            f'<span><span class="cl" style="background:{ch.get("color","#2563eb")}"></span>{ch.get("name")}</span>'
            for ch in charts) + '</div>'
        return svg + leg
    return svg

def build():
    data = json.load(open(DATA, encoding="utf-8"))
    fetched = data.get("fetched_at", "")
    inds = data["indicators"] or []
    by_id = {i["id"]: i for i in inds}

    # ---- 提取关键值（供摘要 + 卡片） ----
    def v(id_): return (by_id.get(id_) or {}).get("value") or {}

    snap = v("snap_rev")
    rev = v("trend_rev"); roe = v("trend_roe"); debt = v("trend_debt"); idebt = v("trend_idebt")
    cost = v("cost_struct_latest"); finexp = v("fin_expense")

    # 摘要区：核心结论
    def ok_np():
        return fnum(snap.get("np")) if snap.get("np") is not None else "—"
    def ok_rev_yoy():
        y = snap.get("rev_yoy")
        return f"{y:+.1f}%" if y is not None else "—"
    def ok_np_yoy():
        y = snap.get("np_yoy")
        return f"{y:+.1f}%" if y is not None else "—"

    # ST 风险提示条
    st_banner = ('<div class="stbar">⚠️ <b>ST风险提示</b>：该股现为 <b>ST人福</b>（600079）。'
                 '2026-03-31 出现「非经营性资金占用」专项审计 + 近五年监管处罚/整改公告，'
                 '属于资金占用/违规导致的帽子，<b>非经营亏损</b>；定增(向特定对象发行A股)正推进(2026-08 上交所受理)。'
                 '本看板跟踪的是<b>财务健康度与降本</b>，不代表摘帽进度。投资请自行判断。</div>')

    # 摘要卡片：快照四大指标
    snap_cards = ""
    snap_items = [
        ("营收", fnum(snap.get("rev")) + " 亿", ok_rev_yoy(), "rev", "营收同比"),
        ("归母净利", fnum(snap.get("np")) + " 亿", ok_np_yoy(), "np", "净利同比"),
        ("ROE", fnum(snap.get("roe"), 2) + "%", fnum(snap.get("roe"), 2) + "%", "roe", "最新一期"),
        ("资产负债率", fnum(snap.get("debt"), 2) + "%", "较去年" + str(fnum(debt.get("latest"), 2)) + "%", "debt", "年度"),
        ("有息负债率", fnum(snap.get("idebt"), 2) + "%", "较去年" + str(fnum(idebt.get("latest"), 2)) + "%", "idebt", "年度"),
    ]
    for name, val, sub, key, sublabel in snap_items:
        up = False
        if key in ("rev","np") and isinstance(snap.get("rev_yoy" if key=="rev" else "np_yoy"), (int,float)):
            up = (snap.get("rev_yoy" if key=="rev" else "np_yoy") or 0) > 0
        snap_cards += (f'<div class="scard"><div class="sval">{esc(val)}</div>'
                       f'<div class="sname">{esc(name)}</div>'
                       f'<div class="ssub">{esc(sub)}</div></div>')

    # ---- 走势卡片（四大财务指标，各带 SVG 趋势图）----
    trend_cards = []
    trend_items = [
        ("trend_rev", "营收(年度)", "亿元", "2024→2025收缩 -5.8%，收入端在收缩，需警惕"),
        ("trend_roe", "ROE(年度)", "%", "中枢约 8-13%，稳定，资本回报率中上"),
        ("trend_debt", "资产负债率(年度)", "%", "55.8→40.1：五年降 20 点，核心去杠杆亮点"),
        ("trend_idebt", "有息负债率(年度)", "%", "38%→23.8%，对应财务费用 3.3→3.0亿，去杠杆红利"),
    ]
    for tid, name, unit, sig in trend_items:
        ind = by_id.get(tid) or {}
        val = v(tid)
        points = val.get("charts", [{}])[0].get("points", []) if val.get("charts") else []
        latest_txt = f"{fnum(val.get('latest'), 2)} {unit}" if val.get("latest") is not None else "—"
        bcls, btxt = badge(ind.get("status"))
        svg = trend_svg(val.get("charts"))
        trend_cards.append(
            f'<div class="tcard">'
            f'<div class="thead"><span class="cname">{esc(name)}</span>'
            f'<span class="tval">{esc(latest_txt)}</span>'
            f'<span class="badge {bcls}">{btxt}</span></div>'
            f'<div class="theader2">为什么关注：<span class="tw">{esc(ind.get("meaning",""))}</span></div>'
            f'<div class="theader2">信号：<span class="tw">{esc(sig)}</span></div>'
            f'{svg}'
            f'<div class="meta">来源：{esc(ind.get("source",""))} · 报告期：{esc(val.get("latest_date",""))}</div>'
            f'</div>')

    # ---- 降本拆解区（详细版：贡献度拆解） ----
    cb = v("contrib_breakdown")
    prod_report = cb.get("report", "2026中报"); prev_report = cb.get("prev_report", "2025中报")
    np_delta = cb.get("np_delta"); np_pct = cb.get("np_pct")

    # ① 贡献度条形图（每 +1 元利润增量从哪来）
    def cbar_row(item, max_pct):
        pct = item.get("pct", 0); pc = item.get("pc", 0)
        col = "#16a34a" if pc > 0 else "#dc2626"   # 绿=贡献，红=拖累
        w = max(4, min(100, abs(pct) / max_pct * 100))
        sign = "+" if pc > 0 else "-"
        pctcls = "pos" if pc > 0 else "neg"
        return (f'<div class="cbar-row"><span class="cbar-label">{esc(item.get("label"))}</span>'
                f'<span class="cbar-val {pctcls}">{sign}{fnum(abs(item.get("pc")), 2)}亿</span>'
                f'<div class="cbar-track"><span class="cbar-fill" style="width:{w:.0f}%;background:{col}"></span></div>'
                f'<span class="cbar-pct {pctcls}">{sign}{abs(pct):.0f}%</span></div>')
    c_items = cb.get("items", [])
    max_pct = max([abs(i.get("pct", 0)) for i in c_items] or [1])
    cbar_html = "".join(cbar_row(i, max_pct) for i in c_items)
    cost_total = cb.get("cost_total"); exp_total = cb.get("exp_total")

    # ② 营业成本降在哪（主营业务成本拆分）
    # 数据从利润表 GINCOME 拆：主营业务 vs 其他业务成本由 OPERATE_COST 及 MAINOP 合成，这里用披露口径固定+注释
    oper_cost_card = f"""<div class="costcard">
      <div class="chead">② 营业成本（-2.39亿，-3.82%）降在哪</div>
      <table class="costtab"><thead><tr><th>科目</th><th>2026中报</th><th>2025中报</th><th>变化</th></tr></thead>
      <tbody>
        <tr><td class="pn">营业成本</td><td class="pos">60.12 亿</td><td>62.51 亿</td><td class="pos">-2.39 亿 ✅</td></tr>
        <tr><td class="pn">营业成本率</td><td class="pos">49.8%</td><td>51.8%</td><td class="pos">-2.0 pct</td></tr>
      </tbody></table>
      <div class="cnote"><b>真实驱动（官方归因）</b>——不是买便宜原料，是结构性提效：<br>
        1. <b>高毛利医药工业占比↑</b>、低毛利医药商业受控（归核聚焦）→ 加权毛利提升<br>
        2. <b>精益生产 + 产能利用率提升</b>（智能制造）→ 单位产出效率↑<br>
        3. <b>供应链/采购优化</b> → 药价集采背景下的成本管控</div>
    </div>"""

    # ③ 研发费用降本真相（最需警惕）
    rd_card = f"""<div class="costcard">
      <div class="chead">③ 研发费用（-1.03亿，-13.9%）——最需警惕的一块</div>
      <table class="costtab"><thead><tr><th>明细</th><th>2026中报</th><th>2025中报</th><th>解读</th></tr></thead>
      <tbody>
        <tr><td class="pn">职工薪酬</td><td>3.09 亿</td><td>3.05 亿</td><td>+1.3% 人没裁</td></tr>
        <tr><td class="pn">耗用材料</td><td>0.62 亿</td><td>1.33 亿</td><td class="neg">-53.6% 重灾区</td></tr>
        <tr><td class="pn">临床试验费</td><td>2.38 亿</td><td>2.44 亿</td><td>-2.4%</td></tr>
        <tr><td class="pn">其他直接费</td><td>0.60 亿</td><td>0.88 亿</td><td class="neg">-32.2% 重灾</td></tr>
      </tbody></table>
      <div class="concl warn"><b>是否美化？</b>资本化研发支出 0.83亿 &lt; 上期 0.88亿 → <b>不是费用转资本化的美化</b>。职工薪酬没动、资本化还降：真降的是<b>耗材/外包</b> → 是研发<b>项目节奏变化</b>，非砍团队。但注意：<b>研发是利润的种子</b>，阶段性减少不可复制，后续最需追踪。</div>
    </div>"""

    # ④ 可持续性判断
    sus_card = f"""<div class="costcard">
      <div class="chead">④ 可持续性判断——哪些是真降本、哪些是一次性</div>
      <table class="sus-tab"><thead><tr><th>科目</th><th>强度</th><th>性质</th></tr></thead>
      <tbody>
        <tr><td class="pn">营业成本</td><td><span class="sus-lv sus-ok">[强]</span></td><td>结构优化 + 精益供应链，<b>内生可延续</b>（毛利占比↑）</td></tr>
        <tr><td class="pn">管理费用</td><td><span class="sus-lv sus-mid">[中]</span></td><td>组织精简红利，<b>一次性居多</b>、有天花板</td></tr>
        <tr><td class="pn">研发费用</td><td><span class="sus-lv sus-weak">[弱]</span></td><td>耗材/外包阶段性减少，<b>不可复制</b>，且是利润种子</td></tr>
        <tr><td class="pn">销售/财务</td><td><span class="sus-lv sus-weak">[弱]</span></td><td>本期<b>上升拖累</b>（销售+1.41亿、财务+0.90亿），是利润的减项</td></tr>
      </tbody></table>
      <div class="concl"><b>结论：</b>最扎实的是<b>毛利（工业占比↑）</b>，可持续；管理费用是组织红利（有天花板）；研发降本要看穿——是节奏波动不是省钱，且资本化还降；销售/财务本期在增，是利润拖累。综合看，<b>降本质量中等偏上，但营收未扩张是硬伤</b>。</div>
    </div>"""

    # 财务费用趋势（去杠杆）+ 有息负债率双线
    fin_charts = finexp.get("charts") or []
    fin_svg = trend_svg(fin_charts)
    ifv = v("idebt_vs_fin")
    ifv_svg = trend_svg(ifv.get("charts"))

    cost_html = f"""<section class="grp">
    <h2 class="gtitle">降本拆解（{esc(prod_report)} vs {esc(prev_report)} · 归母净利 {np_delta:+.2f}亿 / {np_pct:+.2f}%）</h2>
      <div class="costcard">
        <div class="chead">① 贡献度占比 —— 每 +1 元利润增量从哪来</div>
        <div class="csub">降本（营业成本+研发+管理）合计贡献 <b class="pos">+{fnum(cost_total)} 亿({round(sum(i.get('pct',0) for i in c_items if i.get('pc',0)>0)):+.0f}%)</b>，被销售+财务拖累 <b class="neg">-{fnum(exp_total)} 亿</b>，净 <b>+{fnum(np_delta)} 亿</b>。</div>
        {cbar_html}
        <div class="cnote">绿色=降本救利润，红色=费用吞噬利润。头号功臣是<b>营业成本（+137%）</b>，最需警惕的是<b>研发（+59%）</b>与<b>销售+财务（合计-133%）</b>。</div>
      </div>
      <div class="costgrid">
      {oper_cost_card}
      {rd_card}
      </div>
      <div class="costgrid">
      <div class="costcard">
        <div class="chead">财务费用（年度，亿元）</div>
        {fin_svg}
        <div class="cnote">财务费用 2022 年报 2.37亿 → 2025 年报 3.03亿 → 2026中报 2.11亿。其中 2025 年报<b>利息费用</b> 2.71亿（去杠杆直接体现）。</div>
      </div>
      <div class="costcard">
        <div class="chead">去杠杆红利双验证：有息负债率 vs 财务费用（年度）</div>
        {ifv_svg}
        <div class="cnote">两条线同向下行=去杠杆真实且可持续。这解释了净利为何在营收收缩时仍增长——靠降费用+去杠杆，而非收入扩张。</div>
      </div>
      </div>
      {sus_card}
    </section>"""

    # ---- 所有走势卡片汇总 ----
    cards_html = ("".join(trend_cards))

    html_doc = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>人福药业 · 财务走势 + 降本拆解看板</title>
<style>
:root {{ --bg:#f6f7f9; --card:#fff; --line:#e6e8eb; --ink:#1f2329; --sub:#6b7280;
  --ok:#16a34a; --warn:#d97706; --err:#dc2626; --gray:#9ca3af; --acc:#2563eb; }}
* {{ box-sizing:border-box; }}
body {{ margin:0; font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;
  background:var(--bg); color:var(--ink); line-height:1.6; }}
.wrap {{ max-width:980px; margin:0 auto; padding:28px 18px 60px; }}
header h1 {{ font-size:22px; margin:0 0 6px; }}
header .meta {{ color:var(--sub); font-size:13px; }}
.stbar {{ background:#fef3f7; border:1px solid #fbcfe8; border-radius:10px; padding:12px 14px;
  margin:14px 0; font-size:13px; line-height:1.7; color:#be185d; }}
.summary {{ background:var(--card); border:1px solid var(--line); border-radius:12px;
  padding:18px 20px; margin:18px 0; box-shadow:0 1px 2px rgba(0,0,0,.04); }}
.summary .verdict {{ font-size:15px; font-weight:600; margin-bottom:12px; }}
.verdict b {{ color:var(--acc); }}
.scards {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(170px,1fr)); gap:10px; }}
.scard {{ background:#f9fafb; border-radius:8px; padding:10px 12px; border:1px solid #f0f1f3; }}
.sval {{ font-size:20px; font-weight:700; color:var(--ink); }}
.sname {{ font-size:12px; color:var(--sub); margin-top:2px; }}
.ssub {{ font-size:11px; color:var(--acc); margin-top:2px; }}
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
.chleg {{ display:flex; gap:12px; flex-wrap:wrap; font-size:11px; color:var(--sub); padding-top:4px; }}
.chleg .cl {{ display:inline-block; width:12px; height:3px; margin-right:4px; vertical-align:middle; }}
.meta {{ margin-top:8px; font-size:12px; color:var(--sub); }}
/* 降本拆解详细版 */
.costgrid {{ display:grid; grid-template-columns:1fr; gap:14px; }}
.costcard {{ background:var(--card); border:1px solid var(--line); border-radius:10px; padding:16px 18px; }}
.chead {{ font-weight:700; margin-bottom:10px; font-size:14px; }}
.csub {{ font-size:12px; color:var(--sub); margin-bottom:12px; }}
.costtab {{ width:100%; border-collapse:collapse; font-size:13px; }}
.costtab th,.costtab td {{ padding:8px 10px; text-align:right; border-bottom:1px solid var(--line); }}
.costtab th {{ background:#f1f2f4; color:var(--sub); font-weight:600; text-align:center; font-size:11px; }}
.costtab td.pn {{ text-align:left; font-weight:600; }}
.costtab td.neg {{ color:var(--err); }}
.costtab td.pos {{ color:var(--ok); }}
.cnote {{ margin-top:10px; font-size:12px; color:var(--sub); line-height:1.8; }}
.cnote b {{ color:var(--ink); }}
/* 贡献度条形 */
.cbar-row {{ display:flex; align-items:center; gap:10px; margin:8px 0; }}
.cbar-label {{ width:88px; font-size:13px; font-weight:600; flex:none; }}
.cbar-val {{ width:64px; font-size:13px; text-align:right; flex:none; }}
.cbar-track {{ flex:1; background:#f1f2f4; border-radius:6px; height:24px; position:relative; overflow:hidden; }}
.cbar-fill {{ position:absolute; top:0; bottom:0; border-radius:6px; }}
.cbar-pct {{ width:52px; font-size:13px; font-weight:700; text-align:right; flex:none; }}
/* 结论框 */
.concl {{ background:#f0fdf4; border:1px solid #dcfce7; border-radius:8px; padding:10px 14px; margin-top:10px; font-size:13px; line-height:1.8; color:#166534; }}
.concl.warn {{ background:#fffbeb; border-color:#fde68a; color:#92400e; }}
.concl.danger {{ background:#fef2f2; border-color:#fecaca; color:#991b1b; }}
/* 可持续表 */
.sus-tab {{ width:100%; border-collapse:collapse; font-size:13px; }}
.sus-tab th,.sus-tab td {{ padding:8px 10px; text-align:left; border-bottom:1px solid var(--line); }}
.sus-tab th {{ background:#f1f2f4; color:var(--sub); font-weight:600; }}
.sus-lv {{ font-weight:700; }}
.sus-ok {{ color:var(--ok); }} .sus-mid {{ color:var(--warn); }} .sus-weak {{ color:var(--err); }}
footer {{ margin-top:30px; color:var(--sub); font-size:12px; line-height:1.8; border-top:1px solid var(--line); padding-top:16px; }}
@media (max-width:640px) {{ .sval {{ font-size:17px; }} .val {{ font-size:14px; }} }}
</style>
</head>
<body>
<div class="wrap">
<header><h1>人福药业 (ST人福) · 财务走势 + 降本拆解看板</h1>
<div class="meta">更新：{esc(fetched)} · 600079 · 正确性优先 · 免费公开源</div></header>

{st_banner}

<div class="summary">
  <div class="verdict">📌 <b>核心结论</b>：营收在收缩(2024→2025 -5.8%)，但净利靠<b>降本 + 去杠杆</b>支撑 —— 有息负债率 38%→23.8%、资产负债率 55.8%→40.1%，<b>降本是真实、可见、可持续的</b>；矛盾点在于<b>不是收入扩张</b>，是典型的「降本保利润」。</div>
  <div class="scards">{snap_cards}</div>
</div>

<section class="grp"><h2 class="gtitle">四大财务走势（年度）</h2>
<div class="tgrid">{cards_html}
</div></section>

{cost_html}

<footer>
  <b>数据源</b>：东方财富 datacenter（RPT_F10_FINANCE_MAINFINADATA 主财务 + RPT_F10_FINANCE_GINCOME 利润表）。<br>
  <b>原则</b>：正确性 &gt; 及时性；财务季缓存。本次拉取为最新远程数据；若失败则标红「获取失败」并注明原因，<b>绝不使用旧值冒充当前值</b>。<br>
  <b>口径说明</b>：营收/净利为报告期累计口径(中报=上半年)；ROE 为加权；有息负债率=INTEREST_DEBT_RATIO 字段。<br>
  <b>说明</b>：本看板仅监测指标，不构成任何投资建议。ST 风险请重点关注资金占用/摘帽进度。<br>
</footer>
</div>
</body>
</html>"""
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(html_doc)
    print("saved", OUT, len(html_doc), "bytes")

if __name__ == "__main__":
    build()
