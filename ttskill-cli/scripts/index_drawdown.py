#!/usr/bin/env python3
"""指数回撤统计（2026-08 会话验证）

用法: python3 index_drawdown.py <index_code> [start_date] [end_date]
示例: python3 index_drawdown.py 931722 20160817 20260817

数据源: 中证指数官网 API (csindex.com.cn) 日线
输出: 回撤事件全景、最大/平均/中位回撤、显著回撤分位、恢复时间、当前状态

背景: 该脚本由 931722 指数回撤分析会话沉淀。
- 官网 API: https://www.csindex.com.cn/csindex-home/perf/index-perf?indexCode=XXX&startDate=YYYYMMDD&endDate=YYYYMMDD&frequency=daily
- 基日可向 startDate 传基日前一天，接口返回 earliest 可用数据时自动截断
- 价格指数口径（不含股息）；高股息指数需另注全收益口径更高
"""
import json
import statistics
import sys
import urllib.request
from datetime import datetime


def fetch(url):
    req = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Referer': 'https://www.csindex.com.cn/'})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode('utf-8', errors='replace'))


def main():
    code = sys.argv[1] if len(sys.argv) > 1 else '931722'
    start = sys.argv[2] if len(sys.argv) > 2 else '20160817'
    end = sys.argv[3] if len(sys.argv) > 3 else '20260817'
    url = (f"https://www.csindex.com.cn/csindex-home/perf/index-perf"
           f"?indexCode={code}&startDate={start}&endDate={end}&frequency=daily")
    d = fetch(url)
    rows = d.get('data', [])
    series = sorted([(r['tradeDate'], float(r['close']))
                     for r in rows if r.get('close') and r.get('tradeDate')])
    if len(series) < 2:
        print("数据不足", url)
        return
    print(f"数据: {series[0][0]} ~ {series[-1][0]}, {len(series)} 个交易日")

    # 每日回撤（相对峰值）
    drawdown = []
    peak = -1
    for t, c in series:
        peak = max(peak, c)
        drawdown.append((t, (c / peak - 1) * 100))

    # 回撤阶段: 峰值 → 谷底 → 恢复(或进行中)
    phases = []
    in_dd = False
    for i, (t, dd) in enumerate(drawdown):
        if dd < 0:
            if not in_dd:
                in_dd = True
                start_peak = drawdown[i - 1][0] if i > 0 else t
                trough = (t, dd)
            elif dd < trough[1]:
                trough = (t, dd)
        else:
            if in_dd:
                phases.append({'start': start_peak, 'trough_date': trough[0],
                               'dd': trough[1], 'recover': t})
                in_dd = False
    if in_dd:
        phases.append({'start': start_peak, 'trough_date': trough[0],
                       'dd': trough[1], 'recover': None})

    print("\n=== 全部回撤阶段 ===")
    for p in phases:
        rec = p['recover'] or '进行中'
        print(f"  {p['trough_date']} dd={p['dd']:+.2f}% 起于{p['start']} 恢复:{rec}")

    dds = [p['dd'] for p in phases]
    sig = [p for p in phases if p['dd'] <= -5]

    print(f"\n=== 统计 ===")
    print(f"回撤事件总数: {len(phases)}")
    print(f"显著回撤(>=5%): {len(sig)}")
    print(f"最大回撤: {min(dds):.2f}%")
    print(f"平均回撤(全部): {statistics.mean(dds):.2f}%")
    print(f"中位回撤(全部): {statistics.median(dds):.2f}%")

    def pctile(vals, p):
        vals = sorted(vals)
        k = (len(vals) - 1) * p
        f = int(k)
        c = min(f + 1, len(vals) - 1)
        return vals[f] + (vals[c] - vals[f]) * (k - f)

    if sig:
        sig_dds = [p['dd'] for p in sig]
        print(f"\n=== 显著回撤分位（按深度，从浅到深）===")
        for v in sorted(sig_dds, reverse=True):
            print(f"  {v:+.2f}%")
        print(f"  50%分位: {pctile(sig_dds, 0.5):+.2f}% (一半回测比这浅)")
        print(f"  80%分位: {pctile(sig_dds, 0.8):+.2f}% (80%回撤不比这深)")
        print(f"  90%分位: {pctile(sig_dds, 0.9):+.2f}%")

    # 恢复时间
    print("\n=== 恢复时间（谷底→回到前高，自然日）===")
    recs = []
    for p in phases:
        if p['recover'] is None:
            continue
        d0 = datetime.strptime(p['trough_date'], '%Y%m%d')
        d1 = datetime.strptime(p['recover'], '%Y%m%d')
        days = (d1 - d0).days
        recs.append(days)
        print(f"  {p['trough_date']} dd={p['dd']:+.1f}% → 恢复 {days} 天")
    if recs:
        print(f"  平均恢复: {statistics.mean(recs):.0f} 天 | 中位: {statistics.median(recs):.0f} 天")
        recs_nox = [(r, p) for r, p in zip(recs, [x for x in phases if x['recover']])
                    if p['dd'] > -30]
        if recs_nox:
            print(f"  排除极端(>-30%)后平均: {statistics.mean([r for r, _ in recs_nox]):.0f} 天")

    # 当前回撤状态
    last_dd = drawdown[-1][1]
    peak_so_far, peak_date = series[-1][1], series[-1][0]
    for j in range(len(series) - 1, -1, -1):
        if series[j][1] >= peak_so_far:
            peak_so_far, peak_date = series[j][1], series[j][0]
    print(f"\n=== 当前状态 ===")
    print(f"最新回撤: {last_dd:+.2f}% ({series[-1][0]})")
    print(f"当前回撤起点: {peak_date} 峰值 {peak_so_far:.2f} → 现 {series[-1][1]:.2f} = {last_dd:+.2f}%")


if __name__ == '__main__':
    main()