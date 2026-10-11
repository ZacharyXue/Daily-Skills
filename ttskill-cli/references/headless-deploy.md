# 无桌面服务器（ECS）部署与远程登录

本文件是 `ttskill-cli` 的 ECS 专项补充。**桌面环境不需要读这个文件**——桌面上 `ttskill login` 会自己弹浏览器，正常登录即可。

需要读它的场景：
- 在无桌面 Linux 服务器（阿里云 ECS 等）上装 ttskill
- `ttskill login` 报 `Linux Secret Service 写入失败: secret-tool: Cannot autolaunch D-Bus without X11 $DISPLAY`
- token 30 天过期，需要让用户重新扫码

---

## 一、安装（ECS 特有的三个坑）

> 与主文档 `SKILL.md` 的「安装」章节配合看：这里只列 ECS 上**额外会踩**的坑，Step 3「写入 Agent 入口」/ Step 4「同步业务包」/ Step 5「刷新路由」的常规命令不重复。

### 1. 取下载地址 → 下载 → 解压

```bash
# 取下载地址（返回 JSON 里的 data.download_url）
curl -sL "https://skills.tiantianfunds.com/ai-smart-skill-service/openapi/base-package/resolve?platform=linux&arch=x64&env=prod"

curl -sL --max-time 120 -o /tmp/ttskill-base.zip "<download_url>"
echo "<sha256>  ttskill-base.zip" | sha256sum -c -

# ⚠️ ECS 常无 unzip：用 Python 解压
rm -rf /tmp/ttskill-extract && mkdir /tmp/ttskill-extract
python3 -c "
import zipfile
with zipfile.ZipFile('/tmp/ttskill-base.zip') as z:
    z.extractall('/tmp/ttskill-extract')
"
```

### 2. 安装后必须恢复可执行权限

Python `zipfile` 解压**不保留可执行位**，`bin/ttskill` 和 `runtime/node` 会变成 `-rw-r--r--`，运行报 `Permission denied`。

```bash
cd /tmp/ttskill-extract/ttskill-base-linux-x64-<ver>
bash install.sh    # 安装到 ~/.local/share/ttfund/ttskill-base/

chmod -R +x ~/.local/share/ttfund/ttskill-base/ttskill-base-linux-x64-<ver>/bin \
           ~/.local/share/ttfund/ttskill-base/ttskill-base-linux-x64-<ver>/runtime

export PATH="$HOME/.local/bin:$PATH"
ttskill --version
```

### 3. 必须装 unzip

ttskill 在 Linux 上用 `unzip -Z1` 校验 skill 包 zip 清单，缺失时报 `读取 Skill 包文件清单失败: undefined`（错误信息被 `spawnSync` 吞成 undefined，极难排查）。

```bash
sudo apt-get install -y unzip
```

---

## 二、凭证存储 patch（ECS 必做，否则登录必失败）

**背景**：`credential-store.js` 在 Linux 分支强制走 `secret-tool`（Secret Service），无 D-Bus/X11 的服务器读写都失败。源码里本来就有 legacy 文件路径（`auth/token.json` / `auth/device-key.json`），patch 成直接读写文件即可。

**位置**：`~/.local/share/ttfund/ttskill-base/ttskill-base-linux-x64-<ver>/src/credential-store.js`

一键应用（幂等，可重复执行）：

```bash
python3 scripts/patch_linux_credential.py <ttskill-base-dir>     # 打 patch
python3 scripts/patch_linux_credential.py --check <ttskill-base-dir>  # 检查状态，输出 PATCHED / NOT_PATCHED
```

四个函数被改成：

```js
// 1. secretServiceRead —— 从文件读 token/device-key
function secretServiceRead(record) {
  const legacyPath = record.legacyPath();
  if (!exists(legacyPath)) return null;
  try {
    return readJson(legacyPath);
  } catch {
    return null;
  }
}

// 2. secretServiceWrite —— 写文件（临时文件 + rename 原子写入）
function secretServiceWrite(record, payload) {
  const legacyPath = record.legacyPath();
  fs.mkdirSync(path.dirname(legacyPath), { recursive: true });
  fs.writeFileSync(legacyPath + ".tmp", JSON.stringify(payload, null, 2) + "\n", { mode: 0o600 });
  fs.renameSync(legacyPath + ".tmp", legacyPath);
}

// 3. secretServiceDelete —— 删文件
function secretServiceDelete(record) {
  fs.rmSync(record.legacyPath(), { force: true });
}

// 4. removeLegacyFile —— Linux 下绝不能删（native 存储就是 legacy 文件）
function removeLegacyFile(record) {
  if (process.platform === "linux") return;
  fs.rmSync(record.legacyPath(), { force: true });
}
```

⚠️ **第 4 个是关键**：`writeCredential` 成功后调 `removeLegacyFile` 清理「旧遗留文件」，但 patch 后 Linux 的 native 存储**就是**那个文件，不拦截会被立刻删掉 → 登录「成功」但 token 不存在。

**凭证的实际落盘位置**（排查时直接看这里，别去 `ttskill-base/auth/` 找）：
`~/.local/share/ttfund-skills/auth/token.json` 与同目录 `device-key.json`（0600 明文）。

---

## 三、远程登录：cloudflared 隧道 + 飞书发链接（唯一方式）

**原理**：`ttskill login` 会在**服务器本机**起一个监听 `127.0.0.1:8765` 的回调服务，而它要求的回调是**浏览器发起的 POST**（不是 GET 重定向）。所以让浏览器能连通到那个服务即可 —— 用 cloudflared 反向隧道把本机 8765 暴露成公网 HTTPS，再把登录 URL 里的 `callback_url` 换成隧道地址，然后把链接**通过飞书消息发给用户**。

