#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ETF 看板 · 分享图生成器（小红书竖版 3:4，每只标的一张）
=====================================================
用法：python3 share_card.py [标的名称...]     # 不带参数=全部生成
产物：../public/exports/share/<slug>.png      （1240×1653，可直接发小红书）

封面框架（2026-10 借鉴成熟财报拆解号后重构）
  · 系列栏    「ETF 观察 NO.N ｜ 一图看懂一只标的」—— 编号建追更预期
  · 标签行    类型 / 估值状态 / 月份 —— 一眼看清是哪类资产、现在什么位置
  · 矛盾标题  对仗短句，把核心张力压成一句可截图单独传播的话（只讲位置，不给结论）
  · 数据区    PE(5y) 与 PB(10y) 并列；拿不到 PE 时降级 PE → PB → 回撤 三级
  · 五格数据  回撤 / 回撤进度 / 历史最大回撤 / MA20(破位标红) / BIAS(公开公认区间)
  · 该看什么  这只该盯哪个指标（中性观察指引，不含买卖建议）
  · 合规      数据来源 + 不构成投资建议 固定位

维护要点
  · 分位配色统一走 zone_of()，PE 与 PB 两列必须同色语义（曾出现 PB 缺「中位=蓝」档）
  · dd_progress 传来是小数（0.58），make_hook 内部归一化后再比较
  · PE/PB 背离时 generate.view() 会在估值面打 ⚠，本文件把该提示带进分享图
