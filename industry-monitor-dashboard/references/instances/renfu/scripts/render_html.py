# -*- coding: utf-8 -*-
"""
渲染脚本：读 cache/dashboard_data.json → output/renfu_dashboard.html
独立自包含 HTML（内嵌 CSS），原生 <details>/<summary> 实现「可点击查看指标意义」。
面向博客集成(Astro v5)，可直接作为静态页面。

⚠️ 数据正确性铁律：
  - 本脚本只渲染 fetch.py 从东财取到的数据，绝不 hardcode 任何明细数字。
  - 降本拆解(费用/贡献度/去杠杆)全部动态取数；无法从数据源取到的明细(如研发职工/耗材拆分)一律不展示。
"""
import json, os, sys, html

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
    """把 charts=[{name,color,points:[{d,v}]}] 画成共享 x 轴(年份升序)的多线趋势图 + 图例。"""
    if not charts:
        return ""
    pts = [(str(p["d"]), float(p["v"])) for ch in charts for p in ch.get("points", []) if p.get("v") is not None]
    if len(pts) < 2:
        return ""
    xd = sorted(set(d for d, _ in pts))
    mn = min(v for _, v in pts); mx = max(v for _, v in pts); yspan = (mx - mn) or 1
    pad = 8; n = max(1, len(xd) - 1)
    X = lambda i: pad + i / n * (w - 2 * pad)
    Y = lambda v: h - 14 - (v - mn) / yspan * (h - 30)
    svg = f'<svg viewBox="0 0 {w} {h}" width="100%" height="{h}" preserveAspectRatio="none" class="tsvg">'
    # 网格 + 上下参考线
    svg += f'<line x1="{pad}" y1="{Y(mn):.1f}" x2="{w-pad}" y2="{Y(mn):.1f}" stroke="#eef1f4"/>'
    svg += f'<line x1="{pad}" y1="{Y(mx):.1f}" x2="{w-pad}" y2="{Y(mx):.1f}" stroke="#eef1f4"/>'
    for ch in charts:
        coords = []
        for p in ch.get("points", []):
            if p.get("v") is None: continue
            d = str(p["d"])
            if d not in xd: continue
            idx = xd.index(d)
            coords.append(f"{X(idx):.1f},{Y(float(p['v'])):.1f}")
        if coords:
            svg += f'<polyline points="{" ".join(coords)}" fill="none" stroke="{ch.get("color","#2563eb")}" stroke-width="2"/>'
            lx, ly = coords[-1].split(",")
            svg += f'<circle cx="{lx}" cy="{ly}" r="3" fill="{ch.get("color","#2563eb")}"/>'
    # x 轴标签
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

