#!/usr/bin/env python3
"""Fetch A-share company financials from Eastmoney datacenter API (no key needed).

Verified working 2026-08. Two reports:
  - RPT_F10_FINANCE_MAINFINADATA  main financial indicators per report period
  - RPT_F10_FN_MAINOP             main business composition (by product/industry/region)

Usage:
  python3 fetch_eastmoney.py 000933.SZ              # latest periods (default 30 rows)
  python3 fetch_eastmoney.py 000933.SZ --annual     # keep only annual reports (12-31)
  python3 fetch_eastmoney.py 000933.SZ --mainop     # business composition, latest period only
  python3 fetch_eastmoney.py 000933.SZ --json       # raw JSON
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://emweb.securities.eastmoney.com/",
}
API = "https://datacenter.eastmoney.com/securities/api/data/v1/get"


def get(url: str) -> dict:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode())


def fetch_finance(secucode: str, page_size: int = 30) -> list[dict]:
    url = (
        f"{API}?reportName=RPT_F10_FINANCE_MAINFINADATA&columns=ALL"
        f"&filter=(SECUCODE%3D%22{secucode}%22)"
        f"&pageNumber=1&pageSize={page_size}&sortTypes=-1&sortColumns=REPORT_DATE"
    )
    return get(url)["result"]["data"]


def fetch_mainop(secucode: str, page_size: int = 30) -> list[dict]:
    url = (
        f"{API}?reportName=RPT_F10_FN_MAINOP&columns=ALL"
        f"&filter=(SECUCODE%3D%22{secucode}%22)"
        f"&pageNumber=1&pageSize={page_size}&sortTypes=-1&sortColumns=REPORT_DATE"
    )
    return get(url)["result"]["data"]


def fmt_finance(r: dict) -> str:
    rev = (r.get("TOTALOPERATEREVE") or 0) / 1e8
    profit = (r.get("PARENTNETPROFIT") or 0) / 1e8
    eps = r.get("EPSJB") or 0
    bps = r.get("BPS") or 0
    roe = eps / bps * 100 if bps else 0
    return (
        f"{r.get('REPORT_DATE_NAME', '?'):<10} "
        f"营收={rev:>9.1f}亿 归母净利={profit:>8.1f}亿 "
        f"EPS={eps:>5.2f} ROE≈{roe:>5.1f}% "
        f"毛利率={(r.get('XSMLL') or 0):>5.1f}% "
        f"净利率={(r.get('XSJLL') or 0):>5.1f}% "
        f"每股CF={(r.get('MGJYXJJE') or 0):>5.2f} "
        f"负债率={(r.get('ZCFZL') or 0):>5.1f}%"
    )


def main() -> None:
    p = argparse.ArgumentParser(description="Eastmoney A-share financials")
    p.add_argument("secucode", help="e.g. 000933.SZ or 601600.SH")
    p.add_argument("--annual", action="store_true", help="keep only annual (12-31) periods")
    p.add_argument("--mainop", action="store_true", help="show business composition instead")
    p.add_argument("--json", action="store_true", help="raw JSON output")
    args = p.parse_args()

    if args.mainop:
        rows = fetch_mainop(args.secucode)
        if not rows:
            print("no data", file=sys.stderr)
            sys.exit(1)
        latest = rows[0].get("REPORT_NAME") or rows[0].get("REPORT_DATE", "?")
        print(f"== {args.secucode} {latest} mainop ==")
        out = []
        for r in rows:
            if (r.get("REPORT_NAME") or r.get("REPORT_DATE")) != (rows[0].get("REPORT_NAME") or rows[0].get("REPORT_DATE")):
                continue
            inc = r.get("MAIN_BUSINESS_INCOME") or 0
            if inc <= 0:
                continue
            cost = r.get("MAIN_BUSINESS_COST") or 0
            gm = (r.get("GROSS_RPOFIT_RATIO") or 0) * 100  # NOTE: RPOFIT typo is the real field name
            ratio = (r.get("MBI_RATIO") or 0) * 100
            item = r.get("ITEM_NAME") or "?"
            out.append({
                "item": item,
                "income_亿": round(inc / 1e8, 1),
                "pct": round(ratio, 1),
                "cost_亿": round(cost / 1e8, 1),
                "gross_margin_pct": round(gm, 1),
            })
        if args.json:
            print(json.dumps(out, indent=2, ensure_ascii=False))
        else:
            for o in out:
                print(f"  {o['item'][:26]:<28} 收入={o['income_亿']:>10.1f}亿({o['pct']:>5.1f}%) "
                      f"成本={o['cost_亿']:>10.1f}亿 毛利率={o['gross_margin_pct']:>5.1f}%")
        return

    rows = fetch_finance(args.secucode)
    if args.annual:
        rows = [r for r in rows if str(r.get("REPORT_DATE", "")).endswith("12-31")]
    if args.json:
        print(json.dumps(rows, indent=2, ensure_ascii=False))
        return
    for r in rows:
        print(fmt_finance(r))


if __name__ == "__main__":
    main()
