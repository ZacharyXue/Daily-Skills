#!/usr/bin/env python3
"""wiki_lint.py — 知识库落库自检（四项），2026-10-01 实测可用

用法:  python3 scripts/wiki_lint.py [wiki_root]      # 默认 /root/wiki
检查:
  ① wikilink 断链（指向不存在的页面文件）
  ② index.md 完整性（每个页面都已登记）
  ③ frontmatter 必备键（title/created/updated/type/tags）+ 每页 >= 2 出链
  ④ 页数 == index 登记条目数（账实一致，防「凭记忆 +1」）
退出码: 0 全绿 / 1 有问题
"""
import re
import sys
import pathlib

root = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "/root/wiki")
pages = sorted(list(root.glob("concepts/**/*.md")) + list(root.glob("entities/*.md")))
names = {p.stem for p in pages}
index_txt = (root / "index.md").read_text(encoding="utf-8")
index_count = len(re.findall(r"^- \[\[", index_txt, flags=re.M))

broken, unregistered, issues = [], [], []
for p in pages:
    text = p.read_text(encoding="utf-8")
    body = re.sub(r"^---.*?---", "", text, count=1, flags=re.S)
    links = re.findall(r"\[\[([^\]|]+)(?:\|[^\]]*)?\]\]", body)
    if len(links) < 2:
        issues.append(f"{p.name}: 出链 {len(links)} < 2")
    for link in links:
        if link not in names:
            broken.append(f"{p.name} -> [[{link}]]")
    for key in ("title:", "created:", "updated:", "type:", "tags:"):
        if not re.search(rf"^{key}", text, flags=re.M):
            issues.append(f"{p.name}: 缺 {key}")
    if f"[[{p.stem}|" not in index_txt and f"[[{p.stem}]]" not in index_txt:
        unregistered.append(p.stem)

print(f"页面 {len(pages)} | index 登记 {index_count}")
print(f"断链 {len(broken)}:", broken or "无")
print(f"未登记 {len(unregistered)}:", unregistered or "无")
print(f"其它问题 {len(issues)}:", issues or "无")
mismatch = len(pages) != index_count
if mismatch:
    print(f"⚠️ 账实不一致: 文件 {len(pages)} vs index 登记 {index_count}")
sys.exit(1 if (broken or unregistered or issues or mismatch) else 0)
