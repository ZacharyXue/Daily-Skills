# -*- coding: utf-8 -*-
"""
data-source-router.adapters.reits — 公募 REITs 数据（2026-09 实测下沉）
====================================================================
来源：
  1. 腾讯行情 qt.gtimg.cn —— REITs 全量清单（枚举 sh508000-508999 / sz180000-180999 批量探测）
  2. 东财基金公告 api.fund.eastmoney.com/f10/JJGG —— 定期报告清单（季报/中报/年报）
  3. 东财 PDF 库 pdf.dfcfw.com/pdf/H2_{公告ID}_1.pdf —— 定期报告全文（pymupdf 解析）

接口（kind）：
  cn_reits_list()                      → [{code,name,price,mktcap,date}]
  cn_reits_report_list(code="508068")  → [{date,id,title,rtype}]
  cn_reits_report_data(report_id="AN...") → 解析后的指标 dict

⚠️ PDF 解析依赖 pymupdf：只在 `/root/hermes-venv/bin/python` 下可用（系统 python3 无）。lazy import。
⚠️ 已下载 PDF 落盘 ~/.hermes/dsr-reits/pdf/，解析结果缓存 ~/.hermes/dsr-reits/parsed.json
   （避免重复下载/解析；DSR 的 sqlite 缓存另有一层 TTL）。
"""
import os
import re
import json
import time
import random
import urllib.request

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"}
HOME = os.path.expanduser("~/.hermes/dsr-reits")
PDF_DIR = os.path.join(HOME, "pdf")
PARSED = os.path.join(HOME, "parsed.json")
PROBE_CACHE = os.path.join(HOME, "probe.json")
os.makedirs(PDF_DIR, exist_ok=True)

NUM = r'([\d,]+\.?\d*)'
PROJ = r'([\u4e00-\u9fa5A-Za-z0-9]{2,20}(?:项目|公寓|家园|苑|大厦|中心|社区))'
DAYS = {"Q1": 90, "Q2": 91, "Q3": 92, "Q4": 92, "H1": 181, "FY": 365}


def _get(url, headers=None, timeout=25, tries=3, binary=False):
    h = dict(UA)
    if headers:
        h.update(headers)
    err = ""
    for _ in range(tries):
        try:
            r = urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=timeout)
            return r.read() if binary else r.read().decode("utf-8", "ignore")
        except Exception as e:
            err = str(e)
            time.sleep(1.5)
    raise IOError("fetch failed: %s (%s)" % (url, err))


# ---------------- 1. 全量 REITs 清单 ----------------
def list_reits(force=False):
    """枚举 sh508xxx / sz180xxx 批量探测出全市场 REITs（约 20 次请求，首次慢）"""
    if not force and os.path.exists(PROBE_CACHE) and time.time() - os.path.getmtime(PROBE_CACHE) < 86400:
        return json.load(open(PROBE_CACHE))
    codes = ["sh508%03d" % i for i in range(1000)] + ["sz180%03d" % i for i in range(1000)]
    out = []
    for i in range(0, len(codes), 100):
        chunk = codes[i:i + 100]
        try:
            raw = _get("https://qt.gtimg.cn/q=" + ",".join(chunk), timeout=20).encode("latin1").decode("gbk", "ignore")
        except Exception:
            continue
        for line in raw.split(";"):
            line = line.strip()
            m = re.match(r'v_(\w+)="(.*)"', line)
            if not m:
                continue
            code, body = m.group(1), m.group(2)
            f = body.split("~")
            if len(f) < 50 or not f[1].strip():
                continue
            out.append({"code": code, "name": f[1], "price": f[3], "mktcap": f[45] if len(f) > 45 else "",
                        "date": f[30]})
        time.sleep(0.3)
    json.dump(out, open(PROBE_CACHE, "w"), ensure_ascii=False)
    return out


# ---------------- 2. 定期报告清单 ----------------
def report_list(code, pages=3):
    c6 = code[2:] if code[:2] in ("sh", "sz") else code
    recs = []
    for page in (1, 2, 3)[:pages]:
        t = _get("https://api.fund.eastmoney.com/f10/JJGG?callback=cb&fundcode=%s&pageIndex=%d"
                 "&pageSize=50&type=0&_=1" % (c6, page), headers={"Referer": "https://fund.eastmoney.com/"})
        try:
            j = json.loads(t[t.find("(") + 1:t.rfind(")")])
        except Exception:
            break
        data = j.get("Data") or []
        if not data:
            break
        for it in data:
            ti = it["TITLE"]
            if any(k in ti for k in ["季度报告", "中期报告", "年度报告"]):
                rtype = ("H1" if "中期报告" in ti else "FY" if "年度报告" in ti
                         else "Q1" if ("第1季度" in ti or "第一季度" in ti)
                         else "Q3" if ("第3季度" in ti or "第三季度" in ti)
                         else "Q2" if "第2季度" in ti else "Q4" if "第4季度" in ti else "?")
                recs.append({"date": it["PUBLISHDATEDesc"], "id": it["ID"], "title": ti[:70], "rtype": rtype})
        time.sleep(random.uniform(0.4, 0.9))
    recs.sort(key=lambda x: (x["date"], x["rtype"]))
    return recs


