---
name: code-study
description: 问题驱动的源码阅读系统 — 每天从「用户可见行为」出发追踪一个真实问题的源码调用链，产出排查笔记推送到飞书群，积累架构直觉和工程经验。
version: 2.0.0
tags: [code-reading, architecture, learning, cron]
---

# 问题驱动源码阅读系统

通过定时 cron 自动阅读指定仓库的源码，每天从「用户可见行为」出发追踪一个问题的调用链，产出排查笔记推送到飞书群。

## 核心理念

> **问题驱动，不是模块扫读。** 每天挑一个真实问题（例如「pytest 敲下去后怎么一步步发现 test_*.py 的？」），从用户入口一路追到核心逻辑，输出「问题 → 调用链 → 关键发现」的排查笔记。读起来像 debug 了一遍，而不是在读文档。

为什么不用模块扫读：按目录顺序提取设计决策的产出「像文档，缺乏场景锚点，没有感觉的用处」。问题驱动先有问题再找答案，产出排查笔记，读者跟着走一遍调用链就像自己 debug 过。

## 目录结构

```
~/.hermes/code-study/               ← 运行时数据（进度、笔记）
├── repos/                           # 每仓库一个 YAML，维护问题进度
│   └── {repo-name}.yaml
├── notes/                           # 排查笔记按仓库归档
│   └── {repo-name}/
│       └── 2026-08-12-问题简述.md
└── patterns_library.md              # 跨仓库设计模式积累

~/zach-skills/code-study/            ← 本 skill 的模板和默认配置
├── SKILL.md
└── templates/
    ├── defaults.yaml                # 全局默认 custom_prompt
    └── repo.yaml                    # 仓库配置模板
```

## 仓库配置 (repos/{name}.yaml)

### 完整 Schema（questions 驱动）

```yaml
# ===== 标识与路径 =====
name: my-project                      # 仓库简称
git_url: https://github.com/...       # 远程地址
local_path: /home/xzh/path/to/repo    # 本地路径

# ===== 推送 =====
feishu_chat_id: "oc_xxxxxxxxxxxxx"    # 飞书群 ID
schedule: "0 8 * * *"                 # cron 表达式
enabled: true                         # 是否启用

# ===== 阅读引导（留空则用 defaults.yaml）=====
custom_prompt: |
  仓库专属的关注点...

# ===== 范围控制 =====
exclude_paths:                        # 跳过的目录
  - "tests/"
  - "docs/"

# ===== 问题与进度 =====
questions:
  - q: "用户敲下 XX 命令后，底层一步步发生了什么？"
    status: pending                   # pending → done
    answer_log: []                    # 每次回答追加一条
```

### 字段说明

| 字段 | 必需 | 说明 |
|------|------|------|
| `name` | ✓ | 仓库简称，用于文件命名 |
| `git_url` | | 远程地址，用于参考 |
| `local_path` | ✓ | 本地绝对路径 |
| `feishu_chat_id` | ✓ | 排查笔记推送目标群 |
| `schedule` | ✓ | cron 表达式，控制阅读频率 |
| `enabled` | ✓ | 一键开关，不用删 cron |
| `custom_prompt` | | 覆盖全局 defaults.yaml |
| `exclude_paths` | | 扫描时跳过的目录 |
| `questions` | | 问题列表，首次为空时 AI 扫描建议生成 |
| `questions[].q` | ✓ | 问题原文（从用户可见行为出发） |
| `questions[].status` | ✓ | pending / done |
| `questions[].answer_log` | | 每次回答追加一条记录 |

## 问题设计原则

- **从「用户可见行为」出发**：敲了什么命令、点了什么、发了什么请求、触发什么事件
- **追踪调用链直到核心逻辑**：每一步标注源码文件:行号
- **第一个问题通常是**：「这个工具的使用方式是什么，每一步底层做了什么」
- **避免抽象的设计问题**（「XX 用了什么设计模式」），要具体的行为问题（「XX 命令怎么一步步生效的」）
- **避免「怎么用」的 API 教程问题**，要「底层怎么实现」的机制问题

## 生命周期

每个仓库经历两个阶段：

```
Phase 1: 手动初始化（交互式，需要用户参与）
  ├── 1. 讨论仓库是否适合、阅读重点、问题方向
  ├── 2. 确认后 clone 仓库到本地
  ├── 3. 创建飞书群 → 拿到 chat_id
  ├── 4. 创建 repos/{name}.yaml（填写基础信息，questions 留空）
  ├── 5. 用户对 Hermes 说"扫描 {name} 的问题"
  ├── 6. AI 扫目录 + 用户可见行为 → 生成建议问题列表
  ├── 7. 用户确认/修改/排序
  └── 8. 问题列表写入 YAML，创建 cron job

Phase 2: 每日自动（cron 无人值守）
  ├── cron 触发 → 读 YAML → 选第一个 pending 问题 → 读代码追调用链
  ├── 产出排查笔记 → 存 notes/ → 推飞书群
  └── 问题 done 后由 cron agent 标记 status: done
```

