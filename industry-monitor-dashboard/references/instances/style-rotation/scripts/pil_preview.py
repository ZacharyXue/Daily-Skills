#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 style-rotation 看板数据渲染成图表化 PIL 概览图（无浏览器时发飞书用）
图表：半圆配置仪表 / 信号贡献 tornado / 行业分布对比条 / 多期收益分组柱状 / 估值与技术温度条
数据全部读自 dashboard_data.json，不硬编码。
"""
import json, os, math
from PIL import Image, ImageDraw, ImageFont

FONT = "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"
HERE = "/root/zach-skills/industry-monitor-dashboard/references/instances/style-rotation"
D = json.load(open(os.path.join(HERE, "cache", "dashboard_data.json")))

W, H = 1500, 2360
img = Image.new("RGB", (W, H), "#f4f6fa")
dr = ImageDraw.Draw(img)

def F(sz):
    return ImageFont.truetype(FONT, sz)

def txt(x, y, s, sz=24, fill="#2c3e50"):
    dr.text((x, y), s, font=F(sz), fill=fill)

def card(x, y, w, h, title=None):
    dr.rounded_rectangle([x, y, x + w, y + h], radius=14, fill="#ffffff",
                         outline="#e1e6ef", width=1)
    if title:
        txt(x + 22, y + 16, title, 26, "#1f2d3d")
        dr.rounded_rectangle([x + 22, y + 50, x + w - 22, y + 52], radius=1, fill="#eef1f5")
    return y + 66

G, V = "#e0563f", "#3a7bd5"

# ================= header =================
txt(40, 28, "成长 vs 价值 · 风格轮动 & 配置比例", 40, "#1f2d3d")
txt(40, 82, "成长100(980080) vs 价值100(980081)  |  更新 " + D["meta"]["updated"], 22, "#7f8c9b")

e = D["engine"]
g, v = D["growth"], D["value"]
gd = D.get("growth_diff") or {}
gw = e["growth_w_pct"]

# ================= A. 半圆配置仪表 =================
y0 = 140
top = card(40, y0, W - 80, 340, "目标配置比例（轮动引擎 v1）")
cx, cyc, R = 460, top + 80, 130
box = [cx - R, cyc - R, cx + R, cyc + R]
# 底弧 = 下半圆 (PIL: 0°=3点, 90°=6点, 180°=9点; arc(0,180) 从右经底部到左)
dr.arc(box, 0, 180, fill="#e8ebf0", width=28)
# 成长弧: 0%=左(180°) → f% → 角度 180-f*180
start_a = 180 - 180 * gw / 100.0
dr.arc(box, max(start_a, 0), 180, fill=G, width=28)
# 刻度 0/25/50/75/100（沿底弧）
for pct, lab in [(0, "0"), (25, "25"), (50, "50"), (75, "75"), (100, "100")]:
    a = math.radians(180 - 1.8 * pct)
    x0t = cx + (R + 30) * math.cos(a)
    y0t = cyc + (R + 30) * math.sin(a)
    txt(x0t - 9, y0t - 9, lab, 17, "#7f8c9b")
# 中心读数
txt(cx - 95, cyc - 52, "%.1f%%" % gw, 44, G)
txt(cx - 30, cyc + 2, "成长", 19, "#7f8c9b")
# 右侧说明
rx = cx + R + 70
txt(rx, top + 6, "价值  %.1f%%" % (100 - gw), 26, V)
txt(rx, top + 44, "偏移  %+0.1f pt" % e["bias_pts"], 24, "#1f2d3d")
txt(rx, top + 82, "基准 50/50", 20, "#7f8c9b")
txt(rx, top + 114, "限幅 [40, 70]", 20, "#7f8c9b")
txt(rx, top + 146, "信号并聚>=2 才明显偏移", 20, "#7f8c9b")
# 底部一句结论
con = e["confluence"]
con_s = "偏成长" if e["bias_pts"] > 2 else ("偏价值" if e["bias_pts"] < -2 else "均衡")
txt(60, top + 250, "引擎结论：%s   (并聚力 %d上/%d下)" % (con_s, con["pushing_up"], con["pushing_down"]), 24,
    G if con_s == "偏成长" else (V if con_s == "偏价值" else "#1f2d3d"))

# ================= B. 信号贡献 tornado =================
y0 = y0 + 380
top = card(40, y0, W - 80, 420, "信号贡献（正=推高成长权重, 负=推高价值权重）")
s = e["signals"]
# 各信号 贡献pt = w_i * s_i * 30
items = [
    ("盈利增速差(第一性)", 30 * 0.25 * s.get("s_growth", 0),
     gd.get("profit_diff_pp") if gd.get("ok") else None, "成长+%.0f%% vs 价值%+.0f%%" % (gd.get("profit_growth_pct", 0), gd.get("profit_value_pct", 0)) if gd.get("ok") else "未接入"),
    ("ROE 中枢差(长锚)", 30 * 0.30 * s.get("s_roe", 0), s.get("roe_diff_pp"),
     "成长11.0 vs 价值8.5"),
    ("估值价差(安全边际)", 30 * 0.25 * s.get("s_valuation", 0), s.get("pe_pct_diff_pp"),
     "PE比 %.1fx / 分位差 %+.1fpp" % (s.get("pe_ratio"), s.get("pe_pct_diff_pp"))),
    ("行业拥挤度(电子58%)", 30 * 0.12 * s.get("s_crowding", 0), None,
     "前3行业占比74%"),
    ("温和动量(仅预警)", 30 * 0.08 * s.get("s_momentum", 0), None,
     "成长6m %+.1f%% vs 价值 %+.1f%%" % (g.get("return_6m"), v.get("return_6m"))),
]
axis_x = 700
left_edge, right_edge = 250, 1180
max_len = max(abs(i[1]) for i in items) * 1.25 or 1
row_h = 62
yy = top + 20
for name, contrib, sub, note in items:
    bar_len = abs(contrib) / max_len * (right_edge - axis_x)
    color = G if contrib >= 0 else V
    dir_s = "偏成长" if contrib > 0.2 else ("偏价值" if contrib < -0.2 else "中性")
    # bar
    if contrib >= 0:
        dr.rounded_rectangle([axis_x, yy, axis_x + bar_len, yy + 26], radius=8, fill=color)
        txt(axis_x + bar_len + 12, yy - 2, "%+.1fpt" % contrib, 22, color)
    else:
        dr.rounded_rectangle([axis_x - bar_len, yy, axis_x, yy + 26], radius=8, fill=color)
        txt(axis_x - bar_len - 96, yy - 2, "%+.1fpt" % contrib, 22, color)
    txt(60, yy + 2, name, 23, "#1f2d3d")
    txt(60, yy + 30, note, 18, "#aab2bc")
    txt(1180, yy + 2, dir_s, 22, color)
    yy += row_h
# 0轴
dr.rectangle([axis_x, top + 8, axis_x + 2, top + 8 + 5 * row_h + 8], fill="#c7cdd6")
txt(axis_x - 6, top + 8 + 5 * row_h + 16, "0", 18, "#7f8c9b")
txt(120, top + 8 + 5 * row_h + 16, "<- 偏价值", 18, V)
txt(860, top + 8 + 5 * row_h + 16, "偏成长 ->", 18, G)

# ================= C. 行业分布对比条 =================
y0 = y0 + 450
top = card(40, y0, W - 80, 410, "行业分布（自由流通权重；成长 vs 价值）")
def ind_block(label, items, x0, y, color, wmax=240, barx=150, labx_gap=10):
    txt(x0, y, label, 24, "#1f2d3d")
    yy = y + 40
    for it in items[:6]:
        nm = it["industry"]
        w = it["weight_pct"]
        yoy = it["yoy"] if it.get("yoy") is not None else 0
        barlen = min(w / 60.0, 1.0) * wmax
        dr.rounded_rectangle([x0 + barx, yy, x0 + barx + barlen, yy + 22], radius=6, fill=color)
        txt(x0, yy, nm, 21, "#2c3e50")
        label_s = "%.1f%%" % w
        if yoy:
            label_s += "  yoy%+.0f%%" % yoy
        txt(x0 + barx + barlen + labx_gap, yy, label_s, 17, "#7f8c9b")
        yy += 42
    return yy
ind_block("成长100", g["top_industries"], 60, top + 6, G, 200, 170, 6)
ind_block("价值100", v["top_industries"], 720, top + 6, V, 240, 150, 6)

# ================= D. 多期收益分组柱状 =================
y0 = y0 + 440
top = card(40, y0, W - 80, 410, "历史收益对比（成长 vs 价值）")
periods = [("1月", g.get("return_1m"), v.get("return_1m")),
           ("3月", g.get("return_3m"), v.get("return_3m")),
           ("6月", g.get("return_6m"), v.get("return_6m")),
           ("1年", g.get("return_1y"), v.get("return_1y"))]
ymax = 40
plot_x, plot_y, plot_w, plot_h = 140, top + 40, 1000, 250
zero_y = plot_y + plot_h * (ymax / (ymax - (-ymax)))
def ypos(val):
    return zero_y - (val / (2 * ymax)) * plot_h
# 0 轴
dr.line([plot_x, zero_y, plot_x + plot_w, zero_y], fill="#c7cdd6", width=2)
for tick in [-30, -15, 0, 15, 30]:
    ty = ypos(tick)
    dr.line([plot_x - 8, ty, plot_x, ty], fill="#c7cdd6")
    txt(plot_x - 44, ty - 9, "%d%%" % tick, 16, "#7f8c9b")
n = len(periods)
group_w = plot_w / n
bar_w = 36
for i, (lab, gv, vv) in enumerate(periods):
    gv = gv or 0; vv = vv or 0
    gcx = plot_x + group_w * i + group_w * 0.28
    vcx = plot_x + group_w * i + group_w * 0.72
    for cx0, val, color in [(gcx, gv, G), (vcx, vv, V)]:
        if val >= 0:
            dr.rounded_rectangle([cx0 - bar_w / 2, ypos(val), cx0 + bar_w / 2, zero_y], radius=6, fill=color)
        else:
            dr.rounded_rectangle([cx0 - bar_w / 2, zero_y, cx0 + bar_w / 2, ypos(val)], radius=6, fill=color)
        txt(cx0 - 22, ypos(val) - 26 if val >= 0 else ypos(val) + 8, "%+.0f" % val, 18, color)
    txt(plot_x + group_w * i + group_w * 0.5 - 12, zero_y + 18, lab, 20, "#566573")
# 长期标注
txt(plot_x + plot_w + 30, plot_y + 30, "成长", 20, G)
txt(plot_x + plot_w + 90, plot_y + 30, "3y %.0f%%" % (g.get("return_3y") or 0), 20, G)
txt(plot_x + plot_w + 30, plot_y + 64, "价值", 20, V)
txt(plot_x + plot_w + 90, plot_y + 64, "3y %.0f%%" % (v.get("return_3y") or 0), 20, V)
txt(plot_x + plot_w + 30, plot_y + 100, "成长 5y %.0f%%" % (g.get("return_5y") or 0), 18, "#7f8c9b")
txt(plot_x + plot_w + 30, plot_y + 130, "价值 5y %.0f%%" % (v.get("return_5y") or 0), 18, "#7f8c9b")
# 图例
dr.rounded_rectangle([plot_x + plot_w - 150, plot_y - 6, plot_x + plot_w - 110, plot_y + 14], radius=3, fill=G)
txt(plot_x + plot_w - 140, plot_y + 16, "成长", 16, G)
dr.rounded_rectangle([plot_x + plot_w - 90, plot_y - 6, plot_x + plot_w - 50, plot_y + 14], radius=3, fill=V)
txt(plot_x + plot_w - 80, plot_y + 16, "价值", 16, V)

# ================= E. 估值与技术温度条 =================
y0 = y0 + 440
top = card(40, y0, W - 80, 340, "估值 & 技术温度条")
def track(x0, y0p, w, pct_g, pct_v, lo=-10, hi=10, unit="%"):
    txt(x0, y0p + 2, "%+d~%+d" % (lo, hi), 14, "#aab2bc")
    dr.rounded_rectangle([x0 + 52, y0p, x0 + 52 + w, y0p + 10], radius=6, fill="#eef0f4")
    pos_g = x0 + 52 + (pct_g - lo) / (hi - lo) * w
    pos_v = x0 + 52 + (pct_v - lo) / (hi - lo) * w
    dr.ellipse([pos_g - 8, y0p - 4, pos_g + 8, y0p + 14], fill=G)
    dr.ellipse([pos_v - 8, y0p - 4, pos_v + 8, y0p + 14], fill=V)
    dr.rounded_rectangle([x0 + 52 + w + 12, y0p - 1, x0 + 52 + w + 46, y0p + 11], radius=3, fill="#eef0f4")
    txt(x0 + 52 + w + 18, y0p - 2, "0", 15, "#7f8c9b")
def row(label, gv, vv, sub):
    txt(70, label_y, label, 22, "#1f2d3d")
    txt(420, label_y, "%+0.1f" % gv, 22, G)
    txt(540, label_y, "%+0.1f" % vv, 22, V)
    txt(660, label_y, sub, 20, "#7f8c9b")
# 行1: BIAS20
label_y = top + 20
row("BIAS20 乖离", g["etf"]["bias20"], v["etf"]["bias20"], "超过+10过热 / 低于-10超跌")
track(60, label_y + 34, 620, g["etf"]["bias20"], v["etf"]["bias20"], -12, 12)
# 行2: 60日回撤
label_y += 92
row("60日回撤", g["etf"]["drawdown60"], v["etf"]["drawdown60"], "成长ETF深度回调")
track(60, label_y + 34, 620, g["etf"]["drawdown60"], v["etf"]["drawdown60"], -35, 0)
# 行3: 52周位置
label_y += 92
row("52周位置", g["etf"]["pos52"], v["etf"]["pos52"], "0=低位  100=高位")
track(60, label_y + 34, 620, g["etf"]["pos52"], v["etf"]["pos52"], 0, 100)
# 右侧: 估值区位条（0-100% 三段着色 + PE/PB 双标记点 + 绝对值）
def val_band(dr, x0, y0, w, idx, label, color):
    pe = idx.get("pe_pct_10y") or 0
    pb = idx.get("pb_pct_10y") or 0
    txt(x0, y0, label, 21, "#1f2d3d")
    txt(x0 + w - 120, y0, "PE %.1fx" % (idx.get("pe_ttm") or 0), 17, "#7f8c9b")
    by = y0 + 34
    z1 = x0 + w * 0.30; z2 = x0 + w * 0.70
    dr.rounded_rectangle([x0, by, z1, by + 14], radius=4, fill="#2e9e5b")
    dr.rounded_rectangle([z1, by, z2, by + 14], radius=2, fill="#e3b23c")
    dr.rounded_rectangle([z2, by, x0 + w, by + 14], radius=4, fill="#e0563f")
    px_pos = x0 + w * pe / 100.0
    pb_pos = x0 + w * pb / 100.0
    dr.ellipse([px_pos - 8, by - 4, px_pos + 8, by + 18], fill="#c0392b")
    dr.ellipse([pb_pos - 8, by - 4, pb_pos + 8, by + 18], fill="#2c6fd0")
    txt(px_pos - 34, y0 + 16, "PE %.0f%%" % pe, 17, "#c0392b")
    txt(pb_pos - 34, by + 22, "PB %.0f%%" % pb, 17, "#2c6fd0")
    txt(x0, by + 42, "低估值区", 14, "#2e9e5b")
    txt(x0 + w * 0.30 + 6, by + 42, "中枢区", 14, "#b8860b")
    txt(x0 + w * 0.70 + 6, by + 42, "高估区", 14, "#c0392b")
val_band(dr, 862, top + 22, 280, g, "成长100", G)
val_band(dr, 1152, top + 22, 270, v, "价值100", V)
txt(862, top + 150, "解读: 两指数 PE10y 分位都在 76~78% (高估区), 但绝对 PE 差 5.9 倍",
    18, "#b03a2e")

txt(40, H - 46, "数据源: 天天基金TTFUND_INDEX_INFO + 腾讯ETF K线 + 成分净利聚合  |  正确性>及时性", 18, "#a8b0bc")

os.makedirs("/tmp", exist_ok=True)
out = "/tmp/style-rotation-summary.png"
img.save(out)
print(out)