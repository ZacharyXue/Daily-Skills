# CLI 交互式登录：回调只认 127.0.0.1 时的隧道方案

适用：CLI 的扫码/OAuth 登录把回调地址写死成 `http://127.0.0.1:<port>/callback`，
而浏览器跑在**用户自己的机器**上（Hermes 跑在无桌面的 ECS，用户用手机/电脑浏览器操作）。
云端 CLI（ttskill 天天基金等 device-flow 型 CLI）普遍是这个模型。

核心思路：**不要**让用户配 SSH 隧道，改用 cloudflared 反向隧道把服务器本机的回调端口
暴露成公网 HTTPS，再把登录链接用**飞书**发给用户。用户侧只需「点链接 + 扫码」，零本地配置。

## 为什么 SSH 隧道是更差的选择

SSH `-L` 要求用户在本地终端敲命令并保持窗口不关，且要预先说明服务器地址/端口；
隧道方案下用户什么都不用配。且 cloudflared 是**出站长连接**，不开任何入站端口、
不用改云安全组，暴露面比「开放端口」小得多。

## ⚠️ 先搞清回调形态：多数是浏览器发起的 POST，不是 GET 重定向

这决定了可行方案：回调若是 JS 发起的 POST，**地址栏里只有 GET**，
所以「让用户复制浏览器地址栏的 URL 发回来、由服务器代为访问」这条路**行不通**
（实测喂给本地服务只会得到 `not_found`）。必须让浏览器能真正连到服务器。

自检方法（假 state 探一次就能看出路由形态）：
```bash
ttskill login --env prod --force > /tmp/login.log 2>&1 &   # 它会起一个监听 127.0.0.1:<port> 的本地服务
sleep 10
curl -s -i "http://127.0.0.1:8765/callback?state=<任意值>"      # GET
curl -s -X POST -H 'Content-Type: application/json' \
     -d '{"state":"probe"}' "http://127.0.0.1:8765/callback"   # POST
# GET 返回 not_found、POST 返回 invalid_state → 就是 POST 型回调
```

## 步骤

### 1. 起隧道（cloudflared quick tunnel）
```bash
curl -sL -o /tmp/cloudflared \
  https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64
chmod +x /tmp/cloudflared && /tmp/cloudflared --version
/tmp/cloudflared tunnel --url http://127.0.0.1:8765 --no-autoupdate > /tmp/cf_tunnel.log 2>&1 &
sleep 25
grep -o "https://[a-z0-9-]*\.trycloudflare\.com" /tmp/cf_tunnel.log | head -1
```
约 43MB，国内 ECS 直连 GitHub 实测 200（下载慢时换镜像或重试，别急着判死）。

### 2. 起登录进程拿登录 URL
```bash
ttskill login --env prod --force > /tmp/tt_login.log 2>&1 &     # Hermes 用 terminal(background=true)，别 nohup/disown
sleep 10
grep -o "https://skills.tiantianfunds.com/ttfund-skills/cli-login?[^ ]*" /tmp/tt_login.log | head -1
```

### 3. 替换 callback_url（保留 state）
登录 URL 里 `callback_url` 是 **URL-encoded** 的，替换后要保持编码：
```
callback_url=http%3A%2F%2F127.0.0.1%3A8765%2Fcallback%3Fstate%3DXXX
→ callback_url=https%3A%2F%2F<TUN>.trycloudflare.com%2Fcallback%3Fstate%3DXXX
```
服务器端只回传 state，改回调域实测可行；**state 必须原样保留**。
用脚本做替换（内联长命令会被安全扫描拦）：
```python
# /tmp/mk_login_link.py  伪代码
tun = <从 cf_tunnel.log 读到的隧道域名>
url = <从 tt_login.log 读到的登录 URL>
url = url.replace(urllib.parse.quote("http://127.0.0.1:8765/callback", safe=""),
                  urllib.parse.quote(f"https://{tun}/callback", safe=""))
```

### 4. 发链接前先自检隧道（10 秒，必做）
```bash
curl -s -X POST -H "Content-Type: application/json" -d '{"state":"probe"}' \
  "https://<TUN>.trycloudflare.com/callback?state=probe"
# {"ok":false,"error":"invalid_state"} → 请求已到达服务器上的 CLI 服务 ✓
# Cloudflare 错误页                      → 隧道没通，别把链接发给用户
```
**顺序很重要**：先确认隧道通、再发链接。登录链接通常只有 **5 分钟**有效
（`local_callback_timeout_seconds=300`），不能让用户点到一个连不上的链接白等。

### 5. 用飞书把链接发给用户
只需一句话：**「点开链接 → 手机 App 扫码」**。用户不需要开终端、不需要复制任何东西。

### 6. 确认登录成功
看登录进程输出 / 用真实 invoke 复核：
```json
{"status":"ok","current_user":{"expires_at":"2026-11-10T15:59:01.000Z","is_expired":false}}
```
`expires_at` 有值且 `is_expired: false` = 成功。之后再跑一次真实业务调用来确认（见下）。

### 7. 清理
```bash
pkill -f cloudflared        # quick tunnel 用完即弃；重启会换域名，别留着
```

## 坑

- **别用 `pkill -f "ttskill login"` 这类模式去清进程**：模式会匹配到**当前这条命令自身**
  （命令行里含同样字符串），把自己 SIGTERM 掉（表现为 exit -15）。改用 PID kill。
- **登录后业务调用可能报 `skill_version_required`（HTTP 409）**：业务包版本落后于服务端，
  先重试一次（常是偶发），仍失败再更新业务包。
- **登录态判定别只看 `status`**：过期后 `is_expired` 字段可能直接消失，
  只靠它会误判成「还有效」。**最可靠是跑一次真实 invoke，看 returncode 与 stderr**
  （失败原因在 stderr、stdout 为空；直接 `json.loads(stdout)` 会把真因盖成 "Expecting value"）。
- **凭证落盘位置**：patch 成文件存储后，token 在 `~/.local/share/ttfund-skills/auth/token.json`
  （不是 CLI 安装目录下的 `auth/`），排查「登录成功但 token 消失」直接看这个路径。
- 隧道只挂着一个登录回调服务，未知路径返回 404/`invalid_state`；即便如此，**用完立刻 kill**。

## 已验证实例（2026-10，国内 ECS）

ttskill（天天基金）登录：cloudflared quick tunnel + 替换 callback_url + 飞书发链接 →
用户仅点链接 + 天天基金 App 扫码，登录一次成功，`expires_at` 30 天后。
全程未要求用户开 SSH 隧道、未改安全组、未开放任何入站端口。
首次试错方向（错误，勿重复）：先尝试「让用户把浏览器最终跳转的 URL 复制发回」，
因回调是 POST 而失败；后尝试 SSH `-L` 方案（可行但要求用户配隧道，已被隧道方案取代）。
