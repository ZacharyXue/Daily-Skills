# Reading Notes → Blog Article Conversion Pattern

## When this applies

After completing the chapter-by-chapter review and compression of WeChat Read highlights, the user may say the result is "可读性太差" (unreadable). This means they want a flowing narrative article, not a highlight dump.

## The two-phase workflow

### Phase 1: Extraction & Review (highlight-dump format)
- Every highlight as a separate `>` block
- Chapter-by-chapter review with user
- Compression only when user explicitly asks ("你觉得要怎么压缩")
- Goal: extract and curate the raw material

### Phase 2: Article Conversion (flowing prose)
- Triggered by user saying the dump is unreadable
- Rewrite the ENTIRE file as a cohesive article
- Structure as logical steps, not chapter-by-chapter
- Embed all 💭 thoughts in prose (they give the article a personal voice)
- Preserve all key frameworks (CPR, STATE, AMRP, three "小聪明" types)
- Add transitions between sections
- Add a "读后" conclusion

## Format transformation

| Before (Phase 1) | After (Phase 2) |
|---|---|
| `> 划线原文` blocks stacked | Quoted text woven into paragraphs |
| Chapter headings = book chapter names | Section headings = logical steps |
| 💭 at end of quote blocks | 💭 inline after the point it comments on |
| No introduction, no conclusion | Intro ("什么是关键对话") + "读后" summary |
| Passive presentation of quotes | Active narration with the reader's voice |

## First section structure

The opening should:
1. Define what the book is about (the concept of "关键对话")
2. Include the user's favorite quote from Chapter 1 (the "弄巧成拙" one)
3. State the book's core thesis (共享观点库)
4. Then begin the step-by-step framework walkthrough

## What NOT to do

- Do NOT keep the `> quote` / `💭` stacked format for the final blog post
- Do NOT structure by original book chapters — reorganize by logical theme
- Do NOT drop any 💭 thoughts during conversion
- Do NOT convert framework explanations into bullet lists — keep them as prose
- Do NOT ship Phase 1 output as the final article

## Preview workflow

After writing Phase 2:
1. `npm run build` to verify no build errors
2. `npx astro dev --host 0.0.0.0 --port 4321` (in background)
3. Navigate browser to `http://localhost:4321/blog/<slug>`
4. Use `browser_console` to extract `article.innerText` and verify all 💭 are present
5. Show snapshot/screenshot to user for approval

## Real example from this session

Original: 270 lines of `> quote` / `💭` highlights, one per chapter
Converted to: ~200 lines of flowing prose in 9 logical steps:
明确目的 → 选对话题(CPR) → 控制情绪 → 注意观察(双路处理) → 保证安全 → 陈述观点(STATE) → 了解动机(AMRP) → 面对反馈 → 从对话到行动