## 工作流

### ⚠️ 添加新仓库：先讨论再落盘

当用户提到想加入新仓库时，**不要一上来就写 YAML 和建飞书群**。正确流程：

1. 先确认仓库是否适合阅读（方向匹配、代码质量、学习价值）
2. 讨论阅读重点和问题拆分思路
3. 确认飞书群是否就绪
4. 以上全部确认后再落盘

用户明确纠正过这个行为。

### Phase 1: 手动初始化

#### 问题扫描（交互式，必须用户确认）

此步骤**不能由 cron 自动完成**，必须由用户在对话中触发：

1. 用户说"扫描 {name} 的问题"
2. AI 用 `search_files` 扫 `local_path` 目录结构（跳过 `exclude_paths`）
3. 结合用户可见行为（CLI 命令、API、事件）设计问题
4. 为每个问题生成建议的 `q`，按阅读优先级排序
5. 展示给用户确认/修改
6. 确认后写入 YAML

#### 问题拆分原则

- 一个问题 = 一条可独立追踪的调用链（从一个入口到一个核心逻辑）
- 建议 5-15 个问题，避免太碎（>30）或太粗（<3）
- 按依赖关系排序：基础机制 → 上层组合
- 第一个问题通常是「整体使用方式 + 底层每一步做了什么」

### Phase 2: 每日阅读（cron 自动）

1. 读 `repos/{name}.yaml`，找第一个 `status: pending` 的问题
2. 从问题的 `q` 出发，用 `read_file` + `search_files` 追踪调用链
3. 按下面的格式输出排查笔记
4. 笔记存 `notes/{repo}/`，问题标 `done`，`answer_log` 追加一条

## 输出格式

```markdown
## 问题
{问题原文}

## 调用链
Step 0：{用户入口} → {文件:行号}，{做什么}
Step 1：→ {文件:行号}，{做什么}
...（逐层追踪，每步标注文件和行号）

## 关键发现
1. {洞察1：设计决策/架构模式/为什么这样做}
2. {洞察2}
3. {洞察3}
```

## Cron 设置

每个仓库一个 cron job。Hermes cron 的 `deliver` 参数支持 `feishu:chat_id` 格式。

### ⚠️ Cron 推送的关键陷阱（已踩坑）

**cron 的 deliver 机制是将 agent 的最终回复推送给目标平台。** 如果你的 prompt 让 agent 做了很多工作（写文件、更新 YAML），但最终回复只是一句"✅ 已完成"，那么推送到飞书群的就只有这一句话，而不是排查笔记。

**正确做法：**
1. **不要在 cron 中加载 code-study skill** — skill 的复杂指令会覆盖 prompt，导致 agent 行为不可控
2. **prompt 中直接内联输出格式模板** — 简单直接，不依赖外部文件
3. **指示 agent 直接输出排查笔记作为唯一回复** — 不要写"验证通过"、"已完成"等废话
4. **笔记存档由 cron agent 的副作用完成**（write_file 到 notes/ + 更新 YAML），但最终回复必须是排查笔记内容

### 经过验证的 Cron Prompt 模板

```
你是代码阅读助手。按以下步骤执行：

1. 读取 ~/.hermes/code-study/repos/{name}.yaml，找到第一个 status=pending 的问题
2. 从问题的 q 字段出发，追踪 {语言} 源码调用链（用 read_file + search_files）
3. 按以下格式直接输出排查笔记（这是你推送到飞书群的唯一回复，不要写「验证通过」「已完成」等废话）：

## 问题
{问题原文}

## 调用链
Step 0：{用户入口} → {文件:行号}，{做什么}
Step 1：→ {文件:行号}，{做什么}
...（逐层追踪，每步标注文件和行号）

## 关键发现
1. {洞察1：设计决策/架构模式/为什么这样做}
2. {洞察2}
3. {洞察3}

4. 输出完成后，将以上笔记内容保存到 ~/.hermes/code-study/notes/{name}/{日期}-{问题简述}.md
5. 在 YAML 中把该问题的 status 改为 done，在 answer_log 中追加一条记录（日期 + 笔记文件路径 + 一句话摘要）
```

关键点：`skills: []`（空数组）、`enabled_toolsets: ["terminal","file"]`。

## 全局默认配置

全局默认配置位于本 skill 的 `templates/defaults.yaml`，定义通用 `custom_prompt` 和输出格式。仓库级 YAML 中不写的字段自动继承全局默认。

## 注意事项

- **先讨论再落盘**：当用户提到想加入新仓库时，先确认仓库是否合适、阅读重点是什么、问题如何拆解。不要一上来就写 YAML 和建飞书群。用户纠正过这个行为。
- `questions` 列表支持手动维护，也支持 AI 扫描建议
- `answer_log` 记录每次回答的日期、笔记路径、摘要
- 写深度文章是独立操作，不嵌入每日阅读流程
- 仓库 YAML 文件和 notes/ 都属于运行时数据，存 `~/.hermes/code-study/`；skill 模板和 defaults 存本仓库
