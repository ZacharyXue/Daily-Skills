# -*- coding: utf-8 -*-
"""
保租房 REITs 看板 · 取数层
=========================
数据全部走 data-source-router（唯一入口），本脚本只做编排 + 领域计算。

kinds 用到：
  cn_reits_list          全量公募 REITs 清单（腾讯行情枚举，自动发现新上市）
  cn_reits_report_list   某只基金的定期报告清单（季报/中报/年报）
  cn_reits_report_data   单份报告解析（净值/分派率/可供分配/出租率/收缴率/剩余租期）
  cn_reits_dividend      已宣告分红记录（TTL 口径）
  cn_stock_kline         日K（前复权，回撤/波动）
  cn_stock_quote         实时行情

产出：data/latest.json
用法：/root/hermes-venv/bin/python scripts/fetch.py [--force]
"""
import os
import sys
import json
import argparse
import datetime as dt
import statistics as st

sys.path.insert(0, "/root/zach-skills/data-source-router")
import data_router as DSR  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")
os.makedirs(DATA, exist_ok=True)

# 保租房 REITs 名称关键词（自动发现新上市；命中后再人工复核加入 KNOWN）
KW = ["租赁住房", "保障房", "保租房", "安居", "有巢", "宽庭", "恒泰", "宁巢", "昌保", "人才公寓", "青年公寓"]
TODAY = dt.date.today()
PRIO = {"H1": 0, "FY": 0, "Q1": 1, "Q2": 1, "Q3": 1, "Q4": 1}
DAYS = {"Q1": 90, "Q2": 91, "Q3": 92, "Q4": 92, "H1": 181, "FY": 365}
LPR1Y = 3.00  # 2026-08-20 LPR 1年期(%)


def d(s):
    try:
        return dt.datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        return None


def discover(force=False):
    """全量 REITs → 保租房子集（含新上市）"""
    allr = DSR.get("cn_reits_list", force=force)[0]
    bt = [a for a in allr if any(k in a["name"] for k in KW)]
    return allr, bt


