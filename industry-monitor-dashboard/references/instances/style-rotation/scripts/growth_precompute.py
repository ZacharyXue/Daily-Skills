#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
growth_precompute.py — 盈利增速差预计算（第一性信号, 手动/月度后台跑）
等权聚合「国证成长100(980080) vs 国证价值100(980081)」成分股净利/营收同比，
产出 cache/growth_diff.json → fetch.py 读取后注入配置引擎。

思路（对齐广发框架「短期风格看盈利增速差」）：
  增速差 = 成长成分等权净利同比 − 价值成分等权净利同比
  由于免费源无指数权重，用「等权聚合」作稳健代理（成分盈利方向一致时近似足够）。

⚠️ 东财 TOTALOPERATEREVETZ/PARENTNETPROFITTZ 同比字段有 bug(实测人福 -579%)，
一律用「同报告期累计值 ÷ 去年同报告期累计值 − 1」重算，不信字段。

用法：
  /root/hermes-venv/bin/python scripts/growth_precompute.py
  产物: cache/growth_diff.json {ok, profit_g, profit_v, profit_diff_pp, rev_g, rev_v, n_g, n_v, note}
"""
import sys, os, json, datetime, threading, concurrent.futures
sys.path.insert(0, "/root/zach-skills/data-source-router")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import data_router as DSR

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "cache", "growth_diff.json")

INDICES = {"growth": ("980080", "成长100"), "value": ("980081", "价值100")}

def _constituents(code):
    """成分股列表 [code,...] via akshare(国证指数)。运行 python 需装有 akshare。失败→None。"""
    try:
        import akshare as ak
        df = ak.index_stock_cons(symbol=code)
        return [str(c).zfill(6) for c in df["品种代码"].tolist()]
    except Exception as e:
        return None

def _stock_tail_yoy(code):
    """单只成分：取最新两期(同报告期类型) 累计营收/净利 → 同比。返回 (rev_yoy, profit_yoy) or None。
    数据走 data-source-router cn_financial_series(东财主财务)。过滤掉异常(低基数/负转正)。"""
    try:
        rows = DSR.get("cn_financial_series", secucode=f"{code}.SH" if code.startswith("6") else f"{code}.SZ",
                       report_name="RPT_F10_FINANCE_MAINFINADATA", page=6)[0]
    except Exception:
        return None
    if not isinstance(rows, list) or len(rows) < 2:
        return None
    best = None
    pairs = _group_latest2(rows, None)
    # 选最新报告期(新一期日期最近)的那组
    pairs = sorted(pairs, key=lambda p: (p[0].get("REPORT_DATE") or ""), reverse=True)
    for newer, older in pairs[:1]:  # 只取最新报告期类型
        n_rev = newer.get("TOTALOPERATEREVE"); o_rev = older.get("TOTALOPERATEREVE")
        n_np = newer.get("PARENTNETPROFIT"); o_np = older.get("PARENTNETPROFIT")
        if not all(isinstance(x, (int, float)) and x == x for x in [n_rev, o_rev, n_np, o_np]):
            continue
        if n_rev <= 0 or n_np <= 0:
            continue
        rev_yoy = (n_rev / o_rev - 1) * 100 if o_rev else None
        profit_yoy = (n_np / o_np - 1) * 100 if o_np else None
        # 低基数/异常过滤
        if profit_yoy is not None and abs(profit_yoy) > 2000:
            profit_yoy = None
        if rev_yoy is not None and abs(rev_yoy) > 2000:
            rev_yoy = None
        best = (rev_yoy, profit_yoy)
        break  # 用同一报告类型的最邻近两期
    return best

def _group_latest2(rows, keyf):
    """按『报告期类型(季)』分组(跨年同季度归一组)，组内按日期倒序，各取最新两期做同口径同比。"""
    groups = {}
    for r in rows:
        name = r.get("REPORT_DATE_NAME") or ""
        if not name:
            continue
        q = {"年报": "A", "中报": "H", "一季报": "Q1", "三季报": "Q3", "年度": "A"}.get(name[4:], "")
        if not q and "年报" in name:
            q = "A"
        if not q:
            continue
        groups.setdefault(q, []).append(r)
    pairs = []
    for q, seq in groups.items():
        seq = sorted(seq, key=lambda r: r.get("REPORT_DATE") or "", reverse=True)
        if len(seq) >= 2:
            pairs.append((seq[0], seq[1]))
    return pairs

def _agg(stocks, label):
    """等权聚合成分同比，输出 均值/中位数/去离群均值 三口径（中位数最稳健）。"""
    rev, prof = [], []
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
        for res in ex.map(_stock_tail_yoy, stocks):
            if res:
                if res[0] is not None: rev.append(res[0])
                if res[1] is not None: prof.append(res[1])
    def stats(vals):
        if not vals:
            return None, None, None
        import statistics
        mean = sum(vals) / len(vals)
        med = statistics.median(vals)
        # 去离群均值：剔除偏离均值 2σ 外的点后重算
        sd = statistics.pstdev(vals)
        if sd > 0:
            keep = [x for x in vals if abs(x - mean) <= 2 * sd]
            trimmed = sum(keep) / len(keep) if keep else mean
        else:
            trimmed = mean
        return mean, med, trimmed
    rm, rmd, rt = stats(rev)
    pm, pmd, pt = stats(prof)
    return {"rev_mean": rm, "rev_median": rmd, "rev_trimmed": rt,
            "profit_mean": pm, "profit_median": pmd, "profit_trimmed": pt,
            "n": len(stocks), "n_valid_rev": len(rev), "n_valid_prof": len(prof)}

def main():
    out = {"ok": False, "updated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), "note": ""}
    agg = {}
    for style, (code, name) in INDICES.items():
        stocks = _constituents(code)
        if not stocks:
            out["note"] = f"{name} 成分获取失败"; print(out["note"]); break
        print(f"{name}: {len(stocks)} 成分，聚合中…")
        agg[style] = _agg(stocks, name)
    if len(agg) == 2:
        g = agg["growth"]; v = agg["value"]
        def diff(gk, vk):
            gv, vv = g.get(gk), v.get(vk)
            return (gv - vv) if (gv is not None and vv is not None) else None
        out.update({
            "ok": True,
            "profit_growth_pct": g["profit_mean"], "profit_value_pct": v["profit_mean"],
            "profit_diff_pp": diff("profit_mean", "profit_mean"),
            "profit_median_diff_pp": diff("profit_median", "profit_median"),
            "profit_median_growth_pct": g["profit_median"], "profit_median_value_pct": v["profit_median"],
            "profit_trimmed_diff_pp": diff("profit_trimmed", "profit_trimmed"),
            "profit_trimmed_growth_pct": g["profit_trimmed"], "profit_trimmed_value_pct": v["profit_trimmed"],
            "rev_growth_pct": g["rev_mean"], "rev_value_pct": v["rev_mean"],
            "rev_diff_pp": diff("rev_mean", "rev_mean"),
            "rev_median_diff_pp": diff("rev_median", "rev_median"),
            "n_growth_valid": g["n_valid_prof"], "n_value_valid": v["n_valid_prof"],
            "note": "等权聚合成分净利/营收同比；均值易被暴涨股拉高，看板口径优先中位数(median)口径"})
        open(OUT, "w").write(json.dumps(out, ensure_ascii=False, indent=1))
        print("written", OUT)
        print("净利:  均值差 %+.1fpp | 中位数差 %+.1fpp | 去离群差 %+.1fpp" % (
            out["profit_diff_pp"] or 0, out["profit_median_diff_pp"] or 0, out["profit_trimmed_diff_pp"] or 0))
    else:
        open(OUT, "w").write(json.dumps(out, ensure_ascii=False, indent=1))
        print("未完成，growth_diff 写为失败(引擎走中性)")

if __name__ == "__main__":
    main()