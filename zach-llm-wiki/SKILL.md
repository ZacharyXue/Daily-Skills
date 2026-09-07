---
name: zach-llm-wiki
description: 子皓个人知识库的 LLM Wiki 工作流 — 博客 vs wiki 分工、ingest 提炼（含反馈闭环）、query 检索、lint 维护、git-crypt 加密恢复。数据本体在 /root/wiki。当子皓说"整理笔记/落库/我的知识库/wiki/queries" 或需要检索个人知识记忆时使用。
version: 2.0.0
tags: [wiki, knowledge-base, knowledge-management, llm-wiki, obsidian, git-crypt]
---

# LLM Wiki — 子皓个人知识库

基于 Karpathy LLM Wiki 模式 + 集成历史 skill（personal-wiki / blog-to-wiki）精华，
按子皓的**博客 vs wiki 分工铁律**定制：博客是对外展示（数据展示 + 知识点的综合），
wiki 是内部认知（本质不变的知识经验）。

## 核心定位（先读）

**Wiki 服务于两个目的：**
1. **助力子皓整理知识**：把散落在博客/读书/研究的认知，缝合成互联的知识点地图
2. **agent 获取知识记忆**：Hermes/任何 LLM agent 回答问题时，wiki 是子皓知识的首选记忆层——先查 wiki 再回答，不用每次重新翻 raw 资料

**源材料定位（避免全盘搜的坑）：**
- 子皓说「我的笔记/知识在 X」时，X 几乎总指**博客文章** `/root/ZacharyXue.github.io/src/content/`，
  不是字面路径（当初「./out」实际就是博客）。先看 `references/blog-source-map.md`，再 clarify 确认。

## 分工铁律（SCHEMA 原文，2026-09-05 用户拍板）

- **进 wiki**：知识经验、判断框架、原理、方法、经验教训、跨文章缝合的认知
- **留博客**：单纯数据收集展示（行情/财报数字/看板）、一次性时点结论、对外综合文章
- **企业对比是知识点的综合展示 → 进博客**（红利ETF四选一、白电双雄等博客原文即归宿），wiki 不建对比页
- **wiki 实体页只存「本质不变」**：生意/护城河/周期属性/治理风险；时点财务数据（净利增速/PE/PB/股息率）一律留博客
- **判据**：去掉日期和数据后依然成立 → 进 wiki；换一天就变 → 留博客
- **单一事实来源**：一个知识点的最新形态只存一处；博客原文通过 `sources:` frontmatter 链接引用，不复制正文（避免双份维护）

## 实体页 vs 概念页

- **实体页**（公司/指数/基金）= 静态本质画像：生意是什么、护城河哪来的、周期属性（价格周期 vs 需求周期）、治理风险、方法论价值。**禁止时点快照数据**（+151%/PE/PB/股息率/单季数字一律留博客）
- **概念页** = 动态判断框架；示例数字写成「演示」口吻，不绑年份/现价
- **不建企业对比页**：对比 = 知识点的综合展示 → 博客原文即归宿

## 页面形态与粒度

- **粒度不预设限制**：按复杂度自然生长（5 行到 200 行均可），用户反馈「这块要展开」就在原页深化，不重开新页
- 每页结构：一句话本质 → 判据/流程 → 关键事实 → 来源链接 → 相关 wikilinks（≥2 出链）
- 概念页给**方法演示**（假设数字），实体页时点数据一行提示「见博客原文」；判据用表格（不是散文）；中文

## Obsidian 兼容（wikilink 铁律）

- Obsidian 按**文件名**（不含 .md）解析 wikilink：`[[cycle-stock-framework|周期股分析框架]]`
- 中文标题做链接 = 死链；统一 kebab-case 文件名 + 管道中文显示
- 每页 ≥2 出链；新建页登记进 `index.md`；动作追加 `log.md`

## 数据位置与加密

```
数据本体: /root/wiki/           ← 独立 git 仓，git-crypt 全量加密
方法论:   /root/zach-skills/zach-llm-wiki/   ← 本 skill（公开仓，只含方法论）
密钥备份: /root/wiki-backup/wiki-gitcrypt-key.age（age+SSH公钥）
恢复密钥: 子皓微信（恢复包 RECOVERY.md 指导）
```

