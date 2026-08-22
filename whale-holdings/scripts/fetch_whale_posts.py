#!/usr/bin/env python3
"""
大佬言论订阅 —— 拉取指定知识星球里关注大佬最近一段时间的言论汇总。

用法:
  python3 fetch_whale_posts.py                        # 默认: 人生要选对 / 老钱, 最近30条
  python3 fetch_whale_posts.py --group-id 222588821821 --watch 8444584182 --limit 30
  python3 fetch_whale_posts.py --json                 # JSON 输出(可管道)

依赖: zsxq-cli 已安装并登录(~/.config/zsxq-cli/config.json)。
数据源: knowledge 星球(知识星球 zsxq)。雪球需 cookie, 暂未接入。
"""
from __future__ import annotations

import argparse, json, re, subprocess, sys

# 订阅源清单: group_id -> (星球名, {关注大佬 user_id: 称呼})
SOURCES = {
    "222588821821": ("人生要选对", {"8444584182": "老钱"}),
}

HTML_TAG = re.compile(r"<e type=\"[^\"]*\"[^>]*/>")


def run(args: list[str]) -> str:
    r = subprocess.run(args, capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        raise RuntimeError(r.stderr[-1000:] or r.stdout[-1000:])
    return r.stdout


def clean(text: str | None) -> str:
    t = HTML_TAG.sub("", text or "")
    return re.sub(r" +", " ", t).strip()


def fetch_posts(group_id: str, watch: dict, limit: int, as_json: bool) -> str:
    raw = run(["zsxq-cli", "group", "+topics", "--group-id", group_id, "--limit", str(limit), "--json"])
    data = json.loads(raw)
    topics = data.get("topics_brief") or []
    hits = []
    for t in topics:
        o = t.get("owner") or {}
        name = (watch.get(o.get("user_id")) or o.get("name")) if o.get("user_id") else None
        if o.get("user_id") not in watch:
            continue
        content = clean(t.get("content"))
        ct = t.get("create_time", "")
        item = {
            "date": ct[:10],
            "author": name or o.get("name") or "?",
            "type": t.get("type", "talk"),
            "content": content[:2000],
            "ref": clean(t.get("referenced_topic", {}).get("content"))[:300] if isinstance(t.get("referenced_topic"), dict) else "",
        }
        if content:
            hits.append(item)
    if as_json:
        return json.dumps({"group_id": group_id, "count": len(hits), "posts": hits}, ensure_ascii=False, indent=2)
    lines = [f"# 大佬言论 · 共 {len(hits)} 条"]
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
    ap.add_argument("--json", action="store_true", help="JSON 输出")
    a = ap.parse_args()

    if a.group_id and a.watch:
        group_id = a.group_id
        watch = {uid: uid for uid in a.watch.split(",") if uid}
    elif a.group_id or a.watch:
        sys.exit("需同时提供 --group-id 和 --watch，或都不提供走默认订阅源")
    else:
        group_id, (_name, watch) = next(iter(SOURCES.items()))

    print(fetch_posts(group_id, watch, a.limit, a.json))


if __name__ == "__main__":
    main()