"""
import os
import sys
import html
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import generate  # noqa: E402
import indices_meta as IM  # noqa: E402

OUT_DIR = os.path.normpath(os.path.join(HERE, "../public/exports/share"))
CHROME = "/root/.cache/ms-playwright/chromium_headless_shell-1234/chrome-headless-shell-linux64/chrome-headless-shell"
W, H = 1240, 1653


def esc(s):
    return html.escape(str(s or ""))


def zone_of(pct):
    """分位 → 语义色 + 文案（PE / PB 共用，保证两列颜色语义一致）"""
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
    """页脚一句话（图内文字，与矛盾标题区分：这里说价格与估值的配合关系）"""
    p = r.get("pe5_pct")
    prog = (r.get("dd_progress") or 0) * 100
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


def make_hook(kind, p, pb, dd, prog):
    """矛盾标题：把核心张力压成一句对仗短句（封面用，可截图单独传播）。

    只描述「位置」，不给买卖结论——与看板「给各维度位置、不给综合结论」一致。
    借鉴成熟财报拆解号的封面写法：名词对名词 / 肯定对否定，14 字以内。

    ⚠️ prog（回撤进度）传来的是 0.58 这样的小数，必须先归一化再做百分数比较，
       否则「回撤进度 95%」会被判成「刚跌一点」（2026-10 实测踩过）。
    """
    if prog is not None and prog <= 1:
        prog = prog * 100

    if p is None:
        # 没有 PE 分位时：先用 PB（资产端）判断，再退回回撤口径
        if pb is not None:
            if pb >= 80 and (prog or 0) >= 50:
                return "资产不便宜，价格先跌"
            if pb >= 80:
                return "资产不便宜，价格还没跌"
            if pb <= 35 and (prog or 0) >= 50:
                return "资产便宜，价格也跌透了"
            if pb <= 35:
                return "资产便宜，价格还立着"
            return "资产不贵不便宜，价格走自己的"
        if dd is None:
            return "只有价格，没有估值分位"
        if prog is not None and prog >= 60:
            return "跌得够深，位置够低"
        if prog is not None and prog < 30:
            return "刚跌一点，位置还高"
        return "跌了一段，位置在中途"

    # 双高：盈利端和资产端都很贵
    if p >= 80 and pb is not None and pb >= 80:
        return "收息是真的，位置是贵的" if kind == "红利" else "盈利是真的，价格是贵的"
    # 背离：PE 便宜但 PB 不便宜 —— 盈利被压缩出来的「假便宜」
    if pb is not None and p <= 25 and pb >= 40:
        return "PE 的便宜，PB 的真相"
    # 双低
    if p <= 20 and (pb is None or pb <= 35):
        if prog is not None and prog >= 50:
            return "便宜是真的，跌也是真的"
        return "估值趴下了，价格还立着"
    if p >= 80:
        return "价不便宜，得靠盈利追上"
    if p >= 60:
        return "位置偏高，安全垫不厚"
    if p <= 35:
        return "位置不贵，等的是盈利"
    return "不上不下，最费耐心"


def build_card(r, idx=1):
    name = r["name"]
    code = r.get("etf_code") or ""
    mt = r.get("meta") or {}
    vw = r.get("views") or {}
    p = r.get("pe5_pct")
    pb = r.get("pb10y")
    col, zone_txt = zone_of(p)
    pbcol = zone_of(pb)[0] if pb is not None else "#6b7280"
    pbv = r.get("pb")
    pbtxt = ("PB %.2f" % pbv) if pbv is not None else "PB —"
    roetxt = (" · ROE %.1f%%" % r["roe"]) if r.get("roe") is not None else ""

    # ── 主数据区：PE → PB → 回撤 三级降级 ──
    if p is not None:
        big = f"{p:.0f}<span class='u'>%</span>"
        biglabel = "PE 估值分位（近 5 年）"
        bar = (f"<div class='bar'><div class='fill' style='width:{min(max(p,0),100):.1f}%;"
               f"background:linear-gradient(90deg,#16a34a,#0ea5e9 {max(0,60-p):.0f}%,#f59e0b {max(0,90-p):.0f}%,#e11d48)'></div>"
               f"<div class='mark' style='left:{min(max(p,0),100):.1f}%'></div></div>"
               f"<div class='barscale'><span>便宜 0%</span><span>贵 100%</span></div>")
        sub = (f"<div class='perow'>PE <b>{r.get('pe5_cur')}</b>　5 年区间 "
               f"<b>{r.get('pe5_lo')} ~ {r.get('pe5_hi')}</b></div>")
        if pb is not None:
            pb_block = (f"<div class='hcol side'><div class='k'>PB 估值分位（近 10 年）</div>"
                        f"<div class='big2' style='color:{pbcol}'>{pb:.0f}<span class='u'>%</span></div>"
                        f"<div class='zone' style='color:{pbcol}'>{pbtxt}{roetxt}</div></div>")
            hero_cls = "hero2"
        else:
            pb_block, hero_cls = "", "hero1"
    elif pb is not None:
        # 无 PE 分位：把 PB 提到主位（资产端口径，比只显示「无数据」有用得多）
        col = pbcol
        zone_txt = "近 10 年偏高区间" if pb >= 70 else ("近 10 年中位" if pb >= 40 else "近 10 年偏低区间")
        big = f"{pb:.0f}<span class='u'>%</span>"
        biglabel = "PB 估值分位（近 10 年）"
        bar = (f"<div class='bar'><div class='fill' style='width:{min(max(pb,0),100):.1f}%;"
               f"background:linear-gradient(90deg,#16a34a,#0ea5e9 {max(0,60-pb):.0f}%,#f59e0b {max(0,90-pb):.0f}%,#e11d48)'></div>"
               f"<div class='mark' style='left:{min(max(pb,0),100):.1f}%'></div></div>"
               f"<div class='barscale'><span>便宜 0%</span><span>贵 100%</span></div>")
        sub = (f"<div class='perow'>{pbtxt}{roetxt}　"
               f"<b>无公开历史 PE 序列</b>，此处为资产端（PB）口径</div>")
        pb_block, hero_cls = "", "hero1"
    else:
        ddv = r.get("cur_dd")
        big = f"{ddv:.1f}<span class='u'>%</span>" if ddv is not None else "—"
        biglabel = "当前回撤（距历史高点）"
        bar = ""
        sub = "<div class='perow'>无公开历史 PE 与 PB 序列，仅按价格位置</div>"
        pb_block, hero_cls = "", "hero1"

    # ── 五格数据（用户 2026-10 定：去掉现价/今日涨跌，把 MA20 放回来并标破位状态）──
    cells = []
    if r.get("cur_dd") is not None:
        cells.append(("当前回撤", f"{r['cur_dd']:.1f}%", "距历史高点", "#111827"))
    if r.get("dd_progress") is not None:
        cells.append(("回撤进度", f"{r['dd_progress']*100:.0f}%", "vs 历史最大", "#111827"))
    if r.get("max_dd") is not None:
        cells.append(("历史最大回撤", f"{r['max_dd']:.1f}%", str(r.get("max_dd_date") or ""), "#111827"))
    ma20, price_ = r.get("ma20"), r.get("price")
    if ma20 and price_:
        gap = (price_ / ma20 - 1) * 100
        if gap < 0:
            cells.append(("MA20 均线", f"{ma20:.3f}", "破位 %.2f%%" % gap, "#e11d48"))
        else:
            cells.append(("MA20 均线", f"{ma20:.3f}", "站上 +%.2f%%" % gap, "#16a34a"))
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
    # PE/PB 背离时（generate.view 在估值面打了 ⚠），把提示带进分享图，
    # 否则「位置解读：赔率与胜率都占优」会被当成「PE 低=可买」，而资产端可能根本不便宜
    warn_html = ""
    _val = (vw.get("valuation") or "")
    if "⚠" in _val:
        _seg = _val.split("⚠")[-1].strip().rstrip("。").split("　")[0].replace("**", "")
        warn_html = "<div class='warn'>⚠ " + esc(_seg) + "</div>"

    # ── 封面框架：系列栏 + 标签行 + 矛盾标题 + 观察点 ──
    oneline = mt.get("share_sub") or mt.get("represent") or ""
    stitle = mt.get("share_title") or name
    kind = IM.KIND.get(stitle, "指数")
    watch = IM.WATCH.get(stitle, "")
    hook = make_hook(kind, p, pb, r.get("cur_dd"), r.get("dd_progress"))
    if p is None:
        stat, statcol = ("仅有 PB 口径" if pb is not None else "仅有价格位置"), "#6b7280"
    elif p >= 80:
        stat, statcol = "估值偏高", "#e11d48"
    elif p >= 40:
        stat, statcol = "估值中位", "#0ea5e9"
    else:
        stat, statcol = "估值偏低", "#16a34a"
    today = generate.datetime.now().strftime("%Y-%m")
    tags_html = (f"<span class='tg'><i style='background:#0ea5e9'></i>{esc(kind)}</span>"
                 f"<span class='tg'><i style='background:{statcol}'></i>{esc(stat)}</span>"
                 f"<span class='tg'><i style='background:#94a3b8'></i>{esc(today)}</span>")
    watch_html = (f"<div class='watch'><span class='wk'>该看什么</span>"
                  f"<span class='wv'>{esc(watch)}</span></div>") if watch else ""

    return f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8"><style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{width:{W}px;height:{H}px;font-family:"PingFang SC","Microsoft YaHei","WenQuanYi Zen Hei",sans-serif;
background:#ffffff;color:#111827;overflow:hidden}}
.wrap{{width:{W}px;height:{H}px;padding:54px 68px 38px;display:flex;flex-direction:column}}
.series{{display:flex;align-items:center;gap:14px;font-size:25px;font-weight:800;color:#94a3b8;letter-spacing:1px}}
.series b{{color:#111827;font-size:27px}}
.tags{{display:flex;gap:14px;margin-top:18px;flex-wrap:wrap}}
.tg{{display:inline-flex;align-items:center;gap:10px;font-size:23px;font-weight:700;color:#374151;
background:#f1f5f9;border-radius:999px;padding:9px 22px}}
.tg i{{width:13px;height:13px;border-radius:50%;display:inline-block}}
h1{{font-size:70px;font-weight:800;margin-top:18px;letter-spacing:-1px;line-height:1.15}}
.hook{{font-size:52px;font-weight:800;color:#a16207;letter-spacing:-1px;line-height:1.2;
margin-top:18px;padding-left:28px;position:relative}}
.hook:before{{content:"";position:absolute;left:0;top:12px;bottom:12px;width:8px;border-radius:4px;
background:linear-gradient(180deg,#f5b942,#d97706)}}
.code{{font-size:28px;color:#9ca3af;margin-top:8px;font-weight:600}}
.oneline{{font-size:29px;color:#374151;margin-top:12px;line-height:1.45}}
.hero{{margin-top:26px;background:#f8fafc;border:2px solid #eef2f7;border-radius:28px;padding:32px 42px 26px}}
.hero .k{{font-size:28px;color:#6b7280;font-weight:600}}
.herocols{{display:flex;gap:44px;align-items:flex-start}}
.hcol{{flex:1;min-width:0}}
.hcol.side{{border-left:2px solid #eef2f7;padding-left:40px}}
.hero .big{{font-size:148px;font-weight:800;line-height:1;margin-top:8px;color:{col};letter-spacing:-4px}}
.hero .big .u{{font-size:68px;margin-left:6px}}
.hero .big2{{font-size:110px;font-weight:800;line-height:1;margin-top:16px;letter-spacing:-4px}}
.hero .big2 .u{{font-size:52px;margin-left:4px}}
.hero.hero2 .big{{font-size:126px}}
.zone{{font-size:30px;font-weight:700;color:{col};margin-top:10px}}
.bar{{position:relative;height:20px;border-radius:12px;background:#e9edf2;margin-top:18px;overflow:hidden}}
.bar .fill{{position:absolute;left:0;top:0;bottom:0;border-radius:12px}}
.bar .mark{{position:absolute;top:-7px;width:5px;height:36px;background:#111827;border-radius:3px;transform:translateX(-2px)}}
.barscale{{display:flex;justify-content:space-between;font-size:22px;color:#9ca3af;margin-top:10px}}
.perow{{font-size:27px;color:#4b5563;margin-top:12px}}
.perow b{{color:#111827}}
.grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin-top:22px}}
.cell{{background:#f8fafc;border-radius:20px;padding:16px 20px}}
.cell .ck{{font-size:23px;color:#9ca3af;font-weight:600}}
.cell .cv{{font-size:44px;font-weight:800;margin-top:4px;letter-spacing:-1px}}
.cell .cs{{font-size:21px;color:#b6bec9;margin-top:2px}}
.take{{margin-top:auto;background:#111827;color:#fff;border-radius:24px;padding:26px 32px}}
.take .tk{{font-size:24px;color:#9ca3af;font-weight:700;letter-spacing:2px}}
.take .tt{{font-size:32px;font-weight:700;line-height:1.45;margin-top:8px}}
.take .warn{{font-size:24px;color:#fbbf24;line-height:1.4;margin-top:12px}}
.watch{{display:flex;align-items:baseline;gap:14px;margin-top:16px;font-size:24px}}
.watch .wk{{flex:none;font-size:22px;font-weight:800;color:#0ea5e9;letter-spacing:2px}}
.watch .wv{{color:#4b5563;line-height:1.45}}
.foot{{display:flex;justify-content:space-between;align-items:flex-end;margin-top:20px;
font-size:22px;color:#b6bec9}}
.foot b{{color:#6b7280}}
</style></head><body><div class="wrap">
  <div class="series">ETF 观察 <b>NO.{idx:02d}</b> ｜ 一图看懂一只标的</div>
  <div class="tags">{tags_html}</div>
  <h1>{esc(name)}</h1>
  <div class="code">{esc(mt.get('full_name') or name)}{('　' + esc(code)) if code else ''}</div>
  <div class="oneline">{esc(oneline)}</div>
  <div class="hook">「{esc(hook)}」</div>

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
    {warn_html}
  </div>

  {watch_html}

  <div class="foot">
    <div><b>{esc(headline(r))}</b></div>
    <div>{esc(generate.datetime.now().strftime('%Y-%m-%d'))} · 数据：中证官网/腾讯行情/天天基金 · 不构成投资建议</div>
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
    for i, r in enumerate(rows, 1):
        if want and r["name"] not in want:
            continue
        code = (r.get("meta") or {}).get("share_slug") or r.get("etf_code") or r["name"]
        code = "".join(ch if (ch.isalnum() or ch in "-_") else "" for ch in str(code)) or "idx"
        p = os.path.join(OUT_DIR, "%s.png" % code)
        render(build_card(r, idx=i), p)
        print("✓", r["name"], "->", p, os.path.getsize(p) if os.path.exists(p) else "FAIL")


if __name__ == "__main__":
    main()
