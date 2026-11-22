#!/usr/bin/env python3
"""博客改动的端到端校验：CDP 驱动 headless chrome，真 hover / 真 click / 读计算样式。

截图只能“看个大概”，hover/focus/剪贴板/ localStorage 这类**交互态**截图根本验不了。
本脚本直接走 CDP，能断言：
  - 计算样式（颜色、opacity、行高、::after 内容）
  - 元素几何（scrollWidth/clientWidth，判定真溢出）
  - 真实鼠标事件（Input.dispatchMouseEvent → hover / click）
  - localStorage 持久化（导航后重新读）

用法：
    python3 cdp_check.py <url> [--mobile]      # 全套检查（S5-S8 那套）
    python3 cdp_click_anchor.py <url>          # 只验锚点点击 / 剪贴板回退

依赖：/root/hermes-venv/bin/python（有 websockets）+ ms-playwright 的 chrome-headless-shell。

KICK：chrome 必须加 --remote-debugging-port，并从 /json/list 拿 webSocketDebuggerUrl；
      --dump-dom 不够用：它拿不到交互后的状态，而且**inline 经典脚本比 Astro 的 module 脚本先跑**，
      所以把诊断脚本直接插在 </body> 前会测到一个还没跑业务 JS 的中间态（踩过）。
"""
import asyncio
import glob
import json
import subprocess
import sys
import time
import urllib.request

import websockets

CH = glob.glob('/root/.cache/ms-playwright/chromium_headless_shell-*/chrome-headless-shell-linux64/chrome-headless-shell')[0]
PORT = 9334


