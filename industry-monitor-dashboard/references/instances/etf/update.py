#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ETF 红利看板 · 一键更新
用法:  cd etf-dashboard && python3 update.py
流程: 拉数据(中证官网PE5y主锚 + 可选天天基金增强 + 腾讯行情/K线) -> 生成 HTML -> 落到 public/exports/etf-dashboard.html
之后按需: git add + commit + push (看板为静态页, push 后 GitHub Pages 自动更新)
"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import generate_html
import generate

if __name__ == "__main__":
    # generate_html.main() 已含 取数+渲染; 这里补写盘到博客 public/exports/
    cfg, rows, errs, src_status = generate.main()
    kline_date = rows[0]["date"] if rows else None
    html = generate_html.build_html(cfg, rows, errs, kline_date, src_status)
    out = os.path.normpath(os.path.join(HERE, "../public/exports/etf-dashboard.html"))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(html)
    import datetime
    print(f"✅ 已更新 {out} ({len(html)} 字节, {len(rows)} 只标的, {datetime.datetime.now():%Y-%m-%d %H:%M})")
    print(f"   数据源状态: 天天基金PB10y={'可用' if src_status.get('ttfund_ok') else '未取到(' + str(src_status.get('ttfund_note') or '') + ')'}")
    for r in rows:
        print(f"   {r['name']} -> [{generate_html.SIG_LABEL.get(r['sig_key'])}]")
