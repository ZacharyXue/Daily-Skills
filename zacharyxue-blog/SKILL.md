---
name: zacharyxue-blog
description: Develop and maintain the ZacharyXue.github.io Astro v5 blog — add posts, projects, fix rendering bugs, and apply consistent styling.
---

Trigger: any task on `/root/ZacharyXue.github.io/` — add/edit blog posts, projects, styles, fix rendering, build/deploy.

## 用户写作工作流（先确认，再落盘）

- **博客是副产品，教会用户是主目标**。把讨论/教程沉淀成文章前，先确认用户真的想要「写文章」这一步——用户常先要答疑和讲解，文章是最后才沉淀。
- **长篇技术文必须先给提纲**：动手写正文前，先输出章节级提纲（含每节要点 + 代码示例范围），等用户确认结构、深度、篇幅后再写。用户明确说「首先先看看你的提纲」时尤其如此。
- 提纲按「纠正误解 → 核心知识 → 对比/选型」等递进结构组织，标注是否需展开的章节。
- **用户确认提纲后，落到 `src/content/blog/YYYY-MM-DD-slug.md`，再 `npm run build` 验证。**

## 写作格式偏好（用户明确要求，2026-08-17 确认）

- **图标多、文字少**：正文优先用表格 + emoji 图标（✅/⚠️/🔴/🟡/🟢/📉/💰 等）传递信息，减少大段纯文字。表格能承载的信息不要用段落写。
- **技术拆解/源码分析类文：mermaid 图驱动**（2026-08-16 确认）——流程/架构/对比尽量画成 mermaid（flowchart/graph/stateDiagram），每节一段引导文字即可。OpenCodeReview 拆解文 11 张图 + 少量文字获认可。图渲染机制与验证方法见 `astro-blog` skill 的「Mermaid 图渲染」节。
- 结论/重点用「**一句话总结**」或粗体短句收尾，不写长篇小结。
- 数据密集类文章（指数/基金/回测）的排版范式：
  - 核心指标 → 单行表格（| 指标 | 数值 |）
  - 历史/对比数据 → 多行表格（含 emoji 标注升降、好坏）
  - 阈值/规则 → 表格 + emoji 分级（❌ 不买 / 🟡 分批 / 🟢 加仓 / 🔴 重仓）
  - 起止时间 → 用「→」箭头，日期不带时分
  - 引用数据标注数据来源与日期（如「数据截至 2026-08-14」），自算口径要注明（如「回撤统计基于日线自算」）
- **投研/数据类文章写之前，先输出数据来源清单**（每项数据的来源接口/网站 + 拉取日期 + 是否自算），用户确认后再动笔；文末再落一遍来源说明
- **投研/指数分析类文章默认 `hide_from_home: true`**（用户偏好：分析文不进首页列表；构建后 grep dist/index.html 验证首页无此 slug、dist/blog/index.html 有）

### 渲染与结构铁律（用户实测反馈，2026-08-17）

- **表格单元格内禁用 `**加粗**`**：Astro Markdown 表格里加粗+emoji 混用渲染不稳定（用户实测"加粗失效"）。表格内的强调一律靠 emoji（🟢/🔴/🟡/⚠️）和数值本身，加粗只用在正文段落和 `> 引用块` 里。
- **成稿前合并重复信息**：同一数据/结论只出现一次。典型坑：风险清单章节 vs 芒格死法清单高度重叠（铝价/成本/散户/杠杆各写两遍）——写芒格评估时就删掉独立的风险清单，合并成一张表。章节数宁少勿多（10 章 → 7 章这种合并方向是对的）。
- **公开文章禁止出现内部路径/skill 名**：不要写 `zach-skills/...`、`~/.hermes/...`、skill 文件名（如 `munger-evaluation.md`）。框架来源可以说"芒格逆向评估框架"，不能写文件路径。写完 grep 检查 `zach-skills|\.hermes|references/` 无残留。

## Project overview

