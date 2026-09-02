#!/usr/bin/env python3
"""data-source-router CodeAct 层自检 — 真实取数验证（不猜）。

覆盖 4 个 CodeAct 优化点：意图解析/成功判定/摘要+指针/确定性失败链。
用法：python3 selfcheck.py  （退出码 0=全通过）
"""
import sys, json
sys.path.insert(0, "/root/zach-skills/data-source-router")

from data_router import get, achieve, fetch_detail, resolve_intent, validate
from data_router import INTENT_MAP, VALIDATORS, FAILOVER_KINDS

PASS = []
def check(name, cond, detail=""):
    PASS.append(cond)
    print(("  ✅" if cond else "  ❌"), name, detail)

def main():
    print("[1] 意图地图 DSL")
    k, p = resolve_intent("kline", symbol="600519")
    check("kline归一symbol", k == "cn_stock_kline" and p["symbol"] == "sh600519", p)
    k2, _ = resolve_intent("financial_series", code="600519")
    check("financial_series路由kind", k2 == "cn_financial_series")
    check("意图地图覆盖", len(INTENT_MAP) >= 10, f"{len(INTENT_MAP)} intent")

    print("[2] 成功判定 DSL")
    check("quote有效", validate("cn_stock_quote", {"name":"x","price":1.0})[0])
    check("quote无效拒绝", not validate("cn_stock_quote", {"price":0})[0])
    check("kline空拒绝", not validate("cn_stock_kline", [])[0])
    check("校验器覆盖", len(VALIDATORS) >= 20, f"{len(VALIDATORS)} kinds")

    print("[3] 摘要+指针")
    r = achieve("kline", symbol="600519", count=60)
    check("kline取数成功", r.ok, r.reason)
    check("kline摘要化", all(x in r.summary for x in ("bars","to","high","low")), json.dumps(r.summary, ensure_ascii=False)[:120])
    check("kline回源data_ref", bool(r.data_ref) and r.big)
    if r.data_ref:
        d = fetch_detail(r.data_ref)
        check("fetch_detail还原全量", isinstance(d, list) and len(d) == 60, f"{len(d)} bars")
    r2 = achieve("gh_repo", owner="volcano-sh", repo="volcano")
    check("gh_repo关键字段摘取", r2.ok and "stargazers_count" in r2.summary, f"{r2.raw_size_hint}B {json.dumps(r2.summary,ensure_ascii=False)[:80]}")

    print("[4] 确定性失败链")
    check("失败链配置", len(FAILOVER_KINDS) >= 3, str(FAILOVER_KINDS))
    check("未知意图兜底", not achieve("no_such_intent").ok)

    print("\n=================")
    if all(PASS):
        print(f"✅ 全部 {len(PASS)} 项自检通过（4 个 CodeAct 优化点就绪）")
        return 0
    print(f"❌ {len(PASS)-sum(PASS)}/{len(PASS)} 项失败")
    return 1

if __name__ == "__main__":
    sys.exit(main())