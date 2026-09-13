#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
机构态度印证脚本 — 用卖方研报数据验证你对个股的观点
=====================================================
用法:
    python3 institution_attitude.py 600585
    python3 institution_attitude.py 600585 --view 看空   # 带着观点看数据
    python3 institution_attitude.py 600585 --view 抄底   # 带着观点看数据

数据源: 东财研报中心 (经 data-source-router cn_research_report)
卖方评级永远喊多(钝化) → 评级分布只能参考;
真正有效的信号 = ①研报覆盖密度趋势 ②是否敢给目标价 ③EPS预测方向 ④研报标题措辞。

输出: 结构化「印证结论」, 用于回答: 你的观点 vs 机构动向, 谁在支持谁。
"""
import sys, os, json, datetime

def _root():
    d = os.path.dirname(os.path.abspath(__file__))
    for _ in range(6):
        if os.path.isdir(os.path.join(d, "data-source-router")):
            return d
        d = os.path.dirname(d)
    return os.environ.get("ZACH_SKILLS", "/root/zach-skills")

sys.path.insert(0, os.path.join(_root(), "data-source-router"))
from data_router import get

VIEWS = {
    "看空":  "你觉得它要跌/不值得买",
    "看多":  "你觉得它值得买/被低估",
    "抄底":  "你觉得跌到底了，想接",
    "回避":  "你不确定，想看看机构是不是也看空",
}

def analyze(code, years=3):
    d, src, meta, tier = get("cn_research_report", code=code, years=years)
    if not d.get("ok"):
        return {"ok": False, "note": d.get("note", "")}
    reps = d.get("reports", [])
    by_year = d.get("by_year", {})
    by_rating = d.get("by_rating", {})

    # ---- 1. 覆盖密度趋势 ----
    yl = sorted(by_year.keys())
    total = d.get("count", 0)
    yr_avg = total / max(1, len(yl))
    recent = sum(by_year.get(y, 0) for y in yl[-1:])          # 最近一年
    shrunk = recent < yr_avg * 0.6
    growing = recent > yr_avg * 1.2

    # ---- 2. 目标价覆盖 ----
    with_aim = [r for r in reps if r.get("aim_price")]
    aim_recent = [r for r in with_aim if (r.get("date") or "")[:4] in (yl[-1:] or [""])]
    aim_ever = len(with_aim) > 0

    # ---- 3. EPS 预测方向 ----
    eps_this = [float(r["eps_this"]) for r in reps if r.get("eps_this")]
    eps_next = [float(r["eps_next"]) for r in reps if r.get("eps_next")]
    e_this_mid = sorted(eps_this)[len(eps_this)//2] if eps_this else None
    e_next_mid = sorted(eps_next)[len(eps_next)//2] if eps_next else None
    eps_dir = None
    if e_this_mid and e_next_mid:
        eps_dir = "上修" if e_next_mid > e_this_mid * 1.03 else ("下修" if e_next_mid < e_this_mid * 0.97 else "持平")

    # ---- 4. 研报标题情绪 ----
    titles = [r.get("title", "") for r in reps]
    neg_kw = ["承压", "压力", "下滑", "回落", "低迷", "底部", "谨慎", "担忧", "不及预期", "阵痛", "挑战", "调整期"]
    pos_kw = ["反转", "改善", "拐点", "回暖", "修复", "成长", "高景气", "超预期", "布局", "价值", "推荐", "高增"]
    neg_hits = sum(any(k in t for k in neg_kw) for t in titles)
    pos_hits = sum(any(k in t for k in pos_kw) for t in titles)

    # ---- 5. 机构数 ----
    orgs = len(set(r.get("org", "") for r in reps))

    return {
        "ok": True, "code": code, "years": years,
        "total": total, "by_year": by_year, "by_rating": by_rating,
        "orgs": orgs, "shrunk": shrunk, "growing": growing,
        "aim_total": len(with_aim), "aim_recent": len(aim_recent), "aim_ever": aim_ever,
        "eps_this_mid": e_this_mid, "eps_next_mid": e_next_mid, "eps_dir": eps_dir,
        "neg_titles": neg_hits, "pos_titles": pos_hits,
        "recent_year": yl[-1] if yl else None, "recent_count": recent,
        "sample_recent": [{"d": r["date"], "org": r["org"], "rating": r["rating"], "t": r["title"][:36]}
                          for r in reps[-5:]],
    }

def verdict(code, view=None, years=3):
    a = analyze(code, years)
    if not a.get("ok"):
        return f"❌ {code} 机构数据获取失败: {a.get('note','')}"
    L = []
    L.append(f"===== 机构态度印证 · {code} =====")
    L.append(f"近{years}年研报: {a['total']}篇 | 机构 {a['orgs']}家 | 年度分布 {a['by_year']}")
    L.append(f"评级分布: {a['by_rating']}")
    cov = "⚠️ 覆盖收缩" if a["shrunk"] else ("✅ 覆盖增长" if a["growing"] else "➖ 覆盖平稳")
    L.append(f"覆盖趋势: {cov} (最近一年 {a['recent_count']}篇)")
    if a["aim_ever"]:
        L.append(f"目标价: 历史给过 {a['aim_total']} 篇, 最近一年仅 {a['aim_recent']} 篇" +
                 ("= ⚠️ 机构不敢定价(看空信号)" if a["aim_recent"] == 0 else "= 仍有定价锚"))
    else:
        L.append("目标价: 从未给过。⚠️ 若同业普遍给目标价而它不给=机构回避定价；若行业普遍不给=常态（需对比同业判断）")
    if a["eps_dir"]:
        L.append(f"EPS预测: 今年中位 {a['eps_this_mid']} → 明年中位 {a['eps_next_mid']} = {a['eps_dir']}")
    L.append(f"标题情绪: 负面词 {a['neg_titles']} 条 / 正面词 {a['pos_titles']} 条")
    if a["sample_recent"]:
        L.append("最近研报:")
        for r in a["sample_recent"]:
            L.append(f"  [{r['d']}] {r['org']} {r['rating']} {r['t']}")

    # ---- 观点对照 ----
    # 看空信号强度排序：覆盖收缩 > EPS下修 > 目标价从有到无 > 标题负面
    bear_signals = []
    if a["shrunk"]: bear_signals.append("研报覆盖在收缩")
    if a["eps_dir"] == "下修": bear_signals.append("EPS预测在下调")
    if a["aim_ever"] and a["aim_recent"] == 0: bear_signals.append("目标价从有到无(机构不敢定价)")
    if a["neg_titles"] > a["pos_titles"]: bear_signals.append("研报标题偏负面")
    bull_signals = []
    if a["growing"]: bull_signals.append("研报覆盖在扩张")
    if a["aim_recent"] > 0: bull_signals.append("机构仍在给目标价")
    if a["eps_dir"] == "上修": bull_signals.append("EPS预测在上调")
    if a["pos_titles"] > a["neg_titles"]: bull_signals.append("研报标题偏正面")

    if view:
        L.append("")
        L.append(f"── 你带着观点「{VIEWS.get(view, view)}」──")
        if view in ("看空", "回避"):
            if bear_signals: L.append("✅ 有 " + str(len(bear_signals)) + " 项信号支持你的观点: " + "、".join(bear_signals))
            else: L.append("⚠️ 无机构信号支持看空——你可能是少数派, 检查逻辑")
            if a["growing"]: L.append("   ⚠️ 反面: 覆盖在扩张")
        elif view in ("看多", "抄底"):
            if bull_signals: L.append("✅ 有 " + str(len(bull_signals)) + " 项信号支持你的观点: " + "、".join(bull_signals))
            else: L.append("⚠️ 无机构信号支持抄底——逆势行为需更强理由（估值安全边际?）")
            if bear_signals: L.append("   ⚠️ 反面信号: " + "、".join(bear_signals[:2]))
    return "\n".join(L)

if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    code = args[0] if args else None
    view = None
    if "--view" in sys.argv:
        i = sys.argv.index("--view")
        if i + 1 < len(sys.argv): view = sys.argv[i+1]
    years = 3
    if "--years" in sys.argv:
        i = sys.argv.index("--years")
        if i + 1 < len(sys.argv): years = int(sys.argv[i+1])
    if not code:
        print(__doc__); sys.exit(1)
    print(verdict(code, view, years))