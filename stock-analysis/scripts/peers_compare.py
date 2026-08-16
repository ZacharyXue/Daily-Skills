#!/usr/bin/env python3
"""Peer comparison for A-share stocks — Eastmoney datacenter API.

Fetches unified-period financials (annual by default) for a list of stocks
and prints a comparison table. Period can be switched via --period.

Usage:
  python3 peers_compare.py 000933.SZ 601600.SH 000807.SZ
  python3 peers_compare.py 000933.SZ 601600.SH --period 2026中报
  python3 peers_compare.py --csv 000933.SZ 601600.SH   # CSV output
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request


def fetch(secucode: str, page_size: int = 30) -> list[dict]:
    url = ("https://datacenter.eastmoney.com/securities/api/data/v1/get"
           "?reportName=RPT_F10_FINANCE_MAINFINADATA&columns=ALL"
           f"&filter=(SECUCODE%3D%22{secucode}%22)"
           f"&pageNumber=1&pageSize={page_size}&sortTypes=-1&sortColumns=REPORT_DATE")
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://emweb.securities.eastmoney.com/",
    })
    with urllib.request.urlopen(req, timeout=20) as r:
        d = json.loads(r.read().decode())
    return d.get("result", {}).get("data", [])


def find(rows: list[dict], period: str) -> dict | None:
    for r in rows:
        if r.get("REPORT_DATE_NAME") == period:
            return r
    return None


def pick_default(rows: list[dict]) -> dict | None:
    """Latest annual report by default (2025年报, 2024年报, ...)."""
    for r in rows:
        name = r.get("REPORT_DATE_NAME") or ""
        if name.endswith("年报"):
            return r
    return rows[0] if rows else None


def summarize(r: dict, name: str) -> dict:
    rev = (r.get("TOTALOPERATEREVE") or 0) / 1e8
    profit = (r.get("PARENTNETPROFIT") or 0) / 1e8
    eps = r.get("EPSJB") or 0
    bps = r.get("BPS") or 0
    cf = r.get("MGJYXJJE") or 0
    gm = r.get("XSMLL") or 0
    nm = r.get("XSJLL") or 0
    debt = r.get("ZCFZL") or 0
    roe = (eps / bps * 100) if bps else 0
    return {
        "name": name,
        "period": r.get("REPORT_DATE_NAME", "?"),
        "rev": rev, "profit": profit, "eps": eps, "roe": roe,
        "gm": gm, "nm": nm, "cf": cf, "debt": debt,
    }


def main():
    p = argparse.ArgumentParser(description="A-share peer financial comparison")
    p.add_argument("codes", nargs="+", help="stock codes, e.g. 000933.SZ")
    p.add_argument("--period", default=None, help='exact report name e.g. "2025年报" (default: latest annual)')
    p.add_argument("--csv", action="store_true", help="CSV output")
    args = p.parse_args()

    rows_out = []
    for code in args.codes:
        try:
            rows = fetch(code)
            r = find(rows, args.period) if args.period else pick_default(rows)
            if not r:
                print(f"{code}: no data", file=sys.stderr)
                continue
            s = summarize(r, code)
            rows_out.append(s)
            print(f"{code}: {s['period']} 营收={s['rev']:.1f}亿 净利={s['profit']:.1f}亿 "
                  f"EPS={s['eps']:.2f} ROE={s['roe']:.1f}% 毛利率={s['gm']:.1f}% "
                  f"净利率={s['nm']:.1f}% 每股CF={s['cf']:.2f} 负债率={s['debt']:.1f}%",
                  file=sys.stderr)
        except Exception as e:
            print(f"{code}: ERR {e}", file=sys.stderr)
        time.sleep(0.3)

    if args.csv:
        import csv
        w = csv.DictWriter(sys.stdout, fieldnames=list(rows_out[0].keys()) if rows_out else [])
        w.writeheader()
        w.writerows(rows_out)
    else:
        if not rows_out:
            return
        hdr = f"{'代码':<12}{'营收(亿)':>12}{'净利(亿)':>12}{'EPS':>7}{'ROE%':>7}{'毛利率%':>8}{'净利率%':>8}{'每股CF':>8}{'负债率%':>8}"
        print(hdr)
        for s in rows_out:
            print(f"{s['name']:<12}{s['rev']:>12.1f}{s['profit']:>12.1f}{s['eps']:>7.2f}"
                  f"{s['roe']:>7.1f}{s['gm']:>8.1f}{s['nm']:>8.1f}{s['cf']:>8.2f}{s['debt']:>8.1f}")


if __name__ == "__main__":
    main()
