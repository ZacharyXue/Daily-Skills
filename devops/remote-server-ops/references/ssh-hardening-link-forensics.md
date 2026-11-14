# SSH 防爆破 + 链路取证实战（2026-11-14，ECS 894MB）

本次会话的完整证据链与可复用脚本。核心结论：**用户以为「内存满导致 SSH 连不上」，实测是用户侧链路丢包；chrome 目录零进程与内存无关；防爆破方案因 IP 动态必须走 hashlimit 黑名单。**

> **最终定案（当日 21:59 闭环）**：PMTU 黑洞假设 **被证伪**。用户换 IP/网络后 `cwnd` 从 2 回到 36、稳定登录 → 病因 100% 在用户侧运营商链路，服务端无需再改。详见「三·补」。

## 用户的三条硬约束（先记住再动手）

1. **「我的 ip 是会动态变更的，这里需要的是禁掉部分 ip 地址，而不能开白名单的形式」** → 任何依赖固定源 IP 的方案（安全组白名单、防火墙 allowlist）都不可用。
2. **「maxtstartups打开可能导致攻击方打更多流量」** → 用户先于 agent 识别出该风险，agent 原建议（10:30:100 → 100:30:200）被撤回。
3. **「你不要先动手，先规划」** → 诊断收敛前不得实施修复。

## 一、资源侧排除（每项都要有数字）

| 检查 | 实测 | 结论 |
|---|---|---|
| `free -m` | total 916MB / used 696 / available 214~233MB / swap 空闲 1.55GB | 紧但够 |
| `journalctl -k \| grep -icE 'oom'` | **0**（开机至今） | 从未 OOM |
| `/proc/pressure/memory` | some avg10=4.60 / full avg10=4.26 | 轻微 |
| `ps ... \| grep '[s]shd'` | `1 of 10-100 startups` | 槽位远未饱和 |
| `nf_conntrack_count` | 0 / 7168 | 干净 |
| `ip -s link show eth0` | errors 0 / dropped 0 | 网卡无丢包 |
| `ping 223.5.5.5` | 0.98ms / 0% | 服务器出网正常 |
| 实时带宽 2s 采样 | RX 0KB/s / TX 2KB/s | 未打满 |
| `du -sh /root/hermes-venv/chrome/` | 391MB，**`ps \| grep chrom` 全空** | 磁盘非内存，与故障无关 |

## 二、链路侧实锤（对照组是决定性的）

同一时刻同一 sshd：

| 源 | rtt | cwnd/ssthresh | 重传 | lastsnd | 判定 |
|---|---|---|---|---|---|
| 用户 39.144.128.102（中国移动） | **333ms** | **2/2** | 1578/6357 = **25%** | 258s→294s 持续暴涨 | 半死 |
| 用户新尝试 | 309ms | 10 | 43/86 = **50%** | 静止 | FIN-WAIT-1 |
| 爆破器 27.118.23.21 | 230ms | 10 | 干净 | 活跃 | 健康 |

**扫描器都比用户连得快 → 责任在用户到服务器这段链路。**

## 三、「认证成功但仍连不上」的推理链

sshd 日志反复出现 `Accepted publickey for root from 39.144.128.102`（15:59/16:09/16:10/16:13/16:19 共 5 次），而客户端只报 `Connection closed by 47.85.183.215 port 22`。

关键观测：
- `FIN-WAIT-1` 连接 **Send-Q 积压 1121 字节** → 服务端发包发不出去
- `rcvmss:536`（正常 1360+）→ 客户端宣告 MSS 异常小
- 小包认证通、大包数据死 → PMTU 黑洞假设（交给用户客户端 ping 二分验证，服务端不可自行判定）

客户端验证（Windows）：
```bat
ping -f -l 1400 47.85.183.215
ping -f -l 1300 47.85.183.215
ping -f -l 1200 47.85.183.215
ssh -vvv aliyun
```

## 三·补、最终定案：换链路前后对照（PMTU 假设被证伪）

用户换 IP 后（`36.28.83.128`）同一 sshd 上的对比，直接把病因钉死在用户侧链路：

| 指标 | 旧 `39.144.128.102`（移动） | 新 `36.28.83.128` |
|---|---|---|
| `cwnd` | **2** | **36** |
| `rtt` | 333ms | 225ms |
| 重传率 | 25%~50% | 15.7% |
| TCP 状态 | Send-Q 积压 1121 字节，静止 | `app_limited`（空闲正常） |
| 结果 | 认证成功即断 | 稳定登录 10+ 分钟 |

**反直觉事实**：旧 IP 那条「半死」连接实际存活 **2 小时 14 分**（`last`: `15:59 - 18:14 (02:14)`）。
→ 这类故障**是间歇性的，不是彻底不通**。用户说「连不上」往往是一段时间内反复失败，别按完全断链去查。

