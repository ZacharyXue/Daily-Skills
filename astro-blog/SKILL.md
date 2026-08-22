---
name: astro-blog
description: Maintain the ZacharyXue.github.io Astro v5 static blog — add/edit posts,
  projects, fix rendering bugs, build, and deploy to GitHub Pages.
---

## Triggers

- Adding, editing, or fixing blog posts, projects, or docs
- Tag display issues, layout bugs, rendering problems
- Build failures, content collection schema errors
- Deploying to GitHub Pages

## Repository location

**Canonical path**: `/root/ZacharyXue.github.io/`  
**Remote**: `git@github.com:ZacharyXue/ZacharyXue.github.io.git`

The repo lives DIRECTLY under `/root/`. A stale duplicate at `/home/xzh/xzh/ZacharyXue.github.io/` was deleted back then — the one at `/root/` is canonical.

## Project layout

```
/root/ZacharyXue.github.io/    # Astro v5, GitHub Pages
  src/content/
    blog/         # Posts: YYYY-MM-DD-slug.md
    projects/     # Projects: project-slug.md
    docs/         # Docs: slug.md
  src/layouts/    # BlogLayout, ProjectLayout, BaseLayout
  src/pages/      # Routes: blog/, projects/, custom/
  public/         # Static files served as-is
```

## Key commands

```bash
cd /root/ZacharyXue.github.io
npm run dev         # Dev server at localhost:4321
npm run build       # Build to dist/
npm run preview     # Preview built site
```

Deployment is automatic via GitHub Actions on push to `main`.

## Pitfalls

### Astro HTML escaping in `{}` expressions

Astro auto-escapes `{expression}` output. Do NOT use `.join()` with HTML strings
to render lists of elements — the HTML tags will appear as literal text on the page.

```astro
<!-- ❌ BROKEN: renders "tag1</span><span class=tag>tag2" as text -->
<div class="tags">
  <span class="tag">{tags.join('</span><span class="tag">')}</span>
</div>

<!-- ✅ CORRECT: use .map() to render Astro elements -->
<div class="tags">
  {tags.map(tag => <span class="tag">{tag}</span>)}
</div>
```

### File naming in blog/

Filenames MUST be `YYYY-MM-DD-kebab-case-slug.md`. The date prefix must match
the `date` frontmatter field. The slug is auto-extracted from the filename
(strips date prefix and `.md` extension).

```yaml
# src/content/blog/2026-07-22-llm-as-judge.md
---
title: LLM as Judge
date: 2026-07-22        # MUST match filename date
tags: [LLM, AI]
---
```

### Content schema

Frontmatter must match `src/content/config.ts` schemas:

**Blog posts:**
```yaml
---
title: string
date: Date
tags: string[]
description?: string
draft?: boolean        # true = hidden from lists
hide_from_home?: boolean  # true = in /blog list but NOT on homepage (index.astro filters it)
pinned?: boolean
---
```

`hide_from_home: true` 只影响首页 `src/pages/index.astro`（`.filter(p => !p.data.draft && !p.data.hide_from_home)`），**不影响 /blog 列表页**。投研/指数分析类文章用它；技术深度拆解类文章不用（默认 false，上首页）。

**Projects:**
```yaml
---
title: string
url?: string           # GitHub link
tags?: string[]
status?: 'active' | 'archived'
---
```

### 标签展示逻辑 (2026-08-17 实现)

`src/pages/blog/index.astro` 有核心标签过滤，改动时保持语义：
- **标签云**只渲染 `coreTags` = 出现次数 ≥ 2 的标签，按频次降序（60 个全展示太杂，用户明确要求精简）
- **文章条目标签**最多展示前 3 个（`MAX_POST_TAGS = 3`，`.slice(0, MAX_POST_TAGS)`）
- **筛选功能不受影响**：`data-tags` 属性仍保留完整标签 JSON，JS 过滤用完整标签匹配

```astro
const tagCounts = new Map<string, number>();
posts.forEach(p => (p.post.data.tags || []).forEach(t => tagCounts.set(t, (tagCounts.get(t) || 0) + 1)));
const coreTags = [...tagCounts.entries()]
  .filter(([, n]) => n >= 2)
  .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
  .map(([t]) => t);
const MAX_POST_TAGS = 3;
```