# ---------------- 3. 报告解析 ----------------
def _clean(s):
    return re.sub(r"\s+", "", s)


def _f(v):
    try:
        return float(str(v).replace(",", ""))
    except Exception:
        return None


def _dist_block(c, pers=("本期", "2026年", "2025年", "2024年", "2023年", "2022年")):
    out = {}
    anchors = [(m.start(), "paid" if "实际" in m.group(0) else "dist")
               for m in re.finditer(r"本报告期[^。]{0,12}?(?:可供|实际)分配金额", c)]
    for pos, kind in (anchors[:1] + [a for a in anchors[1:] if a[0] - anchors[0][0] < 900]):
        s = c[pos:pos + 1400]
        tgt = out.setdefault(kind, {})
        for per in pers:
            mm = (re.search(per + r"([\d,]+\.\d{2})(\d+\.\d{3,6})", s)
                  or re.search(per + r"([\d,]+)(\d\.\d{3,6})", s))
            if mm and per not in tgt:
                tgt[per] = [_f(mm.group(1)), _f(mm.group(2))]
    acc = re.search(r"本年累计([\d,]+\.\d{2})(\d+\.\d{3,6})", c)
    if acc:
        out.setdefault("dist", {})["本年累计"] = [_f(acc.group(1)), _f(acc.group(2))]
    return out


