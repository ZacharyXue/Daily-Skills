#!/usr/bin/env python3
"""ROIC (Return on Invested Capital) for A-share stocks — Eastmoney datacenter API.

ROIC = NOPAT / Invested Capital
  NOPAT   = 营业利润 × (1 - 所得税率)   # 所得税率 = 所得税 / 利润总额
  Invested Capital = 股东权益(含少数) + 有息负债(短期借款+一年内到期+长期借款+应付债券)

Usage:
  python3 roic.py 000333.SZ
  python3 roic.py 000333.SZ 600690.SH           # multiple
  python3 roic.py 000333.SZ --periods 2025年报 2026中报
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request


def fetch(report: str, secucode: str) -> list[dict]:
    url = ("https://datacenter.eastmoney.com/securities/api/data/v1/get"
           f"?reportName={report}&columns=ALL"
           f"&filter=(SECUCODE%3D%22{secucode}%22)"
           "&pageNumber=1&pageSize=30&sortTypes=-1&sortColumns=REPORT_DATE")
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


def pick_recent(rows: list[dict]) -> dict | None:
    """Latest period present in data."""
    return rows[0] if rows else None


def compute(balance: dict | None, income: dict | None) -> dict | None:
    if not balance or not income:
        return None
    Y = 1e8
    # 股东权益（含少数股东权益，用 TOTAL_EQUITY）
    eq = balance.get("TOTAL_EQUITY")
    if not isinstance(eq, (int, float)):
        return None
    # 有息负债
    debt_keys = ["SHORT_LOAN", "NONCURRENT_LIABILITIES_1YEAR",
                 "LONG_LOAN", "BOND_PAYABLE"]
    debt = sum(balance.get(k, 0) for k in debt_keys if isinstance(balance.get(k), (int, float)))
    invested = eq + debt  # 投入资本 (元)

    op = income.get("OPERATE_PROFIT")
    tax = income.get("INCOME_TAX")
    tp = income.get("TOTAL_PROFIT")
    if not all(isinstance(v, (int, float)) for v in [op, tax, tp]) or tp == 0:
        return None
    nopat = op * (1 - tax / tp)  # NOPAT

    # 对照组：ROE
    peq = balance.get("TOTAL_PARENT_EQUITY") or balance.get("TOTAL_OWNERS_EQUITY")
    np = income.get("PARENT_NETPROFIT")
    roe = None
    if isinstance(peq, (int, float)) and peq and isinstance(np, (int, float)) and peq != 0:
        roe = np / peq * 100

    return {
        "period": income.get("REPORT_DATE_NAME"),
        "eq_billion": eq / Y,
        "debt_billion": debt / Y,
        "invested_billion": invested / Y,
        "nopat_billion": nopat / Y,
        "roic_pct": nopat / invested * 100 if invested else None,
        "roe_approx_pct": roe,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="ROIC for A-share stocks")
    ap.add_argument("codes", nargs="+", help="e.g. 000333.SZ")
    ap.add_argument("--periods", nargs="+", default=["2025年报", "2026中报"])
    args = ap.parse_args()

    for secucode in args.codes:
        balance = fetch("RPT_F10_FINANCE_GBALANCE", secucode)
        income = fetch("RPT_F10_FINANCE_GINCOME", secucode)
        print(f"\n=== {secucode} ===")
        for period in args.periods:
            b = find(balance, period)
            i = find(income, period)
            res = compute(b, i)
            if not res:
                print(f"  {period}: 缺数据")
                continue
            roic = f"{res['roic_pct']:.1f}%" if res["roic_pct"] is not None else "--"
            roe = f"{res['roe_approx_pct']:.1f}%" if res["roe_approx_pct"] is not None else "--"
            print(f"  {period}: ROIC={roic}  ROE≈{roe}  "
                  f"投入资本{res['invested_billion']:.0f}亿  NOPAT{res['nopat_billion']:.0f}亿")
        time.sleep(0.3)


if __name__ == "__main__":
    main()