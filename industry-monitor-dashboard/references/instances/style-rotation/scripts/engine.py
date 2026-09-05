#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
engine.py — 成长/价值 配置比例引擎（v1）

目标：给「成长ETF(国证成长100/980080) vs 价值ETF(国证价值100/980081)」一个可落地、
可解释的配置权重偏移，不做二值切换。

依据（调研 + 广发《成长与价值风格轮动框架》 + 本机 2026-09 CAR-z 真回测）：
  1. 纯动量/CAR-z 回测无效（成长占优周期里反复下车，12% < 满仓成长28%）→ 动量只做极端预警，权重最低
  2. 配置比例由「基本面相对盈利 + 估值安全边际 + 行业拥挤度」联合决定，宏观作闸门
  3. 信号并聚（confluence）：≥2 个同向才允许明显偏移，单信号禁止触发大动 → 避免两头打脸
  4. mistiming > 错过：宁可慢半拍，别在信号不足以确认时砍掉当前风格
  5. 权重限幅 [40%, 70%]，保守—渐变，非 0/100 切换

输入 data（dict，见 fetch.py）：
  g, v = 成长/价值 指数指标对象，字段:
    roe, pe_ttm, pe_pct_10y, pb, top_industries[{industry,weight_pct}],
    return_1m/3m/6m/1y, etf_ma_bias(短期), etf_drawdown
  可选: growth_diff_nm (盈利增速差,净利口径) / growth_diff_rev(营收口径) — 缺省则该项中性

输出：
  { growth_w_pct, value_w_pct, bias_pts,  # 相对基准50/50的偏移
    signals: {...每信号读数+方向贡献},   # 透明可追溯
    confluence: {pushing_up, pushing_down},  # 同向信号并聚力
    caveats: [...] }
