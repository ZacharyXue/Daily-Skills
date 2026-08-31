"""
finance.py — 金融数据适配器（实测可用源，ECS 视角 2026-08 验证）

覆盖：
  cn_stock_quote   A股/港股/美股实时快照   → 腾讯 qt.gtimg.cn
  cn_stock_kline   前复权日K                 → 腾讯 web.ifzq.gtimg.cn
  cn_financial     个股财务摘要              → 东财 datacenter-web（免token）
  us_financial_sec 美股财报(公司事实)        → SEC EDGAR companyfacts/submissions（需UA）

注意：
  - AKShare 在 ECS 上实时/K线接口断连(ConnectionError)，仅 stock_financial_abstract 可用
  - Yahoo(yfinance) 429 被限流，Stooq 被JS墙 → 美股行情走腾讯 usAAPL 或 SEC 财报
  - SEC 必须带 User-Agent(含邮箱)，否则 403 (whale-holdings 已踩坑)
  - 腾讯K线 vol 单位=手(100股)，成交额×100
"""
import os
import json
import time
import logging
import urllib.parse
from dataclasses import dataclass

import requests

log = logging.getLogger("dsr.finance")

UA = os.getenv("SEC_USER_AGENT", "Zachary Zhou zacharyxue@example.com")
SESSION = requests.Session()

TENCENT_QUOTE = "https://qt.gtimg.cn/q={symbol}"
TENCENT_KLINE = ("https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
                 "?param={symbol},day,,,{count},qfq")
EASTMONEY_FIN = ("https://datacenter-web.eastmoney.com/api/data/v1/get"
                 "?reportName=RPT_LICO_FN_CPD&columns=SECURITY_CODE,SECURITY_NAME_ABBR"
                 "&filter=(SECURITY_CODE=\"{code}\")")
SEC_SUBMISSIONS = "https://data.sec.gov/submissions/CIK{cik}.json"
SEC_COMPANYFACTS = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"

@dataclass
class Quote:
    symbol: str          # 规范代码 e.g. sh600519 / hk00700 / usAAPL
    name: str
    price: float
    change_pct: float
    prev_close: float
    open: float
    high: float
    low: float
    volume: float
    ts: str
    # 估值字段(仅 A/港股有意义, 美股常为空): PE/PB/总市值/换手率
    pe: float | None = None
    pb: float | None = None
    mktcap: float | None = None   # 总市值(亿)
    turnover: float | None = None  # 换手率%

def _req(url, headers=None, timeout=10):
    r = SESSION.get(url, headers=headers or {}, timeout=timeout)
    r.raise_for_status()
    return r

# ============ 腾讯行情 ============
def _parse_tencent_quote(symbol, text):
    """腾讯 qt.gtimg.cn 返回 v_symbol="..."，字段用 ~ 分隔。"""
    try:
        body = text.split('="', 1)[1].rsplit('"', 1)[0]
        f = body.split("~")
        # 字段索引: 0代码 1名称 2现价(a股:3) ... 腾讯不同市场字段位不同，用名称+关键位
        # A/港/美股通用: f[1]=名称, f[3]=当前价, [4]=昨收, [5]=今开
        idx = len(f)
        # 统一用相对靠前的稳定位
        name = f[1]
        price = float(f[3]) if len(f) > 3 and f[3] else 0.0
        prev_close = float(f[4]) if len(f) > 4 and f[4] else 0.0
        open_p = float(f[5]) if len(f) > 5 and f[5] else 0.0
        # 涨跌幅: A股在字段[32], 港股[32], 美股[31] — 用价格算更稳
        change_pct = 0.0
        if prev_close:
            change_pct = (price - prev_close) / prev_close * 100
        # 高低/量: 随市场变位，尽力取
        def _f(i, default=0.0):
            try:
                return float(f[i]) if i < len(f) and f[i] else default
            except (ValueError, TypeError):
                return default
        # 取 ts（含日期那一位）
        ts = next((x for x in f if "/" in x and ":" in x), "")
        # 估值字段：腾讯 A股固定位 ≈ [39]PE [45]总市值(亿) [46]PB [38]换手率%
        # 容错：某位越界/空/非法 → None，不因单个字段失败拖垮整条解析
        def _fully(i):
            try:
                return float(f[i]) if i < len(f) and f[i] else None
            except (ValueError, TypeError):
                return None
        return Quote(symbol=symbol, name=name, price=price, change_pct=round(change_pct, 2),
                     prev_close=prev_close, open=open_p, high=_f(33), low=_f(34),
                     volume=_f(6), ts=ts, pe=_fully(39), pb=_fully(46),
                     mktcap=_fully(45), turnover=_fully(38))
    except Exception as e:
        raise ValueError(f"腾讯行情解析失败 {symbol}: {e}")

