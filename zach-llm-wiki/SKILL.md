---
name: zach-llm-wiki
description: 子皓个人知识库的 LLM Wiki 工作流 — 博客 vs wiki 分工、ingest 提炼、query 检索、lint 维护。数据本体在 /root/wiki（git-crypt 加密私有仓），skill 只含方法论。当子皓说"整理笔记/落库/我的知识库/wiki/queries" 或需要检索个人知识记忆时使用。
version: 1.1.0
tags: [wiki, knowledge-base, knowledge-management, llm-wiki]
---

# LLM Wiki — 子皓个人知识库

基于 Karpathy LLM Wiki 模式，但按子皓的**博客 vs wiki 分工铁律**定制：
博客是对外展示（数据展示 + 知识点的综合），wiki 是内部认知（本质不变的知识经验）。

## 核心定位（先读）

**Wiki 服务于两个目的：**
1. **助力子皓整理知识**：把散落在博客/读书/研究的认知，缝合成互联的知识点地图
2. **agent 获取知识记忆**：Hermes/任何 LLM agent 回答问题时，wiki 是子皓知识的首选记忆层——先查 wiki 再回答，不用每次重新翻 raw 资料

**分工铁律（SCHEMA 原文）：**
- **进 wiki**：知识经验、判断框架、原理、方法、经验教训、跨文章缝合的认知
- **留博客**：单纯数据收集展示（行情/财报数字/看板）、一次性时点结论、对外综合文章
- **企业对比是知识点的综合展示 → 进博客**，wiki 不建对比页（博客原文即归宿）
- **wiki 实体页只存「本质不变」**：生意/护城河/周期属性/治理风险；时点财务数据（净利增速/PE/PB/股息率）一律留博客
- **判据**：去掉日期和数据后依然成立 → 进 wiki；换一天就变 → 留博客

## 数据位置与加密

```
数据本体: /root/wiki/           ← 独立 git 仓，git-crypt 全量加密
方法论:   /root/zach-skills/llm-wiki/   ← 本 skill（公开仓，只含方法论）
密钥备份: /root/wiki-backup/wiki-gitcrypt-key.age
恢复密钥: 子皓微信（RECOVERY.md 指导）
```

**安全约定：**
- 本 skill 只含方法论，绝不写入 /root/wiki 内容
- /root/wiki 是独立 git 仓（不是 zach-skills 的子模块），git-crypt 加密后 push 到 GitHub 私有仓 zach-wiki
- 解锁：`git-crypt unlock`；新机器恢复见 RECOVERY.md
- ⚠️ 不要在 wiki 数据仓内保存任何明文密钥/token

## 目录结构

```
wiki/
├── SCHEMA.md       # 领域规则 + 标签 taxonomy + 页面阈值（权威配置）
├── index.md        # 内容目录：先读这里定位所有页面
├── log.md          # 行动日志（append-only）
├── concepts/       # 概念/框架页（五大域：investing/cloud-native/llm-eng/algorithms/soft-skills）
├── entities/       # 实体页（公司/指数/基金，只存本质）
└── queries/        # 有价值的查询结论回填
```

## 三大操作

### 1. Ingest（落库/整理笔记）

触发：子皓说「整理笔记」「落库」「把这些内容收进 wiki」。

**输入源：**
- 博客文章：`/root/ZacharyXue.github.io/src/content/blog/*.md`（+ projects/）
- 微信读书笔记、知识星球、对话中的知识点

**流程（一篇源 → 多个页面更新）：**
1. **读原文**（read_file + 大纲扫瞄），识别知识点
2. **按分工铁律分流**：能提炼的→wiki；纯数据→告知子皓留在博客即可
3. **查 index.md + search_files**：已有页面？命中就更新，没有且够格（2+ 来源或核心）才建页
4. **写/更新页面**：
   - frontmatter 完整（title/created/updated/type/tags/sources/confidence）
   - wikilink 格式 `[[文件名|中文显示]]`（文件名 kebab-case，obsidian 兼容）
   - 每页至少 2 个出链；页面 30-200 行；「一句话本质」开头
5. **更新 index.md**（登记/改摘要/总页数）+ **log.md**（追加动作）
6. **commit**（git-crypt 自动加密）——只 commit 不 push，推送由子皓决定

**提炼三条准则（子皓偏好）：**
- 知识点粒度不预设限制，按复杂度自然生长
- 不重复冗余叙述；单一事实来源（一个知识点只存一处最新形态）
- 先粗后细：子皓反馈「这块展开」就在原页深化

### 2. Query（回答子皓问题 / agent 检索知识记忆）

触发：子皓问知识性问题（如「我对水泥的判断框架是啥」），或 agent 需要子皓的背景知识时。

**流程：**
1. 读 index.md 定位相关页面
2. 命中则 read_file 相关页，综合回答（引用 wiki 页）
3. **有价值的答案回填**：如果是深度对比/综合分析，新建 queries/ 页面，别让结论消失进聊天
4. 更新 log.md

**关键：question 优先用 wiki 而不是重新去翻博客原文**——wiki 是编译过的知识，这是它存在的意义。

### 3. Lint（维护）

触发：周期性检查或刚做完大 ingest。

- 孤儿页（无入链）、断链（wikilink 指向不存在文件）→ 用脚本扫描
- index 完整性：每个页面都在 index.md
- frontmatter 完整 + tags 在 taxonomy 内
- 页面 >200 行提示拆分
- `confidence: low` / `contested` 页面清单给子皓复核

## 写作风格（子皓偏好）

- 每页「一句话本质」开头（加粗）
- 判据用表格（不是散文）
- 概念页给**方法演示**（假设数字），不绑定时点价格/年份
- 实体页只写本质，时点数据一行提示「见博客原文」
- 深度细节留博客，wiki 只存不会过期的认知
- 中文

## 相关

- 博客仓库：/root/ZacharyXue.github.io（数据源 + 对外展示）
- zach-skills 其他：data-source-router（取数）、stock-analysis、investment-mindset
- 本 skill 的私有数据策略：同 career-data/social-data（独立 git 仓 + gitignore 保护不随公开仓泄露）