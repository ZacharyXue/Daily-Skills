#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 style-rotation 看板数据渲染成图表化 PIL 概览图（无浏览器时发飞书用）
v3 宽松化：画布 1500x2580、卡片间隔 44、行距放宽、字号降一档，消除文字交叉。
图表：半圆配置仪表 / 信号贡献 tornado / 行业分布对比条 / 多期收益分组柱状 / 估值区位条+温度条
"""
import json, os, math
from PIL import Image, ImageDraw, ImageFont

FONT = "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"
HERE = "/root/zach-skills/industry-monitor-dashboard/references/instances/style-rotation"
D = json.load(open(os.path.join(HERE, "cache", "dashboard_data.json")))

W, H = 1500, 2720
img = Image.new("RGB", (W, H), "#f4f6fa")
dr = ImageDraw.Draw(img)

def F(sz):
    return ImageFont.truetype(FONT, sz)

def txt(x, y, s, sz=21, fill="#2c3e50"):
    dr.text((x, y), s, font=F(sz), fill=fill)

def card(x, y, w, h, title=None):
    dr.rounded_rectangle([x, y, x + w, y + h], radius=16, fill="#ffffff",
                         outline="#e1e6ef", width=1)
    if title:
        txt(x + 26, y + 18, title, 25, "#1f2d3d")
        dr.rounded_rectangle([x + 26, y + 56, x + w - 26, y + 58], radius=1, fill="#eef1f5")
    return y + 74

G, V = "#e0563f", "#3a7bd5"
GAP = 44

# ================= header =================
txt(40, 28, "成长 vs 价值 · 风格轮动 & 配置比例", 36, "#1f2d3d")
txt(40, 84, "成长100(980080) vs 价值100(980081)  |  更新 " + D["meta"]["updated"], 21, "#7f8c9b")

e = D["engine"]
g, v = D["growth"], D["value"]
gd = D.get("growth_diff") or {}
gw = e["growth_w_pct"]

# ================= A. 半圆配置仪表 (h=400) =================
y0 = 140
top = card(40, y0, W - 80, 400, "目标配置比例（轮动引擎 v1）")
cx, cyc, R = 430, top + 130, 150
box = [cx - R, cyc - R, cx + R, cyc + R]
dr.arc(box, 0, 180, fill="#e8ebf0", width=30)
start_a = 180 - 180 * gw / 100.0
dr.arc(box, max(start_a, 0), 180, fill=G, width=30)
for pct, lab in [(0, "0"), (25, "25"), (50, "50"), (75, "75"), (100, "100")]:
    a = math.radians(180 - 1.8 * pct)
    x0t = cx + (R + 34) * math.cos(a)
    y0t = cyc + (R + 34) * math.sin(a)
    txt(x0t - 9, y0t - 9, lab, 16, "#7f8c9b")
txt(cx - 92, cyc - 56, "%.1f%%" % gw, 44, G)
txt(cx - 30, cyc - 2, "成长", 19, "#7f8c9b")
# 右侧说明区（两列更宽松）
rx = cx + R + 96
txt(rx, top + 20, "价值  %.1f%%" % (100 - gw), 27, V)
txt(rx, top + 62, "偏移  %+0.1f pt" % e["bias_pts"], 23, "#1f2d3d")
txt(rx, top + 104, "基准  50/50    限幅  [40, 70]", 20, "#7f8c9b")
txt(rx, top + 138, "信号并聚>=2 才明显偏移，否则收敛±12pt", 20, "#7f8c9b")
con = e["confluence"]
con_s = "偏成长" if e["bias_pts"] > 2 else ("偏价值" if e["bias_pts"] < -2 else "均衡")
txt(60, top + 290, "引擎结论：%s    (并聚力 %d上 / %d下，阈值 %d)" % (con_s, con["pushing_up"], con["pushing_down"], con["threshold"]), 24,
    G if con_s == "偏成长" else (V if con_s == "偏价值" else "#1f2d3d"))

# ================= B. 信号贡献 tornado (h=540) =================
y0 += GAP + 400
top = card(40, y0, W - 80, 540, "信号贡献（正=推高成长权重, 负=推高价值权重）")
s = e["signals"]
items = [
    ("盈利增速差\n(第一性)", 30 * 0.25 * s.get("s_growth", 0),
     "成长+%.0f%% vs 价值%+.0f%% 净利同比" % (gd.get("profit_growth_pct", 0), gd.get("profit_value_pct", 0)) if gd.get("ok") else "未接入"),
    ("ROE 中枢差\n(长期锚)", 30 * 0.30 * s.get("s_roe", 0),
     "成长 11.0 vs 价值 8.5 (pp)"),
    ("估值价差\n(安全边际)", 30 * 0.25 * s.get("s_valuation", 0),
     "PE比 %.1fx，分位差 %+.1fpp" % (s.get("pe_ratio"), s.get("pe_pct_diff_pp"))),
    ("行业拥挤度\n(电子58%)", 30 * 0.12 * s.get("s_crowding", 0),
     "前3行业占比74%，风控刹车"),
    ("温和动量\n(仅预警)", 30 * 0.08 * s.get("s_momentum", 0),
     "成长6m %+.1f%% vs 价值 %+.1f%%" % (g.get("return_6m"), v.get("return_6m"))),
]
axis_x = 720
left_edge, right_edge = 260, 1160
max_len = max(abs(i[1]) for i in items) * 1.25 or 1
row_h = 78
yy = top + 22
for name, contrib, note in items:
    bar_len = abs(contrib) / max_len * (right_edge - axis_x)
    color = G if contrib >= 0 else V
    dir_s = "偏成长" if contrib > 0.2 else ("偏价值" if contrib < -0.2 else "中性")
    if contrib >= 0:
        dr.rounded_rectangle([axis_x, yy + 14, axis_x + bar_len, yy + 40], radius=10, fill=color)
        txt(axis_x + bar_len + 14, yy + 14, "%+.1fpt" % contrib, 21, color)
    else:
        dr.rounded_rectangle([axis_x - bar_len, yy + 14, axis_x, yy + 40], radius=10, fill=color)
        txt(axis_x - bar_len - 86, yy + 14, "%+.1fpt" % contrib, 21, color)
    # 名称两行 + 说明一行
    lines = name.split("\n")
    txt(60, yy, lines[0], 22, "#1f2d3d")
    txt(60, yy + 26, lines[1], 18, "#8a94a3")
    txt(60, yy + 54, note, 17, "#aab2bc")
    txt(1170, yy + 16, dir_s, 21, color)
    yy += row_h
dr.rectangle([axis_x, top + 14, axis_x + 2, top + 14 + 5 * row_h], fill="#c7cdd6")
txt(axis_x - 8, top + 14 + 5 * row_h + 10, "0", 17, "#7f8c9b")
txt(150, top + 14 + 5 * row_h + 10, "<- 偏价值", 17, V)
txt(900, top + 14 + 5 * row_h + 10, "偏成长 ->", 17, G)

# ================= C. 行业分布对比条 (h=460) =================
y0 += GAP + 540
top = card(40, y0, W - 80, 460, "行业分布（自由流通权重；成长 vs 价值）")
def ind_block(label, items, x0, y, color, wmax=230, barx=160, colw=540):
    txt(x0, y, label, 23, "#1f2d3d")
    yy = y + 44
    for it in items[:6]:
        nm = it["industry"]
        w = it["weight_pct"]
        yoy = it["yoy"] if it.get("yoy") is not None else 0
        barlen = min(w / 60.0, 1.0) * wmax
        dr.rounded_rectangle([x0 + barx, yy, x0 + barx + barlen, yy + 24], radius=7, fill=color)
        txt(x0, yy, nm, 20, "#2c3e50")
        label_s = "%.1f%%" % w + (("  yoy%+.0f%%" % yoy) if yoy else "")
        txt(x0 + barx + barlen + 8, yy, label_s, 16, "#7f8c9b")
        yy += 52
ind_block("成长100", g["top_industries"], 60, top + 8, G, 230, 160, 540)
ind_block("价值100", v["top_industries"], 720, top + 8, V, 200, 140, 500)

# ================= D. 多期收益分组柱状 (h=440) =================
y0 += GAP + 460
top = card(40, y0, W - 80, 440, "历史收益对比（成长 vs 价值）")
periods = [("1月", g.get("return_1m"), v.get("return_1m")),
           ("3月", g.get("return_3m"), v.get("return_3m")),
           ("6月", g.get("return_6m"), v.get("return_6m")),
           ("1年", g.get("return_1y"), v.get("return_1y"))]
ymax = 40
plot_x, plot_y, plot_w, plot_h = 140, top + 44, 1020, 270
zero_y = plot_y + plot_h * (ymax / (ymax - (-ymax)))
def ypos(val):
    return zero_y - (val / (2 * ymax)) * plot_h
dr.line([plot_x, zero_y, plot_x + plot_w, zero_y], fill="#c7cdd6", width=2)
for tick in [-30, -15, 0, 15, 30]:
    ty = ypos(tick)
    dr.line([plot_x - 8, ty, plot_x, ty], fill="#c7cdd6")
    txt(plot_x - 46, ty - 9, "%d%%" % tick, 15, "#7f8c9b")
n = len(periods)
group_w = plot_w / n
bar_w = 42
for i, (lab, gv, vv) in enumerate(periods):
    gv = gv or 0; vv = vv or 0
    gcx = plot_x + group_w * i + group_w * 0.28
    vcx = plot_x + group_w * i + group_w * 0.72
    for cx0, val, color in [(gcx, gv, G), (vcx, vv, V)]:
        if val >= 0:
            dr.rounded_rectangle([cx0 - bar_w / 2, ypos(val), cx0 + bar_w / 2, zero_y], radius=7, fill=color)
        else:
            dr.rounded_rectangle([cx0 - bar_w / 2, zero_y, cx0 + bar_w / 2, ypos(val)], radius=7, fill=color)
        txt(cx0 - 26, ypos(val) - 28 if val >= 0 else ypos(val) + 8, "%+.0f" % val, 17, color)
    txt(plot_x + group_w * i + group_w * 0.5 - 12, zero_y + 22, lab, 20, "#566573")
# 右侧长期 + 图例
rx = plot_x + plot_w + 34
txt(rx, plot_y, "成长 3y %+.0f%%" % (g.get("return_3y") or 0), 20, G)
txt(rx, plot_y + 36, "价值 3y %+.0f%%" % (v.get("return_3y") or 0), 20, V)
txt(rx, plot_y + 80, "成长 5y %+.0f%%" % (g.get("return_5y") or 0), 18, "#7f8c9b")
txt(rx, plot_y + 114, "价值 5y %+.0f%%" % (v.get("return_5y") or 0), 18, "#7f8c9b")
dr.rounded_rectangle([plot_x + plot_w - 190, plot_y - 10, plot_x + plot_w - 150, plot_y + 10], radius=3, fill=G)
txt(plot_x + plot_w - 180, plot_y + 14, "成长", 16, G)
dr.rounded_rectangle([plot_x + plot_w - 120, plot_y - 10, plot_x + plot_w - 80, plot_y + 10], radius=3, fill=V)
txt(plot_x + plot_w - 110, plot_y + 14, "价值", 16, V)

# ================= E. 温度 + 估值区位 (h=450) =================
y0 += GAP + 440
top = card(40, y0, W - 80, 450, "技术温度 & 估值区位")
def track(x0, y0p, w, pct_g, pct_v, lo=-10, hi=10):
    txt(x0 + 52, y0p - 6, "%+d~%+d" % (lo, hi), 14, "#aab2bc")
    dr.rounded_rectangle([x0 + 52, y0p, x0 + 52 + w, y0p + 12], radius=6, fill="#eef0f4")
    pos_g = x0 + 52 + (pct_g - lo) / (hi - lo) * w
    pos_v = x0 + 52 + (pct_v - lo) / (hi - lo) * w
    dr.ellipse([pos_g - 9, y0p - 5, pos_g + 9, y0p + 17], fill=G)
    dr.ellipse([pos_v - 9, y0p - 5, pos_v + 9, y0p + 17], fill=V)
    dr.rounded_rectangle([x0 + 52 + w + 14, y0p - 1, x0 + 52 + w + 48, y0p + 13], radius=3, fill="#eef0f4")
    txt(x0 + 52 + w + 20, y0p - 2, "0", 15, "#7f8c9b")
def row(label, gv, vv, sub):
    txt(70, label_y, label, 21, "#1f2d3d")
    txt(400, label_y, "%+0.1f" % gv, 22, G)
    txt(520, label_y, "%+0.1f" % vv, 22, V)
    txt(640, label_y, sub, 18, "#7f8c9b")
label_y = top + 18
row("BIAS20 乖离", g["etf"]["bias20"], v["etf"]["bias20"], "超过+10过热 / 低于-10超跌")
track(60, label_y + 38, 615, g["etf"]["bias20"], v["etf"]["bias20"], -12, 12)
label_y += 104
row("60日回撤", g["etf"]["drawdown60"], v["etf"]["drawdown60"], "成长ETF深度回调")
track(60, label_y + 38, 615, g["etf"]["drawdown60"], v["etf"]["drawdown60"], -35, 0)
label_y += 104
row("52周位置", g["etf"]["pos52"], v["etf"]["pos52"], "0=低位 100=高位")
track(60, label_y + 38, 615, g["etf"]["pos52"], v["etf"]["pos52"], 0, 100)

# 右侧估值：PE / PB 各画独立 band（单一标记点，避免 73/76 重叠）
def one_band(x0, y0b, w, pct, label, color):
    pct = pct or 0
    txt(x0, y0b - 2, label, 17, "#566573")
    z1 = x0 + w * 0.30; z2 = x0 + w * 0.70
    dr.rounded_rectangle([x0, y0b + 14, z1, y0b + 28], radius=4, fill="#2e9e5b")
    dr.rounded_rectangle([z1, y0b + 14, z2, y0b + 28], radius=2, fill="#e3b23c")
    dr.rounded_rectangle([z2, y0b + 14, x0 + w, y0b + 28], radius=4, fill="#e0563f")
    pos = x0 + w * pct / 100.0
    dr.ellipse([pos - 8, y0b + 10, pos + 8, y0b + 32], fill=color)
    txt(pos + 14, y0b + 12, "%.0f%%" % pct, 16, color)
def val_head(x0, y0b, label, pe_abs):
    txt(x0, y0b, label, 22, "#1f2d3d")
    txt(x0 + 470, y0b, "PE %.1fx" % pe_abs, 17, "#7f8c9b")
val_head(862, top + 18, "成长100", g.get("pe_ttm") or 0)
one_band(862, top + 44, 500, g.get("pe_pct_10y"), "PE 10y分位", "#c0392b")
one_band(862, top + 92, 500, g.get("pb_pct_10y"), "PB 10y分位", "#2c6fd0")
val_head(862, top + 148, "价值100", v.get("pe_ttm") or 0)
one_band(862, top + 174, 500, v.get("pe_pct_10y"), "PE 10y分位", "#c0392b")
one_band(862, top + 222, 500, v.get("pb_pct_10y"), "PB 10y分位", "#2c6fd0")
txt(862, top + 300, "解读: 两指数 PE10y 分位都在 76~78%\n(均落红区高估)，绝对 PE 差 5.9 倍", 18, "#b03a2e")

txt(40, H - 52, "数据源: 天天基金TTFUND_INDEX_INFO + 腾讯ETF K线 + 成分净利聚合  |  正确性>及时性", 17, "#a8b0bc")

os.makedirs("/tmp", exist_ok=True)
out = "/tmp/style-rotation-summary.png"
img.save(out)
print(out)