**安全约定：**
- 本 skill 只含方法论，绝不写入 /root/wiki 内容
- /root/wiki 是独立 git 仓（不是 zach-skills 的子模块），git-crypt 加密后 push 到 GitHub 私有仓 zach-wiki
- git-crypt 无口令概念：密钥随机生成，用户零记忆负担；风险只在「密钥文件丢失」
- 密钥丢失 = 云端密文永久无解 → 必须 ≥2 处备份（本地 + 异地/微信恢复包）
- ⚠️ 不要在 wiki 数据仓内保存任何明文密钥/token；完整加密恢复流程见 `references/git-crypt-setup.md`

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
- 微信读书笔记（weread-skills）、知识星球（zsxq）、对话中的知识点

**流程（一篇源 → 多个页面更新）：**
1. **通读原文全部正文**（read_file，不要只看大纲）再动手
2. **反馈闭环（提炼前先验证吸收，part 2.0 新增）**：每篇提炼前，先引导子皓用自己的话说出该文的「本质认知/判断框架」（一句话本质 + 记住点），对照其输出纠正偏差——只有确认他真正吸收了，才把认知写进 wiki 页；没吸收的点宁可不建页
3. **按分工铁律分流**：能提炼的→wiki；纯数据→告知子皓留在博客即可
4. **查 index.md + search_files**：已有页面？命中就更新，没有且够格（2+ 来源或核心）才建页
5. **写/更新页面**：
   - frontmatter 完整（title/created/updated/type/tags/sources/confidence）
   - wikilink 格式 `[[文件名|中文显示]]`；每页至少 2 个出链；「一句话本质」开头
6. **更新 index.md**（登记/改摘要/总页数）+ **log.md**（追加动作）
7. **commit**（git-crypt 自动加密）——只 commit 不 push，推送由子皓决定

**主题线分批**（先做 1-2 条线样例给子皓审，满意再铺开）：
投资（已完 9 篇）→ 云原生（volcano/containerd/linux-ops 3 篇）→ LLM工程（loop/judge/codex/上下文压缩）→ 算法（DP/单调队列/数论）→ 软技能（关键对话/控制论）

**批量 ingest 模式（2026-09-07 全部 5 线落库验证）**：
- 15 篇博客 → 3 个 delegate_task 并行子代理通读提炼（按主题线分组），子代理只读不写，输出 JSON（page_name/essence/points/remember/merge_with）
- 主代理拿到提炼后按规范写 wiki 页、更新 index/log/SCHEMA taxonomy、跑 lint（wikilink 断链 + index 完整性脚本）、commit 一次 + push 远端
- 子代理 context 必须写明：全部博客路径、wiki 分工铁律（去日期成立才进）、输出结构；schema 的 required 必须放顶层（properties 内部会报错）
- 例子：算法 6 篇→6 概念页、云原生 4 篇→4 页、LLM 5 篇→5 页、项目 3 篇→3 实体页、随笔（hello-world）判定不建页直接留博客

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

## Pitfalls（历史踩坑，必读）

- **实体页塞时点数据 = 白干**（用户明确纠正过）：+151% / PE / PB 这类下次看就过期
- **对比页进 wiki = 重复劳动**：博客原文已是归宿
- **wikilink 用中文 = Obsidian 死链**：必须 `[[文件名|中文显示]]`
- **git-crypt 密钥丢失 = 云端密文永久无解**：密钥必须 ≥2 处备份（本地 + 异地/微信恢复包）
- **用户报的目录名常不存在**：先对照 blog-source-map.md，再 clarify 确认，省一次全盘 find

## 相关

- 博客仓库：/root/ZacharyXue.github.io（数据源 + 对外展示）
- Hermes 内置 `llm-wiki`（research）：通用 Karpathy 基建（SCHEMA 模板/lint 细节），本 skill 是其「子皓定制变体」
- zach-skills 其他：data-source-router（取数）、stock-analysis、investment-mindset
- 本 skill 的私有数据策略：同 career-data/social-data（独立 git 仓 + gitignore 保护不随公开仓泄露）