"""
import math

BASE = 50.0          # 基准成长权重 %
G_MIN, G_MAX = 40.0, 70.0   # 限幅
CONFLUENCE_THRESHOLD = 2    # 同向信号数 ≥2 才明显偏移
CONFLUENCE_TOLERANCE = 12.0 # 并聚力不足时，允许的最大偏移 pt

# 各信号权重（和为1；rate=宏观利率方向闸门）
W = {"roe": 0.27, "val": 0.22, "growth": 0.22, "crowd": 0.11, "mom": 0.08, "rate": 0.10}


def _clamp(x, lo, hi):
    return max(lo, min(hi, x))


def _fmt(x, nd=1):
    if x is None:
        return None
    return round(x, nd)


def score_roe(diff_pp):
    """ROE 中枢差(成长-价值, pp)。长期风格锚：成长 ROE 更高→成长盈利质量更强→略偏成长。"""
    if diff_pp is None:
        return 0.0
    return _clamp(diff_pp / 6.0, -1.0, 1.0)   # ±6pp 饱和


def score_valuation(pe_pct_g, pe_pct_v, pe_ratio):
    """估值价差：成长相对价值的贵贱。pe_pct 差量化拥挤度，PE比量化绝对溢价。负向(越贵越减)。"""
    if pe_pct_g is None or pe_pct_v is None:
        return 0.0
    # 分位差：成长分位 - 价值分位 >30pp = 成长过热(减)；< -20pp = 成长相对便宜(略加)
    pct_diff = pe_pct_g - pe_pct_v
    s1 = _clamp(-pct_diff / 40.0, -1.0, 0.8)
    # 绝对 PE 溢价(成长/价值)：>6x 极端溢价减分位，<3x 相对正常
    s2 = 0.0
    if pe_ratio:
        s2 = _clamp(-(pe_ratio - 4.0) / 4.0, -0.5, 0.3)
    return _clamp(s1 + s2, -1.0, 1.0)


def score_crowding(top_industries_g):
    """行业拥挤度安全边际：成长被单一/极少数行业主导=过热风险。前3行业权重占比。"""
    if not top_industries_g:
        return 0.0
    top3 = sum(x.get("weight_pct", 0) for x in sorted(
        top_industries_g, key=lambda t: -t.get("weight_pct", 0))[:3])
    if top3 > 70:
        return -0.8      # 极度拥挤(如电子+电力设备+军工>70%)
    if top3 > 60:
        return -0.4
    if top3 > 50:
        return -0.15
    return 0.05


def score_momentum(rm6_g, rm6_v):
    """温和动量：只做极端预警(相机减配)，不做切换依据。成长6m>>价值→克制加成长(防追高)；成长大幅落后→回补。"""
    if rm6_g is None or rm6_v is None:
        return 0.0
    d = rm6_g - rm6_v
    if d > 30:
        return -0.4      # 成长6m跑赢>30% → 拥挤过热，克制
    if d > 15:
        return -0.15
    if d < -25:
        return 0.4       # 成长6m大幅落后 → 逆向回补
    if d < -10:
        return 0.2
    return 0.0


def score_growth(gdiff_nm):
    """盈利增速差(成长-价值 净利同比中位数, pp)。『第一性』主导信号：增速差向上→增配成长。"""
    if gdiff_nm is None:
        return 0.0
    return _clamp(gdiff_nm / 20.0, -1.0, 1.0)   # ±20pp 饱和


def score_rate(delta_bp):
    """宏观利率闸门：中国10Y国债收益率 60日变化(bp)。利率上行→贴现率升→压制成长(长久期)。
    这是风格轮动最可靠的宏观 separator（tradethepool 等实证）；作为方向闸门参与加权。"""
    if delta_bp is None:
        return 0.0
    return _clamp(-delta_bp / 20.0, -1.0, 1.0)   # +20bp→-1(利空成长), -20bp→+1(利多成长)


def run(data):
    g = data["growth"]
    v = data["value"]
    signals = {}
    directions = {}

    # 1) ROE 中枢(长期锚)
    roe_diff = (g.get("roe") - v.get("roe")) if (g.get("roe") is not None and v.get("roe") is not None) else None
    s_roe = score_roe(roe_diff)
    signals["roe_diff_pp"] = _fmt(roe_diff)
    signals["roe_growth"] = g.get("roe"); signals["roe_value"] = v.get("roe")
    signals["s_roe"] = _fmt(s_roe); directions["roe"] = _dir(s_roe)

    # 2) 估值价差(安全边际)
    pe_ratio = (g.get("pe_ttm") / v.get("pe_ttm")) if (g.get("pe_ttm") and v.get("pe_ttm")) else None
    s_val = score_valuation(g.get("pe_pct_10y"), v.get("pe_pct_10y"), pe_ratio)
    signals["pe_pct_diff_pp"] = _fmt((g.get("pe_pct_10y") - v.get("pe_pct_10y"))
                                     if g.get("pe_pct_10y") is not None and v.get("pe_pct_10y") is not None else None)
    signals["pe_ratio"] = _fmt(pe_ratio)
    signals["s_valuation"] = _fmt(s_val); directions["val"] = _dir(s_val)

    # 3) 行业拥挤度(安全边际)
    s_crowd = score_crowding(g.get("top_industries"))
    signals["s_crowding"] = _fmt(s_crowd, 2); directions["crowd"] = _dir(s_crowd)

    # 4) 温和动量(极端预警)
    s_mom = score_momentum(g.get("return_6m"), v.get("return_6m"))
    signals["mom_6m_growth"] = g.get("return_6m"); signals["mom_6m_value"] = v.get("return_6m")
    signals["s_momentum"] = _fmt(s_mom); directions["mom"] = _dir(s_mom)

    # 5) 盈利增速差(第一性，可缺省→中性)
    s_growth = score_growth(data.get("growth_diff_nm"))
    signals["growth_diff_nm"] = data.get("growth_diff_nm")
    signals["s_growth"] = _fmt(s_growth); directions["growth"] = _dir(s_growth)

    # 6) 宏观利率闸门(10Y国债60日变化bp)
    rate_delta = data.get("macro_rate_delta_bp")
    s_rate = score_rate(rate_delta)
    signals["rate_10y"] = data.get("macro_rate_10y")
    signals["rate_delta_60d_bp"] = rate_delta
    signals["s_rate"] = _fmt(s_rate); directions["rate"] = _dir(s_rate)

    # 加权偏移
    bias = (W["roe"] * s_roe + W["val"] * s_val + W["growth"] * s_growth
            + W["crowd"] * s_crowd + W["mom"] * s_mom + W["rate"] * s_rate) * 30.0   # 满偏 ±1 → ±30pt

    # 信号并聚：同向推动成长的信号数
    pushing_up = sum(1 for k in directions if directions[k] == "up")
    pushing_down = sum(1 for k in directions if directions[k] == "down")
    net_push = pushing_up - pushing_down

    # 并聚力不足 → 收敛到基准（防单信号误切）
    caveats = []
    if abs(net_push) < CONFLUENCE_THRESHOLD:
        bias = _clamp(bias, -CONFLUENCE_TOLERANCE, CONFLUENCE_TOLERANCE)
        caveats.append(f"信号并聚力不足(净同向{net_push}<{CONFLUENCE_THRESHOLD})，已收敛偏移至±{CONFLUENCE_TOLERANCE}pt内")

    g_w = _clamp(BASE + bias, G_MIN, G_MAX)
    # 限幅提示
    applied = g_w - BASE
    if g_w >= G_MAX:
        caveats.append("触达上限70%，成长已超配阈值；勿追高")
    if g_w <= G_MIN:
        caveats.append("触达下限40%，成长已最低配；勿过度砍成长(成长非线性趋势大周期内慎重)")

    return {
        "growth_w_pct": round(g_w, 1), "value_w_pct": round(100 - g_w, 1),
        "bias_pts": round(applied, 1),
        "signals": signals, "directions": directions,
        "confluence": {"pushing_up": pushing_up, "pushing_down": pushing_down, "net_push": net_push,
                       "threshold": CONFLUENCE_THRESHOLD},
        "weights": W, "bounds": {"min": G_MIN, "max": G_MAX, "base": BASE},
        "caveats": caveats,
    }


def _dir(s):
    if s is None:
        return "flat"
    if s > 0.15:
        return "up"      # 指向成长相对占优/偏贵须减(负向)→ 用正负语义统一: s>0=偏成长
    if s < -0.15:
        return "down"
    return "flat"


if __name__ == "__main__":
    demo = {
        "growth": {"roe": 11.0, "pe_ttm": 60.6, "pe_pct_10y": 76.2, "top_industries": [
            {"industry": "电子", "weight_pct": 58.0}, {"industry": "电力设备", "weight_pct": 8.4},
            {"industry": "国防军工", "weight_pct": 7.8}],
            "return_6m": 17.6},
        "value": {"roe": 8.5, "pe_ttm": 10.4, "pe_pct_10y": 77.8, "top_industries": [],
                  "return_6m": 15.0},
        "growth_diff_nm": None,
    }
    import json
    print(json.dumps(run(demo), ensure_ascii=False, indent=1))