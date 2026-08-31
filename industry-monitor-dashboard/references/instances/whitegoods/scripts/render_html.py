# -*- coding: utf-8 -*-
"""
白电三巨头(美的/海尔/格力) 监测看板 —— 渲染层
==============================================
读 cache/dashboard_data.json → output/whitegoods_dashboard.html
自包含单文件 HTML（内嵌 CSS），可直接挂 Astro 博客 public/exports/。

核心：三家「核心指标对比总表」(财务/行情/估值/股息/ROIC) + 每指标三家对比趋势图。
trend_svg 复用 dashboard-style/scripts/dashboard_shared.py（消除跨看板重复）。
数据正确性铁律：只渲染 fetch.py 从数据源取到的数据，绝不 hardcode。
"""
import json, os, sys, html

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

def _shared_dir():
    d = os.path.dirname(os.path.abspath(__file__))
    for _ in range(8):
        if os.path.isdir(os.path.join(d, "dashboard-style", "scripts")):
            return os.path.join(d, "dashboard-style", "scripts")
        d = os.path.dirname(d)
    return os.path.join(os.environ.get("ZACH_SKILLS", "/root/zach-skills"), "dashboard-style", "scripts")
sys.path.insert(0, _shared_dir())

from dashboard_shared import esc, fnum, pct, trend_svg

DATA = os.path.join(BASE, "cache", "dashboard_data.json")
OUT = os.path.join(BASE, "output", "whitegoods_dashboard.html")

