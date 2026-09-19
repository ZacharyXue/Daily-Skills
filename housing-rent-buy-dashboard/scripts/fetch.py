#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
housing-rent-buy-dashboard 数据抓取（DSR 版）
=============================================
统一走 data-source-router（唯一取数入口）：
  cn_housing_city(city)    → 城市房价/租金/售租比/区县（创房价手机站）
  cn_housing_trend(city)   → 新房月均价趋势 近6月（房天下）
  cn_lpr()                 → LPR 历史 2019-08 至今（中国银行）

本脚本只做组装 + 落盘（data/housing_{YYYYMMDD}.json + latest.json），
抓取/缓存/重试/低频规范全部在 DSR（adapters/housing.py，间隔>=2s）。
默认 force=True 强制回源（手动看板更新要最新）；
--cache 用 DSR 缓存（TTL 1天，调试/快速预览用）。

用法：python3 scripts/fetch.py [--cache]
"""
import argparse, json, os, sys
from datetime import datetime

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(BASE, "data")
sys.path.insert(0, "/root/zach-skills/data-source-router")
import data_router as DSR  # noqa: E402

CITIES = {"sh": "上海", "hz": "杭州"}
# 如需恢复范围，加回：bj北京 gz广州 sz深圳 su苏州（创房价 su / 房天下 suzhou）——代码自动适配


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", action="store_true", help="用 DSR 缓存而非强制回源")
    args = ap.parse_args()
    force = not args.cache
    os.makedirs(DATA, exist_ok=True)

    all_data = {"fetched_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "cities": {}, "ftx_trend": {}}
    print(f"[1/3] 创房价 {len(CITIES)} 城房价/租金 (DSR, force={force})...")
    for code in CITIES:
        d, src, meta, tier = DSR.get("cn_housing_city", city=code, force=force)
        if not isinstance(d, dict) or "price" not in d or not d["price"].get("meta", {}).get("avg"):
            raise RuntimeError(f"{code} cn_housing_city 获取失败: {meta}")
        all_data["cities"][code] = d
        print(f"  {code}: 房价 {d['price']['meta'].get('avg')} 租金 {d['rent']['meta'].get('avg')} "
              f"分区 {len(d['price']['districts'])}/{len(d['rent']['districts'])}")

    print("[2/3] 房天下新房趋势...")
    for code in CITIES:
        d, src, meta, tier = DSR.get("cn_housing_trend", city=code, force=force)
        if not isinstance(d, list) or len(d) < 2:
            raise RuntimeError(f"{code} cn_housing_trend 获取失败: {meta}")
        all_data["ftx_trend"][code] = d
        print(f"  {code}: {len(d)} points")

    print("[3/3] LPR 历史...")
    lpr, src, meta, tier = DSR.get("cn_lpr", force=force)
    if not isinstance(lpr, list) or len(lpr) < 20:
        raise RuntimeError(f"cn_lpr 获取失败: {meta}")
    all_data["lpr"] = lpr
    print(f"  {len(lpr)} 条 ({lpr[0]['date']} → {lpr[-1]['date']})")

    stamp = datetime.now().strftime("%Y%m%d")
    with open(os.path.join(DATA, f"housing_{stamp}.json"), "w", encoding="utf-8") as f:
        json.dump(all_data, f, ensure_ascii=False, indent=1)
    with open(os.path.join(DATA, "latest.json"), "w", encoding="utf-8") as f:
        json.dump(all_data, f, ensure_ascii=False, indent=1)
    print(f"✅ 保存 data/housing_{stamp}.json + latest.json")


if __name__ == "__main__":
    main()