def start_chrome(width, height):
    proc = subprocess.Popen(
        [CH, '--no-sandbox', '--disable-gpu', '--hide-scrollbars',
         f'--remote-debugging-port={PORT}', f'--window-size={width},{height}', 'about:blank'],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(80):
        try:
            data = json.load(urllib.request.urlopen(f'http://127.0.0.1:{PORT}/json/list', timeout=1))
            if data:
                return proc, data[0]['webSocketDebuggerUrl']
        except Exception:
            time.sleep(0.25)
    proc.kill()
    raise RuntimeError('chrome 起不来')


class CDP:
    def __init__(self, ws):
        self.ws = ws
        self.n = 0

    async def send(self, method, **params):
        self.n += 1
        mid = self.n
        await self.ws.send(json.dumps({'id': mid, 'method': method, 'params': params}))
        while True:
            msg = json.loads(await self.ws.recv())
            if msg.get('id') == mid:
                if 'error' in msg:
                    raise RuntimeError(f'{method}: {msg["error"]}')
                return msg.get('result', {})

    async def js(self, expr):
        r = await self.send('Runtime.evaluate', expression=expr, returnByValue=True, awaitPromise=True)
        return r.get('result', {}).get('value')

    async def center(self, selector):
        return await self.js(
            f"(() => {{ const el = document.querySelector({json.dumps(selector)});"
            " if (!el) return null; const r = el.getBoundingClientRect();"
            " return {x: r.left + r.width/2, y: r.top + r.height/2}; })()")

    async def hover(self, selector):
        c = await self.center(selector)
        if not c:
            return False
        await self.send('Input.dispatchMouseEvent', type='mouseMoved', x=c['x'], y=c['y'], buttons=0)
        return True

    async def click(self, selector):
        c = await self.center(selector)
        if not c:
            return False
        for t in ('mousePressed', 'mouseReleased'):
            await self.send('Input.dispatchMouseEvent', type=t, x=c['x'], y=c['y'],
                            button='left', clickCount=1, buttons=1)
        return True


async def main():
    url = sys.argv[1]
    mobile = '--mobile' in sys.argv
    proc, ws_url = start_chrome(390 if mobile else 1280, 900)
    try:
        async with websockets.connect(ws_url, max_size=20 * 1024 * 1024) as ws:
            cdp = CDP(ws)
            await cdp.send('Page.enable')
            await cdp.send('Runtime.enable')
            await cdp.send('Page.navigate', url=url)
            await asyncio.sleep(2.5)

            print('== 页面 ==', await cdp.js('document.title'))

            print('\n--- S5 引用块文字颜色 ---')
            print(await cdp.js(
                "(() => { const q = document.querySelector('article blockquote p');"
                " const p = document.querySelector('article .article-body > p');"
                " if (!q || !p) return '引用块或正文段落没找到（换一篇有引用块的文章再测）';"
                " const cq = getComputedStyle(q).color, cp = getComputedStyle(p).color;"
                " return (cq === cp ? '一致 ✓  ' : '不一致 ✗  ') + '引用=' + cq + ' 正文=' + cp; })()"))

            print('\n--- S6 标题锚点 ---')
            print(await cdp.js(
                "(() => { const h = document.querySelector('article .article-body h2');"
                " if (!h) return '没有 h2';"
                " const a = h.querySelector('.heading-anchor');"
                " return a ? '锚点已注入 ✓ href=' + a.getAttribute('href') + ' 静息opacity=' + getComputedStyle(a).opacity"
                "          : '锚点缺失 ✗'; })()"))
            await cdp.hover('article .article-body h2')
            await asyncio.sleep(0.4)
            print('hover 后 opacity =', await cdp.js(
                "getComputedStyle(document.querySelector('article .article-body h2 .heading-anchor')).opacity"))

            print('\n--- S7 代码块滚动提示 ---')
            print(await cdp.js(
                "(() => { const pres = [...document.querySelectorAll('article .article-body pre')]"
                ".filter(p => p.dataset.language !== 'mermaid');"
                " const wrapped = pres.filter(p => p.parentElement.classList.contains('code-scroll')).length;"
                " const info = pres.map(p => p.scrollWidth + '/' + p.clientWidth).slice(0, 4).join(' ');"
                " return '总代码块=' + pres.length + ' 已包裹=' + wrapped + ' (scrollWidth/clientWidth 前4: ' + info + ')'; })()"))
            print('注入超长行 + 触发 resize 后:')
            print(await cdp.js(
                "(() => { const pre = [...document.querySelectorAll('article .article-body pre')]"
                ".filter(p => p.dataset.language !== 'mermaid')"
                ".sort((a,b) => b.scrollWidth - a.scrollWidth)[0];"
                " const code = pre.querySelector('code');"
                " code.textContent += '\\n' + 'echo ' + 'x'.repeat(220);"
                " window.dispatchEvent(new Event('resize'));"
                " const w = pre.parentElement;"
                " return 'sw=' + pre.scrollWidth + ' cw=' + pre.clientWidth"
                "   + ' is-scrollable=' + w.classList.contains('is-scrollable')"
                "   + ' 提示文字=' + JSON.stringify(getComputedStyle(w, '::after').content); })()"))

            print('\n--- S8 阅读设置 ---')
            print('点击 Aa 前面板 hidden =', await cdp.js("document.getElementById('rp-panel').hidden"))
            await cdp.click('#rp-toggle')
            await asyncio.sleep(0.3)
            print('点击 Aa 后面板 hidden =', await cdp.js("document.getElementById('rp-panel').hidden"),
                  '| aria-expanded =', await cdp.js("document.getElementById('rp-toggle').getAttribute('aria-expanded')"))
            await cdp.click('#rp-panel [data-font="18"]')
            await asyncio.sleep(0.3)
            print(await cdp.js(
                "(() => { const cs = getComputedStyle(document.documentElement);"
                " return 'root fontSize=' + document.documentElement.style.fontSize"
                "   + ' 实际=' + cs.fontSize"
                "   + ' lineHeight 变量=' + document.documentElement.style.getPropertyValue('--reading-line-height')"
                "   + ' body行高=' + getComputedStyle(document.body).lineHeight"
                "   + ' localStorage=' + localStorage.getItem('reading-pref'); })()"))
            print('选中的按钮 aria-pressed:', await cdp.js(
                "[...document.querySelectorAll('#rp-panel [data-font]')].map(b => b.dataset.font + ':' + b.getAttribute('aria-pressed')).join(' ')"))

            await cdp.send('Page.navigate', url=url)
            await asyncio.sleep(2.0)
            print('刷新后 root fontSize =', await cdp.js('document.documentElement.style.fontSize'),
                  '| body行高 =', await cdp.js('getComputedStyle(document.body).lineHeight'))
    finally:
        proc.kill()


asyncio.run(main())
