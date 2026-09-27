# -*- coding: utf-8 -*-
"""
保租房 REITs 看板 · 渲染层
==========================
读 data/latest.json → 自包含单文件 HTML（内嵌 CSS/SVG，无外部依赖）

设计（用户 2026-09 定）：
  · 不给「买/不买」综合结论，只把每个打分项的**当前位置**摊开（历史区间 + 当前标记 + 参考线）
  · 图表优先：趋势用内嵌 SVG，位置用区位条，少堆数字
  · 数据缺失一律显式标注，不拿旧值冒充

用法：python3 scripts/render_html.py
"""
import os
import json
import datetime as dt

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data", "latest.json")
OUT = os.path.join(ROOT, "output", "reits_bt_dashboard.html")
os.makedirs(os.path.dirname(OUT), exist_ok=True)

C = {"ok": "#16a34a", "warn": "#d97706", "err": "#dc2626", "gray": "#9ca3af", "acc": "#2563eb",
     "ink": "#1f2329", "sub": "#6b7280", "line": "#e6e8eb"}
PALETTE = ["#2563eb", "#16a34a", "#d97706", "#dc2626", "#7c3aed", "#0891b2", "#be185d", "#4d7c0f"]


def fnum(v, nd=2, suf=""):
    if v is None:
        return "—"
    try:
        return ("%." + str(nd) + "f%s") % (v, suf)
    except Exception:
        return str(v)


def pct(v, nd=2):
    return "—" if v is None else ("%+." + str(nd) + "f%%") % (v * 100)


def bar(label, cur, lo, hi, unit="%", nd=2, refs=(), cur_text=None, note=""):
    """区位条：历史 [lo,hi] 区间 + 当前位置标记 + 可选参考线"""
    if cur is None or lo is None or hi is None:
        return ('<div class="barrow"><div class="bl">%s</div>'
                '<div class="bmiss">数据不足（该维度暂无足够历史披露）</div></div>' % label)
    span = hi - lo
    # 参考线纳入绘图区间（否则线在区间外就画不出来，标注会误导）
    plo, phi = lo, hi
    for rv, _ in refs:
        plo, phi = min(plo, rv), max(phi, rv)
    pspan = phi - plo
    pos = 50.0 if pspan <= 0 else max(0.0, min(100.0, (cur - plo) / pspan * 100))
    refs_html = ""
    for rv, rl in refs:
        if pspan > 0:
            rp = (rv - plo) / pspan * 100
            refs_html += '<div class="ref" style="left:%.1f%%"><span>%s</span></div>' % (rp, rl)
    if cur_text is None:
        cur_text = fnum(cur, nd, unit)
    return ('<div class="barrow"><div class="bl">%s</div>'
            '<div class="bar"><div class="track"></div>%s'
            '<div class="mark" style="left:%.1f%%"></div>'
            '<div class="cur" style="left:%.1f%%">%s</div></div>'
            '<div class="bends"><span>%s</span><span>%s</span></div>%s</div>'
            % (label, refs_html, pos, pos, cur_text, fnum(lo, nd, unit), fnum(hi, nd, unit),
               ('<div class="bnote">%s</div>' % note) if note else ""))