def cn_stock_quote(symbol):
    """symbol: sh600519 / hk00700 / usAAPL。返回 dict(可JSON化)。"""
    r = _req(TENCENT_QUOTE.format(symbol=symbol),
             headers={"Referer": "https://gu.qq.com/"})
    r.encoding = "gbk"
    q = _parse_tencent_quote(symbol, r.text)
    return q.__dict__

def cn_stock_kline(symbol, count=120):
    """前复权日K。symbol 同上。返回 [{date, open, close, high, low, volume}...]"""
    r = _req(TENCENT_KLINE.format(symbol=symbol, count=count))
    data = r.json()
    node = data.get("data", {}).get(symbol, {})
    # qfqday 或 day
    klines = node.get("qfqday") or node.get("day") or []
    out = []
    for row in klines:
        out.append({
            "date": row[0], "open": float(row[1]), "close": float(row[2]),
            "high": float(row[3]), "low": float(row[4]), "volume": float(row[5]),
        })
    return out

# ============ 东财财报 ============
def cn_financial(code):
    """code: 6位股票代码(600519)。返回财务摘要 dict（东财 datacenter，免token）。"""
    url = EASTMONEY_FIN.format(code=code)
    r = _req(url)
    j = r.json()
    data = j.get("result", {}).get("data", [])
    if not data:
        return {"code": code, "ok": False, "msg": "no data"}
    return {"code": code, "ok": True, "data": data[0]}


def cn_stock_dividend(secucode, page=12):
    """A股分红送配明细(每10股税前派息)。东财 RPT_SHAREBONUS_DET。
    secucode: 带后缀 e.g. '000333.SZ'。
    返回原始 rows(按 REPORT_DATE 倒序)。白电「年度+中期」双分红口径注释:
      股息率基准应取「最近年报(12-31期)派息」, 别用最近一期中报预案(见 dashboards-index 坑位)。
    """
    filt = urllib.parse.quote('(SECUCODE="' + secucode + '")')
    url = ("https://datacenter.eastmoney.com/securities/api/data/v1/get"
           "?reportName=RPT_SHAREBONUS_DET&columns=ALL&filter=" + filt
           + "&pageNumber=1&pageSize=" + str(page) + "&sortTypes=-1&sortColumns=REPORT_DATE")
    last = None
    for i in range(3):
        try:
            r = _req(url, timeout=35)
            j = r.json()
            return j.get("result", {}).get("data", [])
        except Exception as e:
            last = e
            time.sleep(1.2)
    raise last


def cn_financial_series(secucode, report_name="RPT_F10_FINANCE_MAINFINADATA", page=40):
    """东财完整财务序列(多报告期)，供看板做年度趋势/降本拆解。

    secucode: 带后缀 e.g. '600079.SH'。report_name 常用:
      - RPT_F10_FINANCE_MAINFINADATA  主财务(含 INTEREST_DEBT_RATIO 有息负债率)
      - RPT_F10_FINANCE_GINCOME       利润表(费用拆解: 营业成本/销售/管理/研发/财务费用)
    返回该接口原始 rows 列表(按 REPORT_DATE 倒序, 含 REPORT_DATE_NAME 报告期名)。领域逻辑(滤年报/归因)留各看板。
    """
    filt = urllib.parse.quote(f'(SECUCODE="{secucode}")')
    url = ("https://datacenter.eastmoney.com/securities/api/data/v1/get"
           f"?reportName={report_name}&columns=ALL&filter={filt}"
           f"&pageNumber=1&pageSize={page}&sortTypes=-1&sortColumns=REPORT_DATE")
    last = None
    for i in range(3):
        try:
            r = _req(url, timeout=35)
            j = r.json()
            rows = j.get("result", {}).get("data", [])
            return rows
        except Exception as e:
            last = e
            time.sleep(1.2)
    raise last

