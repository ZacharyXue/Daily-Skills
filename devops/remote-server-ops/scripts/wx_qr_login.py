#!/usr/bin/env python3
"""复用 Hermes 的 Weixin iLink QR 登录, 把二维码渲染成 PNG 供飞书发送。

在无桌面服务器上运行, 后台跑本脚本:
    /root/hermes-venv/bin/python wx_qr_login.py 2>&1
首次拿到二维码会打印 READY_QRC_PNG:/tmp/weixin_qr.png — 该图片用 MEDIA: 发飞书给用户扫。
后台轮询扫码状态; 扫码确认后自动保存凭证到 ~/.hermes/weixin/accounts/ 并打印 SUCCESS。

依赖: ~/hermes-venv 里装 aiohttp cryptography 'qrcode[pil]'。
前置: Hermes 源码在 /usr/local/lib/hermes-agent。
"""
import asyncio
import sys

sys.path.insert(0, "/usr/local/lib/hermes-agent")

import aiohttp
import qrcode

from gateway.platforms import weixin as wx
from hermes_constants import get_hermes_home

QR_PNG = "/tmp/weixin_qr.png"
BOT_TYPE = "3"
TIMEOUT_S = 480


def render_png(scan_data: str, path: str = QR_PNG) -> None:
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )
    qr.add_data(scan_data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    img.save(path)
    print(f"READY_QRC_PNG:{path}", flush=True)


async def _fetch_qr(session):
    resp = await wx._api_get(
        session,
        base_url=wx.ILINK_BASE_URL,
        endpoint=f"{wx.EP_GET_BOT_QR}?bot_type={BOT_TYPE}",
        timeout_ms=wx.QR_TIMEOUT_MS,
    )
    qrcode_value = str(resp.get("qrcode") or "")
    qrcode_url = str(resp.get("qrcode_img_content") or "")
    if not qrcode_value:
        raise RuntimeError("QR response missing qrcode")
    scan_data = qrcode_url if qrcode_url else qrcode_value
    return qrcode_value, scan_data


async def main():
    hermes_home = str(get_hermes_home())
    connector = wx._make_ssl_connector()
    async with aiohttp.ClientSession(trust_env=True, connector=connector) as session:
        qr_value, scan_data = await _fetch_qr(session)
        render_png(scan_data)
        print(f"QR_KEY:{qr_value}", flush=True)
        print(f"QR_SCAN_DATA:{scan_data}", flush=True)

        deadline = asyncio.get_event_loop().time() + TIMEOUT_S
        current_base = wx.ILINK_BASE_URL
        refresh_count = 0

        while True:
            if asyncio.get_event_loop().time() > deadline:
                print("ERROR: 微信登录超时", flush=True)
                return None
            try:
                status_resp = await wx._api_get(
                    session,
                    base_url=current_base,
                    endpoint=f"{wx.EP_GET_QR_STATUS}?qrcode={qr_value}",
                    timeout_ms=wx.QR_TIMEOUT_MS,
                )
            except asyncio.TimeoutError:
                await asyncio.sleep(1)
                continue
            except Exception as exc:
                print(f"WARN poll error: {exc}", flush=True)
                await asyncio.sleep(1)
                continue

            status = str(status_resp.get("status") or "wait")
            if status == "wait":
                pass
            elif status == "scaned":
                print("STATUS: 已扫码, 请在微信确认", flush=True)
            elif status == "scaned_but_redirect":
                redirect_host = str(status_resp.get("redirect_host") or "")
                if redirect_host:
                    current_base = f"https://{redirect_host}"
            elif status == "expired":
                refresh_count += 1
                if refresh_count > 3:
                    print("ERROR: 二维码多次过期", flush=True)
                    return None
                print(f"STATUS: 二维码过期, 刷新 ({refresh_count}/3)", flush=True)
                try:
                    qr_value, scan_data = await _fetch_qr(session)
                    render_png(scan_data)  # 过期重渲染了, 要重发图片给用户
                    print(f"QR_KEY:{qr_value}", flush=True)
                except Exception as exc:
                    print(f"WARN refresh failed: {exc}", flush=True)
                    return None
            elif status == "confirmed":
                account_id = str(status_resp.get("ilink_bot_id") or "")
                token = str(status_resp.get("bot_token") or "")
                base_url = str(status_resp.get("baseurl") or wx.ILINK_BASE_URL)
                user_id = str(status_resp.get("ilink_user_id") or "")
                if not account_id or not token:
                    print("ERROR: 扫码确认但凭证不完整", flush=True)
                    return None
                wx.save_weixin_account(
                    hermes_home,
                    account_id=account_id,
                    token=token,
                    base_url=base_url,
                    user_id=user_id,
                )
                result = {
                    "account_id": account_id,
                    "token": token,
                    "base_url": base_url,
                    "user_id": user_id,
                }
                print(f"SUCCESS: {result}", flush=True)
                return result
            await asyncio.sleep(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n用户中断", flush=True)