用户侧只需两件事：**点开飞书里的链接 → 天天基金 App 扫码**。不需要在本地开终端、不需要 SSH、不需要复制任何东西。

### 步骤

```bash
# ① 下载 cloudflared（约 43MB，ECS 直连 GitHub 实测 200）
curl -sL -o /tmp/cloudflared https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64
chmod +x /tmp/cloudflared && /tmp/cloudflared --version

# ② 起隧道（出站长连接：不开任何入站端口、不用改安全组）
/tmp/cloudflared tunnel --url http://127.0.0.1:8765 --no-autoupdate > /tmp/cf_tunnel.log 2>&1 &
sleep 25
grep -o "https://[a-z0-9-]*\.trycloudflare\.com" /tmp/cf_tunnel.log | head -1   # 得到隧道 URL

# ③ 起登录进程拿 URL（Hermes 用 terminal(background=true)，不要 nohup/disown）
ttskill login --env prod --force > /tmp/tt_login.log 2>&1 &
sleep 10
grep -o "https://skills.tiantianfunds.com/ttfund-skills/cli-login?[^ ]*" /tmp/tt_login.log | head -1
```

```python
# ④ 把 URL 里的 callback_url 换成隧道地址（保留 state！）
#    callback_url=http%3A%2F%2F127.0.0.1%3A8765%2Fcallback%3Fstate%3DXXX
# →  callback_url=https%3A%2F%2F<TUN>.trycloudflare.com%2Fcallback%3Fstate%3DXXX
#    （登录 URL 里 callback_url 是 URL-encoded 的，替换后要保持编码）
```

⑤ 把改好的链接**用飞书消息发给用户**，说明「点开链接 → 天天基金 App 扫码」。

### 隧道连通性自检（发链接前先做，10 秒）

```bash
curl -s -X POST -H "Content-Type: application/json" -d '{"state":"probe"}' \
  "https://<TUN>.trycloudflare.com/callback?state=probe"
# 返回 {"ok":false,"error":"invalid_state"}  → 请求已到达服务器上的 ttskill 服务 ✓
# 返回 Cloudflare 错误页                      → 隧道没通，别急着发链接给用户
```

### 登录成功的判据

看 login 进程输出：

```json
{"status":"ok","current_user":{"expires_at":"2026-11-10T15:59:01.000Z","is_expired":false}}
```

`expires_at` 有值且 `is_expired: false` = 成功。再用真实 invoke 复核一次（见主文档 Step 6）。

### 注意事项

- **登录 URL 只有 5 分钟有效**（`local_callback_timeout_seconds=300`）。先自检隧道、再发链接，别让用户面对过期链接
- quick tunnel 每次重启 URL 会变；**登录完成后立刻 kill 掉 cloudflared**（用完即弃）
- 隧道背后只挂着回调服务，未知路径返回 404 / `invalid_state`，暴露面很小
- 登录后若 invoke 报 `skill_version_required`（HTTP 409），重试一次通常即恢复；仍失败再 `ttskill skill update <SKILL_ID> --env prod`

---

## 四、Token 生命周期

| 项目 | 值 |
|------|-----|
| 有效期 | 30 天（`expires_in: 2592000`） |
| 续期 | ❌ ttskill 0.1.2 **存了 refresh_token 但代码不用它刷新** → 过期必须重扫 |
| 过期表现 | `ttskill invoke` 报「登录已过期」。**以真实 invoke 的 stderr 为准**：`status` 的 `is_expired` 字段在过期后可能直接消失，只靠它会误判 |
| 重扫流程 | 重复第三节即可（凭据文件还在，**无需重装、无需重新 patch**） |

> 建议按登录日期 +30 天设 cron 提醒用户重新扫码。

---

## Pitfalls

- **`zipfile` 解压丢可执行位**：`bin/ttskill`、`runtime/node` 变 644，运行报 `Permission denied`。装完必须 `chmod -R +x`。
- **缺 unzip 报 `读取 Skill 包文件清单失败: undefined`**：真因被 `spawnSync` 吞掉，极难排查。`apt install unzip` 即可。
- **`secret-tool: Cannot autolaunch D-Bus without X11 $DISPLAY`**：无桌面服务器标配。别尝试装桌面 / 起 D-Bus，直接 patch 文件存储。
- **patch 后 token 反复消失**：多半是 `removeLegacyFile` 没拦截（patch 第 4 项）。验证：登录后立即 `ls ~/.local/share/ttfund-skills/auth/`。
- **登录「成功」但 invoke 仍报未登录**：确认凭证真的落到 `~/.local/share/ttfund-skills/auth/token.json`（文件存储生效），而不是写进了没人读的 secret-service。
- **别去猜「让用户复制浏览器地址栏 URL 发回来」**：回调是 JS 发起的 POST，地址栏只有 GET，复制回来喂给服务只会得到 `not_found`。已实测此路不通，只能走隧道。
- **login 进程不退出**：CLI 在等回调，属正常；5 分钟超时后自动失败退出。
- **Hermes 用 `terminal(background=true)` 跑长驻进程**：不要用 `nohup`/`disown` 包 shell 后台，用 background 参数，再用 `process(action='poll')` 抓输出。
- **升级 / 重装 ttskill 后**：`credential-store.js` 会被覆盖 → **必须重跑一次 patch**，否则 ECS 上登录立即失效。
