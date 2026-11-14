# Hermes 原生接入个人微信（iLink Bot API）— 无桌面 QR 登录实战

## 结论 / 触发

用户想「Hermes 接个人微信」时，**优先用 Hermes 原生 weixin 适配器**，不要装外部桥（如 openclaw-weixin-cli，那个需要在服务器上装 openclaw 本体，又多一层依赖）。Hermes 自带 `gateway/platforms/weixin.py`，用腾讯 **iLink Bot API** 对接个人微信（区别于 WeCom 企业微信）。

本机环境（无桌面 / 只有 SSH）下，QR 登录的二维码无法在终端显示给用户看 —— 解法：**复用 Hermes 适配器内部的 QR 接口，把二维码渲染成 PNG，经飞书 MEDIA 发给用户手机微信扫**，脚本后台轮询扫码状态、确认后自动保存凭证。

## 一、关键前置（先判身份类型）

对接的是 **iLink bot 身份**（`xxx@im.bot`），**不是你的个人微信本体**。权威约束（官方 weixin.md 文档）：

- iLink bot **拉不进普通微信群**，也**收不到普通微信群的 @ 消息**（多数 bot 型账号）。`@` 你扫码用的个人微信 ≠ `@` bot（两个身份）。
- 实践中**只有 DM 可靠**。若配完群消息不达，是 iLink 端限制，不是 Hermes 的 bug。
- 群策略默认 `disabled`，设成 `open`/`allowlist` 时网关启动会打 `WARNING` 提示这个限制。
- **选型前先问用户**：他到底要「DM 用 Hermes」还是「接管个人微信收发群消息」？后者 iLink bot 路由做不到，需要另议（微信本体方案风险高）。

## 二、环境依赖（Hermes venv）

```bash
~/hermes-venv/bin/pip install aiohttp cryptography   # 适配器必需
~/hermes-venv/bin/pip install 'qrcode[pil]'          # 把二维码渲染成 PNG（本机已装 7.4.2）
```
坑：`qrcode` 没有 `__version__` 属性（用 `import qrcode; qrcode.make(...)` 验证，别读版本号报错）。
PIL 导入若报路径错：`sys.path.insert(0, '/usr/local/lib/hermes-agent')`（或 venv 的 site-packages）后再 `import qrcode, PIL.Image`。

## 三、复用适配器内部实现（核心技巧，脚本见 scripts/wx_qr_login.py）

不要跑交互式 `hermes gateway setup`（终端渲染 QR 你抓不到）。而是从 `gateway/platforms/weixin.py` 直接 import 内部函数，自己控制渲染 + 轮询：

```python
import sys, asyncio
sys.path.insert(0, "/usr/local/lib/hermes-agent")
from gateway.platforms import weixin as wx
from hermes_constants import get_hermes_home

# 复用 Hermes 已封装的 API client + SSL + 常量
resp = await wx._api_get(session, base_url=wx.ILINK_BASE_URL,
                         endpoint=f"{wx.EP_GET_BOT_QR}?bot_type=3", timeout_ms=wx.QR_TIMEOUT_MS)
qrcode_url = str(resp.get("qrcode_img_content") or "")   # 完整可扫 liteapp URL
qrcode_value = str(resp.get("qrcode") or "")
scan_data = qrcode_url if qrcode_url else qrcode_value    # 微信要扫完整 URL，不是 hex
import qrcode
img = qrcode.QRCode(version=None, error_correction=qrcode.constants.ERROR_CORRECT_M,
                    box_size=10, border=4)
img.add_data(scan_data); img.make(fit=True)
img.make_image(fill_color="black", back_color="white").save("/tmp/weixin_qr.png")
```

轮询状态（复用 `wx.EP_GET_QR_STATUS`，`get_qrcode_status?qrcode=<value>`），status 语义：
- `wait` → 继续等
- `scaned` → 用户在手机已扫码，等确认
- `scaned_but_redirect` → 取 `redirect_host` 切换 `current_base_url`
- `expired` → 重新 fetch 一张新 QR 并重渲染 PNG（自动刷新，最多 3 次；**过期要重发图片给用户**）
- `confirmed` → 取 `ilink_bot_id`/`bot_token`/`baseurl`/`ilink_user_id`，调 `wx.save_weixin_account(hermes_home, ...)` 自动写盘到 `~/.hermes/weixin/accounts/`

完整可运行脚本：`scripts/wx_qr_login.py`（后台 `python wx_qr_login.py 2>&1`，watch `READY_QRC_PNG` 标记出现就发图）。

## 四、发给用户扫码（飞书）

QR PNG 生成后，直接在回复里 `MEDIA:/tmp/weixin_qr.png`。告诉用户：
- **约 1 分钟时效，过期自动刷新**——图扫不上/变灰说一声重发。
- 扫完**手机微信里点「确认登录」**（`scaned` 只是「已扫」，要等 `confirmed`）。

后台脚本 `SUCCESS: {...}` 即登录成功、凭证已存盘。

## 五、登录后的固化

凭证已存 `~/.hermes/weixin/accounts/`，但要在 `.env` 设 `WEIXIN_ACCOUNT_ID`（+ 可选 `WEIXIN_TOKEN`），再拉起 gateway（`systemctl restart hermes-gateway`，从外部 shell 操作，见 remote-server-ops Pitfall 4）。DM 访问策略默认 `open`，要收紧设 `WEIXIN_DM_POLICY=allowlist` + `WEIXIN_ALLOWED_USERS`。

## 六、通用化：任何「登录二维码要发给用户」的场景

本技巧可推广到任意「交互式扫码登录、但你在无桌面服务器」的流程：
1. 找该服务 SDK/CLI 里「拿二维码」的内部调用点（往往是 `get_xxx_qrcode`→返回 URL 或 hex）。
2. 用 `qrcode[pil]` 渲染成 PNG 存 `/tmp`。
3. `MEDIA:` 发飞书，后台轮询状态直到确认。
4. 别把二维码 URL（带 token/bot 身份）发到第三方中转，本地渲染发图最干净。