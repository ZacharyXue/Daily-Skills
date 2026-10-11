#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ETF 看板 · 分享图生成器（小红书竖版 3:4，每只指数一张）
=====================================================
用法：python3 share_card.py [标的名称...]     # 不带参数=全部生成
产物：../public/exports/share/<etf_code>.png   （1240×1653，直接可发小红书）

设计原则
  · 图 > 字：一个主数字（估值分位）+ 一条区位条，3 秒能看懂
  · 观点跟着数据走：不写死，用 generate.view() 的实时解读
  · 无数据的指标直接不出现（不显示「—」）
  · 底部标数据来源与日期，避免被当成荐股（合规）
"""
import os
import sys
import json
import html
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import generate  # noqa: E402

OUT_DIR = os.path.normpath(os.path.join(HERE, "../public/exports/share"))
CHROME = "/root/.cache/ms-playwright/chromium_headless_shell-1234/chrome-headless-shell-linux64/chrome-headless-shell"
W, H = 1240, 1653


def esc(s):
    return html.escape(str(s or ""))


def zone_of(pct):
    """分位 → 语义色 + 文案"""
    if pct is None:
        return "#6b7280", "无估值数据"
    if pct >= 90:
        return "#e11d48", "近 5 年最贵的十分之一"
    if pct >= 70:
        return "#f59e0b", "近 5 年偏高区间"
    if pct >= 40:
        return "#0ea5e9", "近 5 年中位"
    if pct >= 10:
        return "#22a06b", "近 5 年偏低区间"
    return "#16a34a", "近 5 年最低区间"


def headline(r):
    """一句话结论（用于分享图的传播句）"""
    p = r.get("pe5_pct")
    prog = (r.get("dd_progress") or 0) * 100
    dd = r.get("cur_dd")
    if p is None:
        return "无历史 PE 数据，仅按价格位置判断"
    if p >= 90 and prog < 40:
        return "估值贴 5 年顶部，价格却还没跌下来"
    if p >= 90:
        return "估值仍贵，价格已经跌了一截"
    if p >= 70:
        return "估值偏高，安全边际不厚"
    if p < 20 and prog >= 50:
        return "估值落到 5 年低位，价格也跌透了"
    if p < 20:
        return "估值便宜，但价格还没怎么跌"
    return "估值与价格都在中位，没有极端"


def build_card(r):
    name = r["name"]
    code = r.get("etf_code") or ""
    mt = r.get("meta") or {}
    vw = r.get("views") or {}
    price = r.get("price")
    chg = r.get("chg_pct")
    p = r.get("pe5_pct")
    col, zone_txt = zone_of(p)
    # 主数字区
    if p is not None:
        big = f"{p:.0f}<span class='u'>%</span>"
        biglabel = "PE 估值分位（近 5 年）"
        bar = (f"<div class='bar'><div class='fill' style='width:{min(max(p,0),100):.1f}%;"
               f"background:linear-gradient(90deg,#16a34a,#0ea5e9 {max(0,60-p):.0f}%,#f59e0b {max(0,90-p):.0f}%,#e11d48)'></div>"
               f"<div class='mark' style='left:{min(max(p,0),100):.1f}%'></div></div>"
               f"<div class='barscale'><span>便宜 0%</span><span>贵 100%</span></div>")
        sub = (f"<div class='perow'>PE <b>{r.get('pe5_cur')}</b>　5 年区间 "
               f"<b>{r.get('pe5_lo')} ~ {r.get('pe5_hi')}</b></div>")
    else:
        ddv = r.get("cur_dd")
        big = f"{ddv:.1f}<span class='u'>%</span>" if ddv is not None else "—"
        biglabel = "当前回撤（距历史高点）"
        bar = ""
        sub = "<div class='perow'>该指数无公开历史 PE 序列</div>"
    # PB 分位（天天基金 10y 口径；有则与 PE 并列展示）
    pb = r.get("pb10y")
    if pb is not None:
        pbcol = "#e11d48" if pb >= 90 else ("#f59e0b" if pb >= 70 else "#22a06b" if pb >= 40 else "#16a34a")
        pbv = r.get("pb")
        pbtxt = ("PB %.2f" % pbv) if pbv is not None else "PB —"
        roetxt = (" · ROE %.1f%%" % r["roe"]) if r.get("roe") is not None else ""
        pb_block = (f"<div class='hcol side'><div class='k'>PB 估值分位（近 10 年）</div>"
                    f"<div class='big2' style='color:{pbcol}'>{pb:.0f}<span class='u'>%</span></div>"
                    f"<div class='zone' style='color:{pbcol}'>{pbtxt}{roetxt}</div></div>")
        hero_cls = "hero2"
    else:
        pb_block = ""
        hero_cls = "hero1"
    # 三格数据（用户 2026-10 定：去掉现价/今日涨跌，把 MA20 放回来并标破位状态）
    cells = []
    if r.get("cur_dd") is not None:
        cells.append(("当前回撤", f"{r['cur_dd']:.1f}%", "距历史高点", "#111827"))
    if r.get("dd_progress") is not None:
        cells.append(("回撤进度", f"{r['dd_progress']*100:.0f}%", "vs 历史最大", "#111827"))
    if r.get("max_dd") is not None:
        cells.append(("历史最大回撤", f"{r['max_dd']:.1f}%", str(r.get("max_dd_date") or ""), "#111827"))
    # MA20：站上/破位（跌破 MA20 = 破位→红；站上→绿）
    ma20, price_ = r.get("ma20"), r.get("price")
    if ma20 and price_:
        gap = (price_ / ma20 - 1) * 100
        if gap < 0:
            cells.append(("MA20 均线", f"{ma20:.3f}", "破位 %.2f%%" % gap, "#e11d48"))
        else:
            cells.append(("MA20 均线", f"{ma20:.3f}", "站上 +%.2f%%" % gap, "#16a34a"))
    # BIAS：按公开公认区间标注（10日 ±4% 常态/±8% 极端；30日 ±6%；20日居中取 ±5%/±8%）
    if r.get("bias20") is not None:
        b = r["bias20"]
        if abs(b) >= 8:
            btxt, bcol = "极端区（|BIAS|≥8%）", "#e11d48"
        elif abs(b) >= 5:
            btxt, bcol = "偏大（|BIAS|≥5%）", "#f59e0b"
        else:
            btxt, bcol = "常态区间（±5% 内）", "#16a34a"
        cells.append(("20日 BIAS", f"{b:+.2f}%", btxt, bcol))
    cells_html = "".join(
        f"<div class='cell'><div class='ck'>{esc(k)}</div>"
        f"<div class='cv' style='color:{col}'>{esc(v)}</div><div class='cs'>{esc(s)}</div></div>"
        for k, v, s, col in cells[:6])
    take = (vw.get("take") or "").replace("**", "")
    price_line = (vw.get("price") or "").replace("**", "")
    # 指数一句话定位
    oneline = mt.get("share_sub") or mt.get("represent") or ""
    return f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8"><style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{width:{W}px;height:{H}px;font-family:"PingFang SC","Microsoft YaHei","WenQuanYi Zen Hei",sans-serif;
background:#ffffff;color:#111827;overflow:hidden}}
.wrap{{width:{W}px;height:{H}px;padding:78px 76px 56px;display:flex;flex-direction:column}}
.tag{{display:inline-block;font-size:26px;font-weight:700;color:{col};background:{col}1a;
border-radius:999px;padding:10px 26px;align-self:flex-start;letter-spacing:1px}}
h1{{font-size:82px;font-weight:800;margin-top:30px;letter-spacing:-1px;line-height:1.15}}
.code{{font-size:30px;color:#9ca3af;margin-top:12px;font-weight:600}}
.oneline{{font-size:31px;color:#374151;margin-top:20px;line-height:1.5}}
.hero{{margin-top:44px;background:#f8fafc;border:2px solid #eef2f7;border-radius:32px;padding:46px 48px 38px}}
.hero .k{{font-size:28px;color:#6b7280;font-weight:600}}
.herocols{{display:flex;gap:44px;align-items:flex-start}}
.hcol{{flex:1;min-width:0}}
.hcol.side{{border-left:2px solid #eef2f7;padding-left:40px}}
.hero .big{{font-size:186px;font-weight:800;line-height:1;margin-top:8px;color:{col};letter-spacing:-4px}}
.hero .big .u{{font-size:84px;margin-left:6px}}
.hero .big2{{font-size:132px;font-weight:800;line-height:1;margin-top:16px;letter-spacing:-4px}}
.hero .big2 .u{{font-size:62px;margin-left:4px}}
.hero.hero2 .big{{font-size:158px}}
.zone{{font-size:30px;font-weight:700;color:{col};margin-top:10px}}
.bar{{position:relative;height:22px;border-radius:12px;background:#e9edf2;margin-top:26px;overflow:hidden}}
.bar .fill{{position:absolute;left:0;top:0;bottom:0;border-radius:12px}}
.bar .mark{{position:absolute;top:-7px;width:5px;height:36px;background:#111827;border-radius:3px;transform:translateX(-2px)}}
.barscale{{display:flex;justify-content:space-between;font-size:22px;color:#9ca3af;margin-top:10px}}
.perow{{font-size:29px;color:#4b5563;margin-top:16px}}
.perow b{{color:#111827}}
.grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:20px;margin-top:34px}}
.cell{{background:#f8fafc;border-radius:22px;padding:22px 24px}}
.cell .ck{{font-size:23px;color:#9ca3af;font-weight:600}}
.cell .cv{{font-size:48px;font-weight:800;margin-top:6px;letter-spacing:-1px}}
.cell .cs{{font-size:21px;color:#b6bec9;margin-top:2px}}
.take{{margin-top:auto;background:#111827;color:#fff;border-radius:26px;padding:34px 38px}}
.take .tk{{font-size:24px;color:#9ca3af;font-weight:700;letter-spacing:2px}}
.take .tt{{font-size:36px;font-weight:700;line-height:1.5;margin-top:12px}}
.foot{{display:flex;justify-content:space-between;align-items:flex-end;margin-top:40px;
font-size:22px;color:#b6bec9}}
.foot b{{color:#6b7280}}
</style></head><body><div class="wrap">
  <div class="tag">{esc(zone_txt)}</div>
  <h1>{esc(name)}</h1>
  <div class="code">{esc(mt.get('full_name') or name)}{('　' + esc(code)) if code else ''}</div>
  <div class="oneline">{esc(oneline)}</div>

  <div class="hero {hero_cls}">
    <div class="herocols">
      <div class="hcol main">
        <div class="k">{biglabel}</div>
        <div class="big">{big}</div>
        <div class="zone">{esc(zone_txt)}</div>
      </div>
      {pb_block}
    </div>
    {bar}
    {sub}
  </div>

  <div class="grid">{cells_html}</div>

  <div class="take">
    <div class="tk">位置解读</div>
    <div class="tt">{esc(take) or esc(price_line)}</div>
  </div>

  <div class="foot">
    <div><b>{esc(headline(r))}</b></div>
    <div>{esc(generate.datetime.now().strftime('%Y-%m-%d'))} · 数据：中证官网/腾讯行情 · 不构成投资建议</div>
  </div>
</div></body></html>"""


def render(html_str, path):
    tmp = "/tmp/_share_card.html"
    open(tmp, "w", encoding="utf-8").write(html_str)
    subprocess.run([CHROME, "--no-sandbox", "--disable-gpu", "--hide-scrollbars",
                    f"--window-size={W},{H}", f"--screenshot={path}", "file://" + tmp],
                   capture_output=True, timeout=120)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    cfg, rows, errs, src_status = generate.main()
    want = sys.argv[1:]
    for r in rows:
        if want and r["name"] not in want:
            continue
        code = (r.get("meta") or {}).get("share_slug") or r.get("etf_code") or r["name"]
        code = "".join(ch if (ch.isalnum() or ch in "-_") else "" for ch in str(code)) or "idx"
        p = os.path.join(OUT_DIR, "%s.png" % code)
        render(build_card(r), p)
        print("✓", r["name"], "->", p, os.path.getsize(p) if os.path.exists(p) else "FAIL")


if __name__ == "__main__":
    main()
