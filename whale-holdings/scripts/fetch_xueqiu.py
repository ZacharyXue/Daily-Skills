#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
雪球大佬观点批量拉取 —— 从 data-source-router 的 xueqiu 适配器取数。

用法:
  python3 fetch_xueqiu.py                            # 全部雪球大佬, 近7天原发言
  python3 fetch_xueqiu.py --days 30                  # 近30天
  python3 fetch_xueqiu.py --gurus 鹿鼎公,段永平      # 只看部分大佬(代号见 GURU_ALIAS)
  python3 fetch_xueqiu.py --keywords 铝,神火         # 只保留提到关键词的发言
  python3 fetch_xueqiu.py --gurus 鹿鼎公 --keywords 华能 --json
  python3 fetch_xueqiu.py --fast                     # 仅调试: 缩短间隔, 禁止正式批量

⚠️ 低频规范: 默认每页间隔 15-60s 随机(模拟人类翻页), 全量13位×3页≈30-40分钟,
   批量任务请拆成多轮(如分3次各拉4-5位), 或先只看重点大佬。

依赖:
  - data-source-router 的 adapters.xueqiu（登录态由 site-login 管理, 失效会报 login_ok=false）
  - 建议 /usr/bin/python3 运行本脚本（playwright 在系统 Python）
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, "/root/zach-skills/data-source-router")
from adapters.xueqiu import user_posts  # noqa: E402

# 雪球大佬清单（user_id + 标签）。增删改这里即可。
GURUS = {
    "鹿鼎公":        {"id": "8790885129", "tag": "周期:煤炭/电力/电解铝/银行, 游戏仓月更"},
    "段永平":        {"id": "1247347556", "tag": "大道无形我有型, 价值投资/美股/苹果茅台"},
    "管我财":        {"id": "9650668145", "tag": "港股价值, 低估逆向"},
    "张翼轸":        {"id": "3559889031", "tag": "ETF/资产配置/指数化, EarlETF"},
    "丹书铁券":      {"id": "9742512811", "tag": "长期价投/私募基金"},
    "安娜2012":      {"id": "3045776970", "tag": "股债平衡, 集中持仓"},
    "孥孥的大树":    {"id": "8592131633", "tag": "股市实战/基金/宏观"},
    "紫金陈":        {"id": "6515752937", "tag": "悬疑作家, 散户视角/回撤规律"},
    "郭荆璞":        {"id": "7571730629", "tag": "行业分析师视角"},
    "jiancai":       {"id": "", "tag": ""},
    "qzy69":         {"id": "1205946512", "tag": "低产高信噪比"},
    "狗不叫":        {"id": "", "tag": ""},
    "指汇盈":        {"id": "5941996397", "tag": "基金策略/行情复盘"},
}

GURU_ALIAS = {  # 别名简化输入
    "超级鹿鼎公": "鹿鼎公",
    "大道无形我有型": "段永平",
    "大树": "孥孥的大树",
}


def resolve(names: list[str]) -> dict:
    """把用户输入的别名/昵称映射到 GURUS，支持'全部'"""
    if not names or "全部" in names:
        return GURUS
    out = {}
    for n in names:
        n = n.strip()
        key = GURU_ALIAS.get(n, n)
        if key in GURUS:
            out[key] = GURUS[key]
        else:
            print(f"⚠️ 未识别的大佬: {n}（可用: {'/'.join(GURUS)}）", file=sys.stderr)
    return out or GURUS


def fmt(hits: list[dict], guru_name: str, tag: str) -> list[str]:
    lines = []
    for h in hits:
        lines.append(f"◾ {h['date']} [{guru_name}] {h['text']}")
        lines.append(f"   🔗 {h['url']}")
    return lines


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--gurus", default="", help="逗号分隔大佬名(默认全部)")
    ap.add_argument("--keywords", default="", help="逗号分隔关键词, 只保留提到的发言")
    ap.add_argument("--days", type=int, default=7, help="时间窗口(天)")
    ap.add_argument("--max-pages", type=int, default=3, help="每人大佬最多翻页数(每页20条, 默认3)")
    ap.add_argument("--fast", action="store_true", help="调试: 缩短间隔(5-8s), 禁止正式批量使用")
    ap.add_argument("--json", action="store_true", help="JSON 输出")
    a = ap.parse_args()

    gurus = resolve([g.strip() for g in a.gurus.split(",") if g.strip()]) if a.gurus else GURUS
    since = datetime.now() - timedelta(days=a.days)
    keywords = [k.strip() for k in a.keywords.split(",") if k.strip()]

    if not a.fast:
        est_min = int(len(gurus) * a.max_pages * 0.6)  # 平均 ~37s/页
        print(f"低频模式: {len(gurus)} 位大佬 × {a.max_pages} 页 ≈ 预计 {max(est_min,1)} 分钟; "
              f"批量任务建议拆多轮(--gurus 每次3-4位)", file=sys.stderr)

    all_hits = []
    problems = []
    for name, cfg in gurus.items():
        if not cfg["id"]:
            problems.append(f"{name}: user_id 未配置(待查)") 
            continue
        try:
            res = user_posts(cfg["id"], keywords="", max_pages=a.max_pages, fast=a.fast)
        except Exception as e:
            problems.append(f"{name}: 异常 {str(e)[:80]}")
            continue
        if not res.get("ok"):
            problems.append(f"{name}: {res.get('error','')[:100]}")
            continue
        hits = []
        for h in res.get("keyword_hits", []):
            try:
                dt = datetime.strptime(h["date"], "%Y-%m-%d %H:%M")
            except Exception:
                dt = datetime.min
            if dt < since:
                continue
            t = h.get("text", "")
            if keywords and not any(k.lower() in t.lower() for k in keywords):
                continue
            hits.append({**h, "guru": name, "tag": cfg["tag"]})
        all_hits.extend(hits)
        print(f"[{datetime.now():%H:%M:%S}] {name}: 拉到 {len(res.get('keyword_hits', []))} 条, 窗口内 {len(hits)} 条",
              file=sys.stderr)

    all_hits.sort(key=lambda x: x["date"], reverse=True)

    if a.json:
        print(json.dumps({"count": len(all_hits), "problems": problems,
                          "posts": all_hits}, ensure_ascii=False, indent=2))
        return

    print(f"# 雪球大佬观点 · {a.days}天 · 共 {len(all_hits)} 条\n")
    for h in all_hits:
        print(h["date"], f"[{h['guru']}]", h["text"][:800])
        print("   ", h["url"])
        print()
    if problems:
        print("--- 问题项 ---")
        for p in problems:
            print("⚠️", p)


if __name__ == "__main__":
    main()