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

### 3. 知识星球（zsxq-skill）

- **用途**：通过对话操作知识星球——浏览星球、搜索/查看/发布/编辑主题、评论回答、管理标签/精华、笔记管理、成员足迹、NPS 反馈等
- **来源**：知识星球官方开源（GitHub `unnoo/zsxq-skill`，2026-08 上线，v2.1.0），安装入口 https://garden.zsxq.com/skill/INSTALL.md
- **CLI 认证**：`zsxq-cli auth login` 设备码授权（浏览器打开授权链接+确认码），token 存系统钥匙串
- **能力亮点**：单一 skill 覆盖旧版 5 个技能(zsxq-shared/group/topic/user/note)；内置场景模式——每日巡场、评论区运营、提问管理、精华标签整理、运营日报/周报、日报海报生成、竖版视频、负面内容监控、批量打标签、成员续费关怀、专栏收录
- **关键要点**：写入/删除操作前必须向用户确认内容；group_id/topic_id 不确定时先查询再写

### 4. 飞书 / Lark 全家桶（lark-* 系列）

- **用途**：批量覆盖飞书全生态操作——通讯录（lark-contact）、IM（lark-im）、云文档（lark-doc/drive/wiki/slides/sheets/base/markdown）、日历（lark-calendar）、任务（lark-task）、审批（lark-approval）、考勤（lark-attendance）、妙记/会议（lark-minutes/vc/vc-agent/note）、邮件（lark-mail）、画板（lark-whiteboard）、事件监听（lark-event）、原生 OpenAPI 探索（lark-openapi-explorer）、自定义 skill 封装（lark-skill-maker）、工作流编排（lark-workflow-*）、OKR（lark-okr）等，共 27 个 skill
- **来源**：Lark/飞书官方 CLI 生态（`@larksuite/cli`，npm 全局安装于 `~/.npm-global/bin`），通过 Hermes agent-entry 分发，软链挂入。单个 skill 依赖 `lark-cli` bin（lark-shared 提供共享认证/授权/URL 二维码规则）
- **常用流程**：先 `lark-cli auth` 确认身份（user vs bot，`--domain` 区分全量/文档/云盘权限）→ 各业务域用对应 lark-* skill 操作
- **关键要点**：
  - bot 身份收不到群附件 → 用 user 身份 `im +chat-messages-list → messages-resources-download` 拉
  - 授权/配置类命令输出的 URL 必须配 `lark-cli auth qrcode` 二维码一起展示
  - group_id/topic_id/token 不确定时先查询再写；写操作前向用户确认

遇到重要的外部/开源 skill 时，在此文件追加条目（名称、用途、来源、工作流要点）。
**不要记录文件位置**（每台机器不同）；也不要移动文件到本仓库——zach-skills 只收录自建 skill。