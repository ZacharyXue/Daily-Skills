#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fetch.py — 成长vs价值风格轮动看板 取数层
标的：成长=国证成长100(980080, 易方达成长ETF 159259) / 价值=国证价值100(980081, 易方达价值ETF 159263)
数据全部走 data-source-router（TTFUND 估值/ROE/行业分布 + 腾讯 ETF K线→技术温度）+ 可选盈利增速差。
输出 cache/dashboard_data.json（供 render_html.py）。
"""
import sys, os, json, datetime, math
sys.path.insert(0, "/root/zach-skills/data-source-router")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import data_router as DSR
import engine

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "cache", "dashboard_data.json")

GROWTH = {"name": "成长100", "index_code": "980080", "ttfund_id": "成长100",
          "etf_symbol": "sz159259", "etf_name": "易方达成长ETF"}
VALUE = {"name": "价值100", "index_code": "980081", "ttfund_id": "价值100",
         "etf_symbol": "sz159263", "etf_name": "易方达价值ETF"}


def _fin():
    def g(v, d=None):
        if v is None:
            return d
        try:
            return None if v in (None, "—", "-") else float(v)
        except (TypeError, ValueError):
            return d
    return g


def _technical(symbol):
    """ETF 短期技术温度：MA20/BIAS/回撤/N日涨跌/52周位置。历史短(次新ETF)则如实标注。"""
    kline, __, ___, ____ = DSR.get("cn_stock_kline", symbol=symbol, count=400)
    if not isinstance(kline, list) or not kline:
        return {"ok": False, "note": "K线获取失败"}
    closes = [k["close"] for k in kline]
    last = closes[-1]
    ma20 = sum(closes[-20:]) / 20
    ma60 = sum(closes[-60:]) / 60
    bias20 = (last - ma20) / ma20 * 100
    hi60 = max(closes[-60:])
    dd60 = (last - hi60) / hi60 * 100
    n5 = (last - closes[-6]) / closes[-6] * 100
    n20 = (last - closes[-21]) / closes[-21] * 100 if len(closes) > 21 else None
    lo52, hi52 = min(closes), max(closes)
    pos52 = (last - lo52) / (hi52 - lo52) * 100 if hi52 > lo52 else None
    return {"ok": True, "close": round(last, 3), "ma20": round(ma20, 3), "ma60": round(ma60, 3),
            "bias20": round(bias20, 1), "drawdown60": round(dd60, 1),
            "chg_5d": round(n5, 1), "chg_20d": round(n20, 1) if n20 is not None else None,
            "pos52": round(pos52, 1) if pos52 is not None else None,
            "n_bars": len(closes), "first_date": kline[0]["date"], "last_date": kline[-1]["date"]}


def _ttfund(idx):
    d, src, meta, tier = DSR.get("cn_ttfund_index", index_id=idx["ttfund_id"])
    if not d.get("ok"):
        return {"ok": False, "note": d.get("note", "TTFUND失败")}
    f = _fin()
    top = [{"industry": x.get("industry"), "weight_pct": f(x.get("weight_pct")),
            "yoy": f(x.get("yoy")), "mktcap_yi": f(x.get("mktcap_yi"))}
           for x in (d.get("top_industries") or [])]
    return {"ok": True, "index_code": d.get("index_code"), "point": f(d.get("point")),
            "pe_ttm": f(d.get("pe_ttm")), "pe_pct_10y": f(d.get("pe_pct_10y")),
            "pb_pct_10y": f(d.get("pb_pct_10y")), "roe": f(d.get("roe")),
            "ytd": f(d.get("ytd")), "return_1m": f(d.get("return_1m")),
            "return_3m": f(d.get("return_3m")), "return_6m": f(d.get("return_6m")),
            "return_1y": f(d.get("return_1y")), "return_3y": f(d.get("return_3y")),
            "return_5y": f(d.get("return_5y")),
            "top_industries": top, "industry_count": d.get("industry_count")}


def _growth_diff():
    """盈利增速差(成长-价值)：等权聚合成分净利润同比/营收同比。
    依赖 lokal 预计算脚本 growth_precompute.py 产物 cache/growth_diff.json; 缺失→中性。"""
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "cache", "growth_diff.json")
    if os.path.exists(p):
        try:
            with open(p) as fh:
                return json.load(fh)
        except Exception:
            pass
    return None


def main():
    growth = _ttfund(GROWTH)
    value = _ttfund(VALUE)
    g_tech = _technical(GROWTH["etf_symbol"])
    v_tech = _technical(VALUE["etf_symbol"])
    gd = _growth_diff()

    data = {
        "meta": {"updated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
                 "growth": GROWTH, "value": VALUE},
        "growth": {**growth, "etf": g_tech},
        "value": {**value, "etf": v_tech},
        "growth_diff": gd,
        "engine": None,
    }
    if growth.get("ok") and value.get("ok"):
        data["engine"] = engine.run({
            "growth": {**growth, "return_6m": growth.get("return_6m")},
            "value": {**value, "return_6m": value.get("return_6m")},
            "growth_diff_nm": (gd or {}).get("profit_diff_pp"),
        })

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=1)
    print("written", OUT)
    print("成长:", "ok" if growth.get("ok") else growth.get("note"),
          "| 价值:", "ok" if value.get("ok") else value.get("note"))
    if data["engine"]:
        e = data["engine"]
        print(f"配置: 成长{e['growth_w_pct']}% / 价值{e['value_w_pct']}%  偏移{e['bias_pts']:+}pt  并聚{e['confluence']['net_push']}")


if __name__ == "__main__":
    main()