---
name: code-study
description: 每日代码阅读系统 — 通过定时任务自动阅读源码仓库，产出知识卡片推送到飞书群，积累架构直觉和工程经验。
version: 1.0.0
tags: [code-reading, architecture, learning, cron]
---

# 每日代码阅读系统

通过定时 cron 自动阅读指定仓库的源码，按模块逐层推进，产出结构化知识卡片，推送到对应飞书群。

## 核心理念

> 每天花 5-10K token 读一小块代码，输出一张知识卡片。日积月累形成可检索的个人代码知识库，目标是培养架构直觉。

## 目录结构

```
~/.hermes/code-study/               ← 运行时数据（进度、笔记、模式库）
├── repos/                           # 每仓库一个 YAML，维护阅读进度
│   └── {repo-name}.yaml
├── notes/                           # 知识卡片按仓库归档
│   └── {repo-name}/
│       └── 2026-08-10-agent-L1.md
└── patterns_library.md              # 跨仓库设计模式积累

~/zach-skills/code-study/            ← 本 skill 的模板和默认配置
├── SKILL.md
└── templates/
    ├── defaults.yaml                # 全局默认 custom_prompt
    └── repo.yaml                    # 仓库配置模板
```

## 阅读层级

每次阅读聚焦**一个模块的一个层次**：

| 层次 | 描述 | 估计 token |
|------|------|-----------|
| L1 结构扫读 | 目录树、入口点、类/函数拓扑、依赖关系 | ~3K |
| L2 模式分析 | 设计模式、数据流、关键抽象、为什么这样组织 | ~5K |
| L3 实现深读 | 死磕一个函数/算法，逐行理解 | ~8K |

**节奏**：不强制 L1→L2→L3 阶梯。`reading_log` 是自由文本，每次记录实际读了什么层面和收获。

## 仓库配置 (repos/{name}.yaml)

### 完整 Schema

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

# ===== 模块与进度 =====
modules:
  - path: src/agent/
    focus: "主循环与消息路由"
    status: pending                   # pending → reading → done
    reading_log:
      - date: "2026-08-10"
        scope: "L1 结构扫读，3 个核心文件"
        files: ["orchestrator.py", "agent_node.py"]
        takeaway: "DAG 拓扑排序 + asyncio.gather 并行同级节点"
```

### 字段说明

| 字段 | 必需 | 说明 |
|------|------|------|
| `name` | ✓ | 仓库简称，用于文件命名 |
| `git_url` | | 远程地址，用于参考 |
| `local_path` | ✓ | 本地绝对路径 |
| `feishu_chat_id` | ✓ | 知识卡片推送目标群 |
| `schedule` | ✓ | cron 表达式，控制阅读频率 |
| `enabled` | ✓ | 一键开关，不用删 cron |
| `custom_prompt` | | 覆盖全局 defaults.yaml |
| `exclude_paths` | | 扫描时跳过的目录 |
| `modules` | | 模块列表，首次为空时 AI 自动扫描生成建议 |
| `modules[].path` | ✓ | 模块相对路径 |
| `modules[].focus` | ✓ | 阅读关注点，注入 prompt |
| `modules[].status` | ✓ | pending / reading / done |
| `modules[].reading_log` | | 每次阅读追加一条 |

## 生命周期

每个仓库经历两个阶段：

```
Phase 1: 手动初始化（交互式，需要用户参与）
  ├── 1. 讨论仓库是否适合、阅读重点、模块方向
  ├── 2. 确认后 clone 仓库到本地
  ├── 3. 创建飞书群 → 拿到 chat_id
  ├── 4. 创建 repos/{name}.yaml（填写基础信息，modules 留空）
  ├── 5. 用户对 Hermes 说"扫描 {name} 的模块"
  ├── 6. AI 扫描目录结构 → 生成建议模块列表
  ├── 7. 用户确认/修改/排序
  └── 8. 模块列表写入 YAML，创建 cron job