def build_fund(meta, force=False):
    code, name = meta["code"], meta["name"]
    reps = DSR.get("cn_reits_report_list", force=force, code=code)[0]
    parsed = {}
    for r in reps:
        try:
            parsed[r["id"]] = DSR.get("cn_reits_report_data", force=force, report_id=r["id"])[0]
        except Exception as e:
            print("  ! parse fail", code, r["id"], e)
    # 分红
    try:
        div = DSR.get("cn_reits_dividend", force=force, code=code)[0]
    except Exception:
        div = {"divs": [], "ytd_cum": None}
    # K线 / 行情
    try:
        kl = DSR.get("cn_stock_kline", force=force, symbol=code, count=700)[0]
    except Exception as e:
        print("  ! kline fail", code, e)
        kl = []
    try:
        q = DSR.get("cn_stock_quote", force=force, symbol=code)[0]
        price = q.get("price") or meta.get("price")
    except Exception:
        price = meta.get("price")

    # 同 period_end 去重（中报/年报优先）
    best = {}
    for r in reps:
        p = parsed.get(r["id"])
        if not p or not p.get("period_end"):
            continue
        u = ((p.get("distributable") or {}).get("本期") or [None, None])[1]
        if not u:
            continue
        cur = best.get(p["period_end"])
        if cur is None or PRIO.get(r["rtype"], 2) < PRIO.get(cur[0], 2):
            best[p["period_end"]] = (r["rtype"], r, p)

    px = {x["date"]: x["close"] for x in kl}
    kd = sorted(px)

    def px_on(day):
        if not day:
            return None
        v = None
        for x in kd:
            if x <= day:
                v = px[x]
            else:
                break
        return v

    series = []
    for pe in sorted(best):
        rtype, r, p = best[pe]
        u = ((p.get("distributable") or {}).get("本期") or [None, None])[1]
        up = ((p.get("paid") or {}).get("本期") or [None, None])[1]
        nd = DAYS.get(rtype, 365)
        b, e = d(p.get("period_beg")), d(pe)
        if b and e:
            nd = max((e - b).days + 1, 30)
        ann_u = round(u * 365 / nd, 4) if u else None
        pxe = px_on(pe)
        series.append({
            "period_end": pe, "rtype": rtype, "pub_date": r["date"],
            "unit_dist": u, "unit_paid": up, "ann_unit_dist": ann_u,
            "nav": p.get("nav"), "occ": p.get("occ_avg"), "occ_src": p.get("occ_src"),
            "collect": p.get("collect_avg"), "lease": p.get("lease_avg"),
            "dy_official": p.get("dy_annual"),
            "dy_calc": round(ann_u / pxe * 100, 2) if (ann_u and pxe) else None,
            "px_at_end": pxe, "pnav": round(pxe / p["nav"], 3) if (pxe and p.get("nav")) else None,
            "revenue": p.get("revenue"), "net_profit": p.get("net_profit"), "ocf": p.get("ocf"),
            "projects": p.get("projects") or {},
        })
    last = series[-1] if series else None

    close = px[kd[-1]] if kd else (float(price) if price else None)
    w1 = [px[x] for x in kd if d(x) >= TODAY - dt.timedelta(days=365)]
    hi1 = max(w1) if w1 else close
    hiall = max(px.values()) if px else close
    vol = mdd = None
    if len(w1) > 20:
        rr = [w1[i] / w1[i - 1] - 1 for i in range(1, len(w1)) if w1[i - 1] > 0]
        vol = round(st.pstdev(rr) * (250 ** 0.5), 4)
        pk, mm = -1e9, 0
        for v in w1:
            pk = max(pk, v); mm = min(mm, v / pk - 1)
        mdd = round(mm, 4)
    ytd0 = next((px[x] for x in kd if x >= "%d-01-01" % TODAY.year), None)
    p1y = next((px[x] for x in kd if d(x) >= TODAY - dt.timedelta(days=365)), None)
    # TTM 实际到手分红
    ev = [(d(x["reg"]), x["per_unit"]) for x in div.get("divs", []) if d(x["reg"])]
    ttm = sum(v for dd, v in ev if (TODAY - dd).days <= 365)

    def prank(vals, v):
        vals = [x for x in vals if x is not None]
        if not vals or v is None:
            return None
        return round(sum(1 for x in vals if x <= v) / len(vals) * 100, 1)

    dh = [s["dy_calc"] for s in series]
    ph = [s["pnav"] for s in series]
    oh = [s["occ"] for s in series]
    ch = [s["collect"] for s in series]
    cur_ann = last["ann_unit_dist"] if last else None
    dy_cur = round(cur_ann / close * 100, 2) if (cur_ann and close) else None
    pnav_cur = round(close / last["nav"], 3) if (last and last.get("nav")) else None

    return {
        "code": code, "name": name, "price": close, "mktcap": meta.get("mktcap"),
        "series": series, "latest_period": last["period_end"] if last else None,
        "latest_rtype": last["rtype"] if last else None,
        "latest_pub": last["pub_date"] if last else None,
        "dy_cur": dy_cur, "dy_official": last["dy_official"] if last else None,
        "dy_ttm": round(ttm / close * 100, 2) if close else None,
        "nav_latest": last["nav"] if last else None, "pnav": pnav_cur,
        "occ": last["occ"] if last else None, "occ_src": last["occ_src"] if last else None,
        "collect": last["collect"] if last else None, "lease": last["lease"] if last else None,
        "dd_1y": round(close / hi1 - 1, 4) if (close and hi1) else None,
        "dd_all": round(close / hiall - 1, 4) if (close and hiall) else None,
        "mdd_1y": mdd, "vol_1y": vol,
        "ret_1y": round(close / p1y - 1, 4) if (p1y and close) else None,
        "ytd": round(close / ytd0 - 1, 4) if (ytd0 and close) else None,
        "dy_pct": prank(dh, dy_cur), "pnav_pct": prank(ph, pnav_cur), "occ_pct": prank(oh, last["occ"] if last else None),
        "dy_min": min([x for x in dh if x]) if [x for x in dh if x] else None,
        "dy_max": max([x for x in dh if x]) if [x for x in dh if x] else None,
        "pnav_min": min([x for x in ph if x]) if [x for x in ph if x] else None,
        "pnav_max": max([x for x in ph if x]) if [x for x in ph if x] else None,
        "occ_min": min([x for x in oh if x]) if [x for x in oh if x] else None,
        "occ_max": max([x for x in oh if x]) if [x for x in oh if x] else None,
        "collect_min": min([x for x in ch if x]) if [x for x in ch if x] else None,
        "collect_max": max([x for x in ch if x]) if [x for x in ch if x] else None,
        "n_periods": len(series),
        "first_period": series[0]["period_end"] if series else None,
        "new_listing": len(series) < 3,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="忽略缓存强制回源")
    a = ap.parse_args()
    allr, bt = discover(a.force)
    print("全市场 REITs %d 只；保租房候选 %d 只" % (len(allr), len(bt)))
    funds = []
    for m in bt:
        print("→", m["code"], m["name"])
        try:
            funds.append(build_fund(m, a.force))
        except Exception as e:
            print("  ! build fail", m["code"], e)
    funds.sort(key=lambda f: -(float(f["mktcap"] or 0)))
    out = {"generated": dt.datetime.now().strftime("%Y-%m-%d %H:%M"), "lpr1y": LPR1Y,
           "universe": len(allr), "funds": funds}
    p = os.path.join(DATA, "latest.json")
    json.dump(out, open(p, "w"), ensure_ascii=False, indent=1)
    print("saved", p, "funds", len(funds))
    for f in funds:
        print("  %-8s %-20s 期数=%-3s P/NAV=%-6s(分位%s) 当前派息=%-6s(分位%s) 官方=%-6s TTM=%-6s 出租率=%-6s 距1年高点=%s" % (
            f["code"], f["name"][:18], f["n_periods"], f["pnav"], f["pnav_pct"], f["dy_cur"], f["dy_pct"],
            f["dy_official"], f["dy_ttm"], f["occ"], f["dd_1y"]))


if __name__ == "__main__":
    main()