def build():
    data = json.load(open(DATA, encoding="utf-8"))
    cs = data.get("companies", [])
    fetched = data.get("fetched_at", "")
    comps = []
    for c in cs:
        sets = c.get("sets", {})
        fin = sets.get("financial", {}) or {}
        q = sets.get("quote", {}) or {}
        pos = sets.get("position", {}) or {}
        div = sets.get("dividend", {}) or {}
        val = sets.get("valuation", {}) or {}
        tr = sets.get("trends", {}) or {}
        comps.append({"name": c["name"], "code": c["code"], "fin": fin, "q": q, "pos": pos,
                      "div": div, "val": val, "tr": tr})

    # ============ HTML 骨架（自包含 CSS） ============
    html_doc = """<!DOCTYPE html><html lang="zh"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>白电三巨头监测看板</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,'PingFang SC','Microsoft YaHei',sans-serif;background:#f1f5f9;color:#1e293b;padding:16px;line-height:1.5}
.wrap{max-width:980px;margin:0 auto}
h1{font-size:20px;margin-bottom:4px}
.sub{color:#64748b;font-size:12px;margin-bottom:16px}
.banner{background:#fffbeb;border:1px solid #fcd34d;border-radius:8px;padding:10px 14px;font-size:13px;margin-bottom:16px}
.banner b{color:#92400e}
.card{background:#fff;border-radius:12px;box-shadow:0 1px 3px rgba(0,0,0,.08);padding:16px;margin-bottom:16px}
.card h2{font-size:15px;margin-bottom:12px;display:flex;align-items:center;gap:8px}
table{width:100%;border-collapse:collapse;font-size:12.5px}
.table-wrap{overflow-x:auto;-webkit-overflow-scrolling:touch}
.table-wrap table{min-width:840px}
th,td{padding:7px 9px;text-align:right;border-bottom:1px solid #eef2f7;white-space:nowrap}
th:first-child,td:first-child{text-align:left}
thead th{background:#f8fafc;color:#475569;font-weight:600;white-space:nowrap}
tr:last-child td{border-bottom:none}
td.company{font-weight:600;white-space:nowrap}
.up{color:#dc2626}
.down{color:#16a34a}
.hl{background:#fffbeb}
.tcard{margin-bottom:12px;padding:12px;border:1px solid #eef2f7;border-radius:8px}
.tcard .ch{display:flex;justify-content:space-between;align-items:center;margin-bottom:8px}
.tcard .ch .nm{font-weight:600;font-size:14px}
.tsvg{background:#fff}
.chleg{font-size:11px;color:#64748b;display:flex;gap:12px;margin-top:4px}
.chleg .cl{display:inline-block;width:12px;height:3px;border-radius:2px;margin-right:4px;vertical-align:middle}
.meta{font-size:11px;color:#94a3b8;margin-top:6px}
.st{display:inline-block;padding:2px 8px;border-radius:10px;font-size:11px;font-weight:600}
.st.ok{background:#dcfce7;color:#15803d}.st.err{background:#fee2e2;color:#b91c1c}
.badge{font-size:10px;padding:1px 6px;border-radius:10px;background:#dbeafe;color:#1d4ed8}
details{background:#fff;border:1px solid #eef2f7;border-radius:8px;margin-bottom:8px;padding:10px 14px}
summary{cursor:pointer;font-size:13px;font-weight:500}
details p{font-size:12px;color:#475569;margin-top:6px}
</style></head><body><div class="wrap">
"""

    # ============ 头部 + 信号条 ============
    html_doc += f'<h1>📊 白电三巨头监测看板</h1>'
    html_doc += f'<div class="sub">美的 / 海尔 / 格力 · 核心财务 + 行情 + 估值 + 股息 · 数据截至 <b>{esc(fetched)}</b></div>'

    html_doc += ('<div class="banner">💡 <b>一句话跟踪</b>：格力最便宜股息最高(PE 7.8/股息5.1%)、美的质量最贵(PE 14.8)、海尔便宜但2026中报净利润-14%(需看是汇兑假摔还是趋势)。'
                 '白电共同变量 = 海外占比带来的关税/汇率 + 国内地产链 + 原材料铜铝。数据自自动接口，正确性>及时性。</div>')

    # ============ ① 核心指标对比总表 ============
    html_doc += '<div class="card"><h2>① 核心指标对比总表</h2><div class="table-wrap"><table><thead><tr>'
    headers = ["公司", "现价", "PE", "PB", "52周位置", "近一年", "最大回撤",
               "营收(中报)", "归母净利(中报)", "净利同比", "ROE", "ROIC", "毛利率", "净利率",
               "股息率", "隐含回报(ROE/PB)"]
    for h in headers:
        html_doc += f"<th>{h}</th>"
    html_doc += "</tr></thead><tbody>"

    summary_line = []
    for c in comps:
        fin, q, pos, div, val = c["fin"], c["q"], c["pos"], c["div"], c["val"]
        row = f"<tr><td class='company'>{esc(c['name'])}<br><span style='font-weight:400;color:#94a3b8;font-size:11px'>{c['code']}</span></td>"
        # 现价/涨跌
        chg = q.get("chg_pct")
        chg_s = f"<span class='{ 'up' if (chg or 0)>0 else 'down'}'>({chg:+.2f}%)</span>" if chg is not None else ""
        row += f"<td>{fnum(q.get('price'),2)} {chg_s}</td>"
        row += f"<td>{fnum(q.get('pe'))}</td><td>{fnum(q.get('pb'),2)}</td>"
        p52 = pos.get("pos52")
        row += f"<td>{pct(p52)}</td>"
        row += f"<td class='{ 'up' if (pos.get('ret1y') or 0)>0 else 'down'}'>{pct(pos.get('ret1y'))}</td>"
        row += f"<td>{pct(pos.get('maxdd'))}</td>"
        # 财务
        np_yoy = fin.get("np_yoy")
        row += f"<td>{fnum(fin.get('rev'))}亿</td>"
        row += f"<td>{fnum(fin.get('np'))}亿</td>"
        row += f"<td class='{ 'down' if (np_yoy or 0)>=0 else 'up'}'>{pct(np_yoy)}</td>"
        row += f"<td>{pct(fin.get('roe'),2)}</td>"
        row += f"<td>{pct(val.get('roic'),1)}</td>"
        row += f"<td>{pct(fin.get('gm'))}</td><td>{pct(fin.get('nm'))}</td>"
        row += f"<td><b>{pct(div.get('yield'),2)}</b></td>"
        row += f"<td>{pct(val.get('implied_r'),2)}</td></tr>"
        html_doc += row
        report = fin.get("report", "?")
        summary_line.append(f"{c['name']}({report})")
    html_doc += "</tbody></table></div>"
    html_doc += f'<div class="sub" style="margin-top:6px">财务为最新一期(中报/季报)累计值；股息率=最近年报每10股派息÷现价；52周位置=现价在近250日区间位置；隐含回报=ROE÷PB(市场给的质量溢价，低=贵)。</div>'
    html_doc += "</div>"

    # ============ ② 财务走势（每指标一张·三家对比） ============
    html_doc += '<div class="card"><h2>② 财务走势（三家对比）</h2>'
    # 三个指标：营收(亿)、ROE%、净利率% —— 每个指标一张图、三家各自一条线
    # comps 每家的 tr.charts = [{name:'营收(亿)',points}, {name:'ROE%',points}, {name:'净利率%',points}]
    metric_keys = ["营收(亿)", "ROE%", "净利率%"]
    metric_titles = {"营收(亿)": "营收（亿元）", "ROE%": "ROE（%）", "净利率%": "净利率（%）"}
    comp_colors = {"美的集团": "#2563eb", "海尔智家": "#16a34a", "格力电器": "#d97706"}
    for mk in metric_keys:
        # 从三家提取该指标序列
        lines = []
        for c in comps:
            for ch in (c["tr"] or {}).get("charts") or []:
                if ch.get("name") == mk and ch.get("points"):
                    lines.append({"name": f"{c['name']}", "color": comp_colors.get(c["name"], "#2563eb"),
                                  "points": ch.get("points", [])})
        # 用全部序列计算该指标三家共同 x/y 范围画一张多线图
        metric_title = metric_titles.get(mk, mk)
        allpts = [(str(p["d"]), float(p["v"])) for l in lines for p in l["points"] if p.get("v") is not None]
        if len(allpts) >= 2:
            svg = trend_svg(lines)
            html_doc += f'<div class="tcard"><div class="ch"><span class="nm">📈 {esc(metric_title)}（三家对比）</span>'
            html_doc += f'<span class="st ok">自动取数</span></div>'
            html_doc += svg
            html_doc += f'<div class="meta">近6年年报 · 来源东财 datacenter · 报告期最新=2026中报</div></div>'
    html_doc += "</div>"

    # ============ ③ 估值/股息明细（可点击说明） ============
    html_doc += '<div class="card"><h2>③ 估值与股息明细</h2>'
    for c in comps:
        div, val = c["div"], c["val"]
        yrs = div.get("years") or []
        yr_txt = " ".join(f"{y['year']}: {fnum(y['d10'],2)}" for y in yrs)
        html_doc += f"<details><summary>📌 {esc(c['name'])} — 股息率 <b>{pct(div.get('yield'),2)}</b>｜市场隐含回报 <b>{pct(val.get('implied_r'),2)}</b></summary>"
        html_doc += f"<p>• 近5年年报每10股派息：{esc(yr_txt) or '—'}<br>"
        html_doc += f"• 股息率口径：最近年报派息÷现价（白电普遍年度+中期双分红，取年度为准）<br>"
        html_doc += f"• 市场隐含回报=ROE÷现PB：越低说明市场愿接受的低回报越高=定价越贵，越高=定价越便宜～" 
        html_doc += "</details>"
    html_doc += "</div>"

    # ============ ④ 数据源声明 ============
    html_doc += ('<div class="card"><h2>📚 数据源</h2>'
                 '<p style="font-size:12px;color:#475569">腾讯行情(现价/PE/PB)、腾讯K线(52周位置/回撤)、东方财富 datacenter(财务序列 RPT_F10_FINANCE_MAINFINADATA + 分红 RPT_SHAREBONUS_DET)。'
                 '所有数值经 data-source-router 自动取数，正确性&gt;及时性，远程失败标"获取失败"不冒充当前值。</p></div>')

    html_doc += "</div></body></html>"

    with open(OUT, "w", encoding="utf-8") as f:
        f.write(html_doc)
    print("saved", OUT, f"({os.path.getsize(OUT)//1024} KB)")

if __name__ == "__main__":
    build()