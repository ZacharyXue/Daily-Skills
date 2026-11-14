# code-server 用户切换 / 免密恢复 / 按需启停 / SSH→GitHub 免密

2026-08-16 阿里云 ECS 47.85.183.215（Ubuntu 24.04, 2核1G+2Gswap）实战记录。

## code-server 切换运行用户（admin → root）

服务是 systemd 模板 `code-server@.service`，`User=%i` → **实例名就是运行用户**：

```bash
systemctl disable --now code-server@admin.service   # 停旧实例 + 去开机自启
systemctl enable --now code-server@root.service     # 启新实例 + 开机自启
```

- 配置按用户隔离：`~/.config/code-server/config.yaml`（bind-addr / auth / password / cert）
- **切用户后密码和监听地址跟着变**（不同用户各自的 config）。实例切换后验证：
  ```bash
  ss -tlnp | grep 8080
  ps -o user= -p $(pgrep -f 'code-server.*node /usr/lib/code-server' | head -1)   # 确认运行用户
  curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8080/healthz            # 200
  ```
- 本机两份配置值：
  - admin：`bind-addr: 0.0.0.0:8080`，`password: 7bb47c573db1e9831aa25c6c`
  - root：`bind-addr: 127.0.0.1:8080`（切用户后手动改成 0.0.0.0），`password: 2b68b89c929d4f84b9e4fcf8`（随后按用户要求统一回 `7bb4...`）

## auth 配置与验证语义

| 配置 | `curl http://127.0.0.1:8080/` | 说明 |
|---|---|---|
| `auth: password` | 302（重定向 /login） | 正常，需密码 |
| `auth: none` | 200 + IDE HTML | 免密，仅限 127.0.0.1 或安全组白名单 |

⚠️ `0.0.0.0:8080` + `auth: none` = 公网任何人 root 权限，必须避免。加固二选一：安全组入方向白名单来源 IP / bind-addr 改 127.0.0.1 + `ssh -L 8080:127.0.0.1:8080 root@HOST` 隧道。

## 1G 小内存：code-server 默认关闭、按需启动

```bash
systemctl stop code-server@root.service && systemctl disable code-server@root.service
# 用时：
systemctl start code-server@root.service
systemctl status code-server@root.service
```

`systemctl is-active` / `is-enabled` 确认状态（inactive / disabled）。这是用户明确偏好，适用于本机所有常驻 web 服务。

## 服务器 → GitHub SSH 免密

排查现状：
```bash
ls ~/.ssh/id_*        # 服务器无私钥 → 未配（ssh -T git@github.com → Permission denied (publickey)）
cat ~/.ssh/authorized_keys   # 含 xzh@zach-legion = 笔记本→服务器免密已配，两者方向不同
```

配置：
```bash
ssh-keygen -t ed25519 -C "xzh@aliyun-ecs" -f ~/.ssh/id_ed25519 -N ""
cat ~/.ssh/id_ed25519.pub     # 用户去 https://github.com/settings/ssh/new 添加
ssh -T git@github.com         # Hi ZacharyXue! 即通
```

注意：GH 用户名 ZacharyXue，git 全局 user.name=xzh / user.email=xuezihao2016@outlook.com。