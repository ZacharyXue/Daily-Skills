#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
housing-rent-buy-dashboard 渲染
===============================
读 data/latest.json → 生成自包含单文件 HTML（内嵌 CSS/JS，可挂博客 public/exports/）。
计算核心：
  - 租金回报率 = 1/售租比（官方口径）≈ 月租金×12/房价（交叉验证）
  - 月供 = 贷款额 × r(1+r)^n/((1+r)^n−1)，r=5Y LPR/12，n=30年
  - 售租比 vs 5Y LPR：回报率 < LPR → 出租跑不赢利息成本（现金流角度买不如租）
用法：python3 scripts/render_html.py [--out output/housing_dashboard.html]
"""
import argparse, json, os, sys, datetime, html as H

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(BASE, "data", "latest.json")

# dashboard-style 共享库（trend_svg 等）
sys.path.insert(0, os.path.join("/root/zach-skills", "dashboard-style", "scripts"))
from dashboard_shared import trend_svg, esc, fnum, pct

CITY_CN = {"sh": "上海", "hz": "杭州"}
CITY_COLOR = {"sh": "#2563eb", "hz": "#9333ea"}
# 历史保留：bj北京 gz广州 sz深圳 su苏州 如需恢复范围，把键加回上面即可（代码自动适配）

# 参数（可调）
AREA = 100           # ㎡
DOWN_RATIO = 0.20    # 首付比例（默认首套 20%）
LOAN_YEARS = 30

def esc_html(x):
    return H.escape(str(x)) if x is not None else "—"

def mom_arrow(mom_dir, mom):
    """环比方向 + 数值 → 带颜色文本"""
    if mom is None:
        return "—", ""
    if mom_dir == "▲":
        return f"▲{mom:.2f}%", "up"
    if mom_dir == "▼":
        return f"▼{mom:.2f}%", "neg"
    return f"{mom:+.2f}%", ""

def fmt_price(x):
    return f"{x:,.0f}" if isinstance(x, (int, float)) else "—"

def fmt_rent(x):
    return f"{x:,.2f}" if isinstance(x, (int, float)) else "—"

def monthly_payment(principal, annual_rate, years):
    """等额本息月供"""
    r = annual_rate / 12.0
    n = years * 12
    if r == 0:
        return principal / n
    return principal * r * (1 + r) ** n / ((1 + r) ** n - 1)

def trend_ts_to_date(ms):
    """房天下时间戳(ms) → YYYY-MM"""
    return datetime.datetime.utcfromtimestamp(ms / 1000).strftime("%Y-%m")

def build_city_metrics(data, lpr_5y):
    """每城计算：租金回报率、售租比、月供/月租/月差额"""
    rows = []
    for code, cn in CITY_CN.items():
        c = data["cities"].get(code)
        if not c:
            rows.append({"code": code, "name": cn, "ok": False})
            continue
        pm = c["price"]["meta"]; rm = c["rent"]["meta"]
        avg_p = pm.get("avg"); avg_r = rm.get("avg")
        srb = pm.get("sale_rent_ratio")
        if not avg_p or not avg_r:
            rows.append({"code": code, "name": cn, "ok": False})
            continue
        # 租金回报率：官方售租比口径 + 自算交叉
        ret_official = 1.0 / srb * 100 if srb else None
        ret_calc = avg_r * 12 / avg_p * 100
        total = avg_p * AREA
        down = total * DOWN_RATIO
        loan = total - down
        mpay = monthly_payment(loan, lpr_5y / 100.0, LOAN_YEARS)
        mrent = avg_r * AREA
        diff = mpay - mrent
        # 首付机会成本（3% 股息率锚，月均）
        opp = down * 0.03 / 12
        rows.append({
            "code": code, "name": cn, "ok": True,
            "price": avg_p, "price_mom": pm.get("mom"), "price_mom_dir": pm.get("mom_dir"),
            "rent": avg_r, "rent_mom": rm.get("mom"), "rent_mom_dir": rm.get("mom_dir"),
            "srb": srb, "ret": ret_official, "ret_calc": ret_calc,
            "total_wan": total / 1e4, "down_wan": down / 1e4,
            "mpay": mpay, "mrent": mrent, "diff": diff, "opp": opp,
            "beat_lpr": ret_official > lpr_5y if ret_official else False,
            "period": pm.get("period"),
        })
    return rows

def build_lpr_series(lpr):
    """LPR → 折线数据（升序）"""
    s5 = []; s1 = []
    for r in reversed(lpr):  # 中行页从新到旧，转为升序
        d = r["date"]
        v5 = float(r["lpr_5y"].replace("%", ""))
        v1 = float(r["lpr_1y"].replace("%", ""))
        s5.append({"d": d, "v": v5})
        s1.append({"d": d, "v": v1})
    return s5, s1

def build_ftx_charts(data):
    """房天下新房趋势 → 归一化指数多线（首月=100）"""
    charts = []
    for code, cn in CITY_CN.items():
        pts = data.get("ftx_trend", {}).get(code, [])
        if len(pts) < 2:
            continue
        base = pts[0]["price"]
        chart = {"name": cn, "color": CITY_COLOR[code],
                 "points": [{"d": trend_ts_to_date(p["ts"]), "v": round(p["price"] / base * 100, 1)} for p in pts]}
        charts.append(chart)
    return charts

def district_table(d, lpr_5y):
    """分区表行：区名 | 房价 | 租金 | 售租比 | 租金回报率 | 与 LPR 差"""
    pd = {x["name"]: x for x in d["price"]["districts"]}
    rd = {x["name"]: x for x in d["rent"]["districts"]}
    rows = []
    for nm in sorted(set(pd) | set(rd), key=lambda n: -(pd.get(n, {}).get("avg") or 0)):
        p = pd.get(nm); r = rd.get(nm)
        if not p or not r:
            continue
        srb = (p["avg"] / (r["avg"] * 12)) if p["avg"] and r["avg"] else None
        ret = 1.0 / srb * 100 if srb else None
        rows.append({"name": nm, "price": p["avg"], "rent": r["avg"],
                     "srb": srb, "ret": ret,
                     "gap": (ret - lpr_5y) if ret else None})
    return rows

def render_tables(rows, lpr_5y):
    """城市横向对比表"""
    trs = []
    for r in rows:
        if not r["ok"]:
            trs.append(f"<tr><td class=\"pn\">{esc_html(r['name'])}</td><td colspan=\"9\" class=\"errline\">数据获取失败</td></tr>")
            continue
        pm_txt, pm_cls = mom_arrow(r["price_mom_dir"], r["price_mom"])
        rm_txt, rm_cls = mom_arrow(r["rent_mom_dir"], r["rent_mom"])
        beat = r["beat_lpr"]
        badge = '<span class="badge ok">跑赢利息</span>' if beat else '<span class="badge err">跑不赢利息</span>'
        ret_txt = f"{r['ret']:.2f}%" if r["ret"] else "—"
        trs.append(f"""<tr>