def svg_lines(series, keys, colors, labels, w=760, h=170, ylab=""):
    pts = [s for s in series if any(s.get(k) is not None for k in keys)]
    if len(pts) < 2:
        return '<div class="bmiss">样本不足，暂不画趋势</div>'
    xs = list(range(len(pts)))
    allv = [s[k] for s in pts for k in keys if s.get(k) is not None]
    lo, hi = min(allv), max(allv)
    if hi - lo < 1e-6:
        lo, hi = lo - 1, hi + 1
    pad = (hi - lo) * 0.15
    lo, hi = lo - pad, hi + pad
    L, R, T, B = 46, 12, 14, 30
    def X(i):
        return L + (i / max(len(pts) - 1, 1)) * (w - L - R)
    def Y(v):
        return T + (1 - (v - lo) / (hi - lo)) * (h - T - B)
    g = ['<svg viewBox="0 0 %d %d" class="tsvg" preserveAspectRatio="none">' % (w, h)]
    for i in range(3):
        gy = T + i * (h - T - B) / 2
        gv = hi - i * (hi - lo) / 2
        g.append('<line x1="%d" y1="%.1f" x2="%d" y2="%.1f" stroke="#eef0f2"/>' % (L, gy, w - R, gy))
        g.append('<text x="%d" y="%.1f" font-size="10" fill="#9ca3af" text-anchor="end">%.2f</text>' % (L - 4, gy + 3, gv))
    for j, k in enumerate(keys):
        seg = []
        for i, s in enumerate(pts):
            if s.get(k) is None:
                continue
            seg.append("%.1f,%.1f" % (X(i), Y(s[k])))
        if len(seg) > 1:
            g.append('<polyline points="%s" fill="none" stroke="%s" stroke-width="2" stroke-linejoin="round"/>'
                     % (" ".join(seg), colors[j]))
        for i, s in enumerate(pts):
            if s.get(k) is None:
                continue
            g.append('<circle cx="%.1f" cy="%.1f" r="2.6" fill="%s"/>' % (X(i), Y(s[k]), colors[j]))
    step = max(1, len(pts) // 7)
    for i, s in enumerate(pts):
        if i % step == 0 or i == len(pts) - 1:
            g.append('<text x="%.1f" y="%d" font-size="9.5" fill="#9ca3af" text-anchor="middle">%s</text>'
                     % (X(i), h - 10, s["period_end"][2:7]))
    g.append('</svg>')
    leg = "".join('<span class="cl" style="background:%s"></span>%s' % (colors[j], labels[j]) for j in range(len(keys)))
    return "".join(g) + '<div class="chleg">%s</div>' % leg


def main():
    D = json.load(open(DATA))
    funds = D["funds"]
    ok = [f for f in funds if f["n_periods"] > 0]

    def med(vals):
        vals = sorted(v for v in vals if v is not None)
        return vals[len(vals) // 2] if vals else None

    med_pnav = med([f["pnav"] for f in ok])
    med_dy = med([f["dy_cur"] for f in ok])
    med_occ = med([f["occ"] for f in ok])
    med_dd = med([f["dd_1y"] for f in ok])
    lpr = D.get("lpr1y", 3.0)

    # ---------- 横向对比表 ----------
    rows = []
    for f in funds:
        if f["n_periods"] == 0:
            rows.append('<tr><td class="pn">%s</td><td>%s</td><td colspan="9" class="neg">新发行/尚无定期报告</td></tr>'
                        % (f["name"], f["code"]))
            continue
        rows.append(
            '<tr><td class="pn">%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td>'
            '<td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>' % (
                f["name"] + (" *" if f.get("new_listing") else ""), f["code"], fnum(f["price"], 3),
                fnum(f["mktcap"], 1),
                fnum(f["pnav"], 3), fnum(f["dy_cur"], 2, "%"), fnum(f["dy_official"], 2, "%"),
                fnum(f["occ"], 2, "%"), fnum(f["collect"], 2, "%"), fnum(f["lease"], 2, "年"),
                pct(f["dd_1y"], 1)))
    table = ('<div class="ptwrap"><table class="ptable"><thead><tr>'
             '<th>基金</th><th>代码</th><th>现价</th><th>市值(亿)</th><th>P/NAV</th>'
             '<th>当前年化派息</th><th>官方口径</th><th>出租率</th><th>收缴率</th><th>剩余租期</th><th>距1年高点</th>'
             '</tr></thead><tbody>%s</tbody></table></div>'
             '<div class="tnote">* 上市未满一年：报告期不足，年化派息率会被首期口径放大（如中航北京昌保 14%%+），'
             '需等第 3 期报告后再看趋势。剩余租期为各项目加权平均剩余租期。</div>' % "".join(rows))

    # ---------- 每只一张卡 ----------
    cards = []
    for i, f in enumerate(funds):
        col = PALETTE[i % len(PALETTE)]
        if f["n_periods"] == 0:
            cards.append('<details class="card"><summary><span class="dot gray"></span>'
                         '<span class="cname">%s</span><span class="val">%s</span>'
                         '<span class="sub">新发行，尚无定期报告</span>'
                         '<span class="badge gray">待披露</span></summary>'
                         '<div class="cbody"><div class="why">该基金已上市/已获批但尚无定期报告可解析，'
                         '下次季报披露后自动纳入。</div></div></details>' % (f["name"], f["code"]))
            continue
        s = f["series"]
        newest = f["latest_period"] or "—"
        bars = []
        bars.append(bar("① 现金分派率（自算年化，最新期单位可供 ÷ 报告期末价）", f["dy_cur"],
                        f["dy_min"], f["dy_max"], "%", 2,
                        refs=[(lpr, "LPR %.2f%%" % lpr)],
                        note="历史区间 = 自身上市以来各报告期；红虚线为 LPR 1 年期，超得越多息差越厚"))
        bars.append(bar("② P/NAV（现价 ÷ 最新披露基金份额净值）", f["pnav"], f["pnav_min"], f["pnav_max"], "", 3,
                        refs=[(1.0, "净值 1.0")],
                        note="净值只有中报/年报披露（半年频）；1.0 以下 = 低于账面净值"))
        bars.append(bar("③ 出租率（报告期末，各项目平均）", f["occ"], f["occ_min"], f["occ_max"], "%", 2,
                        refs=[(95.0, "95%")],
                        note="口径：报告内各不动产项目出租率的算术平均（%s）" %
                             ("来自报告层面汇总值" if f.get("occ_src") == "report_level" else "来自分项目披露")))
        bars.append(bar("④ 距近 1 年最高价回撤", (f["dd_1y"] or 0) * 100, -30.0, 0.0, "%", 1,
                        refs=[], cur_text="%+.1f%%" % ((f["dd_1y"] or 0) * 100),
                        note="标尺固定 -30%% 到 0%%；近250日最大回撤 %s" % pct(f["mdd_1y"], 1)))
        bars.append(bar("⑤ 租金收缴率", f["collect"], f["collect_min"], f["collect_max"], "%", 2,
                        cur_text=fnum(f["collect"], 2, "%"),
                        note="报告期末收缴率，反映实际现金回收（低于 95% 需警惕，本类资产普遍 95% 以上）"))
        dy_svg = svg_lines(s, ["dy_calc", "dy_official"], [col, "#9ca3af"],
                           ["自算年化派息率", "基金披露的官方年化分派率"])
        occ_svg = svg_lines(s, ["occ"], [col], ["报告期末出租率（%）"])
        seq = "".join('<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>'
                      % (x["period_end"], x["rtype"], fnum(x["unit_dist"], 4),
                         fnum(x["ann_unit_dist"], 4), fnum(x["dy_calc"], 2, "%"), fnum(x["dy_official"], 2, "%"),
                         fnum(x["nav"], 4), fnum(x["occ"], 2, "%"))
                      for x in reversed(s))
        badge_html = ('<span class="badge warn">%d 期 · 上市未满一年</span>' % f["n_periods"]
                      if f.get("new_listing") else '<span class="badge gray">%d 期</span>' % f["n_periods"])
        cards.append(
            '<details class="card"><summary><span class="dot" style="background:%s"></span>'
            '<span class="cname">%s</span><span class="val">%s</span>'
            '<span class="sub">P/NAV %s · 当前派息 %s · 出租率 %s · 距高点 %s</span>'
            '<span class="badge">%s</span></summary><div class="cbody">'
            '<div class="barwrap">%s</div>'
            '<div class="trendbox"><div class="tlabel">年化派息率趋势（按报告期）</div>%s</div>'
            '<div class="trendbox"><div class="tlabel">出租率趋势（按报告期）</div>%s</div>'
            '<details class="raw"><summary>逐期原始数据（%d 期）</summary>'
            '<div class="ptwrap"><table class="ptable"><thead><tr><th>报告期末</th><th>类型</th>'
            '<th>单位可供分配</th><th>年化单位可供</th><th>年化派息率</th><th>官方口径</th><th>份额净值</th>'
            '<th>出租率</th></tr></thead><tbody>%s</tbody></table></div></details>'
            '<div class="meta"><span>最新报告：%s（%s）</span><span>已解析 %d 期定期报告</span>'
            '<span>TMM 实际到手派息率 %s</span><span>近1年含分红回报 %s</span></div>'
            '</div></details>' % (
                col, f["name"], f["code"], fnum(f["pnav"], 3), fnum(f["dy_cur"], 2, "%"),
                fnum(f["occ"], 2, "%"), pct(f["dd_1y"], 1), badge_html, "".join(bars),
                dy_svg, occ_svg, len(s), seq, newest, f["latest_rtype"], f["n_periods"],
                fnum(f["dy_ttm"], 2, "%"), pct(f["ret_1y"], 1)))

    html = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>保租房 REITs 看板</title>
<style>
:root{--bg:#f6f7f9;--card:#fff;--line:#e6e8eb;--ink:#1f2329;--sub:#6b7280;--ok:#16a34a;--warn:#d97706;
--err:#dc2626;--gray:#9ca3af;--acc:#2563eb;}
*{box-sizing:border-box;}
body{margin:0;font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;background:var(--bg);
color:var(--ink);line-height:1.6;}
.wrap{max-width:1080px;margin:0 auto;padding:28px 18px 60px;}
header h1{font-size:22px;margin:0 0 6px;}
header .meta{color:var(--sub);font-size:13px;}
.summary{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:18px 20px;margin:18px 0 8px;
box-shadow:0 1px 2px rgba(0,0,0,.04);}
.summary .verdict{font-size:15px;font-weight:600;margin-bottom:12px;}
.stats{display:flex;flex-wrap:wrap;gap:22px;}
.stat{min-width:132px;}
.stat .k{font-size:12px;color:var(--sub);}
.stat .v{font-size:20px;font-weight:700;}
.gtitle{font-size:16px;margin:26px 0 10px;padding-left:10px;border-left:4px solid var(--acc);}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;margin:8px 0;overflow:hidden;}
.card summary{display:flex;align-items:center;gap:10px;padding:13px 16px;cursor:pointer;list-style:none;flex-wrap:wrap;}
.card summary::-webkit-details-marker{display:none;}
.dot{width:9px;height:9px;border-radius:50%;flex:none;}
.dot.gray{background:var(--gray);}
.cname{font-weight:600;}
.val{font-size:14px;font-weight:700;}
.sub{font-size:12px;color:var(--sub);font-weight:400;}
.badge{margin-left:auto;padding:2px 8px;border-radius:12px;font-size:12px;font-weight:600;background:#f1f2f4;color:var(--sub);}
.badge.gray{background:#f1f2f4;color:var(--sub);}
.badge.warn{background:#fef3c7;color:var(--warn);}
.tnote{font-size:11.5px;color:var(--sub);margin-top:6px;line-height:1.7;}
.cbody{padding:6px 16px 16px 20px;font-size:14px;}
.barwrap{display:flex;flex-direction:column;gap:14px;margin:6px 0 14px;}
.barrow{display:grid;grid-template-columns:280px 1fr 132px;gap:10px;align-items:center;}
.bl{font-size:12.5px;color:#374151;line-height:1.35;}
.bar{position:relative;height:26px;}
.track{position:absolute;top:11px;left:0;right:0;height:5px;border-radius:3px;
background:linear-gradient(90deg,#dbeafe,#93c5fd);}
.mark{position:absolute;top:5px;width:2.5px;height:17px;background:#1f2937;border-radius:2px;transform:translateX(-1px);}
.cur{position:absolute;top:-9px;font-size:11.5px;font-weight:700;color:#111827;transform:translateX(-50%);white-space:nowrap;}
.ref{position:absolute;top:2px;height:22px;border-left:1.5px dashed var(--err);}
.ref span{position:absolute;top:-15px;left:3px;font-size:10px;color:var(--err);white-space:nowrap;}
.bends{display:flex;justify-content:space-between;font-size:10.5px;color:var(--sub);}
.bnote{grid-column:2 / 4;font-size:11.5px;color:var(--sub);margin-top:-8px;}
.bmiss{font-size:12px;color:var(--warn);}
.trendbox{margin-top:12px;background:#fafbfc;border-radius:8px;padding:8px 10px;}
.tlabel{font-size:12.5px;color:var(--sub);margin-bottom:2px;}
.tsvg{width:100%;height:170px;display:block;}
.chleg{display:flex;gap:14px;font-size:11px;color:var(--sub);padding-top:2px;flex-wrap:wrap;}
.chleg .cl{display:inline-block;width:12px;height:3px;margin-right:4px;vertical-align:middle;}
.ptwrap{overflow-x:auto;margin-top:8px;}
.ptable{width:100%;border-collapse:collapse;font-size:12.5px;background:var(--card);border:1px solid var(--line);}
.ptable th,.ptable td{padding:6px 8px;text-align:right;border-bottom:1px solid var(--line);white-space:nowrap;}
.ptable th{background:#f1f2f4;color:var(--sub);font-weight:600;text-align:center;}
.ptable td.pn{text-align:left;font-weight:600;}
.ptable td.neg{color:var(--err);}
.raw{margin-top:10px;font-size:13px;}
.raw summary{cursor:pointer;color:var(--acc);}
.meta{margin-top:10px;font-size:11.5px;color:var(--sub);display:flex;gap:16px;flex-wrap:wrap;}
footer{margin-top:30px;color:var(--sub);font-size:12px;line-height:1.9;border-top:1px solid var(--line);padding-top:16px;}
@media(max-width:760px){.barrow{grid-template-columns:1fr;}.bnote{grid-column:1;}}
</style></head><body><div class="wrap">
<header><h1>保租房 REITs 看板</h1>
<div class="meta">更新：@@GEN@@ ｜ 全市场公募 REITs @@UNIV@@ 只，其中保租房 @@NFUND@@ 只（@@NOK@@ 只有可解析定期报告）</div></header>

<div class="summary">
<div class="verdict">不给结论，只给位置：每个维度的历史区间 + 当前位置 + 参考线，自己判断贵不贵</div>
<div class="stats">
<div class="stat"><div class="k">中位 P/NAV</div><div class="v">@@MEDPNAV@@</div></div>
<div class="stat"><div class="k">中位当前年化派息率</div><div class="v">@@MEDDY@@%</div></div>
<div class="stat"><div class="k">对 LPR1Y(@@LPR2@@%)息差</div><div class="v">@@SPREAD@@%</div></div>
<div class="stat"><div class="k">中位出租率</div><div class="v">@@MEDOCC@@%</div></div>
<div class="stat"><div class="k">中位距1年高点</div><div class="v">@@MEDDD@@%</div></div>
</div></div>

<h2 class="gtitle">横向对比</h2>
@@TABLE@@

<h2 class="gtitle">逐只明细（点开看五项位置 + 趋势）</h2>
@@CARDS@@

<footer>
<b>数据源</b>：定期报告原文 PDF（东财基金公告 → pdf.dfcfw.com，pymupdf 解析）· 行情/K线（腾讯）· 分红记录（天天基金）·
统一走 data-source-router（kinds: cn_reits_list / cn_reits_report_list / cn_reits_report_data / cn_reits_dividend / cn_stock_kline）。<br>
<b>口径</b>：①年化派息率＝报告期单位可供分配金额 ÷ 报告期天数 × 365 ÷ 报告期末收盘价（与基金披露的「年化现金流分派率」互相校验，
实测一致）；②P/NAV 的净值只有中报/年报披露 → 半年频；③出租率取报告内各项目算术平均。<br>
<b>原则</b>：正确性 &gt; 及时性；取不到就标「数据不足」，<b>绝不用旧值冒充当前值</b>。季报披露后重新跑 fetch.py 即可刷新。
</footer></div></body></html>"""
    for k, v in {"@@GEN@@": D.get("generated"), "@@UNIV@@": str(D.get("universe")), "@@NFUND@@": str(len(funds)),
                 "@@NOK@@": str(len(ok)), "@@MEDPNAV@@": fnum(med_pnav, 3), "@@MEDDY@@": fnum(med_dy, 2),
                 "@@LPR2@@": "%.2f" % lpr,
                 "@@SPREAD@@": fnum((med_dy - lpr) if (med_dy is not None) else None, 2),
                 "@@MEDOCC@@": fnum(med_occ, 2), "@@MEDDD@@": fnum((med_dd or 0) * 100, 1),
                 "@@TABLE@@": table, "@@CARDS@@": "".join(cards)}.items():
        html = html.replace(k, v)

    open(OUT, "w").write(html)
    print("rendered", OUT, len(html), "bytes")


if __name__ == "__main__":
    main()
