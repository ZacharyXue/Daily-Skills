# -*- coding: utf-8 -*-
"""
渲染脚本：读 cache/dashboard_data.json → output/cement_dashboard.html
独立自包含 HTML（内嵌 CSS），原生 <details>/<summary> 实现「可点击查看指标意义」。
面向博客集成(Astro v5)，可直接作为静态页面。
"""
import json, os, sys, html, datetime

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(BASE, "cache", "dashboard_data.json")
OUT = os.path.join(BASE, "output", "cement_dashboard.html")

def esc(x):
    return html.escape(str(x)) if x is not None else "—"

def fmt_val(ind):
    """从 indicator 提取主展示值字符串 + 附加信息 + 数据日期"""
    v = ind.get("value")
    if not isinstance(v, dict): v = {}
    if ind.get("status") == "failed":
        return "✗ 获取失败", "", None
    # 特化：PB历史分位
    if v.get("pb_percentile") is not None and v.get("latest") is not None:
        return f"PB {v['latest']} · 近250日分位 {v['pb_percentile']:.0f}%", "", v.get("latest_date")
    # 特化：均线(收盘+MA20/60)
    if v.get("close") is not None and v.get("ma20") is not None and v.get("ma60") is not None:
        return f"收 {v['close']:.2f} · MA20 {v['ma20']} · MA60 {v['ma60']}", "", v.get("latest_date")
    # 特化：MACD/RSI
    if v.get("rsi14") is not None and v.get("macd") is not None:
        return f"RSI6 {v.get('rsi6')} · RSI14 {v['rsi14']} · MACD {v['macd']}", "", v.get("latest_date")
    # 特化：KDJ
    if v.get("K") is not None and v.get("J") is not None:
        return f"K {v['K']} · D {v['D']} · J {v['J']}", "", v.get("latest_date")
    # 特化：布林带
    if v.get("mid") is not None and v.get("up") is not None:
        return f"收 {v.get('price')} · 中轨 {v['mid']} · 上轨 {v['up']} · 下轨 {v['low']}", "", v.get("latest_date")
    # 特化：净利类(有 np/np_yoy, 无 latest)——主值显示净利 + 同比
    if v.get("np") is not None and v.get("latest") is None and v.get("close") is None:
        extra = f" <span class='sub'>同比 {v.get('np_yoy',0):+.1f}%</span>" if v.get("np_yoy") is not None else ""
        return f"{v['np']:,.1f} 亿", extra, v.get("report") or v.get("latest_date")
    # 通用单值
    val = v.get("latest") if v.get("latest") is not None else v.get("close")
    unit = ind.get("unit", "")
    valstr = f"{val:,.1f} {unit}" if isinstance(val, (int, float)) else (v.get("note") or "待接入")
    extra = ""
    if v.get("yoy_1y") is not None:
        extra = f" <span class='sub'>1年{v['yoy_1y']:+.1f}%</span>"
    elif v.get("np") is not None:
        extra = f" <span class='sub'>净利{v['np']:,.1f}亿 (同比{v.get('np_yoy',0):+.1f}%)</span>"
    return valstr, extra, v.get("latest_date")

def badge(ind):
    st = ind.get("status", "error")
    if st == "manual": return ("ok", "人工")
    if st == "failed": return ("err", "获取失败")
    if st == "ok": return ("ok", "正常")
    if st == "pending": return ("gray", "接入中")
    return ("err", "异常")

