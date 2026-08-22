# WeChat Article → Blog Post Workflow

End-to-end pattern for reading a WeChat article and turning it into a structured blog post.

## 1. Extract article text

Use the `chinese-web-content` skill's curl + Python technique:

```bash
curl -sL --max-time 15 \
  -H "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 ..." \
  -H "Accept-Language: zh-CN,zh;q=0.9,en;q=0.8" \
  -H "Referer: https://mp.weixin.qq.com/" \
  "<url>" | python3 -c "..." # see chinese-web-content skill for full script
```

## 2. Download images

```bash
# Extract image URLs from data-src attributes
curl ... | python3 -c "
import sys, re
imgs = re.findall(r'data-src=\"(https?://[^\"]+)\"', sys.stdin.read())
for i, url in enumerate(imgs):
    print(url)
"

# Download
mkdir -p /tmp/wechat_article
curl -sLo /tmp/wechat_article/img0.png "<url1>"
# ...

# Check dimensions to identify which is which
file /tmp/wechat_article/img*.png
```

## 3. Copy images to blog

```bash
cp /tmp/wechat_article/img0.png /root/ZacharyXue.github.io/public/descriptive-name.png
# Use kebab-case names. Reference as: ![alt](/descriptive-name.png)
```

## 4. Write blog post

File: `src/content/blog/YYYY-MM-DD-slug.md`

Frontmatter:
```yaml
---
title: 标题
date: YYYY-MM-DD
tags: [tag1, tag2]
description: 摘要
---
```

Content guidelines:
- Start with links to original article + project (if applicable)
- Use Mermaid diagrams to replace dense prose (flowchart, stateDiagram, mindmap)
- Place downloaded images at key transition points
- Use tables for comparison/role matrices
- Use blockquotes (`>`) for key takeaways
- Structure with `##` sections, not a wall of text

## 5. Build and verify

```bash
cd /root/ZacharyXue.github.io
npm run build
```

Check for:
- No build errors
- Shiki warnings (e.g. unsupported language like `gitignore`) — fix by removing language tag
- Images referenced correctly

## 6. Commit

```bash
git add -A && git commit -m "blog: <descriptive title>"
# No push unless asked
```
