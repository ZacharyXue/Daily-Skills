#!/usr/bin/env python3
"""
知识星球「大佬言论」拉取 —— 人生要选对等星球的关注大佬发言，支持时间段过滤与关键词搜索。

用法:
  python3 fetch_whale_posts.py                        # 默认: 人生要选对/老钱, 最近30条
  python3 fetch_whale_posts.py --days 7               # 近一周发言
  python3 fetch_whale_posts.py --search 铝            # 星球内全文搜索"铝"相关主题
  python3 fetch_whale_posts.py --search 神火 --group-id 222588821821
  python3 fetch_whale_posts.py --json

依赖: zsxq-cli 已安装并登录(~/.config/zsxq-cli/config.json)。
数据源: 知识星球 zsxq。雪球走 fetch_xueqiu.py。
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timedelta

# 订阅源清单: group_id -> (星球名, {关注大佬 user_id: 称呼})
SOURCES = {
    "222588821821": ("人生要选对", {"8444584182": "老钱"}),
}

HTML_TAG = re.compile(r"<e type=\"[^\"]*\"[^>]*/>")


def run(args: list[str]) -> str:
    r = subprocess.run(args, capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        raise RuntimeError(r.stderr[-1000:] or r.stdout[-1000:])
    return r.stdout


def clean(text: str | None) -> str:
    t = HTML_TAG.sub("", text or "")
    return re.sub(r" +", " ", t).strip()


def fetch_posts_by_time(group_id: str, watch: dict, days: int, as_json: bool) -> str:
    """按时间窗口拉取：先取最近N条再过滤"""
    raw = run(["zsxq-cli", "group", "+topics", "--group-id", group_id,
               "--limit", "30", "--json"])
    data = json.loads(raw)
    topics = data.get("topics_brief") or []
    since = datetime.now() - timedelta(days=days)
    hits = []
    for t in topics:
        o = t.get("owner") or {}
        if o.get("user_id") not in watch and not watch:
            continue
        ct = t.get("create_time", "")
        try:
            dt = datetime.fromisoformat(ct.replace("Z", "+00:00")).replace(tzinfo=None)
            dt = dt - timedelta(hours=8) if ct.endswith(("+00:00", "Z")) else dt
        except Exception:
            dt = datetime.min
        if dt < since:
            continue
        content = clean(t.get("content"))
        if not content:
            continue
        hits.append({
            "date": ct[:10],
            "author": watch.get(o.get("user_id")) or o.get("name") or "?",
            "type": t.get("type", "talk"),
            "content": content[:2000],
            "ref": clean(t.get("referenced_topic", {}).get("content"))[:300]
                   if isinstance(t.get("referenced_topic"), dict) else "",
        })
    hits.sort(key=lambda x: x["date"], reverse=True)
    return render(hits, as_json, title=f"近{days}天" if days else "")


def fetch_posts_search(group_id: str, query: str, as_json: bool) -> str:
    """星球内全文搜索（zsxq-cli topic +search, RAG 语义匹配）"""
    raw = run(["zsxq-cli", "topic", "+search", "--group-id", group_id,
               "--query", query, "--json"])
    data = json.loads(raw)
    topics = data.get("topics_brief") or data.get("topics") or []
    hits = []
    for t in topics:
        o = t.get("owner") or {}
        content = clean(t.get("content") or t.get("digest") or "")
        if not content:
            continue
        hits.append({
            "date": (t.get("create_time") or "")[:10],
            "author": o.get("name") or "?",
            "type": t.get("type", "talk"),
            "content": content[:2000],
            "ref": "",
        })
    return render(hits, as_json, title=f"搜索「{query}」")


def render(hits: list[dict], as_json: bool, title: str = "") -> str:
    if as_json:
        return json.dumps({"count": len(hits), "posts": hits},
                          ensure_ascii=False, indent=2)
    label = f" · {title}" if title else ""
    lines = [f"# 大佬言论 · {len(hits)} 条{label}"]
    for h in hits:
        lines.append(f"\n◾ {h['date']} [{h['author']}] #{h['type']}")
        lines.append(f"   {h['content']}")
        if h["ref"]:
            lines.append(f"   └转发: {h['ref']}")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--group-id", help="知识星球 group_id(默认走 SOURCES 订阅源)")
    ap.add_argument("--watch", help="关注大佬 user_id, 逗号分隔(默认走 SOURCES)")
    ap.add_argument("--limit", type=int, default=30, help="拉取最近N条候选主题")
    ap.add_argument("--days", type=int, default=0, help="近N天发言(0=关闭)")
    ap.add_argument("--search", default="", help="星球内全文搜索关键词(与--days互斥)")
    ap.add_argument("--json", action="store_true", help="JSON 输出")
    a = ap.parse_args()

    if a.group_id and a.watch:
        group_id = a.group_id
        watch = {uid: uid for uid in a.watch.split(",") if uid}
    elif a.group_id or a.watch:
        sys.exit("需同时提供 --group-id 和 --watch，或都不提供走默认订阅源")
    else:
        group_id, (_name, watch) = next(iter(SOURCES.items()))

    if a.search:
        print(fetch_posts_search(group_id, a.search, a.json))
    elif a.days:
        print(fetch_posts_by_time(group_id, watch, a.days, a.json))
    else:
        # 兼容旧行为: 按 --limit 拉最近N条
        raw = run(["zsxq-cli", "group", "+topics", "--group-id", group_id,
                   "--limit", str(a.limit), "--json"])
        data = json.loads(raw)
        topics = data.get("topics_brief") or []
        hits = []
        for t in topics:
            o = t.get("owner") or {}
            if o.get("user_id") not in watch:
                continue
            content = clean(t.get("content"))
            if not content:
                continue
            hits.append({
                "date": (t.get("create_time") or "")[:10],
                "author": watch.get(o.get("user_id")) or o.get("name") or "?",
                "type": t.get("type", "talk"),
                "content": content[:2000],
                "ref": clean(t.get("referenced_topic", {}).get("content"))[:300]
                         if isinstance(t.get("referenced_topic"), dict) else "",
            })
        print(render(hits, a.json))


if __name__ == "__main__":
    main()