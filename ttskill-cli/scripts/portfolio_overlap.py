#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""组合重叠体检（两层法）—— 持仓层 Σmin + 净值层相关性

用法（调用前先 export PATH="$HOME/.local/bin:$PATH"）：

  # 1) 从天天基金账户持仓取全部基金（过滤投顾/活期宝）
  python3 scripts/portfolio_overlap.py --from-holdings

  # 2) 指定基金（外部基金 / 候选池也适用）
  python3 scripts/portfolio_overlap.py --codes 515180,159545,012708

  # 3) 调整阈值与输出目录
  python3 scripts/portfolio_overlap.py --from-holdings --corr-thresholds 0.9,0.8,0.6 --out /tmp/pov

产出：
  <out>/report.md   人读报告（两层结果 + 聚类 + 穿透 + 数据缺口）
  <out>/raw.json    机读明细（可直接二次分析）

设计要点（2026-10-18 实测踩坑后固化）：
  - 净值相关性为主判、持仓 Σmin 为辅判：对指数/宽基，前十大只覆盖基金 3%-60%，
    不同指数权重不同但 beta 相同 → 只看 Σmin 会得出"很分散"的错误结论。
  - 数据缺口必须显性化：FOF / ETF 联接 / 债券 / 货币 没有股票前十大，
    列进"未穿透"清单，绝不当 0 重叠参与分母。
  - ttskill 偶发返回 0 字节 → 短超时 + 重试一次即恢复，不判死源。