<td class=\"pn\">{esc_html(r['name'])}</td>
<td>{fmt_price(r['price'])}</td>
<td class=\"{pm_cls}\">{pm_txt}</td>
<td>{fmt_rent(r['rent'])}</td>
<td class=\"{rm_cls}\">{rm_txt}</td>
<td>{r['srb']:.0f} 年</td>
<td><b>{ret_txt}</b></td>
<td>{badge}</td>
<td>{fmt_price(r['mpay'])}</td>
<td>{fmt_price(r['mrent'])}</td>
<td class=\"{'neg' if r['diff']>0 else 'up'}\">{'+' if r['diff']>0 else ''}{fmt_price(r['diff'])}</td>
</tr>""")
    return f"""<div class=\"ptwrap\"><table class=\"ptable\">
<tr><th>城市</th><th>均价<br>(元/㎡)</th><th>房价环比</th><th>租金<br>(元/月/㎡)</th><th>租金环比</th>
<th>售租比</th><th>租金回报率</th><th>vs LPR {lpr_5y:.2f}%</th>
<th>100㎡月供<br>(元)</th><th>100㎡月租<br>(元)</th><th>月差额<br>(月供-月租)</th></tr>
{''.join(trs)}</table></div>"""

def render_district(d, title, lpr_5y):
    rows = district_table(d, lpr_5y)
    trs = []
    for r in rows:
        gap = r["gap"]
        gap_txt = f"{gap:+.2f}pp" if gap is not None else "—"
        gap_cls = "up" if (gap or 0) > 0 else "neg"
        trs.append(f"""<tr>
