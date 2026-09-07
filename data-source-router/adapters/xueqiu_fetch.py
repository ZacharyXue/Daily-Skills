#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
xueqiu_fetch.py — 雪球用户时间线取数（data-source-router 内部脚本）

被 adapters/xueqiu.py 以 subprocess 调起（本脚本依赖 playwright，
必须在 /usr/bin/python3 下运行；data-source-router 所在 venv 不装 playwright）。

读 site-login 的登录态（~/.cache/data-source-login/xueqiu_state.json），
翻页拉 user_timeline.json，关键词过滤本人原发言，输出 JSON 到 stdout。

用法：
    /usr/bin/python3 xueqiu_fetch.py --user-id 1247347556 --keywords 茅台,600519 --max-pages 5 \
        [--state ~/.cache/data-source-login/xueqiu_state.json]

输出 JSON：{ok, user_id, keyword_hits: [...], total_scanned, login_ok, error}
"""
import argparse
import asyncio
import json
import os
import random
import re
import sys
from datetime import datetime

from playwright.async_api import async_playwright

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
DEFAULT_STATE = os.path.expanduser("~/.cache/data-source-login/xueqiu_state.json")


def clean(s):
    if not s:
        return ""
    s = re.sub(r"<[^>]+>", "", s)
    for ent, rep in [("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"), ("&nbsp;", " ")]:
        s = s.replace(ent, rep)
    return re.sub(r"&#\d+;", "", s).strip()


def parse_ts(ts):
    try:
        return datetime.fromtimestamp(int(ts) / 1000).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return str(ts)


def is_match(text, keywords):
    t = (text or "").lower()
    return any(k.lower() in t for k in keywords)


async def fetch_json(page, url, timeout_s=15):
    try:
        return await page.evaluate("""async (u) => {
            const ctl = new AbortController();
            const to = setTimeout(() => ctl.abort(), 15000);
            try {
                const r = await fetch(u, {
                    headers: {'Accept':'application/json','X-Requested-With':'XMLHttpRequest'},
                    credentials: 'include', signal: ctl.signal
                });
                const t = await r.text();
                clearTimeout(to);
                try { return JSON.parse(t); } catch(e) { return {_raw: t.slice(0,200)}; }
            } catch(e) { clearTimeout(to); return {_error: String(e)}; }
        }""", url)
    except Exception as e:
        return {"_error": str(e)}


async def check_login(page, user_id):
    """page=2 需登录（未登录 10022）"""
    r = await fetch_json(
        page,
        f"https://xueqiu.com/v4/statuses/user_timeline.json?user_id={user_id}&page=2&count=1")
    return bool(r and r.get("statuses") is not None)


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--user-id", required=True)
    ap.add_argument("--keywords", default="")
    ap.add_argument("--max-pages", type=int, default=5)
    ap.add_argument("--state", default=DEFAULT_STATE)
    ap.add_argument("--fast", action="store_true",
                    help="调试模式: 间隔5-8s(仅连通性验证, 正式取数禁用)")
    args = ap.parse_args()

    # 模拟人类低频: 默认翻页间隔 15-60s 随机; --fast 仅调试 5-8s
    pause = lambda: asyncio.sleep(random.uniform(5, 8) if args.fast else random.uniform(15, 60))

    keywords = [k.strip() for k in args.keywords.split(",") if k.strip()]
    hits = []
    total_scanned = 0

    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-blink-features=AutomationControlled"])
            ctx_kwargs = {"user_agent": UA, "locale": "zh-CN",
                          "viewport": {"width": 1280, "height": 800}}
            if os.path.exists(args.state):
                ctx_kwargs["storage_state"] = args.state
            context = await browser.new_context(**ctx_kwargs)
            await context.add_init_script(
                "Object.defineProperty(navigator,'webdriver',{get:()=>undefined})")
            page = await context.new_page()
            await page.goto("https://xueqiu.com/", wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(2)

            if not await check_login(page, args.user_id):
                print(json.dumps({"ok": False, "login_ok": False,
                                  "error": "登录态失效（10022）——请运行 site-login 重新扫码",
                                  "keyword_hits": [], "total_scanned": 0}, ensure_ascii=False))
                await browser.close()
                return

            for pg in range(1, args.max_pages + 1):
                r = await fetch_json(
                    page,
                    f"https://xueqiu.com/v4/statuses/user_timeline.json"
                    f"?user_id={args.user_id}&page={pg}&count=20")
                if not r or r.get("error_code") or not r.get("statuses"):
                    break
                for post in r.get("statuses", []):
                    total_scanned += 1
                    text = clean(post.get("text", "") or post.get("description", ""))
                    title = clean(post.get("title", ""))
                    if text in ("", "转发微博", "轉發微博", "Repost"):
                        continue
                    rt = post.get("retweeted_status") or {}
                    rt_text = clean(rt.get("text", ""))
                    own = (title + " " + text).strip()
                    if keywords and not is_match(own, keywords):
                        continue
                    hits.append({
                        "id": str(post.get("id", "")),
                        "date": parse_ts(post.get("created_at", 0)),
                        "text": own[:500] or (rt_text[:500] if rt_text else ""),
                        "url": f"https://xueqiu.com/{args.user_id}/{post.get('id','')}",
                    })
                await pause()  # 反限流: 模拟人类翻页阅读间隔

            await browser.close()

        print(json.dumps({"ok": True, "login_ok": True, "user_id": args.user_id,
                          "keyword_hits": hits, "total_scanned": total_scanned,
                          "error": ""}, ensure_ascii=False))
    except Exception as e:
        print(json.dumps({"ok": False, "login_ok": False,
                          "error": f"xueqiu_fetch 异常: {str(e)[:200]}",
                          "keyword_hits": [], "total_scanned": 0}, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())