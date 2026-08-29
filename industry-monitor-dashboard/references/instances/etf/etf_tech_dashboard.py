#!/usr/bin/env python3
# ETF/指数 技术温度看板 v2 — 文章技术指标(N日涨跌/BIAS/目标价/成交额) + 估值分位 + 回撤 + 更新日期
# 数据源: 腾讯报价(实时价/涨跌/成交额) + 腾讯K线(BIAS/N日涨跌/回撤/MA) + 天天基金(估值分位/ROE)
import json, subprocess, urllib.request, urllib.parse, time
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont

HOME = "/root"
TT = "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"
def F(sz): return ImageFont.truetype(TT, sz)

API = "/root/.local/bin"

def ttskill(sid, act, body):
    r = subprocess.run(["ttskill","invoke",sid,"--action",act,"--body",json.dumps(body,ensure_ascii=False)],
        capture_output=True,text=True,timeout=90,env={"PATH":f"{API}:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"})
    try: return json.loads(r.stdout)["data"]["raw_result"]["body"]["data"]
    except: return {}

# ---------- 数据源 ----------
def tencent_quote(symbol):
    """symbol 如 sh512890 / sz159545。返回实时价/涨跌%/成交额。"""
    req = urllib.request.Request(f"https://qt.gtimg.cn/q={symbol}", headers={"User-Agent":"Mozilla/5.0"})
    raw = urllib.request.urlopen(req, timeout=15).read().decode("gbk", errors="replace")
    f = raw.split('"')[1].split("~")
    return {
        "name": f[1], "price": float(f[3]), "prev": float(f[4]),
        "chg": float(f[32]), "chg_pct": float(f[33]),
        # f36 = "现价/量/额(元)", f58 = 成交额(万)
    }

def tencent_kline(symbol, days=260, retry=3):
    """腾讯K线前复权, 返回 [(date, close, high, vol)]"""
    for i in range(retry):
        try:
            url = f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={symbol},day,,,{days},qfq"
            req = urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0","Referer":"https://gu.qq.com/"})
            d = json.loads(urllib.request.urlopen(req, timeout=15).read())
            data = d["data"][symbol]
            kl = data.get("qfqday") or data.get("day")
            if not kl: raise ValueError("no klines")
            return [(r[0], float(r[2]), float(r[3]), float(r[5])) for r in kl]  # date, close, high, vol
        except Exception as e:
            if i == retry-1: raise
            time.sleep(1)

def index_valuation(iid):
    d = ttskill("TTFUND_INDEX_INFO","query",{"index_id":iid})
    v = d.get("valuation") or {}
    return {"pe":v.get("pe_ttm"),"pe_pct":v.get("pe_percentile_10y"),
            "pb":v.get("pb"),"pb_pct":v.get("pb_percentile_10y"),"roe":v.get("roe")}

# ---------- 指标计算 ----------
def vbias(closes, price, n=20):
    """BIAS乖离率 = (现价 - MA(N)) / MA(N) * 100"""
    if len(closes) < n: return None
    ma = sum(closes[-n:]) / n
    return (price - ma) / ma * 100

def vi_change(closes, price, n):
    """近N个交易日涨跌幅(%)"""
    if len(closes) <= n: return None
    return (price / closes[-1-n] - 1) * 100

def build_watch(name, symbol, index_id):
    q = tencent_quote(symbol)
    kl = tencent_kline(symbol)
    closes = [c for _, c, _, _ in kl]
    highs  = [h for _, _, h, _ in kl]
    vols   = [v for _, _, _, v in kl]
    price = q["price"]
    # MA20
    ma20 = sum(closes[-20:])/20
    # 距一年高点回撤
    hi_1y = max(highs)
    dd_hi = (price/hi_1y - 1)*100
    # 估值
    val = index_valuation(index_id) if index_id else {}
    r = {"name": q["name"], "symbol": symbol, "price": price,
         "chg_pct": q["chg_pct"],
         "chg5": vi_change(closes, price, 5), "chg20": vi_change(closes, price, 20),
         "bias20": vbias(closes, price, 20),
         "vol_amt": sum(vols[-5:])/5,  # 5日均量(手)
         "dd_hi": dd_hi,
         # BIAS目标价: 使 BIAS 达 10%/15% 对应的价格 = MA20*(1+bias_target/100)
         "target10": ma20*1.10, "target15": ma20*1.15,
         "pe_pct": val.get("pe_pct"), "pb_pct": val.get("pb_pct"), "roe": val.get("roe"),
         "ma20": ma20,
         "date": kl[-1][0] if kl else ""}
    return r

# ---------- 看板数据 (个别指数, 用户关注) ----------
WATCH = [
    ("中证红利低波", "sh512890", "H30269"),
    ("中证红利",     "sh515180", "000922"),
    ("港股通央企红利","sh520900", None),   # 无估值分位
    # ("华夏红利低波", "sz159545", "H30269"), # 可加
]
rows = []
errs = []
for name, sym, iid in WATCH:
    try:
        rows.append(build_watch(name, sym, iid))
    except Exception as e:
        errs.append(f"{name}({sym}): {repr(e)[:80]}")

