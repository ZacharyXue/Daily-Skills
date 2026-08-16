# Zach Skills（重要自建技能库）

薛子皓的重要 Hermes skill 集。**只收录关键、长期可复用的自建 skill**（不是所有创建的 skill 都放这里）。所有 skill 遵循 Hermes skill 规范（YAML frontmatter + Markdown），通过软链接入 `~/.hermes/skills/`。

> 记录原则：创建**重要/关键**的 skill 时，才放入本目录并登记到下方索引。普通/一次性 skill 直接建在 `~/.hermes/skills/` 下，不在此记录。

## 下载方式

```bash
# 方式一：git clone（推荐）
git clone git@github.com:ZacharyXue/Daily-Skills.git zach-skills

# 方式二：只取单个 skill（示例：career-coach）
ln -sfn $(pwd)/career-coach ~/.hermes/skills/career-coach
```

注意：适配 Hermes skill 规范，**使用软链而非拷贝**——软链让 skill 更新直接作用于 Hermes，无需反复同步。

## 本目录 Skill 索引

| Skill | 说明 | 触发场景 |
|-------|------|----------|
| [career-coach](career-coach/) | 职业成长教练：复盘工作/学习、判断价值、深挖技术深度、对齐业界、规划发展路径、沉淀简历 | 晚间复盘、职业困惑、学习路径规划 |
| [code-study](code-study/) | 问题驱动的源码阅读系统：从用户可见行为出发追踪调用链，产出排查笔记推送飞书群 | 每日 cron 源码阅读、想搞懂一个真实 bug 的根因 |
| [whale-holdings](whale-holdings/) | 大佬持仓跟踪：SEC 13F 机构持仓披露，巴菲特/李录/Burry 等买什么、加仓什么、清仓什么 | 说「看下 XX 的持仓」「13F」 |
| [skill-creation-guide](skill-creation-guide/) | 创建/管理重要自建 skill 的完整流程：规范、目录结构、软链接入、README 维护 | 新建重要 skill、维护本仓库 |

## 仓库结构

```
zach-skills/
├── README.md            ← 本文件：本目录 skill 说明 + 下载方式
└── <skill-name>/        ← 每个重要自建 skill 一个目录（SKILL.md + references/ + scripts/）
```

## 开发规范

- 每个自建 skill 必须有：`name`（小写连字符）、`description`（含触发时机）、`version`
- 新建重要 skill 后创建软链：`ln -sfn /root/zach-skills/<name> ~/.hermes/skills/<name>`
- 修改自建 skill 直接改仓库文件（**不要用 skill_manage 操作软链**，会失败），改完 `git add + commit`
- 代码只 commit 不 push，推送由用户自行决定
- 新增/删除本目录 skill 必须同步更新本 README 索引表

## 相关

- Hermes 官方文档：https://hermes-agent.nousresearch.com/docs