### Mermaid 图渲染（无需额外配置）

博客通过 `src/layouts/BlogLayout.astro` 的 CDN 加载 mermaid@11，`data-language="mermaid"` 的代码块自动渲染成图（`mermaid.initialize({ startOnLoad: false })` + `mermaid.run`）。**直接在文章里写 ```mermaid 代码块即可**，无需 astro 插件配置。

验证 mermaid 语法：用 mermaid.ink 在线渲染 API（无需本地安装）：
```bash
# base64 编码图定义 → HTTP 200 = 语法 OK
python3 -c "
import base64, urllib.request
d = open('/tmp/diagram.mmd').read()
enc = base64.urlsafe_b64encode(d.encode()).decode()
url = f'https://mermaid.ink/img/{enc}'
print(urllib.request.urlopen(url, timeout=20).status)  # 200 = valid
"
```

用户偏好（2026-08-16 确认）：**技术拆解文以图为主、文字精简**——OpenCodeReview 拆解文用 11 张 mermaid 图 + 每节一段引导文字的「图驱动」结构获用户认可。写作时优先把流程/架构/对比画成 mermaid（flowchart/graph/stateDiagram），文字只做点睛。

### Missing element styles in global.css

If a Markdown element (table, `<details>`, `<kbd>`, etc.) renders poorly in blog posts,
it's because `src/styles/global.css` has no rules for it — the browser defaults kick in
with barely-visible borders or cramped spacing. Always add scoped rules under `article`
selector with light + dark mode variants.

**Table example** (browser default has no visible borders):

```css
article table {
  border-collapse: collapse;
  width: 100%;
  margin-bottom: 1rem;
}
article table th, article table td {
  border: 1px solid #ddd;       /* use #ddd not #eee — #eee is invisible */
  padding: 0.6em 0.8em;
}
article table th {
  background: #f5f6fa;
  font-weight: 600;
}
article table tr:nth-child(even) { background: #fafbfc; }

[data-theme="dark"] article table th,
[data-theme="dark"] article table td {
  border-color: #3a3a4e;
}
[data-theme="dark"] article table th { background: #252540; }
[data-theme="dark"] article table tr:nth-child(even) { background: #1e1e35; }
```

**Border visibility rule**: `#eee` borders are near-invisible on white backgrounds.
For h1/h2 underlines and table borders that need to be clearly seen, use `#ddd` or
`#ccc` instead. `#eee` is fine only for very subtle separators.

### Diagnosing visual issues: global.css first

When the user reports a rendering problem ("表格样式不好", "分割线看不清"), always check
`src/styles/global.css` FIRST before assuming it's a specific page or embedded content
issue. Most element-level styling gaps (tables, code blocks, images) originate from
missing rules in the global stylesheet, not from individual page templates. Only after
confirming global.css handles the element should you look at layout-specific overrides.

### Astro join escaping bug

Full reproduction and fix in `references/astro-join-escaping-bug.md`.

### Build before commit

Always run `npm run build` before committing — it catches schema mismatches and
syntax errors that would fail the GitHub Actions deploy.

### Local preview requires dev server

`npm run build` produces static files in `dist/` but does NOT serve them.
To view the site locally:

```bash
npm run dev -- --host 0.0.0.0   # → http://localhost:4321
```

The user saying "can't see the article" after build succeeds usually means they're
looking at a stale deployed site (not pushed) or expecting `build` to serve files.
Always offer to start the dev server if they want to preview locally.

### 读书笔记 from 微信读书 (WeRead)

When the user finishes a book on WeChat Read and wants a reading-notes blog post:

1. **Check skills-lock.json first** — the blog repo's `skills-lock.json` references
   `Tencent/WeChatReading`. Clone it if not already available:
   ```bash
   git clone --depth 1 https://github.com/Tencent/WeChatReading.git /tmp/WeChatReading
   ```
   Read the SKILL.md and relevant sub-skill docs (book.md, notes.md, readdata.md).

2. **API key** is in `~/.bashrc`: `export WEREAD_API_KEY='wrk-...'`

3. **Data extraction** — call the gateway API in sequence:
   ```bash
   # Search for bookId
   curl -X POST https://i.weread.qq.com/api/agent/gateway \
     -H "Authorization: Bearer $WEREAD_API_KEY" \
     -d '{"api_name":"/store/search","keyword":"<书名>","count":5,"skill_version":"1.0.4"}'
   
   # Then: /book/getprogress, /book/info, /book/bookmarklist, /review/list/mine, /book/chapterinfo
   ```

4. **Save raw API responses** to `/tmp/wr_*.json` — these are the recovery source
   if the generated file gets corrupted during the review process.

5. **Generate structured notes** — group highlights (bookmarks) and personal
   thoughts (reviews) by chapter. Pair thoughts with their corresponding
   highlights where the `abstract` field matches. Use `> quote` for highlights
   and `💭 *thought*` for personal notes. Skip "第X部分" summary chapters
   (user considers them fluff).

6. **CRITICAL: Never consolidate or compress during initial generation.** Every
   single highlight must appear as its own `> quote` block — do NOT merge similar
   highlights, do NOT group them into structured tables or bullet lists, do NOT
   summarize. 41 highlights means 41 separate `>` blocks. Consolidating = data loss.
   The user will review each one individually and decide what to keep.

7. **Chapter-by-chapter review workflow.** After generating the draft, present ONE
   chapter at a time. Show ALL highlights in that chapter, numbered. The user may:
   - Say "好的 下一部分" or "继续" → keep all as-is, move on
   - Say "只保留 X 和 Y" → delete the rest from that chapter
   - Say "先展开内容由我决定" → show all individually numbered, let user pick
   - Say "你觉得要怎么压缩内容" → analyze duplicates, propose a compression plan
   - Edit or bold specific phrases (e.g. "弄巧成拙" → **弄巧成拙**)

   Never move to the next chapter until the user explicitly approves.

8. **Compression rules (when user asks):**
   - **Remove fluff**: if the user says "不要，没什么实质信息", delete immediately
   - **Merge duplicates**: same concept appearing in multiple near-identical sentences → one merged quote
   - **Group by topic**: e.g. three kinds of "小聪明想法" → one structured block
   - **NEVER delete 💭 thoughts**: 8 thoughts stays 8 thoughts, 33 stays 33
   - Always present a compression plan (theme table + target count) before executing

9. **User corrections and regressions:**
   - If the user says "好像压缩过了，看看历史对话", the file was accidentally
     overwritten. Use `session_search` to find the approved version, then restore it.
   - If the file gets corrupted, regenerate from `/tmp/wr_*.json` raw data, then
     re-apply ALL user-approved edits (Chapter 1 simplification, bolding, deletions,
     previous compression decisions).
   - The `patch` tool may fail if the file changed on disk between read and write;
     re-read the file and try again with updated context.

10. **Adding personal explanations** — when the user asks you to explain a concept
    (e.g. "AMRP 展开讲讲"), give a detailed conversation-level explanation FIRST,
    then add a condensed version as a `>` quote block into the notes. The blog
    version should be the condensed takeaway, not the full conversational explanation.

11. **PHASE 2: Article conversion.** After all chapters are reviewed and compressed,
    the user may say the highlight-dump format is unreadable ("可读性太差").
    This is a SEPARATE phase — rewrite the entire file as a flowing narrative article:

    - **Structure as a logical progression, not chapter-by-chapter.** Introduce what
      the book is about, then walk through the framework as "steps" the reader can follow.
    - **Keep ALL 💭 thoughts embedded in the prose** — they give the article a personal voice.
    - **Preserve all key frameworks** (CPR, STATE, AMRP, three "小聪明" types) but
      present them as coherent paragraphs, not bullet lists of quotes.
    - **Add transitions** between sections so it reads as one article, not 13 mini-chapters.
    - **Add a "读后" conclusion** that ties everything together.
    - **Preview before committing**: run `npm run dev` and navigate to the blog post
      URL. Use `browser_console` to extract `article.innerText` and verify all
      💭 thoughts are present and the structure flows.

    The compressed highlight-dump is the RAW MATERIAL. The article is the FINAL PRODUCT.
    Do NOT ship the raw material as a blog post — the user explicitly rejected this format.

12. **Finalize** — after all chapters reviewed and supplementary thoughts added,
    confirm with user before changing `draft: false` and committing.

Full API reference in `references/weread-api.md`.
Full article conversion example in `references/reading-notes-to-article.md`.

### Embedding external HTML inline (no iframes)

When you need to embed external HTML content (e.g., a resume, a data report) directly
in a project or blog page without double-scrollbar iframe issues:

1. **Copy the HTML + assets into `public/`**:
   ```bash
   cp external.html public/resume/Resume.html
   cp -r external_assets/ public/resume/assets/
   ```

2. **Create a custom Astro page** (`src/pages/projects/<slug>.astro`) that overrides
   the dynamic `[slug].astro` route:

   ```astro
   ---
   import { getCollection } from 'astro:content';
   import { readFileSync } from 'node:fs';
   import ProjectLayout from '/src/layouts/ProjectLayout.astro';

   const projects = await getCollection('projects');
   const project = projects.find(p => p.id === '<slug>.md');
   const { Content } = await project.render();

   const html = readFileSync('public/path/to/file.html', 'utf-8');
   const bodyContent = html.match(/<body[^>]*>([\s\S]*?)<\/body>/)?.[1] ?? '';
   // Fix relative asset paths: assets/... → /public-path/assets/...
   const fixed = bodyContent.replace(/src="assets\//g, 'src="/public-path/assets/');
   ---

   <ProjectLayout frontmatter={project.data}>
     <Content />                      <!-- project description -->
     <div id="embed-root">
       <Fragment set:html={fixed} />  <!-- embedded content -->
     </div>
   </ProjectLayout>
   ```

3. **Isolate styles with CSS `@scope`** — prevents the embedded HTML's styles from
   leaking into the blog's global styles:

   ```css
   @scope (#embed-root) {
     :scope {
       max-width: 860px;
       margin: 0 auto;
       padding: 30px;
       font-family: ...;
     }
     h1 { font-size: 2em; border-bottom: 1px solid #eee; }
     h2 { font-size: 1.3em; }
     /* ... other scoped rules ... */
   }
   ```

   `@scope` is supported in Chrome 118+, Firefox 128+, Safari 17.4+ — fine for a
   personal blog. Only the CSS rules INSIDE the `@scope` block apply to elements
   within `#embed-root`; the blog's global styles remain untouched.

4. **Pitfall — image paths**: Content inside `public/` is served from `/`. If the
   embedded HTML references `src="assets/icon.svg"`, that resolves relative to the
   *page URL* (e.g., `/projects/markdown-resume/assets/...`), not `/resume/assets/`.
   Always fix asset paths with a regex replace.

5. **Pitfall — duplicate route warning**: Both `[slug].astro` (dynamic) and
   `<slug>.astro` (static) generate the same route. Astro picks the static page
   (listed second in build output), which is what you want. The warning is harmless.

### Git push with remote conflicts

When `git push` is rejected because remote has new commits:

```bash
git pull --rebase origin main     # replay local commits on top of remote
# If conflicts: resolve, then
git add <files>
git rebase --continue
git push origin main
```

To accept the remote version of a conflicted file outright:
```bash
git checkout --theirs <file> && git add <file> && git rebase --continue
```

### Editing existing posts

Use `patch` for targeted insertions into existing blog posts (e.g., adding a new
section). After editing, rebuild and commit:

```bash
npm run build && git add <file> && git commit -m "..."
```

When expanding or editing content sections:

1. **去重优先**: If the same command appears in multiple tables (e.g. `du`/`df` in
   both「文件与目录」and「磁盘与存储」), keep it only in the most appropriate section
   and remove from the other. A command shouldn't appear in two tables.

2. **不要统一深度展开**: Not every command needs the grep/awk treatment (13 options,
   10 scenarios). Keep practical, readable depth — a few common usage patterns with
   short inline comments. The reader is skimming for productivity, not studying a
   man page.

3. **快速诊断留在最后**: The「快速诊断套路」section is a one-screen combo summary.
   Don't merge it into the detailed sections — keep it as the finale.
