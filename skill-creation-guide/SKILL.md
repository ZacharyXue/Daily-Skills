---
name: skill-creation-guide
description: 创建/管理**重要** Hermes skill 的完整引导 — 判断哪些 skill 值得入库、目录结构、SKILL.md 规范、软链接入 Hermes、README 维护。触发时机：用户说「新建一个 skill」「把这个流程存成 skill」「怎么创建自己的 skill」、zach-skills 仓库维护。
version: 1.0.0
tags: [hermes, skill, meta, workflow, zach-skills]
---

# 重要自建 Skill 引导（zach-skills 仓库）

本 skill 是「创建重要 skill」的流程引导。zach-skills 仓库（`/root/zach-skills/`，remote: `git@github.com:ZacharyXue/Daily-Skills.git`）**只收录重要、长期可复用的自建 skill**——不是所有创建的 skill 都放这里。

## 判断标准：要不要放入 zach-skills？

**应该放**：
- 长期复用的核心工作流（如职业复盘、源码阅读、持仓跟踪）
- 会和 cron 任务、跨会话反复使用的
- 积累了多轮经验教训、值得版本管理的

**不要放（直接建在 ~/.hermes/skills/ 下）**：
- 一次性小任务
- 短期实验性 skill
- 依赖某个临时环境的技能

拿不准时问用户，让用户决定是否入库。

## 仓库结构

```
/root/zach-skills/
├── README.md              # 本目录 skill 索引表（必须同步维护）
└── <skill-name>/          # 每个重要自建 skill 一个目录
    ├── SKILL.md           # 必需：frontmatter + 正文
    ├── references/        # 可选：长文档/附表
    ├── scripts/           # 可选：可执行脚本
    └── templates/         # 可选：模板文件
```

## 创建新 skill 的流程

### Step 1: 确认目录位置

```bash
# 所有自建 skill 放这里（不要放 ~/.hermes/skills/ 其他地方）
mkdir -p /root/zach-skills/<skill-name>
```

### Step 2: 写 SKILL.md（规范）

```markdown
---
name: <skill-name>                  # 小写连字符，如 whale-holdings
description: <一句话说明 + 触发时机>  # 让 Hermes 知道何时加载它
version: 1.0.0
tags: [相关主题标签]
---

# <标题>

## 核心概念 / 步骤 / 陷阱 ...（正文自由组织）
```

**description 规范**：必须包含「做什么」+「触发时机」（用户说哪些话会触发），e.g. `触发时机：用户说"看下 XX 的持仓"。` 这决定 Hermes 能否在正确时机自动加载 skill。

### Step 3: 软链接入 Hermes

```bash
ln -sfn /root/zach-skills/<skill-name> /root/.hermes/skills/<skill-name>
# 验证：ls -la /root/.hermes/skills/ | grep <skill-name>
```

### Step 4: 更新 README.md 索引表

在 `/root/zach-skills/README.md` 的自建 Skill 索引表中加一行（名称/说明/触发场景）。**删除 skill 时同步移除该行。**

### Step 5: 提交

```bash
cd /root/zach-skills && git add -A && git commit -m "feat(<skill-name>): <一句话说明>"
# 只 commit 不 push，推送由用户决定
```

## 本地数据文件保存规范（凡是 skill 要保存/读写本地数据，必须遵守）

zach-skills 推送到公开仓库 `Daily-Skills`，**私密数据绝不能随公开仓 push**。凡 skill 涉及保存本地数据文件，严格按此规范：

### 1. 私有数据 vs 公开知识分离
- **私有数据**（个人隐私：知识画像/深挖池/岗位需求库/投资持仓/读书笔记等）→ 放 `zach-skills/<skill-name>/data/`（或统一私有目录），并：
  - 在 `zach-skills/.gitignore` 加一行保护（如 `career-data/`）→ **永不随公开仓 push**
  - 需要版本控制就建独立 `.git`，**无远端**（纯本地）
  - 也可复刻 `career-data/` 样板：数据在 skills 目录下、gitignored、独立私有仓
- **公开知识**（可复用流程/代码/模板）→ 正常放 skill 目录，随仓库走

### 2. 每个 skill 的 SKILL.md 必须写「数据保存说明」
至少写清 3 点：**存哪些文件 / 存哪（绝对路径）/ 是否私有进公开仓**。

样板（career-coach）：
```markdown
## 数据保存
- 知识画像 /root/zach-skills/career-data/knowledge-ledger.md（私有，gitignore，独立仓无远端）
- 深挖池   /root/zach-skills/career-data/deepdive-backlog.md（私有，同上）
- 岗位需求 /root/zach-skills/career-data/job-demand.md（私有，同上）
```

### 3. 保存数据前的自检
- 要版本控制？→ 确认私有位置 + .gitignore 保护 + 独立仓无远端
- 会被公开仓 pull/push？→ 确认不会（gitignore 命中 / 无远端）
- 路径是否写进本文档（`## 数据保存`）？→ 必须，否则后续会话找不到

## 修改已有自建 skill

- **直接改仓库文件**（`/root/zach-skills/<name>/...`），**不要用 skill_manage 操作**——skill 是软链，skill_manage 写 symlink 会失败。
- 改完 commit。
- 内容重大变化时 bump `version`。

## 陷阱

1. **软链必须指向 /root/zach-skills/ 内的目录**，不要拷贝文件副本——否则更新不同步。
2. **skill_manage 对软链 skill 的修改会失败**（curl 到 symlink 报错），直接改文件。
3. **description 别写废话**：触发时机必须具体（用户原话级别的关键词），否则 skill 永远不被加载。
4. **README 索引是「事实来源」**：新增/删除 skill 忘记更新，下次审计会缺条目。
5. **不要在知识型 skill 里混合环境细节**：全局环境信息放记忆，skill 只存可复用的流程/知识。