**定案判据（比对照组更硬）**：同一用户「换 WiFi / 手机热点 / 重新拨号」后再看 `ss -tni`：
- `cwnd` 回到 10+、`app_limited` → **用户侧链路，服务端一个参数都不用再动，更别加 MSS clamping**
- 换链路仍一样 → 才怀疑云端 peering / DDoS 清洗，抓 `mtr` 开工单

**旁证（不定罪）**：`mss:128`（正常 1360~1400）+ `rto backoff:7`（退避到 58 秒）= 路径上有异常中转的痕迹，但单凭它不能定案。

## 三·补二、hashlimit 长跑战果（5 小时）

```
规则1  ESTABLISHED,RELATED  RETURN : 44764 包放行
恶意 IP/段 DROP 合计              :   925 包丢弃
hashlimit 通过                     :   449 包放行
兜底 DROP（超限）                  :     2 包
```

- 仅拦 2 次 → 当日攻击以**低频慢扫**为主，hashlimit 是「平时不烧、洪泛才熔断的保险丝」，不是主力防线。
- ⚠️ **兜底 DROP 对用户自己也生效**：密集重试会被丢，必要时调高 `--hashlimit-burst` 或把 22 端口摘出。
- 黑名单确有效（925 包），但**换 IP 就绕过**，只能当止血贴。

## 四、已落地的改动与回滚

| 改动 | 位置 | 回滚 |
|---|---|---|
| cubic→bbr, tcp_mtu_probing=1 | `/etc/sysctl.d/99-ssh-tuning.conf` | `rm` 该文件 + `sysctl -w net.ipv4.tcp_congestion_control=cubic` + `sysctl -w net.ipv4.tcp_mtu_probing=0` |
| SSH_GUARD 链（12 IP + 1 段 DROP + hashlimit 6/min） | iptables INPUT #1 | `iptables -F SSH_GUARD; iptables -X SSH_GUARD; iptables -D INPUT -j SSH_GUARD` |

`sshd_config` 未改动，未装 fail2ban。

## 五、加固脚本（可复用）

```bash
#!/bin/bash
set -u
BAD_IPS=( /* 按 journalctl 统计填入攻击 >=100 次的精确 IP */ )
BAD_NETS=( 45.148.10.0/24 )   # 段内多 IP 轮询才封整段，单 IP 攻击只精确封

log() { logger -t ssh-hardening "$*"; echo "[ssh-hardening] $*"; }

# 幂等清理：顺序必须是 删跳转 → 清空 → 删链（顺序错了会防护归零，见坑 1）
while iptables -D INPUT -j SSH_GUARD 2>/dev/null; do :; done
iptables -F SSH_GUARD 2>/dev/null
iptables -X SSH_GUARD 2>/dev/null

iptables -N SSH_GUARD || { log "ERROR: 建链失败"; exit 1; }
iptables -A SSH_GUARD -m conntrack --ctstate ESTABLISHED,RELATED -j RETURN   # 必须第 1 条
for ip  in "${BAD_IPS[@]}";  do iptables -A SSH_GUARD -s "$ip"  -j DROP; done
for net in "${BAD_NETS[@]}"; do iptables -A SSH_GUARD -s "$net" -j DROP; done
iptables -A SSH_GUARD -p tcp --dport 22 -m conntrack --ctstate NEW \
  -m hashlimit --hashlimit-upto 6/min --hashlimit-burst 6 \
  --hashlimit-mode srcip --hashlimit-name SSHG -j RETURN
iptables -A SSH_GUARD -p tcp --dport 22 -m conntrack --ctstate NEW -j DROP
iptables -A SSH_GUARD -j RETURN
iptables -I INPUT 1 -j SSH_GUARD
```

## 六、改完防火墙的强制验收（本次靠它自证清白）

```bash
iptables -L SSH_GUARD -n -v --line-numbers   # 兜底 DROP 的 pkts 必须为 0
cat /proc/net/xt_hashlimit/SSHG              # 空 = 没限到任何源
```
本次实测：hashlimit RETURN 命中 19 packets（用户正常放行）、兜底 DROP **0 packets**、hashlimit 表为空 → 证明用户连不上**不是**新规则造成的，避免了误判回滚。

> 5 小时后的复测：RETURN 449 包 / 兜底 DROP 仅 2 包 / 黑名单累计丢 925 包 —— 规则长期在正常工作，且始终没挡住用户主会话。

## 六·补、持久化到重启（2026-11-14 实测落地）

规则默认重启即失。选用 **systemd oneshot** 而非 `iptables-persistent`（后者把全表快照成静态文件，刷黑名单还得手改 rules.v4）。