- **Repo**: `/root/ZacharyXue.github.io/` (remote: `git@github.com:ZacharyXue/ZacharyXue.github.io.git`)
- **Framework**: Astro v5 (static SSG), deployed via GitHub Actions → GitHub Pages
- **Content**: Markdown + Content Collections (`src/content/blog/`, `src/content/projects/`)
- **Layouts**: `BlogLayout.astro`, `ProjectLayout.astro`, `BaseLayout.astro`
- **Styles**: `src/styles/global.css` (CSS variables + markdown typography)
- **Commands**: `npm run dev` (localhost:4321), `npm run build`, `npm run preview`
- **Conventions**: Markdown files kebab-case, blog posts `YYYY-MM-DD-slug.md`, commit only (user pushes)

## Pitfalls

### HTML escaping in Astro expressions
**Astro HTML-escapes `{expression}` output by default.** Never use `.join()` to concatenate HTML strings inside `{}` — the tags will render as literal text.

❌ Wrong:
```astro
<div class="tags"><span class="tag">{tags.join('</span><span class="tag">')}</span></div>
```

✅ Correct — use `.map()` with Astro elements:
```astro
<div class="tags">
  {tags.map(tag => <span class="tag">{tag}</span>)}
</div>
```

### Table styles
`global.css` uses targeted `article *` selectors for markdown content. Tables were originally missing — add them via `article table` selectors. Reference: `references/table-styles.css` for the canonical block (borders, zebra striping, dark mode).

**2026-10-18 表格结构改造（改前先读，别回退）**：
- 表格本体现在是 `display: table` + `width: 100%`，**不要再写回 `display:block; overflow-x:auto`**。那个方案会让表格盒按 100% 宽绘制外框，而内层列宽按内容自适应 → 窄表右侧多出一段空白 + 竖线，看起来像多了一列（实测被误判为「Markdown 多写了一个 `|`」，查源文件才发现表只有 3 列）。
- 滚动与外框改由 JS（BlogLayout 的 `<script>`）给每张表包一层 `div.table-scroll` 承担；`.table-scroll` 是 JS 动态创建的元素，**没有 Astro scoped 属性**，所以它的样式必须写在 `global.css` 而不是组件 `<style>` 里，否则不生效。
- `article table td:first-child { white-space: nowrap }` 是修「`ls -lah` 被折成 `ls -` + `lah`」的，别删；表格过宽时交给外层横向滚动。
- 无 JS 时表格仍有 `article table` 自身的边框兜底，不会裸奔。

### 行内目录块（.toc-inline）
文章头下方有一个 `<details class="toc-inline">`，**≥3 个 h2/h3 才渲染**（`showInlineToc`）。原因：左侧那个 34px 悬浮抽屉在桌面首屏几乎看不见，长文需要更明显的入口。抽屉（`.toc-sidebar`）保留，两者并存。
展开态必须保持 `max-height: min(60vh,460px); overflow-y:auto` —— 实测 29 节的长目录展开后会占满整屏、把正文推到屏幕外。

### 邮件讨论卡片（.discuss，零后端）
文章底部一个 mailto 卡片，链接由 BlogLayout 头部常量生成：
```js
const DISCUSS_EMAIL = 'xuezihao2016@outlook.com';   // 改邮箱改这里
const canonicalUrl = new URL(Astro.url.pathname, SITE).href;
const mailtoHref = `mailto:${DISCUSS_EMAIL}?subject=${encodeURIComponent(discussSubject)}&body=${encodeURIComponent(discussBody)}`;
```
- subject = `讨论：《文章标题》`；body = `原文：<链接>\n\n我的评论：\n`（读者打开邮件后光标直接落在「我的评论」后面）。
- 构建后 HTML 里 `&` 会被转义成 `&#38;`，**那是正确的**（浏览器解码回 `&`），别当 bug 修。校验：`grep -o 'href="mailto:[^"]*"' dist/blog/<slug>/index.html` 后 `html.unescape` + `parse_qsl` 解出收件人/subject/body 核对。
- 选的是「零依赖 mailto」方案而非 Web3Forms/giscus：不引第三方、不暴露读者数据；代价是依赖读者本机邮件客户端。若以后要升级成网页表单，见 skill 讨论记录（Web3Forms 250 封/月免费）。

