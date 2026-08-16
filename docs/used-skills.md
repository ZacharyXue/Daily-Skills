# 使用的开源 / 外部 Skill 记录

本目录记录**用户使用的重要外部/开源 skill**（非自建，不放在 zach-skills 目录下，仅在此登记信息）。

> 区别于自建 skill（见根目录 README.md 索引）——这里的 skill 来自官方安装/开源项目，文件实体保留在 Hermes skills 目录（具体位置因机器而异，不在此记录）。

## 当前记录

### 1. 天天基金（ttskill-cli）

- **用途**：查询基金持仓、收益、季报；fund analysis（profit_contribute 看盈亏、TTFUND_BASE_INFOS 看持仓/风格）
- **来源**：天天基金官方 CLI，安装时通过 Hermes agent-entry + OpenCode 分发
- **常用流程**：`ttskill` 拉持仓 → profit_contribute 看盈亏 → TTFUND_BASE_INFOS 看持仓风格 → 对照季报
- **博文偏好**：分析结果先审阅再落盘博客（保留数据细节，不压缩）

### 2. 微信读书（weread-reading-notes）

- **用途**：从微信读书提取划线/想法 → 整理为结构化读书笔记 → 逐章与用户确认 → 发布到博客
- **来源**：基于微信读书 Agent API（Tencent/WeChatReading skill v1.0.4）
- **网关**：`https://i.weread.qq.com/api/agent/gateway`（API key 在 `WEREAD_API_KEY`，请求必带 `skill_version`）
- **工作流要点**：搜书 → bookId → 进度/划线/评论 → 读书笔记 → 博客；逐章确认后再落盘

## 如何新增记录

遇到重要的外部/开源 skill 时，在此文件追加条目（名称、用途、来源、工作流要点）。
**不要记录文件位置**（每台机器不同）；也不要移动文件到本仓库——zach-skills 只收录自建 skill。