```ini
# /etc/systemd/system/ssh-hardening.service
[Unit]
Description=SSH hardening - hashlimit rate limit + static IP blacklist
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/usr/local/sbin/ssh-hardening.sh
ExecStartPost=/bin/sh -c 'iptables -S INPUT | grep -q SSH_GUARD || { echo "SSH_GUARD not attached"; exit 1; }'

[Install]
WantedBy=multi-user.target
```

```bash
install -m 644 /tmp/ssh-hardening.service /etc/systemd/system/
systemctl daemon-reload && systemctl enable --now ssh-hardening.service
```

### 坑 1：`-X` 必须在解除 INPUT 引用之后（错了會防护归零）

首次 `systemctl start` 成功（当时链不存在），`systemctl restart` **直接失败**：
```
iptables: Chain already exists.
[ssh-hardening] ERROR: 建链失败      → status=1/FAILURE
```
结果 `iptables -S INPUT` 变空、`SSH_GUARD` 规则数 0。

根因：`-X` 要求链无任何引用，但当时 INPUT 还挂着 `-j SSH_GUARD` → `-X` 静默失败 → 链残留
→ `-N` 报 exists → 脚本 `exit 1`；**而 `-F` 已把旧规则清空 ⇒ 「链在但零规则」= 防护归零，比不加还危险**。

修正（把删跳转提到最前，并用 while 清掉重复跳转）：
```bash
while iptables -D INPUT -j SSH_GUARD 2>/dev/null; do :; done
iptables -F SSH_GUARD 2>/dev/null
iptables -X SSH_GUARD 2>/dev/null
iptables -N SSH_GUARD || { log "ERROR: 建链失败"; exit 1; }
```

### 坑 2：`RemainAfterExit=yes` 时 `systemctl start` 是空操作

服务已 `active(exited)` 时再 `start` **不重跑 ExecStart，且返回 0**。
实测：手动清空规则 → `systemctl start` → exit 0，但 `iptables -S SSH_GUARD` 报
`No chain/target/match by that name`，规则数 0。
→ **改脚本 / 手动清空后必须用 `systemctl restart`**；开机（inactive）才走 `start`。

### 验收（四条全过）

```bash
systemctl is-enabled ssh-hardening.service   # enabled
systemctl is-active  ssh-hardening.service   # active
systemctl restart ssh-hardening.service      # 无报错
iptables -S SSH_GUARD | grep -c '^-A'        # 17（多次 restart 不翻倍）
iptables -S INPUT | grep -c SSH_GUARD        # 1（无重复跳转）
ss -tn '( sport = :22 )'                     # 现有会话仍在
```

本机实测连跑 4 次 `restart` → 规则数稳定 **17**、INPUT 跳转恒为 1；
「stop + 彻底清空 + start」模拟真实开机 → 17 条完整重建 ✓

清单 = 1 ESTABLISHED 放行 + 12 精确 IP + 1 个 /24 + 1 hashlimit 放行 + 1 兜底 DROP + 1 收尾 RETURN = **17**。
⚠️ 服务跑的是 `/usr/local/sbin/ssh-hardening.sh`；**源本在 `scripts/ssh-hardening.sh`（已入仓）**，修改流程永远是「仓里改 → cp 到系统路径 → `bash -n` → `systemctl restart`」。

## 七、爆破规模量化（决定要不要动手）

```bash
# 单 IP TOP
journalctl -u ssh --since today --no-pager \
  | grep -oE 'from [0-9]+\.[0-9]+\.[0-9]+\.[0-9]+' | awk '{print $2}' \
  | sort | uniq -c | sort -rn | head -20
# 按 /24 聚拢看 C 段轮询
... | awk -F. '{print $2"."$3"."$4}' | sort | uniq -c | sort -rn | head -15
```
本机：5229 次/天 / 115 个独立源；TOP1 `109.160.32.106` 2066 次；`45.148.10.x` 段内 4 个 IP 合计 330+ 次（典型扫描段）。封 TOP 10 个段即可挡掉 ~95%。

## 八、环境坑

- `systemctl is-active sshd` 在 Ubuntu 返回 **inactive**（单元名是 `ssh`）——别据此判断 SSH 挂了。
- `systemctl is-active ufw`=active 但 `ufw status`=inactive：服务在跑 ≠ 规则已加载，判防火墙看 `ufw status` / `iptables -L`。
- 本机 `fail2ban`/`sshguard` apt 源里没有（需先 `apt update`），且 fail2ban 是 Python 常驻 ~50MB，小内存机器不划算。
- Hermes 拦截 `nohup`/`setsid` 后台包装，要后台跑定时回滚须用 `background=true`；但 agent 本机有 root shell，iptables 改错可直接 `-F` 回滚，不一定需要定时器。