### 改版后的视觉自查流程（无浏览器环境）

```bash
CH=$(ls /root/.cache/ms-playwright/chromium_headless_shell-*/chrome-headless-shell-linux64/chrome-headless-shell | head -1)
$CH --no-sandbox --disable-gpu --hide-scrollbars --window-size=1280,1500 \
    --screenshot=/tmp/x.png "http://localhost:4321/blog/<slug>/"
```
- 预览服务：`npx astro preview --port 4321`（**别用 `pkill -f "astro preview"` 停它**：你自己那条命令行里就含这个字符串，pkill 会连当前 shell 一起杀（实测 exit -15 两次）；用 `for p in $(pgrep -f "[a]stro preview"); do kill $p; done`，且**分成两条命令**跑——同一条命令里若出现字面量 `astro preview` 仍会自杀）。
- 分块送 `vision_analyze` 自查：整页长图会被下采样看不清，用 PIL `crop` 切成 900–1300px 区块。
- 截「页面最底部」的正确姿势：把 window 开很高（如 9000）再自动找内容底边——**按行统计非背景像素**（每行采样 `range(0,W,5)`，阈值 >20 才算内容行），取最深内容行上切；只比对单个像素会被底部 1px 杂点骗到。
- 展开态没法直接截：`<details>` 默认收起。复制一份 `index.html` 到 dist 同目录、把 `<details class="toc-inline"` 替换成 `<details class="toc-inline" open`（**注意构建后标签上带 `data-astro-cid-*` 属性，所以匹配串不能写成 `<details class="toc-inline">`**），截完删文件。

### Custom project pages
To override the generic `[slug].astro` for a single project, create `src/pages/projects/<slug>.astro`. It must:
- `import { getCollection } from 'astro:content'` to read frontmatter
- Use the same `ProjectLayout` for consistent chrome
- Build without duplicate-id warnings

When removing the override, delete the `.astro` file and the dynamic route takes over.

### Privacy for embedded content
Before embedding external HTML (resumes, documents) into public pages, confirm with the user — content may contain phone numbers, email, or employment history they don't want publicly indexed. Prefer linking to the source repo over inline embedding when sensitive.

### Mermaid diagrams

The blog supports Mermaid diagrams natively via code fences with `mermaid` language tag. Use them to replace dense prose — state diagrams, flowcharts, and mindmaps all render inline. Build output confirms they're processed without errors.

⚠️ 静态构建产物里**不会**出现 `.mermaid-wrapper` 容器——这是正常机制：BlogLayout 的 `is:inline` 脚本在运行时把 `pre[data-language="mermaid"]` 替换成 `.mermaid-wrapper` 再 `mermaid.run()`。所以 grep `class="mermaid"` 数为 0 不代表图没渲染。校验 mermaid 语法：把代码块源码用 urlsafe base64 拼成 `https://mermaid.ink/svg/<b64>`，HTTP 200 且返回 `<svg` 即语法 OK（有脚本 /tmp/verify_mermaid.py 可复用）。

### Canonical blog skill
This is the **唯一 canonical skill** for the ZacharyXue.github.io repo — the former `astro-blog` was merged into it (content consolidated). Both lived under the same external dir `/root/zach-skills`; now only this one remains. Its technical references (mermaid CSS/global.css/astro escaping) are either in this file or in `references/`.

## Blog post table-of-contents (TOC)

Articles render a clickable TOC automatically. Implementation split across three files — don't duplicate this logic or you'll break TOC/mermaid:

