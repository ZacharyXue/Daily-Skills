#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从 generate.py 的数据层读取并生成 HTML 看板页面."""
import json, os, sys, datetime, re

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
.grid{display:flex;flex-direction:column;gap:12px}
.card{margin:0}
.card>summary{display:block;background:var(--card);border:1px solid var(--line);border-radius:14px;padding:14px 20px;cursor:pointer;list-style:none;position:relative}
.card>summary::-webkit-details-marker{display:none}
.card>summary::after{content:"▾";position:absolute;right:18px;top:16px;color:var(--sub);transition:.15s}
.card[open]>summary{border-radius:14px 14px 0 0}
.card[open]>summary::after{content:"▴"}
.srow{display:flex;align-items:center;gap:10px;flex-wrap:wrap;padding-right:24px}
.sname{font-size:17px;font-weight:700}
.scode{font-size:12px;color:var(--sub)}
.sconcl{font-size:13px;color:#4b5563;margin-top:7px;line-height:1.6;padding-right:24px}
.dot-sig{width:10px;height:10px;border-radius:50%;flex:none}
.dot-sig.add{background:var(--ok)} .dot-sig.dca{background:var(--warn)}
.dot-sig.hot{background:var(--hot)} .dot-sig.dip{background:var(--down)} .dot-sig.watch{background:var(--watch)}
.cbody{background:var(--card);border:1px solid var(--line);border-top:none;border-radius:0 0 14px 14px;padding:16px 20px 18px;display:flex;flex-direction:column;gap:12px}
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
.insight{margin-top:12px;border-left:3px solid #2c6ee8;background:#f7f9fd;border-radius:8px;padding:10px 14px;font-size:13px;line-height:1.75}
.iv{margin:3px 0;color:#374151}
.ivk{display:inline-block;min-width:46px;font-weight:700;color:#1f2937;margin-right:4px}
.iv.take{color:#111827}
.about{margin-top:10px;border:1px solid var(--line);border-radius:8px;padding:8px 12px;font-size:12.5px;background:#fcfcfd}
.about summary{cursor:pointer;color:#2c6ee8;font-weight:600}
.abrow{display:flex;gap:8px;margin-top:6px;line-height:1.7;color:#4b5563}
.abk{flex:none;width:52px;color:#9ca3af;font-weight:600}
.abrow.caveat{color:#b45309}
.sharebar{margin-top:12px;display:flex;align-items:center;gap:12px;flex-wrap:wrap}
.sharebtn{display:inline-block;padding:7px 16px;background:#ff2e4d;color:#fff;border-radius:20px;font-size:13px;font-weight:600;text-decoration:none}
.sharehint{font-size:11.5px;color:#9ca3af}
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
    # 无数据就直接不渲染该格（用户要求：没有的估值指标去掉，别留一排「—」）
    pe5_html = ""
    if r["pe5_pct"] is not None:
        p = r["pe5_pct"]
        vcol = "var(--down)" if p >= 90 else ("var(--warn)" if p >= 70 else "var(--ok)")
        pe5_html = (f'<div class="met pe5"><div class="lab">PE5y 分位 <b>主锚</b></div>'
                    f'<div class="val" style="color:{vcol};font-size:18px">{p:.0f}% '
                    f'<span style="font-size:12px;color:var(--sub)">(PE{r["pe5_cur"]}, {r["pe5_lo"]}~{r["pe5_hi"]})</span></div></div>')
    pb_html = ""
    if r.get("pb10y") is not None:
        pbv = r["pb10y"]
        pbcol = "var(--down)" if pbv >= 90 else ("var(--warn)" if pbv >= 70 else "var(--ok)")
        pbval = f"{r['pb']:.2f}" if r.get("pb") is not None else "—"
        pb_html = (f'<div class="met pe5"><div class="lab">PB10y 分位</div>'
                   f'<div class="val" style="color:{pbcol};font-size:15px">{pbv:.0f}% '
                   f'<span style="font-size:12px;color:var(--sub)">(PB{pbval})</span></div></div>')
    # 历史最大回撤/当前回撤/回撤进度（核心，全资产显示）
    def dd_color(progress):
        # 回撤进度: <25% 安全, 25-50% 中, 50-75% 深, >=75% 极深(接近历史大底)
        if progress >= 0.75: return "var(--hot)"
        if progress >= 0.50: return "var(--warn)"
        if progress >= 0.25: return "var(--down)"
        return "var(--ok)"
    pro = r.get("dd_progress", 0)
    ddcol = dd_color(pro)
    # 回撤窗口：必须显示统计起点（外盘 2000 年起 / A股港股ETF 为 K线可得起点），
    # 否则「标普 -56.8%(26年窗口)」和「520600 -40.1%(1.8年窗口)」放一起会被误读成可比
    win = r.get("kline_start") or "—"
    maxdd_html = (f'<div class="met pe5"><div class="lab">历史最大回撤 '
                  f'<b>(自 {win} 起)</b></div>'
                  f'<div class="val" style="color:var(--down);font-size:15px">{r["max_dd"]:.1f}%'
                  f' <span style="font-size:12px;color:var(--sub)">({r.get("max_dd_date","")})</span></div></div>')
    curdd_html = (f'<div class="met pe5"><div class="lab">当前回撤</div>'
                  f'<div class="val" style="color:{ddcol};font-size:15px">{r["cur_dd"]:.1f}%'
                  f' <span style="font-size:12px;color:var(--sub)">(峰{r.get("cur_dd_peak_date","")})</span></div></div>')
    prog_html = (f'<div class="met pe5"><div class="lab">回撤进度 <b>(vs 历史最大)</b></div>'
                 f'<div class="val" style="color:{ddcol};font-size:15px">{pro*100:.0f}%'
                 f' <span style="font-size:12px;color:var(--sub)">(历史{abs(r["max_dd"]):.0f}%)</span></div></div>')
    metrics = (
        maxdd_html + curdd_html + prog_html +
        pe5_html +
        pb_html +
        m("近5日", fmt_pct(r["chg5"])) +
        m("近20日", fmt_pct(r["chg20"])) +
        m("20日BIAS", f"{r['bias20']:+.2f}%" if r["bias20"] is not None else "—") +
        m("距1年高", fmt_pct(r["dd_hi"])) +
        m("MA20", f"{r['ma20']:.3f}") +
        m("目标10%/15%", f"{r['target10']:.2f}/{r['target15']:.2f}")
    )
    # ---- 指数说明 + 位置解读 + 分享 ----
    def md(s):
        return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s or "")
    vw = r.get("views") or {}
    mt = r.get("meta") or {}
    if mt:
        about = ('<details class="about"><summary>指数是什么 · 怎么用（点开看编制与适用场景）</summary>'
                 '<div class="abrow"><span class="abk">指数</span>'
                 f'<span>{md(mt.get("full_name", ""))}　{md(mt.get("code", ""))}</span></div>'
                 '<div class="abrow"><span class="abk">编制</span>'
                 f'<span>{md(mt.get("what", ""))}</span></div>'
                 '<div class="abrow"><span class="abk">代表</span>'
                 f'<span>{md(mt.get("represent", ""))}</span></div>'
                 '<div class="abrow"><span class="abk">怎么用</span>'
                 f'<span>{md(mt.get("use_for", ""))}</span></div>'
                 + (f'<div class="abrow caveat"><span class="abk">注意</span>'
                    f'<span>{md(mt.get("caveat"))}</span></div>' if mt.get("caveat") else "")
                 + '</details>')
    else:
        about = ""
    insight = ('<div class="insight">'
               f'<div class="iv"><span class="ivk">估值面</span>{md(vw.get("valuation"))}</div>'
               f'<div class="iv"><span class="ivk">价格面</span>{md(vw.get("price"))}</div>'
               f'<div class="iv take"><span class="ivk">综合</span>{md(vw.get("take"))}</div>'
               '</div>') if (vw.get("valuation") or vw.get("price")) else ""
    share_code = (mt.get("share_slug") or r.get("etf_code") or r.get("name"))
    share_code = "".join(ch if (ch.isalnum() or ch in "-_") else "" for ch in str(share_code))
    share = (f'<div class="sharebar">'
             f'<a class="sharebtn" href="share/{share_code}.png" target="_blank" rel="noopener">'
             f'生成分享图 · 小红书竖版</a>'
             f'<span class="sharehint">点开新窗口 → 右键/长按保存图片，即可直接发布</span></div>')
    return f"""
<details class="card">
  <summary>
    <div class="srow">
      <span class="dot-sig {sig}"></span>
      <span class="sname">{r['name']}</span>
      <span class="scode">{r['etf_code']}</span>
      <span class="badge {sig}" style="margin-left:auto">{SIG_LABEL.get(sig, sig)}</span>
    </div>
    <div class="sconcl">{md(vw.get("take")) or "（无结论）"}</div>
  </summary>
  <div class="cbody">
    <div class="metrics">{metrics}</div>
    {insight}
    {about}
    <div class="action"><b>现在该怎么做：</b>{ACTIONS.get(sig, "暂观望")}</div>
    {share}
  </div>
</details>"""

def build_html(cfg, rows, errs, kline_date, src_status=None):
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    cards = "\n".join(render_row(r) for r in rows)
    err_html = f'<div class="err">⚠ 部分标的数据异常：{"；".join(errs)}</div>' if errs else ""
    # 数据源状态行（正确性铁律：可选源失效要明示，不静默）
    if src_status is None:
        src_status = {}
    tt_ok = src_status.get("ttfund_ok")
    tt_note = src_status.get("ttfund_note") or ""
    if tt_ok:
        src_line = "中证官网(PE5y 主锚) + 天天基金(PE/PB 10y 增强) + 腾讯行情/K线"
    else:
        src_line = ("中证官网(PE5y 主锚) + 腾讯行情/K线 "
                    f"<b style=\"color:#d97706\">｜PB10y 未取到：{tt_note or '天天基金源不可用'}（主锚 PE5y 不受影响）</b>")
    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{cfg['title']}</title><style>{CSS}</style></head>
<body>
  <div class="header">
    <h1>{cfg['title']}</h1>
    <div class="meta">更新: {now} &nbsp;·&nbsp; K线截止: {kline_date or '—'} &nbsp;·&nbsp; 数据源: {src_line}</div>
    <div class="note"><b>信号 = 技术面(回撤/MA/BIAS) × 估值面(PE 5年分位)</b> 双视角交叉。<br>「现在该怎么做」给的是可执行动作，判断前请结合估值分位(高位>90%别追高，<50%相对便宜)。本页不构成投资建议。</div>
  </div>
  <div class="grid">{cards}</div>
  {err_html}
  <div class="footer">
    <h3>指标速查</h3>
    <b>历史最大回撤</b> = 统计窗口内「峰值→谷底」的最大跌幅，<b>窗口起点写在每张卡片的指标名里</b>（外盘标普/纳指/黄金 = 2000 年起全历史；A股/港股 ETF = 数据源可得的 K 线起点，通常≈上市以来，最长 5 年左右）。<b>窗口不同的回撤数值不能直接横向比较</b>——26 年窗口的 -56.8% 与 2 年窗口的 -40.1% 不是一回事。<br>
    <b>回撤进度</b> = 当前回撤 ÷ 该标的历史最大回撤（同一窗口内自洽）；1.0 = 回到自身历史大底。<br>
    <b>MA20</b> = 20日均线，现价在其上=趋势偏多，之下=转弱。<br>
    <b>BIAS(乖离率)</b> = (现价−MA20)/MA20。<b>20 日口径参考区间</b>：±5% 内=常态、|BIAS|≥5%=偏大、≥8%=极端（公开口径：10 日乖离率 ±4% 常态/±8% 超买超卖，30 日 ±6%，20 日居中取值）。<br>
    <b>MA20 破位</b> = 现价跌破 20 日均线（标红），站上则标绿——破位代表短期趋势转弱，是「现在该怎么做」的前置过滤器。<br>
    <b>PE5y 分位</b> = 当前PE在近5年所处百分位（用中证官网 <code>indexCsiDsPe</code> 全历史PE自算），判断贵贱的主锚，<b>不依赖登录</b>。<br>
    <b>PE5y 区间</b> = 近5年 PE 的最低~最高，用于定位「当前 PE 离历史底部/顶部还有多远」。<br>
    <b>PB10y 分位</b> = 当前PB在近10年百分位（天天基金口径，可选增强源——该源 token 30 天过期，失效时显示「—」并在此行上方标注；中证官网无 PB 历史，全网免费源暂无 5y PB）。<br>
    <b>PE5y 显示"—"</b> = 该指数非中证官网编制（如国证成长100 980080、恒生系 987016），无历史PE，此时信号回退到 BIAS/回撤判断。<br>
    <b>目标价</b> = MA20 抬到 BIAS 达 10%/15% 的挂单价。<br>
    标的池可编辑 <code>etf-dashboard/watchlist.json</code> 增删品种后重跑 <code>python3 update.py</code> 更新。
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