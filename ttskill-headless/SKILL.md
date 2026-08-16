---
name: ttskill-headless
description: 无桌面服务器（ECS/云主机）上安装天天基金 ttskill CLI 并远程扫码登录 — 解决 secret-tool D-Bus 不可用、凭证存储 patch 成文件模式、SSH 隧道打通 127.0.0.1 回调端口。触发时机：在无桌面 Linux 服务器上装 ttskill、`ttskill login` 报 "Linux Secret Service 写入失败"、需要远程扫码登录天天基金。
version: 1.0.0
tags: [ttfund, ttskill, headless, ecs, login, credential]
---

# ttskill 无头服务器部署与远程登录

天天基金 `ttskill` CLI 在**无桌面环境**（阿里云 ECS 等）的完整部署流程，含两个核心坑的解法：

1. **凭证存储**：ttskill 在 Linux 强制走 Secret Service（`secret-tool`），无 D-Bus/X11 的服务器无法写入 → **patch 源码改为文件存储**
2. **扫码回调**：登录 URL 的回调地址是 `http://127.0.0.1:8765/callback`，指向打开浏览器的机器，扫码后浏览器 POST 到本地 127.0.0.1 → 用户本机扫码时回调到不了服务器 → **SSH 端口转发**打通

## 适用场景

- 服务器上 `ttskill login` 报 `Linux Secret Service 写入失败: secret-tool: Cannot autolaunch D-Bus without X11 $DISPLAY`
- 需要让 Hermes（跑在 ECS 上）能调用 ttskill 查询天天基金持仓/收益
- ttskill 升级重装后需要重新 patch

## 完整安装流程

### Step 0: 下载基础包

```bash
# 获取下载地址（返回 JSON 里的 data.download_url）
curl -sL "https://skills.tiantianfunds.com/ai-smart-skill-service/openapi/base-package/resolve?platform=linux&arch=x64&env=prod"

# 下载 + 校验 sha256
curl -sL --max-time 120 -o /tmp/ttskill-base.zip "<download_url>"
echo "<sha256>  ttskill-base.zip" | sha256sum -c -

# ⚠️ 服务器常无 unzip：用 Python 解压
rm -rf /tmp/ttskill-extract && mkdir /tmp/ttskill-extract
python3 -c "
import zipfile
with zipfile.ZipFile('/tmp/ttskill-base.zip') as z:
    z.extractall('/tmp/ttskill-extract')
"
```

### Step 1: 解压后必须恢复可执行权限

Python zipfile 解压**不保留可执行位**，`bin/ttskill` 和 `runtime/node` 会是 `-rw-r--r--`，运行报 `Permission denied`。

```bash
cd /tmp/ttskill-extract/ttskill-base-linux-x64-<ver>
bash install.sh    # 安装到 ~/.local/share/ttfund/ttskill-base/

# 关键：修复可执行权限
chmod -R +x ~/.local/share/ttfund/ttskill-base/ttskill-base-linux-x64-<ver>/bin \
           ~/.local/share/ttfund/ttskill-base/ttskill-base-linux-x64-<ver>/runtime

export PATH="$HOME/.local/bin:$PATH"
ttskill --version   # 验证，应输出版本号
```

### Step 2: 安装 unzip（ttskill 内部依赖）

ttskill 在 Linux 上用 `unzip -Z1` 校验 skill 包 zip 清单，无 unzip 时报 `读取 Skill 包文件清单失败: undefined`（错误信息被吞成 undefined，很难排查）。

```bash
sudo apt-get install -y unzip
```

### Step 3: Patch 凭证存储（无桌面环境必做）

**背景**：`credential-store.js` 在 Linux 分支调用 `secret-tool`（Secret Service），无 D-Bus 时读写都失败。源码里其实已有 legacy 文件路径（`auth/token.json` / `auth/device-key.json`），patch 成直接读写文件即可。

**位置**：`~/.local/share/ttfund/ttskill-base/ttskill-base-linux-x64-<ver>/src/credential-store.js`

四个函数改成（可直接运行 `python3 scripts/patch_linux_credential.py` 自动应用，幂等可重复执行）：

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

⚠️ 第 4 个是关键：`writeCredential` 成功后会调 `removeLegacyFile` 清理"旧遗留文件"，但 patch 后 Linux 的 native 存储**就是**那个文件，不拦截会被立刻删掉，导致登录"成功"但 token 不存在。

