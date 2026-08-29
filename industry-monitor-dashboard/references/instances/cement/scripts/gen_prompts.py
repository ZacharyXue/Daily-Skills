# -*- coding: utf-8 -*-
"""从 manual/metrics_spec.json 生成可复制的采集 prompt → prompts/collect_prompts.md"""
import json, os
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = json.load(open(os.path.join(BASE, "manual", "metrics_spec.json"), encoding="utf-8"))
out = os.path.join(BASE, "prompts", "collect_prompts.md")
os.makedirs(os.path.dirname(out), exist_ok=True)

L = []
L.append("# 水泥看板 · 缺失指标采集（复制去别的软件问）\n")
L.append("> **用法**：把下面每个问题分别粘给任意 AI/工具（ChatGPT/DeepSeek/Perplexity…），拿到答案后")
L.append("> 把该指标的「答案 + 数据日期」发回 Hermes（直接贴答案文本即可），我会解析保存到 `cache/manual.json` 并在看板展示。\n")
L.append("> 原则：正确性优先，答案必须给出**具体数字 + 口径 + 数据日期**，不确定就明确说\"未披露\"。\n")
L.append("---\n")

for key, v in spec.items():
    L.append(f"## {key} · {v['name']}（单位 {v['unit']}）")
    L.append(f"> 为什么关注：{v['why']}\n")
    L.append("**复制这个问题去问：**\n")
    L.append(f"> {v['prompt']}\n")
    L.append("**期望回复包含这些字段：** " + "、".join(v["fields"].keys()) + "\n")
    L.append("---\n")

txt = "\n".join(L)
with open(out, "w", encoding="utf-8") as f:
    f.write(txt)
print("saved", out, len(txt), "chars")
