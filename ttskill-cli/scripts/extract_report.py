#!/usr/bin/env python3
"""从基金定期报告 PDF 提取 §4.4「投资策略和运作分析」经理原文。

用法: python extract_report.py <季度报告.pdf> [输出文件]
依赖: pymupdf (uv venv /tmp/pdfenv && /tmp/pdfenv/bin/pip install pymupdf)

坑: 目录页也含「投资策略和运作分析」标题行 → 取最后一次出现(=正文)。
     FOF 报告章节编号不同但同标题，同样适用。
"""
import sys

import fitz  # pymupdf


def extract(path: str) -> str:
    doc = fitz.open(path)
    full = "\n".join(p.get_text() for p in doc)

    starts = [m.start() for m in __import__("re").finditer(r"报告期内基金的投资策略和运作分析", full)]
    if not starts:
        starts = [m.start() for m in __import__("re").finditer("运作分析", full)]
    if not starts:
        return "未找到运作分析章节"
    start = starts[-1]  # 目录也有标题，正文靠后

    seg = full[start:]
    cut = len(seg)
    for marker in ["4.5", "§5", "5. 投资组合", "报告期末基金资产组合情况", "\n§", "报告期基金的业绩表现"]:
        i = seg.find(marker)
        if 0 < i < cut:
            cut = i
    return seg[:cut].strip()


if __name__ == "__main__":
    text = extract(sys.argv[1])
    if len(sys.argv) > 2:
        with open(sys.argv[2], "w") as f:
            f.write(text)
    print(text)