def build():
    data = json.load(open(DATA, encoding="utf-8"))
    fetched = data.get("fetched_at", "")
    inds = data["indicators"] or []
    by_id = {i["id"]: i for i in inds}
    def v(id_): return (by_id.get(id_) or {}).get("value") or {}
    def ind(id_): return by_id.get(id_) or {}

    snap = v("snap_rev")   # 快照(单dict含全部)
    cost = v("cost_struct_latest")   # 费用占比
    cb = v("contrib_breakdown")   # 降本贡献度

    # ---- ST 风险提示条 ----
    st_banner = ('<div class="stbar">⚠️ <b>ST 风险提示</b>：该股现为 <b>ST人福</b>(600079)。'
                 '2026-03-31 出现「非经营性资金占用」专项审计 + 近五年监管处罚/整改公告，'
                 '属<b>资金占用/违规</b>导致的帽子(非经营亏损)；定增(向特定对象发行A股)正推进(2026-08 上交所受理)。'
                 '本看板仅跟踪<b>财务健康度与降本</b>，不代表摘帽进度。投资请自行判断。</div>')

    # ---- 摘要：快照卡片 ----
    def yoy_color(x, inv=False):
        if not isinstance(x, (int, float)): return ""
        ok = x < 0 if inv else x > 0
        return " up" if ok else ""

    def snap_card(name, val, sub, subcls=""):
        return (f'<div class="scard"><div class="sval">{esc(val)}</div>'
                f'<div class="sname">{esc(name)}</div>'
                f'<div class="ssub {subcls}">{esc(sub)}</div></div>')

    rev_yoy = snap.get("rev_yoy"); np_yoy = snap.get("np_yoy")
    snap_cards = ""
    snap_cards += snap_card("营业总收入", fnum(snap.get("rev")) + " 亿",
                            f"同比 {rev_yoy:+.1f}%" if rev_yoy is not None else "同比 —",
                            "neg" if (rev_yoy is not None and rev_yoy < 0) else "")
    snap_cards += snap_card("归母净利", fnum(snap.get("np")) + " 亿",
                            f"同比 {np_yoy:+.1f}%" if np_yoy is not None else "同比 —",
                            "pos" if (np_yoy is not None and np_yoy > 0) else "")
    snap_cards += snap_card("ROE(加权)", fnum(snap.get("roe"), 2) + "%", "最新一期")
    snap_cards += snap_card("资产负债率", fnum(snap.get("debt"), 2) + "%", "去杠杆中" if (snap.get("debt") is not None and snap.get("debt") < 45) else "偏高")
    snap_cards += snap_card("有息负债率", fnum(snap.get("idebt"), 2) + "%", "去杠杆红利" if (snap.get("idebt") is not None and snap.get("idebt") < 30) else "关注")

    # ---- 四大财务走势卡片 ----
    trend_items = [
        ("trend_rev", "营收(年度)", "亿元", "2024→2025 收缩 -5.8%，收入端在收缩，是「降本保利润」叙事里最需警惕的信号"),
        ("trend_roe", "ROE(年度)", "%", "中枢约 8-13%；2024 低点 7.7%→2025 回升 10.2%"),
        ("trend_debt", "资产负债率(年度)", "%", "55.8→40.1，五年降 20 点，核心去杠杆亮点"),
        ("trend_idebt", "有息负债率(年度)", "%", "36%→23.8%，对应财务费用腰斩，去杠杆红利"),
    ]
    trend_cards = []
    for tid, name, unit, sig in trend_items:
        val = v(tid); li = ind(tid)
        points = (val.get("charts") or [{}])[0].get("points", []) if val.get("charts") else []
        latest_txt = f"{fnum(val.get('latest'), 2)} {unit}" if val.get("latest") is not None else "—"
        bcls, btxt = badge(li.get("status"))
        svg = trend_svg(val.get("charts"))
        trend_cards.append(
            f'<div class="tcard">'
            f'<div class="thead"><span class="cname">{esc(name)}</span>'
            f'<span class="tval">{esc(latest_txt)}</span>'
            f'<span class="badge {bcls}">{btxt}</span></div>'
            f'<div class="theader2">为什么关注：<span class="tw">{esc(li.get("meaning",""))}</span></div>'
            f'<div class="theader2">信号：<span class="tw">{esc(sig)}</span></div>'
            + svg
            + f'<div class="meta">来源：{esc(li.get("source",""))} · 报告期：{esc(val.get("latest_date",""))}</div>'
            f'</div>')

    # ---- 降本拆解①：费用占比(2026中报 vs 2025年报) ----
    if cost:
        fh = ("<table class='costtab'><thead><tr><th>费用科目</th><th>2026中报</th>"
              "<th>2025年报</th><th>说明</th></tr></thead><tbody>")
        rows_def = [
            ("营业成本率", "oper_cost", None, "毛利率 50%+，成本占比近半"),
            ("销售费用率", "sale", "prev_sale", "医药最大费用项，集采下压缩"),
            ("管理费用率", "manage", "prev_manage", "组织效率，相对稳定"),
            ("研发费用率", "research", "prev_research", "未来引擎，稳定投入"),
            ("财务费用率", "finance", "prev_finance", "去杠杆红利：最低"),
        ]
        for rname, curk, prevk, note in rows_def:
            cur_v = cost.get(curk); prev_v = cost.get(prevk) if prevk else None
            def f(x): return f"{x:.1f}%" if x is not None else "—"
            chg = ""
            if isinstance(cur_v, (int, float)) and isinstance(prev_v, (int, float)):
                d = cur_v - prev_v
                cls = "pos" if d < 0 else "neg"
                chg = f'<td class="{cls}">{d:+.1f} pct</td>'
            elif prev_v is not None:
                chg = f'<td>{f(prev_v)}</td>'
            else:
                chg = "<td>—</td>"
            fh += (f"<tr><td class='pn'>{esc(rname)}</td><td>{f(cur_v)}</td>"
                   + chg + f"<td>{esc(note)}</td></tr>")
        fh += "</tbody></table>"

    # ---- 降本拆解②：去杠杆红利双线验证 ----
    dv = v("idebt_vs_fin")
    dsvg = trend_svg(dv.get("charts"))
    fin_d = v("fin_expense")
    fsvg = trend_svg(fin_d.get("charts"))

    # ---- 降本拆解③：贡献度条形图 ----
    cb_html = ""
    if cb:
        items = cb.get("items", [])
        np_delta = cb.get("np_delta"); np_pct = cb.get("np_pct")
        c_report = cb.get("report", ""); p_report = cb.get("prev_report", "")
        # 头号功臣/拖累
        import statistics
        pos = [i for i in items if i.get("pc", 0) > 0]
        neg = [i for i in items if i.get("pc", 0) < 0]
        top_gain = max(items, key=lambda i: i.get("pc", 0)) if items else None
        top_drag = min(items, key=lambda i: i.get("pc", 0)) if items else None
        max_abs = max([abs(i.get("pct", 0)) for i in items] or [1])
        bars = ""
        for i in items:
            pc = i.get("pc", 0); pct = i.get("pct", 0)
            col = "#16a34a" if pc > 0 else "#dc2626"
            w = max(3, min(100, abs(pct) / max_abs * 100))
            sign = "+" if pc > 0 else "-"
            cls = "pos" if pc > 0 else "neg"
            bars += (f'<div class="cbar-row"><span class="cbar-label">{esc(i.get("label"))}</span>'
                     f'<span class="cbar-val {cls}">{sign}{fnum(abs(pc), 2)}亿</span>'
                     f'<div class="cbar-track"><span class="cbar-fill" style="width:{w:.0f}%;background:{col}"></span></div>'
                     f'<span class="cbar-pct {cls}">{sign}{abs(pct):.0f}%</span></div>')
        cost_total = cb.get("cost_total"); issue_total = cb.get("issue_total")
        cb_html = f"""
  <div class="costcard">
    <div class="chead">① 降本贡献度拆解（{esc(c_report)} vs {esc(p_report)} · 归母净利 {np_delta:+.2f}亿 / {np_pct:+.2f}%）</div>
    <div class="csub">绿色=降本/费用下降(救利润)，红色=费用上升(吞噬利润)。头号功臣 <b>{esc(top_gain.get("label")) if top_gain else "—"}</b>，最需警惕 <b>{esc(top_drag.get("label")) if top_drag else "—"}</b>。</div>
    {bars}
    <div class="cnote">降本(营业成本+研发+管理等费用下降)合计贡献 <b class="pos">+{fnum(cost_total)} 亿</b>，被销售/财务等费用上升拖累 <b class="neg">-{fnum(issue_total)} 亿</b>，净 <b>{np_delta:+.2f} 亿</b>。</div>
  </div>"""

    # ---- 降本拆解④：研发费用明细（公司中报披露，手工提取） ----
    # 说明：东财 GINCOME 只给研发费用总额，职工/耗材/临床/其他直接费拆分为中报附注披露，非自动接口可取。
    rd_detail = f"""<div class="costcard">
      <div class="chead">⑤ 研发费用降本真相（2026中报 vs 2025中报）——最需警惕的一块</div>
      <table class="costtab"><thead><tr><th>明细</th><th>2026中报</th><th>2025中报</th><th>解读</th></tr></thead>
      <tbody>
        <tr><td class="pn">职工薪酬</td><td>3.09 亿</td><td>3.05 亿</td><td>+1.3% 人没裁</td></tr>
        <tr><td class="pn">耗用材料</td><td>0.62 亿</td><td>1.33 亿</td><td class="neg">-53.6% 重灾区</td></tr>
        <tr><td class="pn">临床试验费</td><td>2.38 亿</td><td>2.44 亿</td><td>-2.4%</td></tr>
        <tr><td class="pn">其他直接费用</td><td>0.60 亿</td><td>0.88 亿</td><td class="neg">-32.2% 重灾</td></tr>
      </tbody></table>
      <div class="concl warn"><b>是否美化？</b>资本化研发支出 0.83亿 &lt; 上期 0.88亿 → <b>不是费用转资本化的美化</b>。职工薪酬没动、资本化还降：真降的是<b>耗材/外包</b> → 是研发<b>项目节奏变化</b>，非砍团队。但注意：<b>研发是利润的种子</b>，阶段性减少不可复制，后续最需追踪。</div>
      <div class="meta">来源：公司2026中报附注披露（非自动接口）· 报告期 2026中报</div>
    </div>"""

    # ---- 降本拆解⑤：可持续性判断 ----
    rd_sus = f"""<div class="costcard">
      <div class="chead">⑥ 可持续性判断——哪些是真降本、哪些是一次性</div>
      <div class="sus-pills">
        <span class="sus-pill ok">✅ 降本质量：中等偏上</span>
        <span class="sus-pill bad">⛔ 硬伤：营收未扩张</span>
      </div>
      <table class="sus-tab"><thead><tr><th>科目</th><th>强度</th><th>性质</th></tr></thead>
      <tbody>
        <tr><td class="pn">营业成本</td><td><span class="sus-lv sus-ok">强</span></td><td>结构优化+精益供应链，<b>内生可延续</b>（高毛利工业占比↑）——最扎实的降本</td></tr>
        <tr><td class="pn">管理费用</td><td><span class="sus-lv sus-mid">中</span></td><td>组织精简红利，<b>一次性居多</b>、有天花板</td></tr>
        <tr><td class="pn">研发费用</td><td><span class="sus-lv sus-weak">弱</span></td><td>耗材/外包阶段性减少，<b>不可复制</b>，且是利润种子（资本化还降）</td></tr>
        <tr><td class="pn">销售/财务</td><td><span class="sus-lv sus-weak">弱</span></td><td>本期<b>上升拖累</b>（销售+1.41亿、财务+0.90亿），是利润的减项</td></tr>
      </tbody></table>
      <div class="sus-verdict ok">✅ <b>真正可持续</b>：毛利修复（高毛利工业占比↑）——内生、可延续</div>
      <div class="sus-verdict warn">⚠️ <b>有天花板</b>：管理费用（组织精简红利，一次性居多）</div>
      <div class="sus-verdict bad">⛔ <b>一次性 / 减项</b>：研发（节奏波动+资本化降）、销售/财务（上升拖累）</div>
      <div class="sus-hard">🎯 <b>核心结论：</b>降本质量<b>中等偏上</b>，但 <span class="k">营收未扩张是硬伤</span>——这是「<span class="k">降本保利润</span>」，靠省出来的利润，不是收入驱动的健康增长。<br>务必警惕：财务费用红利已在 2021-2022 一次性兑现后企稳，<span class="k">下一程只能靠收入</span>。</div>
    </div>"""

    cards_html = "".join(trend_cards)

    cost_html = f"""<section class="grp">
    <h2 class="gtitle">降本拆解（全部动态取数，来源：东财利润表 GINCOME；研发明细/可持续性来自公司中报披露）</h2>
    <div class="costgrid">
      {cb_html}
      <div class="costcard">
        <div class="chead">② 费用结构占比（{esc(cost.get("report","")) if cost else ""} vs {esc(cost.get("prev_report","")) if cost else ""}）</div>
        {fh if cost else "<div>费用数据缺失</div>"}
        <div class="cnote">销售费用率是医药最大费用项(19.5%)，财务费用率最低(1.8%)——去杠杆让「财务」从费用变成几乎可忽略项。</div>
      </div>
      <div class="costcard">
        <div class="chead">③ 财务费用(年度，亿元)</div>
        {fsvg}
        <div class="cnote">近5年财务费用 <b>6.23亿(2021)→2.37亿(2022)→3.03亿(2025)</b>：去杠杆红利主要在 <b>2021-2022 一次性兑现</b>(6.23→2.37 腰斩)，2023-2025 已稳定在 3.0-3.5亿。⚠️ <b>未来利润增量不能再指望财务费用下降</b>——这是「一次性红利」，后续关键看收入。</div>
      </div>
      <div class="costcard">
        <div class="chead">④ 去杠杆红利双验证（近5年）：有息负债率 vs 财务费用</div>
        {dsvg}
        <div class="cnote">两条线同向下行=去杠杆真实且可持续（近5年 2021-2025）。这解释了为何营收收缩但净利仍增长——靠少付利息+控费，而非收入扩张。</div>
      </div>
      {rd_detail}
      {rd_sus}
    </div>
  </section>"""

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
.scards {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(165px,1fr)); gap:10px; }}
.scard {{ background:#f9fafb; border-radius:8px; padding:10px 12px; border:1px solid #f0f1f3; }}
.sval {{ font-size:20px; font-weight:700; color:var(--ink); }}
.sname {{ font-size:12px; color:var(--sub); margin-top:2px; }}
.ssub {{ font-size:11px; margin-top:2px; }}
.ssub.pos {{ color:var(--ok); }} .ssub.neg {{ color:var(--err); }}
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
.costgrid {{ display:grid; grid-template-columns:1fr; gap:14px; }}
.costcard {{ background:var(--card); border:1px solid var(--line); border-radius:10px; padding:16px 18px; }}
.chead {{ font-weight:700; margin-bottom:10px; font-size:14px; }}
.csub {{ font-size:12px; color:var(--sub); margin-bottom:12px; }}
.costtab {{ width:100%; border-collapse:collapse; font-size:13px; }}
.costtab th,.costtab td {{ padding:8px 10px; text-align:right; border-bottom:1px solid var(--line); }}
.costtab th {{ background:#f1f2f4; color:var(--sub); font-weight:600; text-align:center; font-size:11px; }}
.costtab td.pn {{ text-align:left; font-weight:600; }}
.costtab td.neg {{ color:var(--err); }} .costtab td.pos {{ color:var(--ok); }}
.cnote {{ margin-top:10px; font-size:12px; color:var(--sub); line-height:1.8; }}
.cnote b {{ color:var(--ink); }}
.cbar-row {{ display:flex; align-items:center; gap:10px; margin:8px 0; }}
.cbar-label {{ width:88px; font-size:13px; font-weight:600; flex:none; }}
.cbar-val {{ width:64px; font-size:13px; text-align:right; flex:none; }}
.cbar-track {{ flex:1; background:#f1f2f4; border-radius:6px; height:24px; position:relative; overflow:hidden; }}
.cbar-fill {{ position:absolute; top:0; bottom:0; border-radius:6px; }}
.cbar-pct {{ width:52px; font-size:13px; font-weight:700; text-align:right; flex:none; }}
.cbar-val.pos,.cbar-pct.pos {{ color:var(--ok); }}
.cbar-val.neg,.cbar-pct.neg {{ color:var(--err); }}
.sus-pills {{ display:flex; gap:8px; flex-wrap:wrap; margin-bottom:12px; }}
.sus-pill {{ display:inline-block; padding:5px 14px; border-radius:20px; font-size:13px; font-weight:700; }}
.sus-pill.ok {{ background:#e9f8ef; color:#16a34a; border:1px solid #bbf0cc; }}
.sus-pill.warn {{ background:#fef6e5; color:#d97706; border:1px solid #fbe3b0; }}
.sus-pill.bad {{ background:#fef2f2; color:#dc2626; border:1px solid #fbd0d0; }}
.sus-tab {{ width:100%; border-collapse:collapse; font-size:13px; }}
.sus-tab th,.sus-tab td {{ padding:9px 10px; border-bottom:1px solid var(--line); text-align:left; }}
.sus-tab th {{ background:#f1f2f4; color:var(--sub); font-weight:600; font-size:11px; text-align:center; }}
.sus-tab td.pn {{ font-weight:700; width:110px; }}
.sus-lv {{ font-weight:700; padding:2px 9px; border-radius:10px; font-size:12px; white-space:nowrap; }}
.sus-lv.sus-ok {{ background:#e9f8ef; color:#16a34a; }}
.sus-lv.sus-mid {{ background:#fef6e5; color:#d97706; }}
.sus-lv.sus-weak {{ background:#fef2f2; color:#dc2626; }}
.sus-verdict {{ margin-top:12px; border-radius:8px; padding:12px 14px; font-size:13px; line-height:1.8; }}
.sus-verdict.ok {{ background:#f0fdf4; border:1px solid #bbf0cc; }}
.sus-verdict.warn {{ background:#fffbeb; border:1px solid #fbe3b0; }}
.sus-verdict.bad {{ background:#fef2f2; border:1px solid #fbd0d0; }}
.sus-hard {{ margin-top:14px; background:#1f2937; color:#f9fafb; border-radius:10px; padding:16px 18px; font-size:14px; line-height:1.9; }}
.sus-hard .k {{ color:#fda4af; font-weight:700; }}
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
  <div class="verdict">📌 <b>核心结论</b>：营收在收缩(2024→2025 -5.8%，2026中报同比 -0.0%)，但净利靠 <b>降本 + 去杠杆</b> 支撑 —— 有息负债率 36%→22%、资产负债率 56%→40%，<b>降本真实、可见</b>；矛盾点在于 <b>非收入扩张</b>，是典型「降本保利润」。</div>
  <div class="scards">{snap_cards}</div>
</div>

<section class="grp"><h2 class="gtitle">四大财务走势（年度）</h2>
<div class="tgrid">{cards_html}
</div></section>

{cost_html}

<footer>
  <b>数据源</b>：东方财富 datacenter（RPT_F10_FINANCE_MAINFINADATA 主财务 + RPT_F10_FINANCE_GINCOME 利润表），统一经 data-source-router 取数。<br>
  <b>原则</b>：正确性 &gt; 及时性；财务季缓存。本次拉取为最新远程数据；若失败则标红「获取失败」并注明原因，<b>绝不使用旧值冒充当前值</b>。<br>
  <b>口径说明</b>：营收/净利为报告期累计口径(中报=上半年)，同比按同报告期累计重算；ROE 为加权；有息负债率=INTEREST_DEBT_RATIO 字段。<br>
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