1. **`astro.config.mjs`** — `rehype-slug` plugin gives every heading an `id` anchor (install: `npm i rehype-slug`):
```js
import rehypeSlug from 'rehype-slug';
markdown: { rehypePlugins: [rehypeSlug] }
```
2. **`src/pages/blog/[slug].astro`** — pass headings into the layout:
```astro
const { Content, headings } = await post.render();
<BlogLayout frontmatter={post.data} headings={headings}>
```
3. **`src/layouts/BlogLayout.astro`** — filter h2/h3 (h1 is the title), render a `<nav class="toc">` box under the header, plus a scroll listener that highlights the current section via `.toc-item a.active`. Only shown when there are ≥2 headings (short posts auto-hide).

Pitfalls:
- **Don't lose the mermaid inline script when editing BlogLayout.astro** — the `<script is:inline>` that loads mermaid from CDN and runs it lives in the same file. When reshaping the layout (e.g. adding TOC), keep both the mermaid block AND the new scroll script, or diagrams silently stop rendering.
- The scroll-highlight `<script>` should be non-inline (Astro-processed); the mermaid loader must stay `is:inline` (CDN-side effects).
- Verify after build: `grep -o 'toc-item' dist/blog/<slug>/index.html | wc -l` (counts compressed HTML) and confirm heading `id="..."` anchors exist.

### frontmatter tags 不能含 `/`（构建会挂）

`tags: [K8s, CI/CD, GitLab]` → 生成 `/tags/CI/CD/` 被解析成两级路由 → 构建报：
```
/tags/CI/CD/index.html  Missing parameter: tag
```
**对策**：tag 值不要带 `/`，用 `DevOps`、`GitLab CI` 这类写法替代。
（grep 自查：`grep -rn "tags:.*\/" src/content/`）

### 增量构建的 `Duplicate id` 警告多为缓存残留

改完文章再 `npm run build`，可能看到：
```
[glob-loader] Duplicate id "<slug>" found in ... Later items with the same id will overwrite earlier ones.
```
源目录里只有一个同名文件时，这是增量缓存残留，**不是真的重复**。
验证：`rm -rf dist && npm run build`，警告消失即确认。

### Shiki syntax highlighting — unsupported languages

Astro's Shiki highlighter doesn't recognize every language identifier. If you get a warning like `The language "gitignore" doesn't exist, falling back to "plaintext"`, either:
- Use a blank fence (no language tag) for `.gitignore` / `.env` / config snippets
- Or map to a supported language: `bash` for shell snippets, `yaml` for config, `text` for generic

This is cosmetic — the warning doesn't break the build, but it's cleaner to avoid it.

### Git workflow
- Commit with `git add -A && git commit -m "..."` then `git push origin main`
- If push rejected with "fetch first", use `git pull --rebase origin main`
- Resolve conflicts by picking the more detailed/current version (usually `--theirs` for upstream enhancements)

## Content collection schemas

Blog frontmatter (`src/content/blog/`):
```yaml
title: string
date: YYYY-MM-DD
tags: [string, ...]
description: string
draft: false  # true = hidden from listings
```

Project frontmatter (`src/content/projects/`):
```yaml
title: string
url: https://github.com/...
tags: [string, ...]
status: active | archived
```

## 参考

- `references/wechat-to-blog-workflow.md` — WeChat 文章提取 → 博客发布的完整工作流，含图片下载、Mermaid 图替换文字、构建验证。
- `references/astro-join-escaping-bug.md` — Astro `{}` 表达式 HTML 转义 bug 完整复现与修复（.join() 渲染成字面文本的坑）。
- `references/reading-notes-to-article.md` — 微信读书笔记 → 文章（Phase 2 叙述化改写）完整示例。
- `references/weread-api.md` — 微信读书数据提取 API 全参考（搜索/bookinfo/bookmarklist/review 等）。
- `references/resume-privacy-architecture.md` — 嵌入外部 HTML（简历等）到项目页的隐私与 @scope 样式隔离。
- `references/table-styles.css` — Canonical 表格样式（边框/斑马纹/暗色主题）。

> 原 `astro-blog` skill 已并入本 skill（内容重叠合并去重）。本文件即为博客技能唯一主干；技术细节（mermaid 渲染机制、global.css 样式坑）正文已有，可安心使用。
