#!/usr/bin/env python3
"""技术面信号快照 — 输入资产代码，输出各层技术面信号状态（手动跑，不设 cron）。

用法:
    python3 layer_timing.py L0            # 沪深300 指数层
    python3 layer_timing.py L1 sh515180   # ETF 层（任意代码）
    python3 layer_timing.py L2 sz000933   # 周期个股层（PB分位）
    python3 layer_timing.py all           # 三层快照

数据全走 data-source-router（腾讯K线 + 东财财务序列）。
"""
import sys
sys.path.insert(0, '/root/zach-skills/data-source-router')
import data_router as R


def stats(rows):
    closes = [r.get('close') for r in rows if r.get('close')][-250:]
    if len(closes) < 100:
        return None
    last = closes[-1]
    ma60 = sum(closes[-60:]) / 60
    ma120 = sum(closes[-120:]) / 120
    ma250 = sum(closes) / len(closes)
    high = max(closes)
    dd = (last / high - 1) * 100
    return {
        'last': round(last, 2), 'ma60': round(ma60, 2), 'ma120': round(ma120, 2),
        'ma250': round(ma250, 2), 'above250': last > ma250, 'golden': ma60 > ma120,
        'dd250': round(dd, 1), 'high250': round(high, 2),
    }


def kline(sym, n=400):
    r = R.achieve('kline', symbol=sym, count=n)
    d = R.fetch_detail(r.data_ref)
    rows = d if isinstance(d, list) else d.get('data', [])
    return r.ok, rows


def show(sym, name, layer):
    ok, rows = kline(sym)
    if not ok or not rows:
        print(f"[{layer}] {name}: K线获取失败")
        return
    s = stats(rows)
    if not s:
        print(f"[{layer}] {name}: 数据不足")
        return
    trend = "多头" if (s['above250'] and s['golden']) else ("空头" if not s['above250'] else "震荡")
    print(f"[{layer}] {name}: 现价{s['last']} MA60={s['ma60']} MA120={s['ma120']} MA250={s['ma250']}")
    print(f"   250日线上方={s['above250']} 60>120金叉={s['golden']} 趋势:{trend} 距250日高点回撤={s['dd250']}%")


def pb_rank(code):
    """周期个股 PB 分位（用最近已披露 BPS 对齐日K）"""
    try:
        r = R.achieve('financial_series', code=code, report_name='RPT_F10_FINANCE_MAINFINADATA')
        d = R.fetch_detail(r.data_ref)
        rows = d if isinstance(d, list) else d.get('data', [])
        bps = {}
        for row in rows:
            bps[str(row.get('REPORT_DATE', ''))[:7]] = row.get('BPS')
        ok, krows = kline('sz' + code.split('.')[0], 800)
        pbs = []
        for r0 in krows:
            ym = str(r0.get('date', ''))[:7]
            cand = None
            for rep in sorted(bps):
                if rep <= ym:
                    cand = rep
            if cand and bps.get(cand):
                pbs.append(r0.get('close') / bps[cand])
        if pbs:
            cur = pbs[-1]
            rank = sum(1 for p in pbs if p < cur) / len(pbs)
            print(f"   PB={cur:.2f} 近{len(pbs)}日样本分位≈{rank*100:.0f}%")
            print(f"   {'🔴 高位(>30%)不碰' if rank > 0.3 else '🟢 低位区可关注(需叠加供给出清信号)'}")
    except Exception as e:
        print("   PB分位计算失败:", repr(e))


if __name__ == '__main__':
    arg = sys.argv[1] if len(sys.argv) > 1 else 'all'
    if arg in ('L0', 'all'):
        show('sh000300', '沪深300', 'L0')
        print()
    if arg in ('L1', 'all'):
        sym = sys.argv[2] if len(sys.argv) > 2 else 'sh515180'
        show(sym, sym, 'L1')
        print()
    if arg in ('L2', 'all'):
        code = sys.argv[2] if len(sys.argv) > 2 else '000933.SZ'
        show('sz' + code.split('.')[0], code, 'L2')
        pb_rank(code)