"""
import argparse
import json
import math
import os
import subprocess
import sys
from collections import defaultdict
from datetime import date

CACHE_DIR = "/tmp/fund_raw"


def run_ttskill(skill, action, body, timeout=150):
    """调 ttskill，返回 stdout 文本（失败返回空串）"""
    cmd = ["ttskill", "invoke", skill, "--action", action, "--body", json.dumps(body)]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.stdout or ""
    except Exception as e:
        print(f"  [warn] {skill} {body} 调用异常: {e}", file=sys.stderr)
        return ""


def fetch_base_infos(code, cache_dir=CACHE_DIR):
    """拉单只基金全档案（带缓存 + 0 字节重试一次）"""
    os.makedirs(cache_dir, exist_ok=True)
    path = os.path.join(cache_dir, f"{code}.json")
    if os.path.exists(path) and os.path.getsize(path) > 2000:
        return path
    for attempt in (1, 2):
        out = run_ttskill("TTFUND_BASE_INFOS", "query", {"fcode": code, "nav_range": "ln"})
        if len(out) > 2000:
            with open(path, "w") as f:
                f.write(out)
            return path
        print(f"  [retry] {code} 第 {attempt} 次取到 {len(out)} 字节", file=sys.stderr)
    return None


def load_json_envelope(path):
    """ttskill 输出前面可能混有日志行，从第一个 { 开始解析"""
    if not path or not os.path.exists(path):
        return None
    s = open(path).read()
    i = s.find("{")
    if i < 0:
        return None
    try:
        return json.loads(s[i:])
    except Exception:
        return None


def get_holdings_list():
    """账户持仓 → [{'code','name','value','ptype'}]（ptype 是小写字段，实测）"""
    out = run_ttskill("ACCOUNT_HOLDING", "holding_list", {})
    j = load_json_envelope_text(out)
    if not j:
        return []
    rows = j["data"]["raw_result"]["body"]["holding_list_result"]
    res = []
    for h in rows:
        try:
            v = float(h.get("assetValue") or 0)
        except Exception:
            v = 0.0
        res.append({
            "code": h.get("fundCode"),
            "name": h.get("fundName"),
            "value": v,
            "ptype": h.get("ptype") or h.get("pType"),
        })
    return res


def load_json_envelope_text(s):
    i = (s or "").find("{")
    if i < 0:
        return None
    try:
        return json.loads(s[i:])
    except Exception:
        return None


def extract_fund(path, code, name, value):
    """从 BASE_INFOS 提取：前十大 / 净值序列 / 资产配置 / 披露日"""
    j = load_json_envelope(path)
    if not j:
        return {"ok": False, "reason": "档案解析失败", "code": code, "name": name, "value": value}
    try:
        ci = j["data"]["raw_result"]["body"]["expansion"]["comprehensive_info"]
    except Exception:
        return {"ok": False, "reason": "信封结构与预期不符", "code": code, "name": name, "value": value}

    fp = ci.get("fund_profile_holdings") or {}
    hl = fp.get("heavyweight_position_latest") or {}
    stocks = {}
    for s in (hl.get("fundStocks") or []):
        # 字段固定：GPDM 代码 / GPJC 名称 / JZBL 占净值比
        nm, cd, w = s.get("GPJC"), s.get("GPDM"), s.get("JZBL")
        try:
            w = float(str(w).replace("%", ""))
        except Exception:
            continue
        if nm and cd:
            stocks[str(cd)] = {"name": nm, "w": w}
    fof = {}
    for s in (hl.get("fundfofs") or []):
        nm, w = s.get("TZJJMC"), s.get("ZJZBL")
        try:
            w = float(str(w).replace("%", ""))
        except Exception:
            continue
        if nm:
            fof[nm] = w

    aa = fp.get("asset_allocation_latest") or {}

    nav = {}
    for it in ((ci.get("nav_history") or {}).get("items") or []):
        ds, r = it.get("FSRQ"), it.get("JZZZL")
        if not ds or r in (None, "", "--"):
            continue
        try:
            nav[ds] = float(r) / 100.0
        except Exception:
            continue

    if stocks:
        reason = ""
    elif fof:
        reason = "FOF，股票前十大不可用 → 需穿透到所持基金"
    elif any(k in name for k in ("货币", "收益宝", "活期")):
        reason = "货币型，无股票持仓（正常，不计入重叠）"
    elif "债" in name:
        reason = "债券型，无股票持仓（正常，不计入重叠）"
    elif "联接" in name:
        reason = "ETF 联接，不直接持股票 → 需穿透到目标 ETF"
    elif "FOF" in name.upper():
        reason = "FOF，属基金持仓 → 需穿透到所持基金"
    else:
        reason = "无股票前十大（未披露/新基金/纯债）"

    return {
        "ok": bool(stocks),
        "code": code, "name": name, "value": value,
        "holdings_date": fp.get("heavyweight_position_report_date"),
        "stocks": stocks, "fof": fof,
        "gp": aa.get("GP"), "zq": aa.get("ZQ"), "hb": aa.get("HB"),
        "nav": nav,
        "reason": reason,
    }


def weekly_returns(daily):
    """日收益序列 → ISO 周收益（复利聚合，避开分红对单位净值的影响）"""
    wk = defaultdict(lambda: 1.0)
    for ds, r in daily.items():
        try:
            y, w, _ = date.fromisoformat(ds).isocalendar()
        except Exception:
            continue
        wk[(y, w)] *= (1 + r)
    return {k: v - 1 for k, v in wk.items()}


def pearson(a, b, weeks=104, min_common=52):
    keys = sorted(set(a) & set(b))[-weeks:]
    if len(keys) < min_common:
        return None, len(keys)
    xs = [a[k] for k in keys]
    ys = [b[k] for k in keys]
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    vx = sum((x - mx) ** 2 for x in xs)
    vy = sum((y - my) ** 2 for y in ys)
    if vx == 0 or vy == 0:
        return None, n
    return cov / math.sqrt(vx * vy), n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from-holdings", action="store_true", help="从天天基金账户持仓取基金清单")
    ap.add_argument("--codes", help="逗号分隔的基金代码（与 --from-holdings 二选一）")
    ap.add_argument("--cache-dir", default=CACHE_DIR)
    ap.add_argument("--corr-thresholds", default="0.9,0.8,0.6")
    ap.add_argument("--out", default="/tmp/portfolio_overlap")
    ap.add_argument("--weeks", type=int, default=104, help="相关性回看周数（默认近 24 个月）")
    args = ap.parse_args()

    thresholds = [float(x) for x in args.corr_thresholds.split(",") if x.strip()]

    # --- 1. 基金清单 ---
    if args.from_holdings:
        all_rows = get_holdings_list()
        funds = [r for r in all_rows if r["ptype"] == "fund" and r["code"]]
        skipped = [r for r in all_rows if r["ptype"] != "fund"]
        print(f"[持仓] 共 {len(all_rows)} 条，纯基金 {len(funds)} 只，"
              f"过滤 {len(skipped)} 条（投顾/活期宝：{[r['name'] for r in skipped]}）")
    elif args.codes:
        codes = [c.strip() for c in args.codes.split(",") if c.strip()]
        funds = [{"code": c, "name": c, "value": 0.0} for c in codes]
    else:
        ap.error("需要 --from-holdings 或 --codes")

    # --- 2. 逐只拉档案 ---
    info = {}
    for f in funds:
        p = fetch_base_infos(f["code"], args.cache_dir)
        if p:
            info[f["code"]] = extract_fund(p, f["code"], f["name"], f["value"])
        else:
            info[f["code"]] = {"ok": False, "code": f["code"], "name": f["name"],
                               "value": f["value"], "reason": "BASE_INFOS 拉取失败（重试后仍为空）",
                               "stocks": {}, "nav": {}}
    have = {c: v for c, v in info.items() if v.get("ok")}
    total_value = sum(v["value"] for v in info.values()) or 1.0

    # --- 3. 持仓层：两两 Σmin ---
    pairs = []
    codes = sorted(have)
    for i in range(len(codes)):
        for k in range(i + 1, len(codes)):
            a, b = codes[i], codes[k]
            wa = {x: d["w"] for x, d in have[a]["stocks"].items()}
            wb = {x: d["w"] for x, d in have[b]["stocks"].items()}
            common = set(wa) & set(wb)
            ov = sum(min(wa[x], wb[x]) for x in common)
            if ov > 0:
                pairs.append({"a": a, "b": b, "overlap": round(ov, 2), "common": sorted(common)})
    pairs.sort(key=lambda x: -x["overlap"])

    # --- 4. 净值层：周收益相关 ---
    wk = {c: weekly_returns(v["nav"]) for c, v in info.items() if v.get("nav")}
    corrs = []
    wcodes = sorted(wk)
    for i in range(len(wcodes)):
        for k in range(i + 1, len(wcodes)):
            a, b = wcodes[i], wcodes[k]
            r, n = pearson(wk[a], wk[b], weeks=args.weeks)
            if r is not None:
                corrs.append({"a": a, "b": b, "r": round(r, 3), "n": n})
    corrs.sort(key=lambda x: -x["r"])

    # --- 5. 聚类（并查集） ---
    def clusters(thr):
        parent = {c: c for c in info}

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        for e in corrs:
            if e["r"] >= thr:
                ra, rb = find(e["a"]), find(e["b"])
                if ra != rb:
                    parent[ra] = rb
        g = defaultdict(list)
        for c in info:
            g[find(c)].append(c)
        return sorted(g.values(), key=lambda x: -sum(info[c]["value"] for c in x))

    # --- 6. 穿透：≥2 只基金共同持有的个股 ---
    expo, detail = defaultdict(float), defaultdict(list)
    for c, v in have.items():
        for _, d in v["stocks"].items():
            expo[d["name"]] += v["value"] * d["w"] / 100
            detail[d["name"]].append(f"{c} {v['name'][:14]}({d['w']}%)")
    repeated = {k: v for k, v in detail.items() if len(v) > 1}

    # --- 7. 报告 ---
    os.makedirs(args.out, exist_ok=True)
    L = []
    L.append("# 组合重叠体检报告（两层法）\n")
    L.append(f"- 基金数：{len(info)}（披露可测算 {len(have)} 只）")
    L.append(f"- 资产市值：{total_value:,.0f} 元")
    L.append(f"- 相关性回看：近 {args.weeks} 周（≥52 共同周）\n")

    L.append("## 一、净值层（主判）：周收益相关性 Top\n")
    L.append("| r | 组合 | 共同周 | 读数 |")
    L.append("|---|---|---|---|")
    for e in corrs[:15]:
        lvl = "几乎同一个 beta" if e["r"] >= 0.97 else ("高度重复" if e["r"] >= 0.9 else
                                                          ("显著相关" if e["r"] >= 0.8 else "相关"))
        L.append(f"| {e['r']} | {e['a']} {info[e['a']]['name'][:16]} × {e['b']} {info[e['b']]['name'][:16]} | {e['n']} | {lvl} |")
    L.append(f"\n> 可比 {len(corrs)} 对；r≥0.9 {sum(1 for e in corrs if e['r'] >= 0.9)} 对，"
             f"r≥0.8 {sum(1 for e in corrs if e['r'] >= 0.8)} 对\n")

    L.append("## 二、按相关性聚类：名义 N 只 → 实际 M 个独立 beta\n")
    for thr in thresholds:
        gs = clusters(thr)
        multi = [g for g in gs if len(g) > 1]
        L.append(f"**r≥{thr}：{len(gs)} 个簇**（多基金簇 {len(multi)} 个）\n")
        for g in multi:
            w = sum(info[c]["value"] for c in g)
            L.append(f"- {w / total_value * 100:.1f}% · {len(g)} 只：" +
                     "、".join(f"{c} {info[c]['name'][:12]}" for c in sorted(g, key=lambda x: -info[x]["value"])))
        L.append("")

    L.append("## 三、持仓层（辅判）：前十大 Σmin 重叠\n")
    if pairs:
        L.append("| 重叠度 | 分级 | 组合 | 共同持股 |")
        L.append("|---|---|---|---|")
        for p in pairs[:12]:
            ov = p["overlap"]
            lvl = "高度" if ov >= 60 else "显著" if ov >= 40 else "中度" if ov >= 20 else "低度"
            names = "、".join(have[p["a"]]["stocks"][x]["name"] for x in p["common"][:4])
            L.append(f"| {ov}% | {lvl} | {p['a']} × {p['b']} | {names} |")
    else:
        L.append("_无可测算的重叠（持仓数据不足）_")
    L.append("\n> ⚠️ 两层结论冲突时**以净值层为准**：前十大只覆盖基金 3%-60%，且不同指数权重不同但 beta 相同，"
             "Σmin 会系统性低估指数基金之间的重复。\n")

    L.append("## 四、穿透：被 ≥2 只基金共同持有的个股\n")
    if repeated:
        for nm, ds in sorted(repeated.items(), key=lambda kv: -len(kv[1]))[:10]:
            L.append(f"- **{nm}**（{len(ds)} 只）：{expo[nm]:,.0f} 元 = 组合 {expo[nm] / total_value * 100:.2f}%；来自 {', '.join(ds)}")
    else:
        L.append("_无_")
    L.append("")

    gaps = [v for v in info.values() if not v.get("ok")]
    gap_codes = {v["code"] for v in gaps}
    no_nav = [v for v in info.values() if not v.get("nav") and v["code"] not in gap_codes]
    L.append("## 五、数据缺口（必须显性化，不计入重叠分母）\n")
    for v in gaps:
        L.append(f"- {v['code']} {v['name']}：{v.get('reason')}")
    for v in no_nav:
        L.append(f"- {v['code']} {v['name']}：无净值序列（取到档案但 nav_history 缺失）→ 未进相关性测算")
    if not gaps and not no_nav:
        L.append("- 无")

    report = "\n".join(L)
    with open(os.path.join(args.out, "report.md"), "w") as f:
        f.write(report + "\n")
    with open(os.path.join(args.out, "raw.json"), "w") as f:
        json.dump({"funds": {c: {k: v for k, v in d.items() if k != "nav"} for c, d in info.items()},
                   "pairs": pairs, "corrs": corrs,
                   "clusters": {str(t): clusters(t) for t in thresholds},
                   "repeated": {k: v for k, v in repeated.items()}},
                  f, ensure_ascii=False, indent=1)
    print(report)
    print(f"\n[落盘] {args.out}/report.md  {args.out}/raw.json")


if __name__ == "__main__":
    main()
