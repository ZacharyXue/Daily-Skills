# -*- coding: utf-8 -*-
"""
data-source-router.adapters.housing — 房产数据（2026-09 实测下沉）
====================================================================
来源（全部网页源，维持「模拟人类低频」规范：请求间隔 >=2s 随机抖动）：

  1. 中国房价行情 **手机站** m.creprice.cn（桌面站 www 被验证码墙拦，手机站免验证码）
     - /city/{code}.html           城市住宅平均房价 + 区县房价排行 + 售租比
     - /city/{code}.html?type=lease 城市住宅平均租金 + 区县租金排行
     city code: bj/sh/gz/sz/hz/su（创房价苏州=su）
  2. 房天下查房价 fangjia.fang.com（新房月均价趋势，近6月窗口）
     - /fangjia/common/ajaxtrenddatanew/{code}?dataType=city&Class=defaultnew
     code: bj/sh/gz/sz/hz/suzhou（房天下苏州=suzhou，两源代码不同！）
  3. 中国银行 LPR 表（2019-08 至今 85 期）
     - bankofchina.com/fimarkets/lilv/fd32/201310/t20131031_2591219.html

接口（kind）：
  cn_housing_city(city="sh")    → {price:{meta,districts}, rent:{meta,districts}}
  cn_housing_trend(city="sh")   → [{ts_ms, price}, ...] 房天下新房月均价
  cn_lpr()                      → [{date, lpr_1y, lpr_5y}, ...]（从新到旧）
"""
import random
import re
import time
import json
import urllib.request

UA_M = "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15"
UA_D = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")

# 网页源低频规范（hard rule）：>=2s 随机抖动
MIN_INTERVAL = 2.0


def _sleep():
    time.sleep(MIN_INTERVAL + random.uniform(0, 2.0))


def _http_get(url, ua, referer=None, timeout=20, tries=3):
    headers = {"User-Agent": ua}
    if referer:
        headers["Referer"] = referer
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read().decode("utf-8", errors="ignore")
        except Exception as e:  # 免费源偶发丢包 ≠ 源坏，短超时报重试即恢复
            last = e
            time.sleep(2.0 * (i + 1))
    raise RuntimeError(f"获取失败 {url}: {last}")


# ---------------------------------------------------------------------------
# 创房价手机站
# ---------------------------------------------------------------------------
_CREPRICE_CODE = {"bj": "bj", "sh": "sh", "gz": "gz", "sz": "sz", "hz": "hz", "su": "su"}


def _parse_city_page(html):
    """城市页 → (meta, districts)。区县仅披露环比(无同比)。"""
    txt = re.sub(r"<[^>]+>", " ", html)
    txt = re.sub(r"\s+", " ", txt)
    meta = {}
    m = re.search(r"平均(?:房价|房租)\s*（([^）]*)）\s*([\d,.]+)\s*元/(?:㎡|月/㎡)\s*环比[：:]\s*([▲▼]?)([\d.]+)%", txt)
    if m:
        meta["period"] = m.group(1)
        meta["avg"] = float(m.group(2).replace(",", ""))
        meta["mom_dir"] = m.group(3)
        meta["mom"] = float(m.group(4))
    m = re.search(r"平均总价\s*([\d,.]+)\s*(?:万元|元/月)", txt)
    if m:
        meta["avg_total"] = float(m.group(1).replace(",", ""))
    m = re.search(r"售租比\s*([\d.]+)", txt)
    if m:
        meta["sale_rent_ratio"] = float(m.group(1))
    m = re.search(r"挂牌数量\s*([\d,]+)\s*套", txt)
    if m:
        meta["listing_count"] = int(m.group(1).replace(",", ""))
    districts = []
    for dm in re.finditer(r"(\d+)\s+([\u4e00-\u9fa5]+(?:区|县|市))\s+([\d,.]+)\s*([+-]?)([\d.]+)%", txt):
        districts.append({
            "rank": int(dm.group(1)),
            "name": dm.group(2),
            "avg": float(dm.group(3).replace(",", "")),
            "mom": (dm.group(4) or "") + dm.group(5),
        })
    return meta, districts


def cn_housing_city(city="sh"):
    """一城的 房价+租金+售租比+区县排行（创房价手机站，2 次请求）"""
    if city not in _CREPRICE_CODE:
        raise KeyError(f"不支持城市码 {city!r}，可选: {list(_CREPRICE_CODE)}")
    code = _CREPRICE_CODE[city]
    out = {}
    for kind, suffix in (("price", ""), ("rent", "?type=lease")):
        url = f"https://m.creprice.cn/city/{code}.html{suffix}"
        html = _http_get(url, UA_M)
        meta, districts = _parse_city_page(html)
        if not meta.get("avg"):
            raise RuntimeError(f"{city}/{kind} 解析失败(页面可能被风控): {url}")
        out[kind] = {"meta": meta, "districts": districts}
        _sleep()
    return out


# ---------------------------------------------------------------------------
# 房天下新房月均价趋势
# ---------------------------------------------------------------------------
_FTX_CODE = {"bj": "bj", "sh": "sh", "gz": "gz", "sz": "sz", "hz": "hz", "su": "suzhou"}


def cn_housing_trend(city="sh"):
    """新房月均价趋势（房天下，近6月窗口）→ [{ts, price}]"""
    if city not in _FTX_CODE:
        raise KeyError(f"不支持城市码 {city!r}，可选: {list(_FTX_CODE)}")
    code = _FTX_CODE[city]
    url = f"https://fangjia.fang.com/fangjia/common/ajaxtrenddatanew/{code}?dataType=city&Class=defaultnew"
    raw = _http_get(url, UA_D, referer=f"https://fangjia.fang.com/{code}/")
    try:
        pts = json.loads(raw)
    except Exception:
        raise RuntimeError(f"房天下趋势解析失败 {city}: {raw[:100]}")
    return [{"ts": p[0], "price": p[1]} for p in pts]


# ---------------------------------------------------------------------------
# LPR 历史
# ---------------------------------------------------------------------------
def cn_lpr():
    """LPR 历史（中国银行 HTML 表，2019-08 至今，从新到旧）"""
    url = "https://www.bankofchina.com/fimarkets/lilv/fd32/201310/t20131031_2591219.html"
    html = _http_get(url, UA_D)
    rows = re.findall(r"<td[^>]*>([^<]*)</td>", html)
    lpr = []
    for i in range(0, len(rows) - 2, 3):
        d, y1, y5 = rows[i].strip(), rows[i + 1].strip(), rows[i + 2].strip()
        if re.match(r"^\d{4}-\d{2}-\d{2}$", d) and "%" in y1:
            lpr.append({"date": d, "lpr_1y": y1, "lpr_5y": y5})
    if len(lpr) < 20:
        raise RuntimeError(f"LPR 解析异常, 仅 {len(lpr)} 条")
    return lpr