# 信号: 结合估值分位 + 回撤 (延续之前双条件)
def signal(r):
    if r.get("pe_pct") is not None and r["dd_hi"] is not None:
        if r["dd_hi"] <= -15 and r["pe_pct"] < 50: return "加仓", (60,200,120)
        elif r["dd_hi"] <= -10 and r["pe_pct"] < 70: return "分批", (140,200,80)
        elif r["dd_hi"] >= -3 or r["pe_pct"] > 95: return "过热/减", (240,90,80)
        return "观望", (160,170,190)
    if r.get("bias20") is not None:
        if r["bias20"] > 10: return "过热/减", (240,90,80)
        if r["bias20"] < -10: return "超跌", (60,200,120)
    return "观望", (160,170,190)
for r in rows:
    r["signal"], r["sig_col"] = signal(r)

# ---------- 渲染看板图 (亮色, 美化, 无遮挡) ----------
# 布局: 顶部标题+更新日期 → 每指数一个卡片 → 底部"怎么看/怎么做"指引
CARD_W, CARD_H = 1640, 300
HEADER = 150
W = 1720
img = Image.new("RGB", (W, HEADER + len(rows)*CARD_H + 400), "#edf2f7")
d = ImageDraw.Draw(img)

def txt(x, y, s, sz, fill=(40,50,70), anchor=None):
    d.text((x,y), s, font=F(sz), fill=fill)

# --- 顶部 ---
# 标题条
d.rounded_rectangle([30,24,W-30,110], radius=16, fill="#ffffff", outline=(215,224,235), width=1)
txt(50, 36, "ETF 红利 · 技术温度看板", 40, (25,35,55))
txt(50, 88, f"更新: {datetime.now():%Y-%m-%d %H:%M}   ·   K线截止: {rows[0]['date'] if rows else '-'}   ·   数据源: 腾讯行情 + 天天基金估值", 20, (110,122,140))
# 数据口径条
d.rounded_rectangle([30,120,W-30,146], radius=10, fill="#e6ecf4")
txt(50, 127, "信号 = 技术面(回撤/BIAS) x 估值面(PE/PB 十年分位) 双视角交叉，以下是此刻能直接执行的操作", 18, (90,102,120))

def met_block(x, y, lab, val, val_col=(40,55,80), accent=None):
    w, h = 224, 64
    d.rounded_rectangle([x, y, x+w, y+h], radius=12, fill="#ffffff", outline=(222,230,240), width=1)
    d.text((x+14, y+8), lab, font=F(15), fill=(125,136,155))
    d.text((x+14, y+32), val, font=F(26), fill=val_col)
    return x + w + 14