# ============ SEC EDGAR 美股财报 ============
def _pad_cik(cik):
    """SEC URL 需要 10 位带前导零，如 0000320193。"""
    return str(int(cik)).zfill(10)

def sec_companyfacts(cik, limit_rows=None):
    """cik: 数字或带前导零字符串(0000320193)。返回公司facts。必须带UA。"""
    r = _req(SEC_COMPANYFACTS.format(cik=_pad_cik(cik)), headers={"User-Agent": UA}, timeout=25)
    return r.json()

def sec_submissions(cik):
    """cik 同上。返回最新 filings 概览。"""
    r = _req(SEC_SUBMISSIONS.format(cik=_pad_cik(cik)), headers={"User-Agent": UA}, timeout=25)
    return r.json()

def sec_latest_revenue(cik):
    """从 companyfacts 提取最近一期收入。注意：上市公司的收入 metric 名会随准则变更，
    如 Apple 2018 起 `Revenues` 停止更新，新版在 `RevenueFromContractWithCustomerExcludingAssessedTax`。
    因此对多个候选 metric，取「end 日期最新」的一条，避免拿到过期数据（正确性>及时性）。"""
    cf = sec_companyfacts(cik)
    facts = cf.get("facts", {})
    gaap = facts.get("us-gaap", {})
    candidates = [
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "Revenue", "Revenues", "SalesRevenueNet", "SalesRevenueServicesGross",
        "SalesRevenueGoodsGross",
    ]
    best = None
    for key in candidates:
        if key not in gaap:
            continue
        units = gaap[key].get("units", {})
        for unit, series in units.items():
            if not isinstance(series, list) or not series:
                continue
            # 只取带 end 的报告值，按 end 排序
            dated = [x for x in series if x.get("end")]
            if not dated:
                continue
            last = max(dated, key=lambda x: str(x.get("end") or ""))
            end = str(last.get("end") or "")
            if best is None or end > best["end"]:
                best = {"metric": key, "end": end, "val": last.get("val"),
                        "unit": unit, "form": last.get("form")}
    return best or {"ok": False, "msg": "no revenue metric found"}


# ============ 中国水泥网（行业价格/成本指数，免费公开源） ============
def _cement_get(path):
    """ccement 接口：短超时(14s)+重试3次(实测偶发单次丢包, 重试即恢复)。返回 Data dict。"""
    url = "https://index.ccement.com/index/" + path
    hdr = {"User-Agent": "Mozilla/5.0", "Referer": "https://index.ccement.com/"}
    last = None
    for i in range(3):
        try:
            r = SESSION.get(url, headers=hdr, timeout=14)
            r.raise_for_status()
            return r.json().get("Data", {})
        except Exception as e:
            last = e
            time.sleep(0.8)
    raise last

