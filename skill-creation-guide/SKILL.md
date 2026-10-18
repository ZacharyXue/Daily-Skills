---
name: skill-creation-guide
description: 创建/管理**重要** Hermes skill 的完整引导 — 判断哪些 skill 值得入库、目录结构、SKILL.md 规范（含认知契约/改稿边界/输出协议/触发边界必填段）、external_dirs 加载、README 维护。触发时机：用户说「新建一个 skill」「把这个流程存成 skill」「怎么创建自己的 skill」、zach-skills 仓库维护。
version: 1.1.1
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

## 认知契约（必填，2026-10 新增）
- 本 skill 哪些环节**必须先由子皓输出**（观点/判断/理解/预测），AI 不得代答
- 产出物三段式：`一、我的原始输出`（原样保留，一字不改）→ `二、整理稿`（AI 补结构/衔接/术语）→ `三、本次补了什么`（AI 列出加了哪些衔接句/小标题）
- 硬边界：**不生成子皓没说过的观点句**

## 改稿边界（必填，2026-10 新增）
- 默认只**标注 + 出建议清单**，不直接改文件/正文；改不改、怎么改由子皓按
- 唯一例外：机械格式类（错别字/单位统一/失活链接）可自动改，但必须在报告里列出"自动改了什么"，禁止静默改

## 输出协议（必填，2026-10 新增）
- 结论 → 证据 → 拆解表 → 风险/数据缺口 → 下一步验证；重要结论标 高/中/低 置信度
- **确定性计算交脚本，LLM 只做语言与参数转译**（不从模型嘴里出数字）
- 数据缺口显性化：拿不到就写「获取失败 + 原因」，绝不用旧值/缓存冒充；宁返回空，不返回被截断的样本

## 触发边界（必填，2026-10 新增）
- 明确写出「说什么话时**不**触发本 skill」。例：说"总结/提炼/概括"只做摘要，说"蒸馏/构建框架"才走本流程

## 数据保存
（见下文"本地数据文件保存规范"）

## 步骤 / 陷阱 ...（正文自由组织）
```

**description 规范**：必须包含「做什么」+「触发时机」（用户说哪些话会触发），e.g. `触发时机：用户说"看下 XX 的持仓"。` 这决定 Hermes 能否在正确时机自动加载 skill。

### Step 3: 确认 Hermes 能加载（**无需软链**）

zach-skills 通过 `external_dirs` 被 Hermes 直接扫描，新建目录自动生效：

```bash
# 确认加载配置里有 /root/zach-skills（一次即可，不需要每个 skill 都做）
grep -A3 "^skills:" /root/.hermes/config.yaml
# 期望看到：skills: / external_dirs: / - /root/zach-skills
```

- **不要建软链**：2026-10 实测 `~/.hermes/skills/` 下与 zach-skills 相关的软链为 0，旧的 `ln -sfn` 做法已废弃
- 只有把 skill 放在 `/root/zach-skills/` 之外时，才需要软链或额外配置目录

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

- **直接改仓库文件**（`/root/zach-skills/<name>/...`），**不要用 skill_manage 操作**——skill_manage 写入的是 `~/.hermes/skills/`，会脱离 zach-skills 的 git 版本管理（zach-skills 是靠 `external_dirs` 加载的，不是靠软链）。
- 改完 commit。
- 内容重大变化时 bump `version`。

## 陷阱

1. **skill 放在 /root/zach-skills/ 内，不要拷贝副本到别处**——靠 `external_dirs` 加载，副本会造成"改了不生效"。
2. **不要用 skill_manage 改 zach-skills 里的 skill**：它写 `~/.hermes/skills/`，改动会脱离 git 管理（不是软链报错的问题，是位置问题）。
3. **description 别写废话**：触发时机必须具体（用户原话级别的关键词），否则 skill 永远不被加载。
4. **README 索引是「事实来源」**：新增/删除 skill 忘记更新，下次审计会缺条目。
5. **不要在知识型 skill 里混合环境细节**：全局环境信息放记忆，skill 只存可复用的流程/知识。
6. **产出物没有「原始输出留档」**（2026-10 新增）：AI 整理稿直接覆盖子皓原话 = 日后分不清哪些认知是他自己的、哪些是 AI 补的脚手架。凡涉及他的思考沉淀，必须双轨留档（三段式）。
7. **评审/校验类 skill 直接改稿**（2026-10 新增）：验真、review、体检类只出「标注 + 建议清单」，改不改由人按；改了就等于 AI 参与了判断，责任归属和可回放性一起没了。

## 来源可信度分级（2026-10 新增）

引用外部材料（研报/自媒体/AI 生成内容）进 skill 时，方法论与数字分级对待：
- **方法论可抄**（流程、校验设计、字段口径）
- **数字不可抄**，除非能追到原始出处（示例：某券商 AI 投研 PPT 全篇无量化提效数据，且自述"全部案例为功能演示的模拟案例"→ 只取其 skill 设计思路）
- 转述他人结论时，同时记下**反例与边界**（样本是否自我选择、口径是否可比、有无相反结论的同类研究）