# --- 每指数卡片 ---
y = 166
ACTIONS = {
    "过热/减": "高位区：不追高。持有可先减 1/3 锁盈，回落到 BIAS<5% 或分位回落到 80% 以下再考虑回补",
    "分批":    "进入买点区：可分 3 批布局，每批 1/3，跌破 MA20 或回撤加深再加，跌破 -20% 停手",
    "加仓":    "深回撤+低估值双重买点：可一次性买入计划的 1/2，剩余按季分批，拿住等估值修复",
    "观望":    "数据不足或中性：暂不动，等回撤加深(>=10%)+估值分位回落，或打上估值数据再判断",
}
for r in rows:
    x0, y0 = 40, y
    # 卡片背景
    d.rounded_rectangle([x0,y0,x0+CARD_W,y0+CARD_H], radius=18, fill="#ffffff", outline=(215,224,235), width=1)
    # 左侧信息区 (名称/现价/涨跌/代码) - 加宽到340, 名称超长自适应缩字号
    nlen = len(r["name"])
    nsz = 28 if nlen <= 6 else (24 if nlen <= 8 else 21)
    d.rounded_rectangle([x0+18,y0+18,x0+340,y0+282], radius=14, fill="#f4f7fb")
    txt(x0+30, y0+34, r["name"], nsz, (30,40,60))
    txt(x0+30, y0+78, f"{r['price']:.3f}", 46, (20,30,50))
    chg_col = (200,70,60) if r["chg_pct"]<0 else (0,150,90)
    txt(x0+30, y0+136, f"今日 {r['chg_pct']:+.2f}%", 22, chg_col)
    txt(x0+30, y0+168, r["symbol"].upper(), 17, (140,150,170))
    # 信号徽章 (大字, 醒目)
    sig = r["signal"]; sc = r["sig_col"]
    bl = len(sig)*26+40
    d.rounded_rectangle([x0+30, y0+198, x0+30+bl, y0+248], radius=14, fill=sc, outline=sc, width=2)
    d.text((x0+46, y0+206), sig, font=F(24), fill=(40,50,70) if sum(sc) > 400 else (255,255,255))

    # 右侧指标区 (两排, 每排5格)
    cx, ryy = x0+365, y0+26
    daily_yi = r["vol_amt"] * 100 * r["price"] / 1e8
    pct_col = lambda v: ((200,70,60) if v<0 else (0,150,90)) if v is not None else (140,150,170)
    row1 = [
        ("近5日",   f"{r['chg5']:+.1f}%" if r['chg5'] else "-",   pct_col(r['chg5'])),
        ("近20日",  f"{r['chg20']:+.1f}%" if r['chg20'] else "-",  pct_col(r['chg20'])),
        ("20日BIAS",f"{r['bias20']:+.1f}%" if r['bias20'] else "-",pct_col(r['bias20'])),
        ("距1年高", f"{r['dd_hi']:+.1f}%", (200,90,70) if r['dd_hi']<=-10 else (40,55,80)),
        ("5日均额", f"{daily_yi:.2f}亿", (40,55,80)),
    ]
    row2 = [
        ("PE 十年分位", f"{r['pe_pct']:.0f}%" if r.get('pe_pct') is not None else "无数据", (220,130,50) if (r.get('pe_pct') or 0)>90 else (40,55,80)),
        ("PB 十年分位", f"{r['pb_pct']:.0f}%" if r.get('pb_pct') is not None else "无数据", (220,130,50) if (r.get('pb_pct') or 0)>90 else (40,55,80)),
        ("ROE",        f"{r['roe']:.1f}%" if r.get('roe') is not None else "-", (40,55,80)),
        ("MA20",       f"{r['ma20']:.3f}", (40,55,80)),
        ("目标10%/15%",f"{r['target10']:.2f}/{r['target15']:.2f}", (0,120,110)),
    ]
    for lab,val,vc in row1: cx = met_block(cx, ryy, lab, val, vc)
    cx, ryy = x0+365, y0+102
    for lab,val,vc in row2: cx = met_block(cx, ryy, lab, val, vc)

    # 操作建议条 (底部, 最关键)
    ay = y0 + 178
    d.rounded_rectangle([x0+365, ay, x0+CARD_W-18, ay+104], radius=12, fill="#f0f6ef", outline=(190,220,200), width=1)
    acc = r["sig_col"]
    d.rounded_rectangle([x0+365, ay, x0+365+10, ay+104], radius=6, fill=acc)
    txt(x0+388, ay+14, "[ 现在该怎么做 ]", 20, (60,90,70))
    txt(x0+388, ay+42, ACTIONS.get(r["signal"], "暂观望"), 18, (50,65,60))
    txt(x0+388, ay+76, "执行前先确认：估值分位来自 10 年历史，回撤按 260 日 K 线自算，见文末口径。", 15, (130,140,150))

    y += CARD_H + 18

# --- 底部：怎么看 / 操作总表 ---
by = y + 8
d.rounded_rectangle([30,by,W-30,by+335], radius=16, fill="#ffffff", outline=(215,224,235), width=1)
txt(50, by+20, "怎么看这张看板（三步 + 指标速查）", 26, (30,40,60))
steps = [
    ("STEP 1 先读信号徽章", "四个状态裕，右上角亮色大字直接告诉你此刻该加仓/分批/减/观望"),
    ("STEP 2 再看估值面", "PE/PB 十年分位：大于90% 历史高位别追高，小于50% 相对便宜；港股无分位就看回撤"),
    ("STEP 3 再看技术面", "回撤(距1年高)与 BIAS(乖离率)：回撤深是超跌机会，BIAS大于10% 短期过热"),
    ("STEP 4 指标速查", "MA20=20日均线(趋势位置); BIAS=(现价-MA20)/MA20, 衡量涨跌是否过度; 目标价=MA20抬到BIAS 10%/15%的挂单价"),
]
yy = by+58
for s1,s2 in steps:
    d.rounded_rectangle([50,yy,50+760,yy+58], radius=10, fill="#f6f8fb")
    txt(66, yy+6, s1, 19, (30,80,80)); txt(66, yy+32, s2, 15, (90,102,120))
    yy += 66
# 右侧操作总表
d.rounded_rectangle([830,by+48,W-40,by+322], radius=12, fill="#f6f8fb")
txt(850, by+62, "信号 - 动作速查", 19, (30,80,80))
acts = [
    ("[过热/减]", "持仓减 1/3 锁盈，不追高"),
    ("[分批]",    "分 3 批，每批 1/3，破 MA20 加"),
    ("[加仓]",    "深回撤+低估值，可重仓分批"),
    ("[观望]",    "数据不足，等回撤加深再定"),
]
ay2 = by+90
for a1,a2 in acts:
    txt(850, ay2, f"{a1}  -  {a2}", 18, (40,55,80)); ay2 += 38

out = "/tmp/etf_tech_dashboard.png"
try:
    img.save(out)
    print("SAVED", out)
except Exception as e:
    import traceback; traceback.print_exc()
    print("SAVE FAIL", repr(e))
print("尺寸:", img.size)
print(json.dumps([{k:r[k] for k in ("name","price","chg_pct","chg5","chg20","bias20","dd_hi","target10","target15","pe_pct","pb_pct","roe","ma20","signal")} for r in rows], ensure_ascii=False, indent=1))