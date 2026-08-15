#!/usr/bin/env python3
"""Fetch and diff SEC 13F institutional holdings.

Subcommands:
  search "<name>"          # find CIK by institution name
  fetch --cik CIK [--n N]  # print latest N filings' holdings (default 1)
  diff  --cik CIK          # compare latest two filings quarter-over-quarter

Usage examples:
  python3 fetch_13f.py search "Himalaya Capital"
  python3 fetch_13f.py fetch --cik 0001709323
  python3 fetch_13f.py diff  --cik 0001709323 --json

Only stdlib. Requires User-Agent per SEC policy (10 req/s max).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

USER_AGENT = "Research research@example.com"
_RATE_LIMIT_S = 0.2  # SEC allows ~10 req/s; be conservative


def http_get(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _throttle():
    time.sleep(_RATE_LIMIT_S)


# ── Step 1: search CIK ─────────────────────────────────────────────────

def search_cik(company: str):
    q = urllib.parse.quote(company)
    url = (f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany"
           f"&company={q}&type=13F&dateb=&owner=include&count=40&output=atom")
    xml = http_get(url)
    cik = re.search(r"<cik>(\d+)</cik>", xml)
    name = re.search(r"<conformed-name>(.*?)</conformed-name>", xml)
    if not cik:
        return None, None
    return cik.group(1).zfill(10), (name.group(1) if name else company)


# ── Step 2: list filings ───────────────────────────────────────────────

def list_filings(cik: str, count: int = 8):
    url = (f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany"
           f"&CIK={cik}&type=13F-HR&dateb=&owner=include&count={count}&output=atom")
    xml = http_get(url)
    filings = []
    for entry in re.findall(r"<entry>(.*?)</entry>", xml, re.S):
        acc = re.search(r"<accession-number>(.*?)</accession-number>", entry)
        date = re.search(r"<filing-date>(.*?)</filing-date>", entry)
        ftype = re.search(r"<filing-type>(.*?)</filing-type>", entry)
        if acc:
            filings.append({
                "accession": acc.group(1),
                "filing_date": date.group(1) if date else "",
                "type": ftype.group(1) if ftype else "13F-HR",
            })
    return filings


def _accession_dir(accession: str) -> str:
    """'0002043585-26-000022' -> '000204358526000022'."""
    return accession.replace("-", "")


def _data_dir(cik: str) -> str:
    """'0001709323' -> '1709323' (strip leading zeros for URL path)."""
    return cik.lstrip("0")


def find_infotable_url(filing) -> str:
    """Open the filing index page and locate the infoTable XML."""
    acc_dir = _accession_dir(filing["accession"])
    url = (f"https://www.sec.gov/Archives/edgar/data/{_data_dir(filing.get('cik', ''))}"
           f"/{acc_dir}/{filing['accession']}-index.htm")
    html = http_get(url)
    # The infoTable XML is the non-primary_doc .xml file in the filing root
    hrefs = re.findall(r'href="(/Archives/edgar/data/[^"]*\.xml)"', html)
    for h in hrefs:
        if "primary_doc" in h:
            continue
        if "/xslForm13F_X02/" in h:
            continue
        return "https://www.sec.gov" + h
    # Fallback: any xml
    for h in hrefs:
        if "primary_doc" not in h:
            return "https://www.sec.gov" + h
    return None


# ── Step 3: parse infoTable XML ────────────────────────────────────────

def parse_infotable(xml_text: str) -> dict:
    """Return {cusip: {name, cls, value, shares}}."""
    root = ET.fromstring(xml_text)
    out = {}
    for table in root.iter():
        if not table.tag.endswith("infoTable"):
            continue
        name = cls = cusip = ""
        value = shares = 0
        for el in table.iter():
            tag = el.tag.split("}")[-1] if "}" in el.tag else el.tag
            if tag == "nameOfIssuer":
                name = (el.text or "").strip()
            elif tag == "titleOfClass":
                cls = (el.text or "").strip()
            elif tag == "cusip":
                cusip = (el.text or "").strip()
            elif tag == "value":
                value = int(el.text or 0)
            elif tag == "sshPrnamt":
                shares = int(el.text or 0)
        if cusip:
            out[cusip] = {"name": name, "cls": cls, "value": value, "shares": shares}
    return out


def fetch_holdings(cik: str, count: int = 1):
    """Return list of {filing, holdings} newest-first."""
    filings = list_filings(cik, count=max(count * 2, 4))
    result = []
    for f in filings:
        f["cik"] = cik
        url = find_infotable_url(f)
        if not url:
            continue
        _throttle()
        xml = http_get(url)
        result.append({"filing": f, "holdings": parse_infotable(xml)})
        if len(result) >= count:
            break
    return result


# ── formatting ─────────────────────────────────────────────────────────

def _fmt_money(v: int) -> str:
    return f"{v:>13,}"


def format_holdings(filing, holdings) -> str:
    lines = []
    lines.append(f"报告期提交: {filing['filing_date']}  类型: {filing['type']}")
    lines.append(f"持仓数: {len(holdings)}")
    lines.append("")
    lines.append(f"{'标的':<32} {'类别':<16} {'价值($)':>13} {'股数':>12}")
    lines.append("-" * 78)
    for cusip in sorted(holdings, key=lambda c: -holdings[c]["value"]):
        h = holdings[cusip]
        lines.append(f"{h['name'][:32]:<32} {h['cls'][:16]:<16} "
                     f"{h['value']:>13,} {h['shares']:>12,}")
    lines.append("-" * 78)
    total = sum(h["value"] for h in holdings.values())
    lines.append(f"{'总计':<32} {'':<16} {total:>13,}")
    return "\n".join(lines)


def diff_holdings(prev, curr) -> str:
    """prev/curr are (filing, holdings) tuples, oldest first."""
    pf, ph = prev
    cf, ch = curr
    all_cusip = sorted(set(ph) | set(ch), key=lambda c: -(ch.get(c, {}).get("value", 0)))

    lines = []
    lines.append(f"对比: {pf['filing_date']} ({pf['type']})  →  {cf['filing_date']} ({cf['type']})")
    lines.append("")
    lines.append(f"{'标的':<32} {'前期价值($)':>13} {'本期价值($)':>13} {'价值变化':>8}  股数变化")
    lines.append("-" * 100)
    for c in all_cusip:
        p = ph.get(c, {})
        q = ch.get(c, {})
        name = q.get("name") or p.get("name")
        pv = p.get("value", 0)
        qv = q.get("value", 0)
        ps = p.get("shares", 0)
        qs = q.get("shares", 0)
        if qv and pv:
            chg = f"{(qv - pv) / pv * 100:+.1f}%"
        elif qv:
            chg = "新增"
        else:
            chg = "清仓"
        if pv and qv:
            shchg = "不变" if qs == ps else f"{ps:,}→{qs:,}"
        elif qv:
            shchg = f"新增{qs:,}股"
        else:
            shchg = f"清仓({ps:,}股)"
        lines.append(f"{name[:32]:<32} {pv:>13,} {qv:>13,} {chg:>8}  {shchg}")
    lines.append("-" * 100)
    pt = sum(h["value"] for h in ph.values())
    qt = sum(h["value"] for h in ch.values())
    lines.append(f"{'总计':<32} {pt:>13,} {qt:>13,} {(qt - pt) / pt * 100 if pt else 0:>+7.1f}%")
    return "\n".join(lines)


# ── CLI ────────────────────────────────────────────────────────────────

def main():
    p = argparse.ArgumentParser(description="SEC 13F holdings fetcher")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("search", help="find CIK by institution name")
    s.add_argument("name")

    f = sub.add_parser("fetch", help="print latest holdings")
    f.add_argument("--cik", required=True)
    f.add_argument("--n", type=int, default=1)
    f.add_argument("--json", action="store_true")

    d = sub.add_parser("diff", help="compare latest two filings")
    d.add_argument("--cik", required=True)
    d.add_argument("--json", action="store_true")

    args = p.parse_args()

    if args.cmd == "search":
        cik, name = search_cik(args.name)
        if not cik:
            print(f"未找到 '{args.name}' 的 13F 记录", file=sys.stderr)
            sys.exit(1)
        print(f"{name}: {cik}")

    elif args.cmd == "fetch":
        results = fetch_holdings(args.cik, count=args.n)
        if not results:
            print("未找到 13F 持仓", file=sys.stderr)
            sys.exit(1)
        if args.json:
            print(json.dumps(results, indent=2, ensure_ascii=False))
        else:
            for r in results:
                print(format_holdings(r["filing"], r["holdings"]))
                print()

    elif args.cmd == "diff":
        results = fetch_holdings(args.cik, count=2)
        if len(results) < 2:
            print("持仓少于两期，无法对比", file=sys.stderr)
            sys.exit(1)
        curr, prev = results[0], results[1]
        if args.json:
            print(json.dumps({
                "prev": {"filing": prev["filing"], "holdings": prev["holdings"]},
                "curr": {"filing": curr["filing"], "holdings": curr["holdings"]},
            }, indent=2, ensure_ascii=False))
        else:
            print(diff_holdings((prev["filing"], prev["holdings"]),
                                 (curr["filing"], curr["holdings"])))


if __name__ == "__main__":
    main()
