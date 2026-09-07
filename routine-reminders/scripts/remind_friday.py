#!/usr/bin/env python3
"""周五例行提醒（21:00）— no_agent cron 脚本，零 token。

周五提醒 = 职业一周复盘 + 理财检查 + 习惯打卡，简短给三点，不做具体执行。
"""
import sys
from pathlib import Path

BACKLOG = Path("/root/zach-skills/career-data/deepdive-backlog.md")
LEDGER = Path("/root/zach-skills/career-data/knowledge-ledger.md")


def main() -> str:
    lines = ["子皓，周五例行三问，10 分钟搞定就收工："]

    # 1. 职业：本周深挖池动了什么
    if BACKLOG.exists():
        text = BACKLOG.read_text(encoding="utf-8")
        done = [l.strip() for l in text.splitlines() if l.strip().startswith("- [x]")]
        doing = [l.strip() for l in text.splitlines() if "⭐" in l and l.strip().startswith("- [ ]")]
        if done:
            lines.append(f"① 职业·本周挖完：{title_of(done[-1])}——可考虑沉淀成博客/简历点了。")
        elif doing:
            lines.append(f"① 职业·还在做：{title_of(doing[0])}，下周接着推。")
        else:
            lines.append("① 职业·池子这周没动，下周挖一个就成。")
    else:
        lines.append("① 职业·backlog 缺失，待补（正常流程会读深挖池）。")

    # 2. 理财：周五惯例——看一眼持仓/估值（提醒，不自动执行）
    lines.append("② 理财·周末前看一眼：持仓估值分位/回撤有没有到买点区间？看板在博客 exports 下，5 分钟完事。")

    # 3. 习惯：打卡回顾
    lines.append("③ 习惯·本周三件小事打个勾（锻炼/早睡/阅读），没做到下周留一个就够。")

    lines.append("周末愉快，别卷。")
    return "\n".join(lines)


def title_of(line: str) -> str:
    import re
    m = re.search(r"\*\*(.+?)\*\*", line)
    return m.group(1) if m else line.lstrip("- [x] ")[:30]


if __name__ == "__main__":
    print(main(), flush=True)
    sys.exit(0)