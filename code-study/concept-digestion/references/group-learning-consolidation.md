# 学习群阶段回顾闭环 — 实测范例（2026-09-15，计算机网络线）

本文件是 concept-digestion 主流程「阶段回顾闭环」的实证样例，供下次同类任务照抄结构。

## 场景

- 群：飞书「计算机网络学习」（`oc_267e55b18abdf91eb74a74a4beadd43b`，用户自建，主题=网络）
- 轨迹：9/13 用户发网购四层示意图 + 自己的理解 → 9/15 说「总结这部分内容」（**指代是那张图，不是 /tmp 文件**）→ 后续逐题深入（CIDR / 环回 / 出网全流程 / 同子网 / 交换机）→ 又一轮 DHCP（四件套 / 掩码错为何不通 / DORA / Client-ID）

## 一次回顾闭环的实际编排

1. 拉群全量消息（`--order asc --page-all`）+ 从 image 消息下载图片 → OCR（image-text-extraction）
2. 输出「知识点轨迹表」：7 个知识点 × 一句话核心 × 状态（✅已讲透）
3. 一轮 5 题覆盖全部 7 点，题面标号对应表号；明确指出可「不会的标这题没懂」
4. 用户作答 → 逐条点评：4 题 ✅、1 题 ⚠️（环回「不会到内核」方向颠倒）→ 单开一节细讲纠正后的流程
5. 落 wiki：4 页（仅确认吸收的内容）
6. 提议并成文博客：出网旅程长文（8 张 mermaid 图）

第二轮（DHCP）同样：先讲透 → 出验证题 → 用户答对/半对 → 补全 → 用户说「落到 wiki 中」→ 新增 2 页 + 更新 1 页。

## 条件化验证题范例（可复用句式）

| 题目 | 检验点 |
|---|---|
| 「掩码从 /18 改成 /24，还能 ping 通网关吗？」 | 是否理解「直连路由由 IP+掩码算出」（答「不一定，看网关是否在新范围内」= 真懂） |
| 「A 下载大文件为什么不影响我？」 | 是否理解交换机定向转发 vs 集线器共享总线（答「不响应」只对一半，需补缓存/小包/低频） |
| 「打破哪个前提才会被 DNS/ARP 广播轰垮？」 | 反推式：能否指出缓存复用 + 低频被打破 |
| 「换网卡（不重装系统）DHCP 会给同一个 IP 吗？」 | DUID（机器身份，磁盘持久）vs IAID（网卡身份） |

## 实测证据清单（网络类概念一次可全取）

```bash
ip -4 addr show <iface>            # IP/CIDR/brd（广播地址自动算出）
ip route show                      # default via … proto dhcp（DHCP 下发的路由）
ip route get <IP>                  # 下一跳决策：有 via=跨子网，无 via=直连
ip neigh show                      # ARP 缓存（网关 MAC、状态 REACHABLE）
ss -lntp                           # 绑定地址：127.0.0.1=只本机 / 0.0.0.0=全部接口
cat /run/systemd/netif/leases/*    # 租约：ADDRESS/NETMASK/ROUTER/DNS/T1/T2/LIFETIME/CLIENTID
journalctl -u systemd-networkd | grep -i dhcp   # 历次 acquired 记录（可证明 IP 一直不变）
cat /etc/machine-id                # DUID 来源（配合 CLIENT-ID 逐字节拆解）
```

配合工具算数（勿心算）：`ipaddress` 算网络/广播/可用主机、`hashlib` 试哈希、web_search 查 IANA PEN 等外部事实。

## 第三、四轮（2026-10-01）：CRC 讲透 + 覆盖度盘点补缺

- 第三轮 CRC：讲前先跑三项**自造对照实验**（逐步演算 / 20000 次翻转统计 / 改数据重算校验的负例）→ 用户两个推测一真一伪，均能用实验直接判定 → 落 1 页 `crc-and-integrity-check`
- 第四轮审计：拉全量 163 条消息 → 逐条比对 index → 报 3 个真缺口（ARP / DNS / 用户态↔内核态路径）→ 新建 3 页 + 补写 2 页（广播类型、bind 可达性）+ 1 处交叉链接 → `wiki_lint.py` 全绿（42 页 = index 42 条）
- 两轮里踩到的两个可复用坑：① 日期误用会话起始日导致 7 页日期错（按 git commit 时间回改 + 写勘误条目）② 页数凭「上次 +1」推算而少算一页（另有 sibling session 插页）

## 产出落点

- wiki（zach-llm-wiki，云原生域，tags 含 `网络`）— 网络线累计 10 页：
  `network-layer-stack` / `cidr-addressing` / `loopback-address` / `layer2-switching` /
  `network-config-four-pieces` / `dhcp-address-assignment` / `crc-and-integrity-check` /
  `arp-mechanism` / `dns-resolution` / `user-kernel-network-path`
- 博客（zihao-blog）：`/blog/outbound-network-journey`（出网全流程，8 图）
