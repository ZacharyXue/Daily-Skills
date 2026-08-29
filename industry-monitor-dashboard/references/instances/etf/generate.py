#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ETF 红利 · 技术温度看板 生成脚本
用法:  cd etf-dashboard && python3 generate.py
产出:  public/exports/etf-dashboard.html  (手动触发更新)

数据源:
  1) 中证官网 csindex index-perf   -> 历史PE(peg字段), 算 <5年分位>
  2) 天天基金 TTFUND_INDEX_INFO    -> 指数档案 + PE/PB 十年分位 + ROE
  3) 腾讯行情 qt.gtimg.cn          -> ETF 实时价/涨跌
  4) 腾讯K线 web.ifzq.gtimg.cn     -> 算 MA20/BIAS20/回撤/N日涨跌/成交额

标的池: 编辑同目录 watchlist.json 的 watchlist 数组, 加/换品种即可.
"""
import json, subprocess, urllib.request, time, sys, os
from datetime import datetime

UA = {"User-Agent": "Mozilla/5.0"}
API = "/root/.local/bin"
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.environ.get("ETF_OUT") or os.path.normpath(os.path.join(HERE, "../public/exports/etf-dashboard.html"))
def _router_root():
    d = HERE
    for _ in range(8):
        if os.path.isdir(os.path.join(d, "data-source-router")): return d
        d = os.path.dirname(d)
    return os.environ.get("ZACH_SKILLS", "/root/zach-skills")
sys.path.insert(0, os.path.join(_router_root(), "data-source-router"))
import data_router as DSR   # 统一数据层: 行情/K线/中证PE/天天基金 全部走 router, 见 data-source-router
YEARS = 5  # 估值分位窗口(年)

# ---------- 数据获取 ----------
def http_json(url, timeout=15, retry=3):
    last = None
    for i in range(retry):
        try:
            req = urllib.request.Request(url, headers=UA)
            return json.loads(urllib.request.urlopen(req, timeout=timeout).read())
        except Exception as e:
            last = e; time.sleep(1)
    raise last

def csindex_pe_pct(index_code):
    """中证官网历史PE(peg) -> 5年分位 (走 data-source-router 统一取数)"""
    try:
        d = DSR.get('cn_csindex_pe', index_code=index_code)[0]
        if not (d and d.get("ok")): return None
        return {"cur_pe": d.get("pe_ttm"), "pct": d.get("pe_pct_5y"),
                "lo": None, "hi": None, "n": d.get("n")}
    except Exception:
        return None

def ttskill_index_info(index_id):
    """天天基金 TTFUND_INDEX_INFO -> PE/PB 10年分位+ROE (走 router)"""
    try:
        d = DSR.get('cn_ttfund_index', index_id=index_id)[0]
        if not (d and d.get("ok")): return {}
        return {"name": None, "pe10y": d.get("pe_pct_10y"), "pb10y": d.get("pb_pct_10y"),
                "pb": None, "roe": d.get("roe"), "pe_ttm": d.get("pe_ttm")}
    except Exception:
        return {}

def tencent_quote(symbol):
    """腾讯实时行情: 现价/涨跌幅 (走 router)"""
    try:
        d = DSR.get('cn_stock_quote', symbol=symbol)[0]
        return {"name": d.get("name"), "price": d.get("price"), "chg_pct": d.get("change_pct")}
    except Exception as e:
        raise ValueError(f"腾讯行情失败 {symbol}: {e}")

def tencent_kline(symbol, days=300):
    """腾讯前复权K线 -> [(date, close, high, vol)] (走 router)"""
    kl = DSR.get('cn_stock_kline', symbol=symbol, count=days)[0]
    return [(r["date"], r["close"], r["high"], r["volume"]) for r in kl]

# ---------- 指标计算 ----------
def vbias(closes, price, n=20):
    if len(closes) < n: return None
    ma = sum(closes[-n:]) / n
    return (price - ma) / ma * 100

def vi_change(closes, price, n):
    if len(closes) <= n: return None
    return (price / closes[-1-n] - 1) * 100

def build_row(w):
    q = tencent_quote(w["etf_symbol"])
    kl = tencent_kline(w["etf_symbol"])
    closes = [c for _, c, _, _ in kl]
    highs  = [h for _, _, h, _ in kl]
    vols   = [v for _, _, _, v in kl]
    price = q["price"]
    ma20 = sum(closes[-20:]) / 20
    dd_hi = (price / max(highs) - 1) * 100
    daily_yi = (sum(vols[-5:]) / 5) * 100 * price / 1e8  # 5日均成交额(亿)
    val = ttskill_index_info(w["ttfund_index"])
    pe5 = csindex_pe_pct(w["csindex"])
    row = {
        "name": q["name"], "etf_code": w["etf_code"], "price": price,
        "chg_pct": q["chg_pct"],
        "chg5": vi_change(closes, price, 5), "chg20": vi_change(closes, price, 20),
        "bias20": vbias(closes, price, 20), "dd_hi": dd_hi, "ma20": ma20,
        "daily_yi": daily_yi,
        "pe5_cur": pe5["cur_pe"] if pe5 else None,
        "pe5_pct": pe5["pct"] if pe5 else None,
        "pe5_lo": pe5["lo"] if pe5 else None, "pe5_hi": pe5["hi"] if pe5 else None,
        "pe10y": val.get("pe10y"), "pb10y": val.get("pb10y"),
        "pb": val.get("pb"), "roe": val.get("roe"),
        "target10": ma20 * 1.10, "target15": ma20 * 1.15,
        "date": kl[-1][0] if kl else "",
    }
    return row

def signal(r):
    # 5年PE分位为主, 优先; 无则退回回撤/BIAS
    if r["pe5_pct"] is not None and r["dd_hi"] is not None:
        if r["dd_hi"] <= -15 and r["pe5_pct"] < 50: return "加仓", "add"
        if r["dd_hi"] <= -10 and r["pe5_pct"] < 70: return "分批", "dca"
        if r["dd_hi"] >= -5 and r["pe5_pct"] >= 90: return "过热/减", "hot"
        if r["pe5_pct"] > 95: return "过热/减", "hot"
        if r["dd_hi"] <= -15 and r["pe5_pct"] < 70: return "加仓", "add"
        return "观望", "watch"
    if r["bias20"] is not None:
        if r["bias20"] > 10: return "过热/减", "hot"
        if r["bias20"] < -10: return "超跌", "dip"
    return "观望", "watch"

ACTIONS = {
    "add":   "深回撤+低估值双重买点：可一次性买入计划的 1/2，剩余按季分批，拿住等估值修复。",
    "dca":   "进入买点区：可分 3 批布局，每批 1/3，跌破 MA20 或回撤加深再加，跌破 -20% 停手。",
    "hot":   "高位区：不追高。持有可先减 1/3 锁盈，回落 PE5y<80% 或 BIAS<5% 再考虑回补。",
    "dip":   "短线超跌：可轻仓博反弹，首次反弹到 MA20 附近减仓，不恋战。",
    "watch": "数据不足或中性：暂不动，等回撤加深(≥10%) + 5年PE分位回落再看。",
}
SIG_LABEL = {"add":"加仓","dca":"分批","hot":"过热/减","dip":"超跌","watch":"观望"}

def main():
    from concurrent.futures import ThreadPoolExecutor, as_completed
    with open(os.path.join(HERE, "watchlist.json"), encoding="utf-8") as fh:
        cfg = json.load(fh)
    def work(w):
        try:
            r = build_row(w); r["signal"], r["sig_key"] = signal(r)
            return r, None
        except Exception as e:
            return None, f"{w['name']}: {repr(e)[:80]}"
    rows, errs = [], []
    with ThreadPoolExecutor(max_workers=6) as ex:
        futs = [ex.submit(work, w) for w in cfg["watchlist"]]
        for f in as_completed(futs):
            r, e = f.result()
            if e: errs.append(e)
            else: rows.append(r)
    # 保持 watchlist 原始顺序 (as_completed 无序)
    order = {w["etf_code"]: i for i, w in enumerate(cfg["watchlist"])}
    rows.sort(key=lambda r: order.get(r["etf_code"], 99))
    return cfg, rows, errs

if __name__ == "__main__":
    # 只测试数据层, HTML生成在 generate_part2 里(单独文件避免超大)
    cfg, rows, errs = main()
    print(json.dumps({"rows": rows, "errs": errs}, ensure_ascii=False, indent=1))