### Step 4: 同步业务 skill 包

```bash
# 获取包列表（返回 data.items[]）
curl -sL "https://skills.tiantianfunds.com/ai-smart-skill-service/openapi/skill-package/list?env=prod" -o /tmp/skill_list.json

# 逐个安装（Python 批量），失败的重试一次
python3 - <<'EOF'
import json, subprocess
d = json.load(open('/tmp/skill_list.json'))
items = d['data']['items'] if 'data' in d else d.get('items', [])
for it in items:
    sid, ver = it['skill_id'], it['version']
    r = subprocess.run(['ttskill','skill','install',sid,'--env','prod','--version',ver],
                       capture_output=True, text=True, timeout=90)
    print(('OK ' if r.returncode==0 else 'FAIL ')+sid)
EOF

# 刷新路由
ttskill agent-entry refresh --env prod
```

### Step 5: 远程扫码登录（SSH 隧道）

**原理**：`ttskill login` 生成的 URL 带 `callback_url=http://127.0.0.1:8765/callback?state=xxx`，浏览器扫码后 POST 到这个地址，该地址必须落在**服务器**上。所以用户在本地开 SSH 隧道，把本地的 8765 端口转发到服务器：

```bash
# ① 用户本地终端（Windows/WSL）执行，保持窗口不关：
ssh -L 8765:127.0.0.1:8765 root@<服务器IP>
```

```bash
# ② 服务器端后台启动登录（Hermes 用 background=true）
ttskill login --env prod
```

```bash
# ③ 从后台进程输出抓 login URL（形如 https://skills.tiantianfunds.com/ttfund-skills/cli-login?...
#    Hermes: process(action='poll') 的输出里 "open this URL in browser:\n<url>"
```

```bash
# ④ 用户浏览器打开该 URL，天天基金 App 扫码。完成后 CLI 收到回调自动完成。
#    登录 URL 5 分钟有效（local_callback_timeout_seconds=300），过期需重新生成。
```

验证登录：`ttskill status --json` 看 `auth.has_token`；或看 login 进程输出 `"status": "ok"`。

## Token 生命周期

| 项目 | 值 |
|------|-----|
| 有效期 | 30 天（`expires_in: 2592000`） |
| 续期 | ❌ ttskill 0.1.2 **存了 refresh_token 但代码不用它刷新**，续期无意义，过期必须重扫 |
| 过期表现 | `ttskill invoke` 报登录失效 / `status` 里 `is_expired: true` |
| 重扫流程 | 重复 Step 5 即可（凭据文件还在，无需重装/patch） |

> 建议在 token 过期前 3-5 天设 cron 提醒用户重新扫码（登录日期 ±30 天）。

## Pitfalls

- **`zipfile` 解压丢可执行位**：`bin/ttskill`、`runtime/node` 变 644，运行报 `Permission denied`。装完必须 `chmod -R +x`。
- **缺 unzip 报 "读取 Skill 包文件清单失败: undefined"**：错误被 `spawnSync` stderr 吞掉，极难排查。`apt install unzip` 即可。
- **`secret-tool: Cannot autolaunch D-Bus without X11 $DISPLAY`**：无桌面服务器标配，别尝试装桌面/起 D-Bus，直接 patch 文件存储。
- **patch 后 token 反复消失**：多半是 `removeLegacyFile` 没拦截（patch 第 4 项）。验证：登录后立即 `ls auth/token.json`。
- **login 进程不退出**：CLI 在等回调，属于正常。5 分钟超时后自动失败退出。
- **登录 URL 回调到用户自己电脑**：用户本机的 127.0.0.1:8765 是自己的机器，**必须**先开 SSH 隧道再扫码，否则扫码后 token 换不到。
- **Hermes 用 background=true 跑 login**：不要用 nohup/disown（Hermes 会拒绝 shell 后台包装），用 `terminal(background=true)`，然后 `process(action='poll')` 抓 URL。

## 复用命令速查

```bash
# 重装后一条命令恢复 patch（幂等）
python3 scripts/patch_linux_credential.py <ttskill-base-dir>

# 检查 patch 状态
python3 scripts/patch_linux_credential.py --check <ttskill-base-dir>
```