def trend_svg(charts, w=520, h=104):
    """将 charts=[{name,color,points:[{d,v}]}] 画成多线迷你趋势图 + 图例。无则回空。"""
    import datetime as dt
    if not charts:
        return ""
    allpts = [(p["d"], float(p["v"])) for ch in charts for p in ch.get("points", []) if p.get("v") is not None]
    if len(allpts) < 2:
        return ""
    dates = [x[0] for x in allpts]; vals = [x[1] for x in allpts]
    def to_date(d):
        d = str(d)
        return dt.date.fromisoformat(d) if len(d) > 7 else dt.date.fromisoformat(d + "-01")
    try:
        d0 = to_date(min(dates)); d1 = to_date(max(dates))
    except Exception:
        d0 = dt.date(2025, 1, 1); d1 = dt.date(2026, 8, 29)
    span = (d1 - d0).days or 1
    mn = min(vals); mx = max(vals); yspan = (mx - mn) or 1
    X = lambda d: (to_date(d) - d0).days / span * (w - 10) + 5
    Y = lambda v: h - 8 - (v - mn) / yspan * (h - 22)
    svg = f'<svg viewBox="0 0 {w} {h}" width="100%" height="{h}" preserveAspectRatio="none" class="tsvg">'
    for ch in charts:
        pts = " ".join(f"{X(p['d']):.1f},{Y(float(p['v'])):.1f}" for p in ch.get("points", []) if p.get("v") is not None)
        svg += f'<polyline points="{pts}" fill="none" stroke="{ch.get("color","#2563eb")}" stroke-width="1.6"/>'
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
    inds = data["indicators"]

    # 按 group 分组（保持 GROUPS 顺序）
    from indicators import GROUPS
    by_group = {}
    for ind in inds:
        by_group.setdefault(ind.get("group", "其他"), []).append(ind)
    group_order = [g for g in GROUPS if g in by_group] + [g for g in by_group if g not in GROUPS]

    # ---- 摘要：达标计数（试规则，后续校准） ----
    counts = {"达标": 0, "观察": 0, "未达标": 0}
    # 简单规则：价格止跌(po425>=300&CEMPI不创新低) / 成本(煤不涨) / 盈利(净利同比>0) / 财务(负债<30) / 估值(PB<0.8) / 技术(价>MA20)
    def num(ind, key):
        v = ind.get("value")
        return v.get(key) if isinstance(v, dict) else None

    def gid(g): return g.get("id")
    find = lambda iid: next((x for x in inds if gid(x) == iid), None)

    verdicts = []
    # 价格止跌
    po = find("po425"); val_po = po.get("value", {}).get("latest") if po else None
    price_ok = bool(val_po and val_po >= 300)
    verdicts.append(("价格", "止跌" if price_ok else "磨底", price_ok))
    # 成本：煤价同比<0=成本利好
    coal = find("coal"); coal_yoy = coal.get("value", {}).get("yoy_1y") if coal else None
    cost_ok = bool(coal_yoy is not None and coal_yoy < 0)
    verdicts.append(("成本", "利好" if cost_ok else "压力", cost_ok))
    # 盈利
    hnp = find("helluo_np"); np_yoy = hnp.get("value", {}).get("np_yoy") if hnp else None
    prof_ok = bool(np_yoy is not None and np_yoy > 0)
    verdicts.append(("盈利", "修复" if prof_ok else "承压", prof_ok))
    # 财务
    dbr = find("debt_ratio"); dr = dbr.get("value", {}).get("latest") if dbr else None
    fin_ok = bool(dr is not None and dr < 30)
    verdicts.append(("财务", "安全" if fin_ok else "警惕", fin_ok))
    # 技术
    ma = find("ma"); close = ma.get("value", {}).get("close") if ma else None
    ma20 = ma.get("value", {}).get("ma20") if ma else None
    tech_ok = bool(close and ma20 and close > ma20)
    verdicts.append(("技术", "走强" if tech_ok else "弱势", tech_ok))
    # 量(代理: 混凝土价稳定)
    con = find("concrete"); cony = con.get("value", {}).get("yoy_1y") if con else None
    vol_ok = bool(cony is not None and cony >= -10)
    verdicts.append(("量", "企稳" if vol_ok else "偏弱", vol_ok))
    # 供给/出清：CR10 上行(>65%) 或 水泥-熟料价差走扩 = 软出清推进
    cr = find("cr10"); crv = cr.get("value", {}).get("latest") if cr else None
    sup_ok = bool(crv is not None and crv >= 65)
    verdicts.append(("供给/出清", "推进" if sup_ok else "缓慢", sup_ok))

    ok_n = sum(1 for _, _, ok in verdicts if ok)
    if ok_n >= 5: verdict_txt = "≥5类达标：接近加仓讨论区"
    elif ok_n >= 3: verdict_txt = "3-4类达标：仍处磨底，跟踪止跌信号"
    else: verdict_txt = f"不足3类达标（{ok_n}/7）：磨底加深，防守为主"

    badge_html = "".join(f'<span class="vb {"ok" if ok else "no"}">{n}·{"✓" if ok else "✗"}</span>' for n, _, ok in verdicts)
    counts_txt = f"达标 {ok_n}/7"

    # ---- 指标卡片 html ----
    cards = []
    for g in group_order:
        items = by_group.get(g, [])
        if not items: continue
        cards.append(f'<section class="group"><h2 class="gtitle">{esc(g)}</h2>')
        for ind in items:
            v = ind.get("value") or {}
            valstr, extra, ldate = fmt_val(ind)
            bcls, btxt = badge(ind)
            st = ind.get("status", "error")
            ttl = ind.get("ttl", "—")
            # 来源+时间
            src = ind.get("source", "")
            src_url = ind.get("source_url", "")
            if st == "manual":
                src_link = f'人工录入 @{esc(ind.get("manual_at",""))}（外部软件）'
            else:
                src_link = f'<a href="{esc(src_url)}" target="_blank">{esc(src)}</a>' if src_url else esc(src)
            fetch_t = ind.get("fetched_at", fetched)
            meta = (f'<div class="meta"><span class="m">来源：{src_link}</span>'
                    f'<span class="m">更新时间：{esc(fetch_t)}</span>'
                    f'<span class="m">TTL：{esc(ttl)}</span>'
                    + (f'<span class="m">数据日期：{esc(ldate)}</span>' if ldate and ldate != "近一周均值" else "")
                    + '</div>')
            # 失败/旧值参考
            errnote = ""
            if st == "failed":
                errnote = (f'<div class="signal errline">⚠ 本次获取失败：{esc(ind.get("error",""))}</div>')
                lg = ind.get("last_good")
                if lg and isinstance(lg, dict) and lg.get("latest") is not None:
                    errnote += (f'<div class="meta"><span class="m errline">上次成功值 {lg.get("latest")}'
                                f' @{esc(ind.get("last_good_at",""))}（非当前，仅参考）</span></div>')
            # 趋势图
            svg = ""
            if v.get("charts"):
                svg = trend_svg(v["charts"])
            valstr_c = f'<span class="val {"up" if False else ""}">{esc(valstr)}</span>{extra}'
            cards.append(
                f'<details class="card"{"" if st != "error" else " open"}>'
                f'<summary><span class="dot {bcls}"></span>'
                f'<span class="cname">{esc(ind.get("name"))}</span>'
                f'{valstr_c}'
                f'<span class="badge {bcls}">{btxt}</span></summary>'
                f'<div class="cbody">'
                f'<div class="why"><b>为什么关注</b>：{esc(ind.get("meaning",""))}</div>'
                f'<div class="signal"><b>看什么信号</b>：{esc(ind.get("signal",""))}</div>'
                f'{errnote}'
                f'<div class="meta">🤖 {meta}</div>'
                f'{svg}'
                f'</div></details>')
        cards.append('</section>')

    peer_html = ""
    peers = data.get("peers")
    if peers:
        hdr = ["公司","营收(亿)","归母净利(亿)","净利同比%","毛利率%","净利率%","ROE%","负债率%","每股CF","25年净利(亿)"]
        rows_h = "".join(f"<th>{h}</th>" for h in hdr)
        body = ""
        for p in peers:
            if "err" in p:
                body += f"<tr><td class='pn'>{esc(p.get('name',''))}</td><td colspan='9' style='color:var(--err)'>取数失败</td></tr>"; continue
            hl = "phl" if p.get("name") == "海螺水泥" else ""
            def fm(x): return f"{x:.1f}" if isinstance(x, (int, float)) else "—"
            neg = "neg" if isinstance(p.get("np_yoy"), (int,float)) and p["np_yoy"] < 0 else ""
            body += (f"<tr class='{hl}'><td class='pn'>{esc(p.get('name',''))}</td>"
                     f"<td>{fm(p.get('rev'))}</td><td>{fm(p.get('np'))}</td>"
                     f"<td class='{neg}'>{fm(p.get('np_yoy'))}</td><td>{fm(p.get('gm'))}</td>"
                     f"<td>{fm(p.get('nm'))}</td><td>{fm(p.get('roe'))}</td><td>{fm(p.get('zcfz'))}</td>"
                     f"<td>{fm(p.get('cf_ps'))}</td><td>{fm(p.get('np25'))}</td></tr>")
        rep = peers[0].get("report", "")
        peer_html = (f'<section class="group"><h2 class="gtitle">同行对比（头部五家 · {esc(rep)}）</h2>'
                     f'<div class="ptwrap"><table class="ptable"><thead><tr>{rows_h}</tr></thead><tbody>{body}</tbody></table></div>'
                     f'<div style="color:var(--sub);font-size:12px;margin-top:8px">海螺高亮 · 来源：东方财富 datacenter · 五家口径统一 {esc(rep)}</div></section>')

    html_doc = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>水泥行业 & 海螺水泥 · 盈利底监测看板</title>
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
.dot {{ width:9px; height:9px; border-radius:50%; flex:none; }}
.dot.ok {{ background:var(--ok); }} .dot.warn {{ background:var(--warn); }}
.dot.err {{ background:var(--err); }} .dot.gray {{ background:var(--gray); }}
.cname {{ font-weight:600; }}
.val {{ font-size:15px; font-weight:700; color:var(--ink); }}
.val.up {{ color:var(--ok); }}
.sub {{ font-size:12px; color:var(--sub); font-weight:400; }}
.badge {{ margin-left:auto; padding:2px 8px; border-radius:12px; font-size:12px; font-weight:600; }}
.badge.ok {{ background:#e9f8ef; color:var(--ok); }} .badge.warn {{ background:#fef3c7; color:var(--warn); }}
.badge.err {{ background:#fef2f2; color:var(--err); }} .badge.gray {{ background:#f1f2f4; color:var(--sub); }}
.cbody {{ padding:0 16px 14px 40px; font-size:14px; }}
.why,.signal {{ margin-bottom:7px; }} .why b,.signal b {{ color:var(--acc); }}
.meta {{ margin-top:8px; font-size:12px; color:var(--sub); display:flex; gap:14px; flex-wrap:wrap; }}
.meta a {{ color:var(--acc); text-decoration:none; }}
.stale-tag {{ color:var(--warn); font-weight:600; }}
.errline {{ color:var(--err); font-weight:600; }}
.tsvg {{ margin-top:8px; background:#fafbfc; border-radius:6px; }}
.chleg {{ display:flex; gap:12px; flex-wrap:wrap; font-size:11px; color:var(--sub); padding-top:4px; }}
.chleg .cl {{ display:inline-block; width:12px; height:3px; margin-right:4px; vertical-align:middle; }}
.ptwrap {{ overflow-x:auto; }}
.ptable {{ width:100%; border-collapse:collapse; font-size:13px; background:var(--card); border:1px solid var(--line); border-radius:10px; }}
.ptable th,.ptable td {{ padding:8px 9px; text-align:right; border-bottom:1px solid var(--line); white-space:nowrap; }}
.ptable th {{ background:#f1f2f4; color:var(--sub); font-weight:600; text-align:center; }}
.ptable td.pn {{ text-align:left; font-weight:600; }}
.ptable tr.phl {{ background:#eef4ff; }}
.ptable tr.phl td.pn {{ color:var(--acc); }}
.ptable td.neg {{ color:var(--err); }}
footer {{ margin-top:30px; color:var(--sub); font-size:12px; line-height:1.8; border-top:1px solid var(--line); padding-top:16px; }}
@media (max-width:640px) {{ .cbody {{ padding-left:30px; }} .val {{ font-size:14px; }} }}
</style>
</head>
<body>
<div class="wrap">
<header><h1>水泥行业 ⏤ 海螺水泥 · 盈利底监测看板</h1>
<div class="meta">更新：{esc(fetched)} · 华新/海螺双股 · 正确性优先 · 免费公开源</div></header>

<div class="summary">
  <div class="verdict"><b>{esc(verdict_txt)}</b> · {esc(counts_txt)}</div>
  <div class="badges">{badge_html}</div>
</div>

{peer_html}

{''.join(cards)}

<footer>
  <b>数据源</b>：中国水泥网 index.ccement.com（价格/成本/需求代理）｜腾讯行情 qt.gtimg.cn + ifzq（估值/技术面）｜东方财富 datacenter（财务/同行对比）。<br>
  <b>原则</b>：正确性 &gt; 及时性；价格/成本日-周缓存、财务季缓存、估值日缓存。每次拉取均为最新远程数据；若本次获取失败，指标将标红「获取失败」并注明原因，<b>绝不使用旧值冒充当前值</b>。<br>
  <b>说明</b>：本看板仅监测指标，不构成任何投资建议。阈值随周期校正。
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
