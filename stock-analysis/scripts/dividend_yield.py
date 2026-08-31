#!/usr/bin/env python3
"""从东财分红接口现算 A 股股息率（正确算法，避免把腾讯字段38换手率当股息率）。

用法: python3 dividend_yield.py 600079 [股价可选，缺省取实时行情]

依赖: 无第三方库，纯 urllib。市场后缀自动判断（6/9开头→.SH，否则→.SZ）。
"""
import sys, json, urllib.request, urllib.parse

UA = {'User-Agent': 'Mozilla/5.0'}
EASTMONEY = 'https://datacenter.eastmoney.com/securities/api/data/v1/get'


def _suffix(code):
    return '.SH' if code.startswith(('6', '9')) else '.SZ'


def _get(url):
    req = urllib.request.Request(url, headers=UA)
    return json.loads(urllib.request.urlopen(req, timeout=25).read().decode('utf-8'))


def _quote_price(code):
    """腾讯实时行情，返回 (现价, 总市值亿, PE, PB)。字段按 ~ 分割。"""
    prefix = 'sh' if code.startswith(('6', '9')) else 'sz'
    url = 'https://qt.gtimg.cn/q=' + prefix + code
    req = urllib.request.Request(url, headers=UA)
    raw = urllib.request.urlopen(req, timeout=15).read().decode('gbk')
    f = raw.split('="', 1)[1].rsplit('"', 1)[0].split('~')
    return {
        'price': float(f[3]),
        'mktcap_yi': float(f[45]) if len(f) > 45 and f[45] else None,
        'pe': float(f[39]) if len(f) > 39 and f[39] else None,
        'pb': float(f[46]) if len(f) > 46 and f[46] else None,
        'turnover': float(f[38]) if len(f) > 38 and f[38] else None,  # 换手率，非股息率
    }


def _dividends(code):
    """东财分红送配，返回 [{report, ex_date, pretax_per_10, progress}]。"""
    filt = urllib.parse.quote('(SECUCODE="' + code + _suffix(code) + '")')
    url = (EASTMONEY + '?reportName=RPT_SHAREBONUS_DET&columns=ALL&filter=' + filt
           + '&pageNumber=1&pageSize=20&sortTypes=-1&sortColumns=EX_DIVIDEND_DATE')
    rows = (_get(url).get('result') or {}).get('data') or []
    out = []
    for r in rows:
        out.append({
            'report': (r.get('REPORT_DATE') or '')[:10],
            'ex_date': (r.get('EX_DIVIDEND_DATE') or '')[:10],
            'pretax_per_10': r.get('PRETAX_BONUS_RMB') or 0,
            'progress': r.get('ASSIGN_PROGRESS'),
        })
    return out


def main():
    code = sys.argv[1] if len(sys.argv) > 1 else '600079'
    q = _quote_price(code)
    print('现价 = %.2f (总市值 %.1f亿, PE %.1f, PB %.2f, 换手率 %.2f%%)'
          % (q['price'], q['mktcap_yi'], q['pe'], q['pb'], q['turnover']))
    print('--- 近年分红 ---')
    for d in _dividends(code)[:6]:
        per_share = d['pretax_per_10'] / 10.0
        yld = per_share / q['price'] * 100 if q['price'] else 0
        print('  %s 报告期 | 除息%s | 每10股派%.3f元 → 每股%.4f → 股息率%.2f%% [%s]'
              % (d['report'], d['ex_date'], d['pretax_per_10'], per_share, yld, d['progress']))


if __name__ == '__main__':
    main()
