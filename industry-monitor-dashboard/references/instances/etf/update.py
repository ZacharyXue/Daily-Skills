#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ETF 红利看板 · 一键更新
用法:  cd etf-dashboard && python3 update.py
流程: 拉数据(5年分位/行情/K线) -> 生成 HTML -> 落到 public/exports/etf-dashboard.html
之后按需: git add + commit + push (看板为静态页, push 后 GitHub Pages 自动更新)
"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import generate_html

if __name__ == "__main__":
    # generate_html.__main__ 已含 main()+渲染+写盘; 显式调用其入口逻辑
    cfg, rows, errs = generate_html.main()
    kline_date = rows[0]["date"] if rows else None
    html = generate_html.build_html(cfg, rows, errs, kline_date)
    out = os.path.normpath(os.path.join(HERE, "../public/exports/etf-dashboard.html"))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(html)
    print(f"✅ 已更新 {out} ({len(html)} 字节, {len(rows)} 只标的, {__import__('datetime').datetime.now():%Y-%m-%d %H:%M})")
    for r in rows:
        print(f"   {r['name']} -> [{generate_html.SIG_LABEL.get(r['sig_key'])}]")