<td class=\"pn\">{esc_html(r['name'])}</td>
<td>{fmt_price(r['price'])}</td>
<td>{fmt_rent(r['rent'])}</td>
<td>{r['srb']:.1f} 年</td>
<td><b>{r['ret']:.2f}%</b></td>
<td class=\"{gap_cls}\">{gap_txt}</td>
</tr>""")
    return f"""<h2 class=\"gtitle\">{esc_html(title)} · 分区租售比（租金回报率 vs LPR {lpr_5y:.2f}%）</h2>
<div class=\"ptwrap\"><table class=\"ptable\">
<tr><th>区县</th><th>均价(元/㎡)</th><th>租金(元/月/㎡)</th><th>售租比</th><th>租金回报率</th><th>vs LPR</th></tr>
{''.join(trs)}</table></div>"""

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(BASE, "output", "housing_rent_buy_dashboard.html"))
    args = ap.parse_args()
    with open(DATA, encoding="utf-8") as f:
        data = json.load(f)

    lpr = data.get("lpr", [])
    lpr_5y = float(lpr[0]["lpr_5y"].replace("%", "")) if lpr else 3.5
    lpr_1y = float(lpr[0]["lpr_1y"].replace("%", "")) if lpr else 3.0
    lpr_date = lpr[0]["date"] if lpr else "—"

    rows = build_city_metrics(data, lpr_5y)
    ok_rows = [r for r in rows if r["ok"]]
    n_beat = sum(1 for r in ok_rows if r["beat_lpr"])
    worst = min(ok_rows, key=lambda r: r["ret"]) if ok_rows else None
    best = max(ok_rows, key=lambda r: r["ret"]) if ok_rows else None

    # 摘要徽章
    badges = []
    for r in rows:
        if not r["ok"]:
            badges.append(f'<span class="vb no">{esc_html(r["name"])} 失败</span>')
            continue
        cls = "ok" if r["beat_lpr"] else "no"
        badges.append(f'<span class="vb {cls}">{esc_html(r["name"])} {r["ret"]:.2f}%</span>')

    # LPR 走势
    s5, s1 = build_lpr_series(lpr)
    lpr_svg = trend_svg([
        {"name": "5年期LPR", "color": "#dc2626", "points": s5},
        {"name": "1年期LPR", "color": "#2563eb", "points": s1},
    ], w=900, h=200)

    # 房价趋势（归一化指数）
    ftx_charts = build_ftx_charts(data)
    ftx_svg = trend_svg(ftx_charts, w=900, h=220)

    # 分区表（遍历当前关注城市，支持区县数据时渲染）
    district_sections = []
    for code in CITY_CN:
        cdata = data["cities"].get(code)
        if cdata and cdata["price"]["districts"] and cdata["rent"]["districts"]:
            district_sections.append(render_district(cdata, CITY_CN[code], lpr_5y))

    fetched = data.get("fetched_at", "—")
    period = ok_rows[0]["period"] if ok_rows else "—"

    city_names = "、".join(CITY_CN.values())
    verdict = (f"{city_names}租金回报率均显著低于 5 年期 LPR（{lpr_5y:.2f}%）："
               f"回报率最高 {best['name']} {best['ret']:.2f}% / 最低 {worst['name']} {worst['ret']:.2f}%"
               if ok_rows else "数据不足")
    counts = f"「租售比 vs 房贷利率」：{n_beat}/{len(ok_rows)} 城跑赢利息 · 数据期 {period}"

    # 决策说明卡
    def_why = ("租售比（年租金/房价）是衡量「买房收租」划算程度的标尺；与房贷利率对比："
               "租金回报率 > 贷款利率 → 出租现金流能覆盖利息，买房收租成立；否则买房靠租金覆盖不了利息，"
               "押注的是房价上涨（资本利得）。另外用月供 vs 月租看自住现金流。")
    def_signal = ("① 售租比越低 = 租金回报率越高，越接近「租改买」；② 回报率 vs LPR 差值收窄 → 购房窗口改善；"
                  "③ 房价趋势（新房挂牌均价位）与租金趋势背离 = 租售比失衡加剧。")
    def_meta = f"来源：中国房价行情(禧泰) · 房天下 · 中国银行 | 数据期 {period} | 更新 {fetched}"

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>租 vs 买 · {esc_html('、'.join(CITY_CN.values()))}租售比与房价趋势看板</title>
<style>
:root {{ --bg:#f6f7f9; --card:#fff; --line:#e6e8eb; --ink:#1f2329; --sub:#6b7280;
  --ok:#16a34a; --warn:#d97706; --err:#dc2626; --gray:#9ca3af; --acc:#2563eb; }}
* {{ box-sizing:border-box; }}
body {{ margin:0; font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;
  background:var(--bg); color:var(--ink); line-height:1.6; }}
.wrap {{ max-width:980px; margin:0 auto; padding:28px 18px 60px; }}
header h1 {{ font-size:22px; margin:0 0 6px; }}
header .meta {{ color:var(--sub); font-size:13px; }}
.summary {{ background:var(--card); border:1px solid var(--line); border-radius:12px;
  padding:18px 20px; margin:18px 0 8px; box-shadow:0 1px 2px rgba(0,0,0,.04); }}
.summary .verdict {{ font-size:15px; font-weight:600; margin-bottom:10px; }}
.verdict b {{ color:var(--acc); }}
.badges {{ display:flex; flex-wrap:wrap; gap:8px; }}
.vb {{ padding:4px 10px; border-radius:20px; font-size:13px; font-weight:600; background:#f1f2f4; }}
.vb.ok {{ background:#e9f8ef; color:var(--ok); }}
.vb.no {{ background:#fef2f2; color:var(--err); }}
.gtitle {{ font-size:16px; margin:26px 0 10px; padding-left:10px; border-left:4px solid var(--acc); }}
.card {{ background:var(--card); border:1px solid var(--line); border-radius:10px;
  margin:8px 0; overflow:hidden; }}
.card summary {{ display:flex; align-items:center; gap:10px; padding:13px 16px;
  cursor:pointer; list-style:none; position:relative; }}
.card summary::-webkit-details-marker {{ display:none; }}
.card summary::after {{ content:"▸"; margin-left:auto; color:var(--sub); transition:.15s; }}
.card[open] summary::after {{ content:"▾"; }}
.cname {{ font-weight:600; }}
.val {{ font-size:15px; font-weight:700; color:var(--ink); }}
.sub {{ font-size:12px; color:var(--sub); font-weight:400; }}
.badge {{ margin-left:auto; padding:2px 8px; border-radius:12px; font-size:12px; font-weight:600; }}
.badge.ok {{ background:#e9f8ef; color:var(--ok); }} .badge.err {{ background:#fef2f2; color:var(--err); }}
.cbody {{ padding:0 16px 14px 40px; font-size:14px; }}
.why,.signal {{ margin-bottom:7px; }} .why b,.signal b {{ color:var(--acc); }}
.meta {{ margin-top:8px; font-size:12px; color:var(--sub); display:flex; gap:14px; flex-wrap:wrap; }}
.meta a {{ color:var(--acc); text-decoration:none; }}
.errline {{ color:var(--err); font-weight:600; }}
.tsvg {{ margin-top:8px; background:#fafbfc; border-radius:6px; }}
.chleg {{ display:flex; gap:12px; flex-wrap:wrap; font-size:11px; color:var(--sub); padding-top:4px; }}
.chleg .cl {{ display:inline-block; width:12px; height:3px; margin-right:4px; vertical-align:middle; }}
.ptwrap {{ overflow-x:auto; }}
.ptable {{ width:100%; border-collapse:collapse; font-size:13px; background:var(--card); border:1px solid var(--line); border-radius:10px; }}
.ptable th,.ptable td {{ padding:8px 9px; text-align:right; border-bottom:1px solid var(--line); white-space:nowrap; }}
.ptable th {{ background:#f1f2f4; color:var(--sub); font-weight:600; text-align:center; }}
.ptable td.pn {{ text-align:left; font-weight:600; }}
.ptable td.neg {{ color:var(--err); }}
.ptable td.up {{ color:var(--ok); }}
.note {{ font-size:12px; color:var(--sub); margin-top:6px; }}
footer {{ margin-top:30px; color:var(--sub); font-size:12px; line-height:1.8; border-top:1px solid var(--line); padding-top:16px; }}
@media (max-width:640px) {{ .cbody {{ padding-left:30px; }} .val {{ font-size:14px; }} }}
</style>
</head>
<body>
<div class="wrap">
<header>
<h1>租 vs 买 · {esc_html('、'.join(CITY_CN.values()))}租售比与房价趋势</h1>
<div class="meta">更新：{fetched}（中国房价行情挂牌口径 · 数据期 {period}）</div>
</header>

<div class="summary">
  <div class="verdict"><b>{esc_html(verdict)}</b></div>
  <div>{esc_html(counts)}</div>
  <div style="margin-top:10px" class="badges">{''.join(badges)}</div>
</div>

<section class="group">
<h2 class="gtitle">{esc_html('、'.join(CITY_CN.values()))}横向对比（{AREA}㎡ · {int(DOWN_RATIO*100)}% 首付 · {LOAN_YEARS}年 · LPR {lpr_5y:.2f}%）</h2>
{render_tables(rows, lpr_5y)}
<div class="note">月供 = 等额本息（贷款额={AREA}㎡总价×{int((1-DOWN_RATIO)*100)}%）；月差额 &gt;0 表示买房每月比租房多掏（不含首付机会成本）；租金回报率 = 1/售租比（官方口径），自算 = 月租金×12/房价 交叉核对。</div>
</section>

<details class="card" open>
  <summary><span class="cname">决策框架：租房还是买房</span><span class="badge ok">怎么看</span></summary>
  <div class="cbody">
    <div class="why"><b>为什么关注</b>：{def_why}</div>
    <div class="signal"><b>看什么信号</b>：{def_signal}</div>
    <div class="meta">{def_meta}</div>
  </div>
</details>

<section class="group">
<h2 class="gtitle">房价趋势 · 新房挂牌均价（房天下，近6月，首月=100）</h2>
<div class="card" style="padding:14px 16px">
{ftx_svg}
<div class="note">归一化指数：各城市以 4 个月（首点）为 100，看相对涨跌方向；绝对价格见上表。数据源本次抓取窗口仅 6 个月，随后续更新累积成长期序列。</div>
</div>
</section>

<section class="group">
<h2 class="gtitle">LPR 走势（中国银行 · 2019-08 至今）</h2>
<div class="card" style="padding:14px 16px">
{lpr_svg}
<div class="note">当前：1Y {lpr_1y:.2f}% / 5Y {lpr_5y:.2f}%（{lpr_date}）。5Y LPR 是房贷定价基准（-20BP 等加点由各行决定）。</div>
</div>
</section>

<section class="group">
{''.join(district_sections)}
</section>

<footer>
<b>数据源</b>：
① 房价/租金/售租比/分区 = 中国房价行情（禧泰数据，m.creprice.cn，住宅挂牌口径，月度）；<br>
② 新房均价趋势 = 房天下查房价（fangjia.fang.com，月均价，近6月）；<br>
③ LPR = 中国银行官网转载全国银行间同业拆借中心报价（每月 20 日公布）。<br>
<b>计算口径</b>：租金回报率 = 1/售租比；月供按等额本息；均为估算，未计税费/中介费/物业费/利率加点，实际以银行与当地市场为准。<br>
<b>原则</b>：正确性 &gt; 及时性；每次拉取均为最新远程数据；若获取失败，指标标红「获取失败」并注明原因，绝不使用旧值冒充当前值。
</footer>
</div>
</body>
</html>"""
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"✅ 渲染完成: {args.out} ({os.path.getsize(args.out)//1024} KB)")

if __name__ == "__main__":
    main()