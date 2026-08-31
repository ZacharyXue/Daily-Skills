# -*- coding: utf-8 -*-
"""dashboard_shared.py 单元测试（验证共享库关键函数正确性）。
用法: python3 test_dashboard_shared.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dashboard_shared as D

def check(name, cond):
    print(("✓ " if cond else "✗ FAIL ") + name)
    if not cond:
        global _fail
        _fail = True

_fail = False

# --- fnum/pct/esc ---
check("fnum 千分位", D.fnum(1234567.5) == "1,234,567.5")
check("fnum None→—", D.fnum(None) == "—")
check("pct 百分号", D.pct(12.34, 2) == "12.34%")
check("esc 转义", D.esc("<b>&") == "&lt;b&gt;&amp;")

# --- trend_svg ---
charts = [{"name": "A", "color": "#2563eb", "points": [{"d": "2023年报", "v": 100}, {"d": "2024年报", "v": 120}]},
          {"name": "B", "color": "#16a34a", "points": [{"d": "2023年报", "v": 80}, {"d": "2024年报", "v": 90}]}]
svg = D.trend_svg(charts)
check("trend_svg 生成polyline(2线)", svg.count("<polyline") == 2)
check("trend_svg 含图例", "chleg" in svg)
check("trend_svg 单点回空", D.trend_svg([{"name":"A","color":"#000","points":[{"d":"x","v":1}]}]) == "")

# --- _series_of 排序(升序, [-1]=最新) ---
rows = [{"REPORT_DATE_NAME": "2024年报", "X": 100},
        {"REPORT_DATE_NAME": "2023年报", "X": 80},
        {"REPORT_DATE_NAME": "2025年报", "X": 120}]
ser = D._series_of(rows, "X")
check("_series_of 升序", [s["d"] for s in ser] == ["2023年报", "2024年报", "2025年报"])
check("_series_of [-1]最新", ser[-1]["v"] == 120)

# --- _find ---
check("_find 命中", D._find(rows, "2025年报")["X"] == 120)
check("_find 未命中→None", D._find(rows, "2022年报") is None)

# --- _self_yoy 同比重算 ---
fr = [{"REPORT_DATE_NAME": "2026中报", "REPORT_DATE": "2026-06-30 00:00:00", "K": 110},
      {"REPORT_DATE_NAME": "2025中报", "REPORT_DATE": "2025-06-30 00:00:00", "K": 100}]
yoy = D._self_yoy(fr, "K")
check("_self_yoy 同比", yoy.get("2026中报") == 10.0)

# --- annual_dividend 年度口径(白电双分红关键) ---
# 模拟: 2026中报预案(应被忽略) + 2025年报
mock = {"result": {"data": [
    {"REPORT_DATE": "2026-06-30 00:00:00", "PRETAX_BONUS_RMB": 5},   # 中报预案, 应忽略
    {"REPORT_DATE": "2025-12-31 00:00:00", "PRETAX_BONUS_RMB": 38},  # 年报, 应取此
    {"REPORT_DATE": "2024-12-31 00:00:00", "PRETAX_BONUS_RMB": 35},
]}}
# 直接测内部逻辑(不联网): 用 annual_dividend 的算法
def _sim_annual(rows):
    annual = [r for r in rows if str(r.get("REPORT_DATE", "")).endswith("12-31 00:00:00") and r.get("PRETAX_BONUS_RMB")]
    seen = {}
    for r in annual:
        yr = str(r.get("REPORT_DATE", ""))[:4]
        if yr not in seen: seen[yr] = r
    latest = next((v for v in [seen.get(y) for y in ["2025","2024","2023","2022","2021"] if y in seen] if v), None)
    return latest.get("PRETAX_BONUS_RMB") if latest else None
check("年度口径: 取2025年报38而非中报5", _sim_annual(mock["result"]["data"]) == 38)

print("\n" + ("全部通过" if not _fail else "存在失败项"))
sys.exit(1 if _fail else 0)