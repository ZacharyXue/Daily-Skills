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
        return Quote(symbol=symbol, name=name, price=price, change_pct=round(change_pct, 2),
                     prev_close=prev_close, open=open_p, high=_f(33), low=_f(34),
                     volume=_f(6), ts=ts)
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
