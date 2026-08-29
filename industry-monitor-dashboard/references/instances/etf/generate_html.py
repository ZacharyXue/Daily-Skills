#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从 generate.py 的数据层读取并生成 HTML 看板页面."""
import json, os, sys, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from generate import main, ACTIONS, SIG_LABEL

# ---------- HTML 模板 ----------
CSS = """
:root{--bg:#edf2f7;--card:#fff;--line:#d7e0eb;--ink:#2a3445;--sub:#7a879c;
--up:#18a05e;--down:#e2544a;--hot:#f59e0b;--ok:#10b981;--warn:#f59e0b;--watch:#94a3b8;}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--ink);font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;padding:24px;max-width:1200px;margin:0 auto}
.header{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:22px 28px;margin-bottom:16px}
.header h1{font-size:26px;font-weight:700}
.header .meta{margin-top:8px;font-size:13px;color:var(--sub)}
.header .note{margin-top:10px;font-size:13px;color:#5a6b82;background:#f0f5fb;border-radius:8px;padding:8px 12px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(340px,1fr));gap:16px}
.card{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:20px;display:flex;flex-direction:column;gap:12px}
.card .top{display:flex;justify-content:space-between;align-items:flex-start}
.card .name{font-size:17px;font-weight:600}
.card .code{font-size:12px;color:var(--sub);margin-top:2px}
.price{font-size:30px;font-weight:700;margin-top:4px}
.chg{font-size:15px;margin-top:2px}
.up{color:var(--up)} .down{color:var(--down)}
.badge{font-size:13px;font-weight:700;padding:5px 12px;border-radius:20px;color:#fff}
.badge.add{background:var(--ok)} .badge.dca{background:var(--warn)}
.badge.hot{background:var(--hot)} .badge.dip{background:var(--down)} .badge.watch{background:var(--watch)}
.metrics{display:grid;grid-template-columns:repeat(2,1fr);gap:8px}
.met{background:#f6f8fb;border-radius:10px;padding:8px 12px}
.met .lab{font-size:11px;color:var(--sub)}
.met .val{font-size:15px;font-weight:600;margin-top:2px}
.pe5{background:#fff7ed;border:1px solid #fde68a}
.action{margin-top:2px;background:#eef7f0;border-radius:10px;padding:10px 14px;font-size:13px;color:#33503a;border-left:4px solid var(--ok)}
.footer{margin-top:16px;background:var(--card);border:1px solid var(--line);border-radius:16px;padding:20px 28px;font-size:13px;color:var(--sub);line-height:1.8}
.footer h3{color:var(--ink);font-size:15px;margin-bottom:8px}
.err{background:#fdf0ef;color:#b0322b;border-radius:8px;padding:8px 12px;margin-top:12px;font-size:13px}
@media(max-width:600px){.metrics{grid-template-columns:repeat(2,1fr)}}
"""

def fmt_pct(v, digits=1, suffix="%"):
    if v is None: return "—"
    return f"{v:+.{digits}f}{suffix}" if isinstance(v,(int,float)) and v!=0 else f"{v:.{digits}f}{suffix}"