Phase 2: 每日自动（cron 无人值守）
  ├── cron 触发 → 读 YAML → 选下一个 pending 模块 → 读代码
  ├── 产出知识卡片 → 存 notes/ → 推飞书群
  └── 模块 done 后手动标记，或 AI 建议标记
```

## 工作流

### ⚠️ 添加新仓库：先讨论再落盘

当用户提到想加入新仓库时，**不要一上来就写 YAML 和建飞书群**。正确流程：

1. 先确认仓库是否适合阅读（方向匹配、代码质量、学习价值）
2. 讨论阅读重点和模块拆分思路
3. 确认飞书群是否就绪
4. 以上全部确认后再落盘

用户明确纠正过这个行为。

### Phase 1: 手动初始化

#### 模块扫描（交互式，必须用户确认）

此步骤**不能由 cron 自动完成**，必须由用户在对话中触发：

1. 用户说"扫描 {name} 的模块"
2. AI 用 `search_files` 扫 `local_path` 目录结构（跳过 `exclude_paths`）
3. 识别核心模块（根据目录名、`__init__.py`/`go.mod`/package 文件等）
4. 为每个模块生成建议的 `path`、`focus`，按阅读优先级排序
5. 展示给用户确认/修改
6. 确认后写入 YAML

#### 模块拆分原则

- 一个模块 = 一个可独立理解的子系统（通常是一个目录或包）
- 建议 6-15 个模块，避免太碎（>30）或太粗（<3）
- 按依赖关系排序：底层基础模块 → 上层业务模块
- 测试目录单独作为模块（学习测试策略）

### Phase 2: 每日阅读（cron 自动）

1. 读 `repos/{name}.yaml`，加载 `defaults.yaml` + 仓库级 `custom_prompt`
2. 找第一个 `status: pending` 的模块
3. 根据 `reading_log` 判断下一步读什么层面
4. 用 `read_file` + `search_files` 读代码
5. 按 `custom_prompt` 指定的格式产出知识卡片
6. 卡片存 `notes/{repo}/`，`reading_log` 追加一条
7. 推送到飞书群

### 模块完成

- 读完后手动标记 `status: done`
- 或 AI 判断「此模块已无新知识可挖」时建议标记
- 不自动标 done，保留用户控制权

## 知识卡片格式

卡片遵循 `custom_prompt` 指定的格式。全局默认输出：

```markdown
## {module_path}
> {一句话概括}

### 关键设计决策
1. **{决策}**：做了什么 + 为什么 + 替代方案
2. ...
3. ...

### 代表性代码
```python
# {为什么选这段}
{code}
```

### 可迁移收获
{怎么用到自己的项目里}
```

## Cron 设置

每个仓库一个 cron job。Hermes cron 的 `deliver` 参数支持 `feishu:chat_id` 格式：

```
cron: code-study-{name}
schedule: {从 YAML 读取}
prompt: 执行代码阅读任务：读 repos/{name}.yaml，按工作流产出知识卡片
deliver: feishu:{feishu_chat_id}
skills: [code-study]
```

## 全局默认配置

全局默认配置位于本 skill 的 `templates/defaults.yaml`，定义通用 `custom_prompt` 和卡片模板。仓库级 YAML 中不写的字段自动继承全局默认。

## 注意事项

- **先讨论再落盘**：当用户提到想加入新仓库时，先确认仓库是否合适、阅读重点是什么、模块如何拆解。不要一上来就写 YAML 和建飞书群。用户纠正过这个行为。
- `modules` 列表支持手动维护，也支持 AI 扫描建议
- `reading_log` 是自由文本，不受 L1/L2/L3 约束，记录实际读了什么
- 写深度文章是独立操作，不嵌入每日阅读流程
- 仓库 YAML 文件和 notes/ 都属于运行时数据，存 `~/.hermes/code-study/`；skill 模板和 defaults 存本仓库