def parse_report_text(txt):
    """解析定期报告全文（兼容 2022-2026 三代披露格式）"""
    import pymupdf  # noqa: F401  (依赖检查)
    c = _clean(txt)
    r = {}
    m = (re.search(r"报告期（(\d{4})年(\d{1,2})月(\d{1,2})日[-—至]{1,2}(\d{4})年(\d{1,2})月(\d{1,2})日）", c)
         or re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日[-—至]{1,2}(\d{4})年(\d{1,2})月(\d{1,2})日", c))
    if m:
        g = m.groups()
        r["period_beg"] = "%s-%02d-%02d" % (g[0], int(g[1]), int(g[2]))
        r["period_end"] = "%s-%02d-%02d" % (g[3], int(g[4]), int(g[5]))
    else:
        r["period_beg"] = r["period_end"] = None
    mm = re.search(r"期末(?:不动产)?基金份额净值" + NUM, c)
    r["nav"] = _f(mm.group(1)) if mm else None
    for k, pat in [("dy_period", r"本期现金流分派率(?:（%）)?(\d+\.\d{1,2})"),
                   ("dy_annual", r"年化现金流分派率(?:（%）)?(\d+\.\d{1,2})"),
                   ("revenue", r"本期收入" + NUM),
                   ("net_profit", r"本期净利润" + NUM),
                   ("ocf", r"本期经营活动产生的现金流量净额" + NUM),
                   ("ebitda", r"本期息税折旧及摊销前利润" + NUM),
                   ("net_asset", r"期末(?:不动产)?基金净资产" + NUM),
                   ("shares", r"基金份额总额" + NUM + "份")]:
        mm = re.search(pat, c)
        r[k] = _f(mm.group(1)) if mm else None
    if r["dy_annual"] is None:
        mm = re.search(r"年化现金流分派率(\d+\.\d{1,2})%", c)
        r["dy_annual"] = _f(mm.group(1)) if mm else None
    blk = _dist_block(c)
    r["distributable"] = blk.get("dist", {})
    r["paid"] = blk.get("paid", {})
    cands = [_f(x) for x in re.findall(r"本期可供分配金额" + NUM, c)]
    r["dist_now"] = cands[0] if cands else None

    projs = {}
    for mm in re.finditer(r"(?:不动产|资产)项目名称：", c):
        seg = c[mm.start():mm.start() + 2200]
        if "出租率" not in seg:
            continue
        nm = re.match(r"(?:不动产|资产)项目名称：([^\n，。、]{2,26})", seg)
        name = nm.group(1) if nm else seg[9:24]
        if name in projs:
            continue
        o = re.search(r"出租率[\s\S]{0,220}?%+(\d{1,3}\.\d{1,2})", seg)
        col = re.search(r"收缴率[\s\S]{0,220}?%+(\d{1,3}\.\d{1,2})", seg)
        rent = re.search(r"租金单价[^\d]{0,120}?" + NUM, seg)
        area = re.search(r"可出租面积[^\d]{0,120}?平米" + NUM, seg)
        lease = re.search(r"剩余租期[\s\S]{0,400}?年(\d+\.\d{1,2})", seg)
        projs[name] = {"occ": _f(o.group(1)) if o else None, "collect": _f(col.group(1)) if col else None,
                       "rent": _f(rent.group(1)) if rent else None, "area": _f(area.group(1)) if area else None,
                       "lease": _f(lease.group(1)) if lease else None}
    if not any(p["occ"] for p in projs.values()):
        for mm in re.finditer(PROJ, c):
            name = mm.group(1)
            if name in projs:
                continue
            seg = c[mm.start():mm.start() + 500]
            o = re.search(r"出租率为?([\d\.]+)%", seg)
            col = re.search(r"收缴率为?([\d\.]+)%", seg)
            if o or col:
                projs[name] = {"occ": _f(o.group(1)) if o else None, "collect": _f(col.group(1)) if col else None,
                               "rent": None, "area": None, "lease": None}
    r["projects"] = projs
    vals = [p["occ"] for p in projs.values() if p["occ"]]
    src = "project"
    if not vals:
        g = (re.findall(r"报告期末出租率[\s\S]{0,220}?%+(\d{1,3}\.\d{1,2})", c)
             or re.findall(r"出租率[\s\S]{0,220}?%+(\d{1,3}\.\d{1,2})", c))
        if g:
            vals = [float(g[0])]
            src = "report_level"
    cv = [p["collect"] for p in projs.values() if p["collect"]] or \
         [float(x) for x in re.findall(r"收缴率[\s\S]{0,220}?%+(\d{1,3}\.\d{1,2})", c)][:1]
    lv = [p["lease"] for p in projs.values() if p["lease"]] or \
         [float(x) for x in re.findall(r"剩余租期[\s\S]{0,400}?年(\d+\.\d{1,2})", c)][:1]
    r["occ_avg"] = round(sum(vals) / len(vals), 2) if vals else None
    r["occ_src"] = src if vals else None
    r["collect_avg"] = round(sum(cv) / len(cv), 2) if cv else None
    r["lease_avg"] = round(sum(lv) / len(lv), 2) if lv else None
    return r


def report_data(report_id):
    import pymupdf
    cache = json.load(open(PARSED)) if os.path.exists(PARSED) else {}
    if report_id in cache:
        return cache[report_id]
    path = os.path.join(PDF_DIR, "%s.pdf" % report_id)
    if not os.path.exists(path) or os.path.getsize(path) < 1000:
        blob = _get("http://pdf.dfcfw.com/pdf/H2_%s_1.pdf" % report_id, timeout=120, binary=True)
        if blob[:4] != b"%PDF":
            raise IOError("not a pdf: %s" % report_id)
        open(path, "wb").write(blob)
        time.sleep(random.uniform(0.4, 0.9))
    doc = pymupdf.open(path)
    txt = "\n".join(p.get_text() for p in doc)
    doc.close()
    res = parse_report_text(txt)
    cache[report_id] = res
    json.dump(cache, open(PARSED, "w"), ensure_ascii=False)
    return res


# ---------------- 4. 分红记录（天天基金 F10 分红送配页） ----------------
def dividend(code):
    """code: sh508068 / 508068。返回已宣告分派记录（每份派现金，按权益登记日）"""
    c6 = code[2:] if code[:2] in ("sh", "sz") else code
    t = _get("https://fundf10.eastmoney.com/fhsp_%s.html" % c6,
             headers={"Referer": "https://fundf10.eastmoney.com/"})
    divs = []
    for m in re.finditer(r"<tr><td>(\d{4})年</td><td>([\d\-]+)</td><td>([\d\-]+)</td>"
                         r"<td>每10份派现金([\d\.]+)元</td><td>([\d\-]+)</td></tr>", t):
        divs.append({"year": m.group(1), "reg": m.group(2), "ex": m.group(3),
                     "per_unit": float(m.group(4)) / 10.0, "pay": m.group(5)})
    ml = re.search(r"累计分红([\d\.]+)元/份", t)
    return {"code": c6, "divs": divs, "ytd_cum": float(ml.group(1)) if ml else None}
