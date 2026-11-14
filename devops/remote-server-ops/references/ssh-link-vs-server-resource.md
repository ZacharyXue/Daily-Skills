# SSH「连不上」实测定案：链路 vs 服务端资源

本机（阿里云 ECS，2C/894Mi，内网 172.19.12.108）2026-11-14 实战记录。
用户报告：「当前无法通过 SSH 连接，应该是内存满了，看一下 /root/hermes-venv/chrome/ 是否可以杀掉呢」。

## 结论先行

**不是内存，不是爆破打满，不是服务端资源 —— 是用户（中国移动 39.144.128.102）到 ECS 这段链路丢包严重。**
修复：`cubic → bbr` + `tcp_mtu_probing=1`（已持久化 `/etc/sysctl.d/99-ssh-tuning.conf`）。

## 一、先否掉用户的假设

```
ps -eo ... | grep -i chrom   → 空（没有任何 chrome / playwright 进程）
du -sh /root/hermes-venv/chrome/  → 391M（= 磁盘占用）
ls  → linux-152.0.7977.42（Chromium 程序文件目录）
```

**`du` 看的是磁盘，不是内存。** 无进程 = 无可杀；删目录只释放 391M 磁盘，内存 0 变化，代价是 browser_exec 失效（需重下 ~150MB）。用户把「磁盘目录」当成了「内存占用」。

## 二、资源侧全部排除（逐条实测数字）

| 检查项 | 实测值 | 判定 |
|---|---|---|
| MemTotal / available | 916MB / 214MB | 偏紧但够用 |
| swap 空闲 | 1550MB | 充足 |
| 内核 OOM 记录（全量 grep） | **0 条** | 从未被 OOM 杀过 |
| PSI `/proc/pressure/memory` some avg10 | 4.60% | 轻微 |
| 最大内存占用 | hermes 自身 RSS 366MB + swap 208MB | 真大头是 hermes，不是 chrome |
| conntrack | 0 / 7168 | 连接表空 |
| eth0 errors / dropped | 0 / 0 | 网卡无丢包 |
| 实时带宽（2s 采样） | RX 0 KB/s，TX 2 KB/s | 远未打满 |
| 服务器 → 223.5.5.5 | 0.98ms / 0% 丢包 | **服务器出网健康** |
| sshd listener | `1 of 10-100 startups` | 未认证槽位远未饱和 |
| 最近 10 分钟 preauth | 27 次 | 爆破在继续但并发不高 |
| 当日失败连接总数 | 5229 次 | 噪音大，非根因 |

## 三、决定性证据：三条并发连接的对照组

同一时刻、同一 sshd 上的三条 `ss -tni '( sport = :22 )'`：

```
# ① 用户老会话 2894（15:59 建，已半死）
rtt:333.548/55.986  cwnd:2 ssthresh:2
bytes_sent:6357 bytes_retrans:1578  bytes_acked:4779
lastsnd:258476 lastrcv:261464       ← 两次采样持续暴涨（258s→294s）
retrans:0/12  delivery_rate 4112bps

# ② 用户新尝试 2895（认证阶段就卡住）
rtt:309.078/154.539
bytes_sent:86 bytes_retrans:43      ← 发了 86 字节，43 在重传 = 50%
rcv_ooopack:1  lastsnd:73388 → 109731

# ③ 国外爆破扫描器 27.118.23.21（健康对照组）
rtt:230.736/36.945  cwnd:10
bytes_sent:1815 bytes_acked:1771   lastsnd:14  ← 活跃传输
```

**读法**：
- `cwnd` 塌到 2 且 `ssthresh` 也是 2 = 拥塞窗口被打到底，吞吐崩溃。
- `bytes_retrans / bytes_sent` 25%~50% = 链路严重丢包。
- `lastsnd` / `lastrcv` 两次采样间**持续暴涨** = 服务端一直没发出新数据，连接已死透（对比健康连接的 14ms）。
- **对照组里扫描器 cwnd 10 活跃，用户 cwnd 2 半死 → 责任在用户侧链路，服务端无罪。**

全局旁证：`TcpRetransSegs 162187 / TcpOutSegs 24798732 ≈ 0.65%`，`TcpExtTCPTimeouts 107685`。

## 四、ping 判据的陷阱

```
ping -c4 39.144.128.102  →  4 packets transmitted, 0 received, 100% packet loss
```

**这不能单独定案** —— 移动/蜂窝网络普遍禁 ICMP 回显。字符串上是 100% 丢包，但真正定案的是上面的 TCP 层指标。报告时必须把 ICMP 结论标注为「辅证」，别当主证。

## 五、修复与验证

```
modprobe tcp_bbr
sysctl -w net.ipv4.tcp_congestion_control=bbr
sysctl -w net.ipv4.tcp_mtu_probing=1
# 持久化 → /etc/sysctl.d/99-ssh-tuning.conf
# 验证：net.ipv4.tcp_available_congestion_control = reno cubic bbr
```

**注意**：不 `modprobe tcp_bbr` 时 `tcp_available_congestion_control` 里只有 `reno cubic`，直接 `sysctl -w ...=bbr` 会失败。模块文件 `/lib/modules/6.8.0-63-generic/kernel/net/ipv4/tcp_bbr.ko.zst` 存在，加载即可。

已改动前：`tcp_congestion_control=cubic`、`default_qdisc=fq_codel`、`tcp_mtu_probing=0`、`tcp_slow_start_after_idle=0`（这项本来就是 0，不背锅）。

## 六、给用户的行动顺序（照搬可用）

1. **阿里云控制台 → ECS → 远程连接（Workbench / VNC）** —— 不走 SSH 链路，立刻能进。
2. 换网络（手机热点 ↔ 家中 WiFi）再试：换了就通 = 运营商链路问题。
3. 重连加保活：`ssh -o ServerAliveInterval=10 -o ServerAliveCountMax=3`。
4. 清僵死会话：`pkill -9 -t pts/0`。
5. 换网络仍不通 = 阿里云到该运营商的 peering 异常，需要开工单，用 `mtr` 抓跳数证据。

## 七、待办（用户未答）

- fail2ban + `MaxStartups 100:30:200`：本次不是根因（槽位 1/10），但 5229 次/天白吃连接数，高峰仍可能抢槽位。已提议，等用户点头。
