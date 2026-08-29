# -*- coding: utf-8 -*-
"""
海螺财报(中报+年报)经营/分红数据提取 → cache/report_helluo.json
- 半年报：吨售价/吨成本/吨毛利/销量(收入-成本口径，与披露毛利率核对)
- 年报：全年每股派息 → 股息率(算, 用现价)
数据源：东方财富公告PDF(公开)。
用法：python3 scripts/extract_report.py  (每次新财报跑一次)
"""
import json, os, re, urllib.request, datetime

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(BASE, "cache")
OUT = os.path.join(CACHE, "report_helluo.json")
STOCK = "600585"
UA = {"User-Agent": "Mozilla/5.0", "Referer": "https://data.eastmoney.com/"}

def _get(url, headers=UA, timeout=25):
    req = urllib.request.Request(url, headers=headers)
    return urllib.request.urlopen(req, timeout=timeout).read()

def list_ann(kind="半年度报告"):
    url = ("https://np-anotice-stock.eastmoney.com/api/security/ann?sr=-1&page_size=40&page_index=1"
           f"&ann_type=A&client_source=web&stock_list={STOCK}&f_node=1&s_node=1")
    d = json.loads(_get(url).decode())
    for a in d.get("data", {}).get("list", []):
        t = a.get("title", "")
        if kind == "半年度报告":
            hit = "半年度报告" in t
        else:
            hit = ("年度报告" in t) and ("半年度" not in t)
        if hit and "摘要" not in t:
            code = a.get("art_code")
            return {"title": t, "pdf": f"https://pdf.dfcfw.com/pdf/H2_{code}_1.pdf",
                    "date": a.get("notice_date", "")}
    return None

def extract_text(pdf_bytes, path="/tmp/_h.pdf"):
    open(path, "wb").write(pdf_bytes)
    import pymupdf
    doc = pymupdf.open(path)
    return "\n".join(f"\n=== PAGE {i+1} ===\n{p.get_text()}" for i, p in enumerate(doc))

def parse_operation(txt):
    """半年报：自产品销量/收入/成本 → 吨售价/吨成本/吨毛利"""
    m_sales = re.search(r"自产品销量为\s*([\d.]+)\s*亿吨", txt)
    m_rev = re.search(r"自产品销售收入\s*([\d.]+)\s*亿元", txt)
    m_cost = re.search(r"自产品销售成本\s*([\d.]+)\s*亿元", txt)
    m_gm = re.search(r"自产品综合毛利率为\s*([\d.]+)%", txt)
    m_sales_yoy = re.search(r"自产品销量为[\d.]+\s*亿吨.*?同比(下降|上升)([\d.]+)%", txt, re.S)
    if not (m_sales and m_rev and m_cost):
        return {}
    sales_t = float(m_sales.group(1)) * 1e8
    rev = float(m_rev.group(1)) * 1e8
    cost = float(m_cost.group(1)) * 1e8
    tp = rev / sales_t; tc = cost / sales_t; tgm = tp - tc
    return {"sales_yt": round(sales_t/1e8, 2),
            "sales_yoy": -float(m_sales_yoy.group(2)) if m_sales_yoy and m_sales_yoy.group(1)=="下降" else (float(m_sales_yoy.group(2)) if m_sales_yoy else None),
            "ton_price": round(tp, 2), "ton_cost": round(tc, 2), "ton_gross_margin": round(tgm, 2),
            "verified": f"毛利率核对 {(tgm/tp*100):.2f}% vs 披露 {m_gm.group(1) if m_gm else '?'}%"}

def parse_dividend(txt):
    """年报：全年每股派息(元)"""
    m = re.search(r"全年每股派发现金红利\s*([\d.]+)\s*元", txt)
    if m: return float(m.group(1))
    m2 = re.search(r"每股派发现金红利\s*([\d.]+)\s*元", txt)  # 末期
    return float(m2.group(1)) if m2 else None

def tencent_price(code="sh600585"):
    import re
    raw = _get(f"https://qt.gtimg.cn/q={code}", headers={"User-Agent": "Mozilla/5.0"}).decode("gbk", "ignore")
    m = re.search(r'="(.*)"', raw); f = m.group(1).split("~")
    return float(f[3]) if len(f) > 3 and f[3] else None

def main():
    res = {}
    # 半年报 → 经营数据
    op = list_ann("半年度报告")
    if op:
        txt = extract_text(_get(op["pdf"]))
        res.update(parse_operation(txt))
        res["op_report"] = f"{op['title']} ({op['date']})"
        res["op_pdf"] = op["pdf"]
    # 年报 → 分红
    ar = list_ann("年度报告")
    if ar:
        atxt = extract_text(_get(ar["pdf"]), "/tmp/_ar.pdf")
        dps = parse_dividend(atxt)
        price = tencent_price()
        res["dps"] = dps
        res["price"] = price
        res["dividend_yield"] = round(dps/price*100, 2) if (dps and price) else None
        res["ar_report"] = f"{ar['title']} ({ar['date']})"
    res["fetched_at"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    os.makedirs(CACHE, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    print("saved", OUT)
    print(json.dumps(res, ensure_ascii=False, indent=1))

if __name__ == "__main__":
    main()