def _series_stats(dates, vals):
    import datetime as dt
    pairs = sorted(zip(dates, vals), key=lambda t: t[0])
    d = [p[0] for p in pairs]; v = [float(p[1]) for p in pairs]
    if not d: return {"ok": False}
    hi = max(v); lo = min(v); latest = v[-1]; ldate = d[-1]
    tgt = str(dt.date.fromisoformat(d[-1]) - dt.timedelta(days=365))
    idx = next((i for i, x in enumerate(d) if x >= tgt), 0)
    yoy = (latest - v[idx]) / v[idx] * 100 if v[idx] else None
    step = max(1, len(d) // 200)
    return {"ok": True, "latest": round(latest, 2), "latest_date": ldate,
            "yoy_1y": round(yoy, 1) if yoy is not None else None,
            "hi": round(hi, 2), "hi_date": d[v.index(hi)], "lo": round(lo, 2), "lo_date": d[v.index(lo)],
            "series": [{"d": d[i], "v": v[i]} for i in range(0, len(d), step)]}

def cn_cement_index(index_type):
    """中国水泥网价格/成本指数。index_type: po425/cempi/coal/clinker/concrete。
    返回 {ok, latest, latest_date, yoy_1y, hi, lo, series:[{d,v}...]}。"""
    if index_type == "cempi":
        sub = _cement_get("priceindex/getPriceIndex").get("cement", {})
        return _series_stats(sub.get("dynamicIndexDate", []), sub.get("dynamicIndexAll", []))
    if index_type == "coal":
        sub = _cement_get("priceindex/getPriceIndex").get("coal_price", {})
        return _series_stats(sub.get("dynamicIndexDate", []), sub.get("dynamicIndexAll", []))
    paths = {"po425": "priceindex/po425zsline", "clinker": "clinker/ClinkerPrice",
             "concrete": "concrete/ConcretePrice"}
    if index_type not in paths:
        raise ValueError(f"未知 ccement index_type: {index_type}")
    d = _cement_get(paths[index_type])
    return _series_stats(d.get("dynamicIndexDate", []), d.get("dynamicIndex", []))

def cn_cement_spread():
    """水泥-熟料价差（近一周均值，供给/盈利弹性代理）。"""
    po = cn_cement_index("po425"); cl = cn_cement_index("clinker")
    if not (po.get("ok") and cl.get("ok")): return {"ok": False, "note": "po425/clinker 缺失"}
    cod = {x["d"]: x["v"] for x in po["series"]}; cld = {x["d"]: x["v"] for x in cl["series"]}
    common = [cod[k] - cld[k] for k in cod if k in cld]
    if not common: return {"ok": False, "note": "无重叠日期"}
    recent = common[-7:] if len(common) >= 7 else common
    return {"ok": True, "latest": round(sum(recent) / len(recent), 1), "latest_date": "近一周均值",
            "series_k": len(common)}


# ============ 指数估值（ETF 看板用：中证官网 PE + 天天基金分位） ============
def cn_csindex_pe(index_code, years=5):
    """中证官网历史PE(peg 字段) → 5年分位。index_code: 000922/H30269/931719 等。
    返回 {ok, pe_pct_5y, pe_ttm, n}。非中证系指数(国证/恒生)无 peg → ok=False。"""
    import datetime as dt
    end = dt.datetime.now().strftime("%Y%m%d")
    start = str(int(end[:4]) - years) + end[4:]
    url = (f"https://www.csindex.com.cn/csindex-home/perf/index-perf?indexCode={index_code}"
           f"&startDate={start}&endDate={end}&frequency=daily")
    try:
        r = _req(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
        data = r.json().get("data") or []
        pe = [x.get("peg") for x in data if isinstance(x, dict) and x.get("peg") is not None]
    except Exception as e:
        return {"ok": False, "note": "中证官网异常: " + str(e)[:50]}
    if not pe:
        return {"ok": False, "note": "无peg(非中证系指数)"}
    cur = pe[-1]
    pct = sum(1 for x in pe if x <= cur) / len(pe) * 100
    return {"ok": True, "pe_pct_5y": round(pct, 1), "pe_ttm": round(cur, 2), "n": len(pe)}

def cn_ttfund_index(index_id):
    """天天基金 TTFUND_INDEX_INFO → PE/PB 10年分位 + ROE。走本地 ttskill CLI(需已login)。
    返回 {ok, pe_ttm, pe_pct_10y, pb_pct_10y, roe}。"""
    import subprocess, os
    api = "/root/.local/bin"
    try:
        r = subprocess.run(["ttskill", "invoke", "TTFUND_INDEX_INFO", "--action", "query",
                            "--body", json.dumps({"index_id": index_id}, ensure_ascii=False)],
            capture_output=True, text=True, timeout=60,
            env={"PATH": f"{api}:/usr/local/bin:/usr/bin:/bin"})
        d = json.loads(r.stdout)["data"]["raw_result"]["body"]["data"]
    except Exception as e:
        return {"ok": False, "note": "ttskill解析失败: " + str(e)[:60]}
    v = d.get("valuation") or {}
    return {"ok": True, "pe_ttm": v.get("pe_ttm"), "pe_pct_10y": v.get("pe_percentile_10y"),
            "pb_pct_10y": v.get("pb_percentile_10y"), "roe": v.get("roe")}
