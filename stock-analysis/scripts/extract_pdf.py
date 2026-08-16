#!/usr/bin/env python3
"""Extract text from PDF reports (annual/semi-annual) with page markers.

Usage:
  python3 extract_pdf.py <input.pdf> [output.txt]

Output format: "=== PAGE N ===" markers between pages for grep-friendly search.
Requires: pip install pymupdf
"""
from __future__ import annotations

import sys
from pathlib import Path


def extract(pdf_path: str, out_path: str | None = None) -> str:
    import pymupdf  # lazy import so --help works without the dep

    doc = pymupdf.open(pdf_path)
    page_count = doc.page_count
    parts = []
    for page in doc:
        parts.append(f"=== PAGE {page.number + 1} ===\n")
        parts.append(page.get_text())
    text = "\n".join(parts)
    doc.close()

    if out_path:
        Path(out_path).write_text(text, encoding="utf-8")
        print(f"{pdf_path} ({page_count} pages) -> {out_path}")
    return text


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    pdf = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else None
    if not Path(pdf).is_file():
        print(f"not found: {pdf}", file=sys.stderr)
        sys.exit(1)
    extract(pdf, out)


if __name__ == "__main__":
    main()
