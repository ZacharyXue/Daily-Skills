# Hermes 迁移到远程服务器

把一个 Hermes 实例（含数据 + 平台连接）完整迁到远程服务器时的策略与坑。核心诉求通常是「不能两边都连不上」——用**先建后切、静态先行、动态最后、全程可回滚**保证任何时刻至少有一边可用。

## 迁移范围：静态资产 vs 平台连接

| 类别 | 内容 | 迁移方式 |
|---|---|---|
| 配置+密钥 | config.yaml / .env / auth.json / SOUL.md | 直接复制（.env 用 stdin 重定向，见 SKILL.md Pitfall 4） |
| 技能 | skills/ | 复制 |
| 记忆 | memories/ | 复制 |
| 会话历史 | state.db | SQLite 在线备份（`.backup`）或停写后复制 |
| 定时任务 | cron/jobs.json | 复制（⚠️ 迁移后本地必须禁用） |
| 源码 | hermes-agent 目录 | **不迁**（目标机 pip 装同版本即可） |
| **平台连接** | 飞书/QQ/微信 gateway | **最后切，最危险** |

## 分阶段（零风险在前，风险集中在平台切换）

0. **全量备份**（本地）：打包关键资产存本地+远端各一份，任何时刻可回滚。
1. **静态资产迁移**：复制 config/.env/skills/memories/cron/state.db，完全不动本地 gateway，零风险。
2. **远端验证（gateway 不启动）**：模型能通、技能/记忆/cron 都在、`hermes --resume` 能读历史会话。验证期无限长都安全。
3. **平台切换**：飞书是 websocket 长连接，**新连接会踢掉旧连接**，所以「先启远程抢连接 → 验证连通 → 确认后才停本地」能做到零窗口。若远程连不上，本地还活着，立即回滚。
4. **切换后验证 + 本地降级为备份**：远程稳定后停本地 gateway 和 cron，但本地 ~/.hermes 保留完整备份 ≥1 周。

## 关键坑

- **cron 重复执行**：迁移后若本地 cron 不关，同一任务（如每日 code-study、复盘）会在两边同时跑，重复产出/抢锁。切完必须禁用本地 cron。
- **远程资源评估**：gateway + 多个平台 + cron 的内存占用，叠加 code-server 等常驻服务，1G 机器会吃紧。迁移前先决定「停常驻服务」还是「加内存」。
- **gateway 切换后模型/配置生效**：改 config 要重启 gateway 才生效（且不能从内部重启，见 SKILL.md Pitfall 4）。

## 环境漂移核实

当系统提示/记忆描述的环境（如「WSL /home/xzh」）与实际执行环境可能不符时，先核实真实身份再下结论：

```bash
hostname            # 主机名（阿里云 iZ... 开头 = ECS）
id                  # 实际 uid/用户（root 还是 xzh）
ls /home/           # 有哪些用户目录（有没有 /home/xzh）
ls /mnt/            # 有没有 Windows 挂载（WSL 特征）
ps aux | grep gateway   # gateway 进程的实际路径/用户
```

判据：`/home/xzh` 不存在 + `/mnt` 空 + `uid=0 root` + hostname 是服务器名 = 当前已跑在远程服务器，memory/系统提示里的 WSL 路径（/home/xzh、/mnt/f/...）全部失效，需后续更新 memory。

## 迁移后的 skill 库清理（确认漂移后的下一步）

确认已迁到新环境后，按「更新 → 删除 → 保留」三类清理 skill 里的旧路径：

1. **批量扫描旧路径**：`grep -rn "旧根路径" ~/.hermes/skills/`（如 `/home/xzh\|/mnt/f`），列出全部引用文件。
2. **更新**：项目已迁到新位置 → 路径改为新位置（如 `/home/xzh/ZacharyXue.github.io` → `/root/ZacharyXue.github.io`）。用 multi-file patch 一次性改，效率高于逐文件改。
3. **删除**：绑定**未迁移项目**的 skill 整库删除（`skill_manage delete`，`absorbed_into=''`），连同其 references/templates。用户原则（2026-08 确立）：未迁移的删除，不留死路径引用。
4. **保留**：环境判据类文档里的旧路径是判断逻辑的一部分（如本文件的 `/home/xzh` 判据），不能删——它记录「如何识别漂移」，删了判据就失效。改完后用 grep 复查剩余引用，逐条确认是「刻意保留」还是「漏改」。
5. **同步更新记忆**：失效的环境条目（旧项目路径、已删 skill 的引用、废弃技术栈）用 memory 批量 remove/replace，腾出空间。

**判据文档 vs 过时引用**的区分：判据文档讨论「环境长什么样」，过时引用假装「环境就是那样」——前者删了会丢知识，后者留着会误导下次执行。
