#!/usr/bin/env python3
"""每日晚间提醒（22:00）— no_agent cron 脚本，零 token。

读取 deepdive-backlog.md 中 ⭐ 在做条目 + 最新条目，生成睡前提醒。
输出空则 cron 不投递（内容缺失时宁可不发，不发错消息）。
"""
import re
import sys
from pathlib import Path

BACKLOG = Path("/root/zach-skills/career-data/deepdive-backlog.md")


def main() -> str:
    if not BACKLOG.exists():
        return "子皓，睡前提醒：深挖池文件没找到，今天要不要看一眼 backlog？"

    text = BACKLOG.read_text(encoding="utf-8")

    # ⭐ 在做条目（可能有多个）
    doing = [l.strip() for l in text.splitlines() if "⭐" in l and l.strip().startswith("- [ ]")]
    # 最新新增条目：主攻线1里最近加的（取每条里的「今天新增」标记）
    new_items = [l.strip() for l in text.splitlines()
                 if "今天新增" in l and l.strip().startswith("- [ ]")]

    if not doing and not new_items:
        return "子皓，睡前提醒：深挖池空着，今天过得怎么样？有值得记的点就丢进 backlog。"

    lines = ["子皓，睡前提一嘴，自己定节奏："]

    if doing:
        lines.append(f"⭐ 在做的：{extract_title(doing[0])}。")
        if len(doing) > 1:
            for d in doing[1:]:
                lines.append(f"   也在做：{extract_title(d)}。")
    if new_items:
        # 最新条目：取 last，通常是刚记的
        newest = extract_title(new_items[-1])
        lines.append(f"池里新记的：{newest}——不急，想碰就碰。")

    lines.append("今晚挖哪个/休息，你说的算。")
    return "\n".join(lines)


def extract_title(line: str) -> str:
    """从 '- [ ] **标题**（说明）...' 提取标题，截断过长描述。"""
    m = re.search(r"\*\*(.+?)\*\*", line)
    if m:
        return m.group(1)
    # 兜底：取前 30 字
    return line.lstrip("- [ ] ")[:30]


if __name__ == "__main__":
    out = main()
    if out:
        print(out, flush=True)
    else:
        # 空输出 → cron 不投递
        sys.exit(0)