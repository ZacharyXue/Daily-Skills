#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
雪球（xueqiu）守护式扫码登录 — site-login skill 适配器

用法（务必用 /usr/bin/python3）：
    /usr/bin/python3 xueqiu_login.py                # 登录（state 有效则直接退出；无效重新扫码）
    /usr/bin/python3 xueqiu_login.py --force        # 强制重新登录
    /usr/bin/python3 xueqiu_login.py --check        # 仅检查登录态有效性

state 默认存 ~/.cache/data-source-login/xueqiu_state.json（可用 --state 覆盖）

设计要点（不要破坏）：
1. 登录判定用 user_timeline **page=2**（未登录返回 10022）——page=1 是公开数据会假阳性
2. 浏览器保持打开直到登录成功——中途关闭扫码结果丢失
3. 二维码用 canvas.toDataURL() 导出纯像素——坐标截图会混入文字
"""
import argparse
import asyncio
import base64
import json
import os
import sys
from datetime import datetime
from pathlib import Path

from playwright.async_api import async_playwright

USER_ID = "1247347556"  # 段永平，仅用于登录验证（任选一个有公开时间线的用户即可）
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

DEFAULT_STATE = os.path.join(
    os.path.expanduser("~/.cache/data-source-login"), "xueqiu_state.json"
)
QR_PATH = os.path.join(os.path.expanduser("~/.cache/data-source-login"), "xueqiu_qr.png")
WINDOW_SECONDS = 10 * 60  # 扫码窗口

# 伪装脚本：隐藏 webdriver
STEALTH_JS = "Object.defineProperty(navigator,'webdriver',{get:()=>undefined})"


def log(msg):
    print(f"[{datetime.now():%H:%M:%S}] {msg}", flush=True)


async def verify_login(page):
    """登录判定：user_timeline page=2（未登录返回 error_code 10022）"""
    try:
        r = await page.evaluate("""async () => {
            const resp = await fetch('https://xueqiu.com/v4/statuses/user_timeline.json?user_id=1247347556&page=2&count=1', {
                headers: {'Accept':'application/json','X-Requested-With':'XMLHttpRequest'},
                credentials: 'include'
            });
            const t = await resp.text();
            try { return JSON.parse(t); } catch(e) { return {_raw: t.slice(0,200)}; }
        }""")
        return isinstance(r, dict) and r.get("statuses") is not None
    except Exception as e:
        log(f"verify 异常: {e}")
        return False


async def export_qr(page):
    """导出二维码：优先 canvas.toDataURL，无 canvas 则回退坐标截图"""
    try:
        data = await page.evaluate("""() => {
            const cs = document.querySelectorAll('canvas');
            for (const c of cs) {
                if (c.width >= 200 && c.width <= 300) {
                    try { return {w: c.width, h: c.height, data: c.toDataURL('image/png')}; }
                    catch(e) { return {w: c.width, h: c.height, data: '', err: String(e)}; }
                }
            }
            return null;
        }""")
        if data and data.get("data"):
            raw = base64.b64decode(data["data"].split(",")[1])
            Path(QR_PATH).parent.mkdir(parents=True, exist_ok=True)
            with open(QR_PATH, "wb") as f:
                f.write(raw)
            return len(raw)
    except Exception as e:
        log(f"导出失败: {e}")
    return 0


async def create_context(pw, state_path):
    browser = await pw.chromium.launch(
        headless=True,
        args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
    )
    kwargs = {
        "user_agent": UA,
        "locale": "zh-CN",
        "viewport": {"width": 1280, "height": 900},
    }
    if os.path.exists(state_path):
        kwargs["storage_state"] = state_path
    context = await browser.new_context(**kwargs)
    await context.add_init_script(STEALTH_JS)
    return browser, context


async def do_login(browser, context, page):
    """完整登录流程：出码 → 等扫码 → 轮询 → 落盘 → 复验"""
    # 点「二维码登录」tab
    for attempt in range(3):
        try:
            el = page.locator("text=二维码登录").first
            if await el.count() > 0 and await el.is_visible():
                await el.click(timeout=5000)
                log("已点二维码tab")
                break
        except Exception:
            await asyncio.sleep(2)
    await asyncio.sleep(2)

    deadline = asyncio.get_event_loop().time() + WINDOW_SECONDS
    n = 0
    while asyncio.get_event_loop().time() < deadline:
        n += 1
        size = await export_qr(page)
        if n == 1 or n % 6 == 0:
            log(f"二维码已导出 {size}B → {QR_PATH}（第{n}次）")
        if await verify_login(page):
            log("✓ 登录成功！保存 state...")
            Path(os.path.dirname(state_path)).mkdir(parents=True, exist_ok=True)
            await context.storage_state(path=state_path)
            os.chmod(state_path, 0o600)
            log(f"state 已保存 → {state_path}")
            # 复验
            if await verify_login(page):
                log("✓ state 复验有效")
            else:
                log("✗ state 复验异常，请重试")
            await browser.close()
            return True
        await asyncio.sleep(5)

    log("扫码窗口超时（10 分钟），未检测到登录")
    await browser.close()
    return False


async def main():
    parser = argparse.ArgumentParser(description="雪球守护式扫码登录")
    parser.add_argument("--state", default=DEFAULT_STATE, help="state 文件路径")
    parser.add_argument("--force", action="store_true", help="强制重新登录")
    parser.add_argument("--check", action="store_true", help="仅检查登录态")
    args = parser.parse_args()
    global state_path, QR_PATH
    state_path = args.state

    async with async_playwright() as pw:
        browser, context = await create_context(pw, args.state)
        page = await context.new_page()
        await page.goto("https://xueqiu.com/", wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(3)

        # --check：仅验证现有 state
        if args.check:
            ok = await verify_login(page)
            log(f"登录态检查: {'✓ 有效' if ok else '✗ 无效（需重新扫码）'}")
            await browser.close()
            sys.exit(0 if ok else 1)

        # 已有 state 且不强制：先试复用
        if os.path.exists(args.state) and not args.force:
            if await verify_login(page):
                log("✓ 复用已有登录态（有效）")
                await browser.close()
                sys.exit(0)
            log("已有 state 无效，重新登录")

        ok = await do_login(browser, context, page)
        sys.exit(0 if ok else 1)


if __name__ == "__main__":
    state_path = DEFAULT_STATE
    asyncio.run(main())