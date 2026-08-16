#!/usr/bin/env python3
"""Quote/valuation lookup for A-share stocks — Tencent quote API (fallback: Eastmoney).

Usage:
  python3 quote_query.py 000933
  python3 quote_query.py 000933 601600 000807
  python3 quote_query.py 000933 --json
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request

# Tencent quote field indices (split by ~)
# 1=name 2=code 3=price 4=prev_close 5=open 6=volume 39=PE 41=high52 42=low52 45=total_mktcap 46=PB
FIELDS = {
    1: "name", 2: "code", 3: "price", 4: "prev_close", 5: "open",
    39: "pe", 41: "high52", 42: "low52", 45: "mktcap_yi", 46: "pb",
}


def market_prefix(code: str) -> str:
    code = code.split(".")[0]
    if code.startswith(("6", "9")):
        return "sh" + code
    return "sz" + code


def fetch_tencent(code: str) -> dict:
    sym = market_prefix(code)
    url = f"https://qt.gtimg.cn/q={sym}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    txt = urllib.request.urlopen(req, timeout=10).read().decode("gbk")
    # v_sz000933="51~神火股份~000933~25.83~..."
    payload = txt.split('="', 1)[1].rsplit('"', 1)[0]
    parts = payload.split("~")
    out = {}
    for idx, label in FIELDS.items():
        if idx < len(parts):
            out[label] = parts[idx]
    return out


def main():
    p = argparse.ArgumentParser(description="A-share quote lookup")
    p.add_argument("codes", nargs="+")
    p.add_argument("--json", action="store_true")
    args = p.parse_args()

    results = []
    for code in args.codes:
        try:
            d = fetch_tencent(code)
            d["_code"] = code
            results.append(d)
        except Exception as e:
            print(f"{code}: ERR {e}", file=sys.stderr)

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
        return

    for d in results:
        mkt = float(d.get("mktcap_yi") or 0)
        price = d.get("price", "?")
        pe = d.get("pe", "?")
        pb = d.get("pb", "?")
        name = d.get("name", d["_code"])
        print(f"{d['_code']} {name}: 现价 {price}  总市值 {mkt:.0f}亿  PE {pe}  PB {pb}")


if __name__ == "__main__":
    main()
