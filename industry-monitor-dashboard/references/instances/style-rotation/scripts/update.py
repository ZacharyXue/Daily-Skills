#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
update.py — 一键更新 成长vs价值风格轮动看板

流程: [可选 成分增速聚合] → fetch(取数+引擎) → render(HTML) → cp 博客 exports
用法:
  python3 scripts/update.py              # 常规: growth_diff 超过 MAX_AGE 才重算增速差
  python3 scripts/update.py --full       # 强制重算成分增速差(慢, 约1分钟)
  python3 scripts/update.py --no-growth  # 跳过增速差(用上次缓存)
"""
import os, sys, subprocess, json, datetime, argparse

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PY = "/root/hermes-venv/bin/python"   # 含 akshare/requests
MAX_AGE_DAYS = 7
EXPORTS = "/root/ZacharyXue.github.io/public/exports/style-rotation-dashboard.html"
GROWTH_DIFF = os.path.join(ROOT, "cache", "growth_diff.json")


def _run(script, args=None):
    cmd = [PY, os.path.join(HERE, script)] + (args or [])
    print(">>", " ".join(cmd))
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
    if r.stdout:
        tail = r.stdout.strip().splitlines()
        print("\n".join(tail[-6:]))
    if r.returncode != 0:
        print("!! stderr:", r.stderr[-400:] if r.stderr else "")
        sys.exit(r.returncode)


def _growth_stale():
    if not os.path.exists(GROWTH_DIFF):
        return True
    try:
        d = json.load(open(GROWTH_DIFF))
        updated = d.get("updated") or ""
        age = (datetime.datetime.now() - datetime.datetime.strptime(updated[:16], "%Y-%m-%d %H:%M")).days
        return age >= MAX_AGE_DAYS
    except Exception:
        return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--full", action="store_true", help="强制重算成分增速差")
    ap.add_argument("--no-growth", action="store_true", help="跳过成分增速差")
    args = ap.parse_args()

    if not args.no_growth and (args.full or _growth_stale()):
        print("== 成分增速差重算(等权净利/营收同比) ==")
        _run("growth_precompute.py")
    else:
        print("== 增速差命中缓存(<=%dd), 跳过 ==" % MAX_AGE_DAYS)

    _run("fetch.py")
    _run("render_html.py")

    src = os.path.join(ROOT, "output", "style-rotation-dashboard.html")
    os.makedirs(os.path.dirname(EXPORTS), exist_ok=True)
    import shutil
    shutil.copy(src, EXPORTS)
    print("== 已复制到博客 exports ==")
    print(EXPORTS)


if __name__ == "__main__":
    main()