def render_row(r):
    sig = r["sig_key"]
    chg_cls = "up" if r["chg_pct"] >= 0 else "down"
    chg_s = f"{r['chg_pct']:+.2f}%"
    def m(lab, val, cls="", vcol=""):
        style = f' style="color:{vcol}"' if vcol else ""
        return f'<div class="met{cls}"><div class="lab">{lab}</div><div class="val"{style}>{val}</div></div>'
    # PE5y 分位 → 主锚, 放第一位, 高中低着色
    pe5_block = "—"
    pe5_cls = ""
    if r["pe5_pct"] is not None:
        p = r["pe5_pct"]
        pe5_cls = " pe5"
        vcol = "var(--down)" if p >= 90 else ("var(--warn)" if p >= 70 else "var(--ok)")
        pe5_block = (f'{p:.0f}% <span style="font-size:12px;color:var(--sub)">'
                     f'(PE{r["pe5_cur"]}, {r["pe5_lo"]}~{r["pe5_hi"]})</span>')
        pe5_html = f'<div class="met{pe5_cls}"><div class="lab">PE5y 分位 <b>主锚</b></div><div class="val" style="color:{vcol};font-size:18px">{pe5_block}</div></div>'
    else:
        pe5_html = '<div class="met"><div class="lab">PE5y 分位</div><div class="val">—</div></div>'
    # PB 分位(天天基金10y口径; 5y无数据源) — 顶部已显示现价, 此处替换为 PB 分位
    if r.get("pb10y") is not None:
        pbv = r["pb10y"]
        pbcol = "var(--down)" if pbv >= 90 else ("var(--warn)" if pbv >= 70 else "var(--ok)")
        pbval = f"{r['pb']:.2f}" if r.get("pb") is not None else "—"
        pb_html = (f'<div class="met pe5"><div class="lab">PB10y 分位</div>'
                   f'<div class="val" style="color:{pbcol};font-size:15px">{pbv:.0f}% '
                   f'<span style="font-size:12px;color:var(--sub)">(PB{pbval})</span></div></div>')
    else:
        pb_html = '<div class="met"><div class="lab">PB10y 分位</div><div class="val">—</div></div>'
    roe_html = m("ROE", f"{r['roe']:.1f}%" if r.get('roe') is not None else "—")
    metrics = (
        pe5_html +
        pb_html +
        m("近5日", fmt_pct(r["chg5"])) +
        m("近20日", fmt_pct(r["chg20"])) +
        m("20日BIAS", f"{r['bias20']:+.2f}%" if r["bias20"] is not None else "—") +
        m("距1年高", fmt_pct(r["dd_hi"])) +
        m("MA20", f"{r['ma20']:.3f}") +
        m("5日均额", f"{r['daily_yi']:.2f}亿") +
        m("目标10%/15%", f"{r['target10']:.2f}/{r['target15']:.2f}") +
        roe_html
    )
    return f"""
<div class="card">
  <div class="top">
    <div>
      <div class="name">{r['name']}</div>
      <div class="code">{r['etf_code']}</div>
      <div class="price">{r['price']:.3f}</div>
      <div class="chg {chg_cls}">{chg_s}</div>
    </div>
    <div class="badge {sig}">{SIG_LABEL.get(sig, sig)}</div>
  </div>
  <div class="metrics">{metrics}</div>
  <div class="action"><b>现在该怎么做：</b>{ACTIONS.get(sig, "暂观望")}</div>
</div>"""

def build_html(cfg, rows, errs, kline_date):
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    cards = "\n".join(render_row(r) for r in rows)
    err_html = f'<div class="err">⚠ 部分标的数据异常：{"；".join(errs)}</div>' if errs else ""
    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{cfg['title']}</title><style>{CSS}</style></head>
<body>
  <div class="header">
    <h1>{cfg['title']}</h1>
    <div class="meta">更新: {now} &nbsp;·&nbsp; K线截止: {kline_date or '—'} &nbsp;·&nbsp; 数据源: 中证官网(5年PE) + 天天基金(分位) + 腾讯行情/K线</div>
    <div class="note"><b>信号 = 技术面(回撤/MA/BIAS) × 估值面(PE 5年分位)</b> 双视角交叉。<br>「现在该怎么做」给的是可执行动作，判断前请结合估值分位(高位>90%别追高，<50%相对便宜)。本页不构成投资建议。</div>
  </div>
  <div class="grid">{cards}</div>
  {err_html}
  <div class="footer">
    <h3>指标速查</h3>
    <b>MA20</b> = 20日均线，现价在其上=趋势偏多，之下=转弱。<br>
    <b>BIAS(乖离率)</b> = (现价−MA20)/MA20，衡量涨跌是否过度：>10%过热，负值=超跌。<br>
    <b>PE5y 分位</b> = 当前PE在近5年所处百分位（用中证官网历史PE自算），判断贵贱的主锚。<br>
    <b>PB10y 分位</b> = 当前PB在近10年百分位（天天基金口径；中证官网无PB历史、暂无5y PB数据源）。<br>
    <b>PE5y 显示"—"</b> = 该指数非中证官网编制（如国证/恒生系，如港股通红利低波 159545），无5y PE分位，此时信号回退到 BIAS/回撤判断。<br>
    <b>目标价</b> = MA20 抬到 BIAS 达 10%/15% 的挂单价。<br>
    标的池可编辑 <code>etf-dashboard/watchlist.json</code> 增删品种后重跑 <code>python3 generate.py</code> 更新。
  </div>
</body></html>"""

if __name__ == "__main__":
    cfg, rows, errs = main()
    kline_date = rows[0]["date"] if rows else None
    html = build_html(cfg, rows, errs, kline_date)
    out = os.path.normpath(os.path.join(HERE, "../public/exports/etf-dashboard.html"))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(html)
    print(f"OK 已生成 {out} ({len(html)} 字节, {len(rows)} 只标的)")
    for r in rows:
        print(f"  {r['name']} -> [{SIG_LABEL.get(r['sig_key'])}]")