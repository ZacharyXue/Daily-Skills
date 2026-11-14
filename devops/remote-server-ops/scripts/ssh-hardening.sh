#!/bin/bash
# SSH 防护：hashlimit 限速 + 恶意 IP 黑名单（动态 IP 友好，不用白名单）
# 生成日期: 2026-11-14
set -u

# ===== 恶意源清单（今日攻击 >=100 次的精确 IP + 专用扫描 C 段）=====
# 依据: journalctl -u ssh --since today 的失败连接统计
BAD_IPS=(
  109.160.32.106    # 2066 次
  77.239.124.36     #  843 次
  120.193.9.169     #  564 次
  176.193.127.227   #  214 次
  51.75.21.168      #  192 次
  148.66.128.231    #  188 次
  148.72.211.221    #  186 次
  103.185.53.178    #  182 次
  27.118.23.21      #  176 次
  2.57.122.150      #   79 次
  193.47.62.69      #   65 次
  150.95.105.97     #   68 次
)
# 整段封：45.148.10.0/24 内至少 4 个 IP(141/151/152/157) 在轮询扫描，合计 330+ 次
BAD_NETS=(
  45.148.10.0/24
)

# hashlimit: 单源 IP 每分钟最多 6 个新建连接，burst 6
RL_UPTODAY=6
RL_BURST=6

log() { logger -t ssh-hardening "$*"; echo "[ssh-hardening] $*"; }

# 幂等清理：顺序必须是 删跳转 → 清空 → 删链
# ⚠️ 若先 -X：INPUT 还引用着该链，-X 必然失败 → 链残留 → -N 报 "Chain already exists" → 脚本 exit 1
#    且此时旧规则已被 -F 清空，等于防护归零（2026-11-14 实测踩到）
while iptables -D INPUT -j SSH_GUARD 2>/dev/null; do :; done   # 循环删干净所有重复跳转
iptables -F SSH_GUARD 2>/dev/null
iptables -X SSH_GUARD 2>/dev/null

iptables -N SSH_GUARD || { log "ERROR: 建链失败"; exit 1; }

# 1) 已建立连接全部放行（保护现有会话，必须有）
iptables -A SSH_GUARD -m conntrack --ctstate ESTABLISHED,RELATED -j RETURN

# 2) 恶意 IP 精确封禁
for ip in "${BAD_IPS[@]}"; do
  iptables -A SSH_GUARD -s "$ip" -j DROP
done
# 3) 恶意 C 段封禁
for net in "${BAD_NETS[@]}"; do
  iptables -A SSH_GUARD -s "$net" -j DROP
done

# 4) hashlimit：22 端口新建连接，单 IP 超过速率直接 DROP
iptables -A SSH_GUARD -p tcp --dport 22 -m conntrack --ctstate NEW \
  -m hashlimit --hashlimit-upto "${RL_UPTODAY}/min" --hashlimit-burst "${RL_BURST}" \
  --hashlimit-mode srcip --hashlimit-name SSHG -j RETURN
iptables -A SSH_GUARD -p tcp --dport 22 -m conntrack --ctstate NEW -j DROP

# 5) 其余流量放行
iptables -A SSH_GUARD -j RETURN

# 挂到 INPUT 最前
iptables -I INPUT 1 -j SSH_GUARD

log "applied: ${#BAD_IPS[@]} IPs + ${#BAD_NETS[@]} nets + hashlimit ${RL_UPTODAY}/min"
