#!/usr/bin/env python3
"""Market position for A-share stocks — Tencent daily K-line API (qfq).

Outputs price-position proxies for timing/market-sentiment judgments
(Marks' pendulum, Neff's reversal):
  - 52-week high/low position (% of range, 100=at high)
  - max drawdown over lookback window
  - 1-year change (price momentum)

Usage:
  python3 market_position.py sz000333 sh600690
  python3 market_position.py 000333 --auto        # auto prefix by code
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request


def auto_prefix(code: str) -> str:
    if code.startswith(("sh", "sz")):
        return code
    return ("sh" if code.startswith(("6", "9")) else "sz") + code


def kline(code: str, ndays: int = 400) -> list[tuple[str, float]]:
    url = (f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
           f"?param={code},day,,,{ndays},qfq")
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://gu.qq.com/",
    })
    with urllib.request.urlopen(req, timeout=25) as r:
        d = json.loads(r.read().decode("utf-8"))
    node = d["data"][code]
    rows = node.get("qfqday") or node.get("day") or []
    return [(x[0], float(x[2])) for x in rows]  # (date, close)


def main() -> None:
    ap = argparse.ArgumentParser(description="Market position of A-share stocks")
    ap.add_argument("codes", nargs="+", help="e.g. sz000333 or 000333")
    ap.add_argument("--window", type=int, default=400,
                    help="lookback days for drawdown/quarter position (default 400)")
    args = ap.parse_args()

    for code in args.codes:
        c = auto_prefix(code)
        try:
            kl = kline(c, args.window)
        except Exception as e:  # noqa: BLE001
            print(f"  {c}: K线抓取失败 {e}")
            continue
        if len(kl) < 2:
            print(f"  {c}: 数据不足"); continue
        closes = [x[1] for x in kl]
        px = closes[-1]

        # 52周 = 近250交易日，不足则用全部
        win = min(250, len(closes))
        hi = max(closes[-win:]); lo = min(closes[-win:])
        pos52 = (px - lo) / (hi - lo) * 100 if hi > lo else 100

        # 最大回撤（lookback 窗口）
        peak = closes[0]; maxdd = 0.0; mdd_date = kl[0][0]
        for dt, c2 in kl:
            if c2 > peak:
                peak = c2
            dd = (peak - c2) / peak * 100
            if dd > maxdd:
                maxdd = dd; mdd_date = dt

        # 近一年涨跌
        y_ago = closes[-win] if len(closes) >= win else closes[0]
        ret1y = (px / y_ago - 1) * 100

        name_lbl = code
        print(f"{'相名':<18} 现价{px:<8.2f} 52周高{hi:.2f}/低{lo:.2f} 区间位置{pos52:>5.1f}%  "
              f"最大回撤{maxdd:>5.1f}%({mdd_date}) 近一年{ret1y:+.1f}%")
        time.sleep(0.2)


if __name__ == "__main__":
    main()