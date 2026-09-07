---
name: routine-reminders
description: 定时提醒体系 — 每日晚间/每周例行提醒子皓该做什么（职业发展/理财/习惯培养/规划）。核心：no_agent 纯脚本 cron（零 token）按星期生成提醒，不建日历。当子皓说"定时提醒/晚上提醒我/每周提醒/建个提醒"时使用。
version: 1.0.0
tags: [cron, reminders, routine, habits, planning, 定时提醒, 习惯]
---

# 定时提醒体系（routine-reminders）

子皓的「例行提醒」配置层：不建日历，用 **no_agent cron + 脚本** 按时间/星期生成提醒，零 token 消耗。

## 核心设计

- **不用 Hermes LLM cron**（每次触发烧 token + 需 pin 模型防漂移）
- 用 **no_agent=true + script**：脚本运行、stdout 直接投递，完全不经过 LLM
- 脚本按「日期 + 星期」+ 读用户状态文件生成提醒内容
- 提醒是「提一嘴」，不自动执行深挖/买入等操作，由子皓决定做不做

## 提醒节奏（当前配置）

| 触发 | 内容 | 实现 |
|---|---|---|
| 每晚 22:00 | 睡前提醒：深挖池⭐在做条目 + 最新条目 + 简短 | `scripts/remind_daily.py` |
| 每周五 21:00 | 周五例行：本周职业复盘 + 理财状态 + 习惯打卡 | `scripts/remind_friday.py` |

> 全程中文，语气务实不啰嗦，4-5 句话内，让子皓自己决定做不做。

## cron 实现

```bash
# 每日 22:00（no_agent，零 token）
cronjob action=create name="晚间提醒" no_agent=true \
  schedule="0 22 * * *" \
  script="/root/zach-skills/routine-reminders/scripts/remind_daily.py" \
  deliver=origin

# 每周五 21:00（no_agent，零 token）
cronjob action=create name="周五例行提醒" no_agent=true \
  schedule="0 21 * * 5" \
  script="/root/zach-skills/routine-reminders/scripts/remind_friday.py" \
  deliver=origin
```

- `deliver=origin`：推送到创建时的会话（微信/飞书）
- no_agent 无模型、无 pin 问题；脚本输出空则不投递（watchdog 语义）
- 修改 job：`cronjob action=update job_id=<id> script=...`；手动触发验：`cronjob action=run job_id=<id>`

## 状态文件读取（提醒内容的输入）

脚本读以下文件拼最新状态（读取失败就返回通用提醒，不报错）：
- `/root/zach-skills/career-data/deepdive-backlog.md` — ⭐ 在做条目、最新条目（职业深挖）
- 理财（预留）：data-source-router / ttskill 行情摘要（可选，后续接）
- 习惯打卡（预留）：`~/habits/log.md`（后续建）

## 维护

- 提醒节奏/内容想调整 → 改脚本 + 本 SKILL.md 节奏表
- 手动触发测试：`cronjob action=run job_id=<id>` → 看 `~/.hermes/cron/output/<id>/` 最新输出
- 不想提醒了：`cronjob action=remove job_id=<id>`（或 pause）

## 相关

- `hermes-cron-ops`：cron 排障/pin/触发验证（本体系 no_agent 天然避开 pin 坑）
- `career-data/deepdive-backlog.md`：每日深挖提醒的输入源