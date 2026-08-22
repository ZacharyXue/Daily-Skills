# Astro .join() HTML escaping bug — reproduction & fix

## Symptom

On the blog list page (`/blog`), tags render as raw HTML text:

```
算法</span><span class="tag">Python</span><span class="tag">LeetCode
```

Instead of rendered tag pills.

## Root cause

In `src/pages/blog/index.astro`, tags were rendered using JavaScript `.join()`:

```astro
<div class="tags">
  <span class="tag">{post.data.tags.join('</span><span class="tag">')}</span>
</div>
```

Astro's template engine HTML-escapes all `{expression}` output by default, so the
`</span><span class="tag">` string inside `.join()` is treated as literal text.

## Fix

Replace `.join()` with `.map()` to render each tag as an Astro element:

```astro
<div class="tags">
  {post.data.tags.map(tag => <span class="tag">{tag}</span>)}
</div>
```

This works because each `<span>` in the `.map()` callback is an Astro JSX element,
not a string — so it's not subject to HTML escaping.

## Affected file

`src/pages/blog/index.astro` — the blog list page (fixed in commit `45ac8ab`).

## Verification

Run `npm run build` and check `dist/blog/index.html`:

```bash
grep -oP '<span class="tag">[^<]+</span>' dist/blog/index.html
```

Should show individual `<span>` elements per tag, not raw `</span>` text.
