#!/usr/bin/env python3
"""Extract text from A-share annual/semi-annual report PDFs.

Usage:
    python3 extract_report_txt.py <pdf1> <pdf2> ...

Writes <input>.txt beside each PDF, with `=== PAGE N ===` markers so
downstream grep anchors can be traced back to source pages.

Notes:
    - Requires pymupdf:  pip install pymupdf
    - Use `import pymupdf`, NOT `import fitz` (deprecated).
"""
from __future__ import annotations

import sys
from pathlib import Path


def extract(pdf_path: str) -> Path:
    import pymupdf  # deferred import so --help works without the dep

    pdf = Path(pdf_path)
    if not pdf.is_file():
        raise FileNotFoundError(pdf)

    doc = pymupdf.open(str(pdf))
    out = pdf.with_suffix(".txt")
    with out.open("w", encoding="utf-8") as fh:
        for page in doc:
            fh.write(f"=== PAGE {page.number + 1} ===\n")
            fh.write(page.get_text())
    n = doc.page_count
    doc.close()
    print(f"{pdf.name} -> {out.name} ({n} pages)")
    return out


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    for arg in sys.argv[1:]:
        try:
            extract(arg)
        except Exception as exc:  # keep going over a batch
            print(f"FAIL {arg}: {exc}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())