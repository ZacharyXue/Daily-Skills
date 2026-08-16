---
name: skill-creation-guide
description: 创建/管理自己的 Hermes skill 的完整引导 — 目录结构、SKILL.md 规范、软链接入 Hermes、README/开源清单维护。触发时机：用户说「新建一个 skill」「把这个流程存成 skill」「怎么创建自己的 skill」、zach-skills 仓库维护。
version: 1.0.0
tags: [hermes, skill, meta, workflow, zach-skills]
---

# 自建 Skill 引导（zach-skills 仓库）

本 skill 是「创建自己的 skill」的流程引导。所有自建 skill 统一存放在 `/root/zach-skills/`（git 仓库，remote: `git@github.com:ZacharyXue/Daily-Skills.git`），通过软链接入 Hermes。

## 仓库结构

```
/root/zach-skills/
├── README.md              # 自建 skill 索引表（必须同步维护）
├── OPENSOURCE_SKILLS.md   # 使用的开源 skill 清单（升级后核对）
└── <skill-name>/          # 每个自建 skill 一个目录
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

## 修改已有自建 skill

- **直接改仓库文件**（`/root/zach-skills/<name>/...`），**不要用 skill_manage 操作**——skill 是软链，skill_manage 写 symlink 会失败。
- 改完 commit。
- 内容重大变化时 bump `version`。

## 维护 OPENSOURCE_SKILLS.md

记录的是 Hermes **bundled**（内置开源）skill，非自建。Hermes 升级后：

```bash
cat /root/.hermes/skills/.bundled_manifest   # 核对数量与 hash
# 数量/内容变化 → 更新 /root/zach-skills/OPENSOURCE_SKILLS.md
```

## 陷阱

1. **软链必须指向 /root/zach-skills/ 内的目录**，不要拷贝文件副本——否则更新不同步。
2. **skill_manage 对软链 skill 的修改会失败**（curl 到 symlink 报错），直接改文件。
3. **description 别写废话**：触发时机必须具体（用户原话级别的关键词），否则 skill 永远不被加载。
4. **README 索引是「事实来源」**：新增/删除 skill 忘记更新，下次审计会缺条目。
5. **不要在知识型 skill 里混合环境细节**：全局环境信息放记忆，skill 只存可复用的流程/知识。