#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ETF 红利 · 技术温度看板 生成脚本
用法:  cd etf-dashboard && python3 generate.py
产出:  public/exports/etf-dashboard.html  (手动触发更新)

数据源:
  1) 中证官网 csindex index-perf   -> 历史PE(peg字段), 算 <5年分位>
  2) 天天基金 TTFUND_INDEX_INFO    -> 指数档案 + PE/PB 十年分位 + ROE
  3) 腾讯行情 qt.gtimg.cn          -> ETF 实时价/涨跌
  4) 腾讯K线 web.ifzq.gtimg.cn     -> 算 MA20/BIAS20/回撤/N日涨跌/成交额

标的池: 编辑同目录 watchlist.json 的 watchlist 数组, 加/换品种即可.
"""
import json, subprocess, urllib.request, urllib.parse, time, sys, os
from datetime import datetime, timedelta
from indices_meta import META

UA = {"User-Agent": "Mozilla/5.0"}
API = "/root/.local/bin"
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.environ.get("ETF_OUT") or os.path.normpath(os.path.join(HERE, "../public/exports/etf-dashboard.html"))
def _router_root():
    d = HERE
    for _ in range(8):
        if os.path.isdir(os.path.join(d, "data-source-router")): return d
        d = os.path.dirname(d)
    return os.environ.get("ZACH_SKILLS", "/root/zach-skills")
sys.path.insert(0, os.path.join(_router_root(), "data-source-router"))
import data_router as DSR   # 统一数据层: 行情/K线/中证PE/天天基金 全部走 router, 见 data-source-router
YEARS = 5  # 估值分位窗口(年)

# ---------- 数据获取 ----------
def http_json(url, timeout=15, retry=3):
    last = None
    for i in range(retry):
        try:
            req = urllib.request.Request(url, headers=UA)
            return json.loads(urllib.request.urlopen(req, timeout=timeout).read())
        except Exception as e:
            last = e; time.sleep(1)
    raise last

def csindex_pe_pct(index_code):
    """中证官网历史PE(peg) -> 5年分位 + PE区间(lo/hi) (走 data-source-router 统一取数)

    主锚数据源：中证官网，**不依赖 ttskill 登录**。用 `indexCsiDsPe` 拿全序列，
    自己算 5 年分位与区间（比 index-perf 更全、更稳，且能给出 PE 波动区间供渲染）。
    """
    try:
        d = DSR.get('cn_csindex_pe_series', index_code=index_code, years=6)[0]
        if not (d and d.get("ok")):
            return None
        series = d.get("series") or []
        if not series:
            return None
        cut = (datetime.now() - timedelta(days=365 * 5)).strftime("%Y%m%d")
        pe5 = [v for dt_, v in series if dt_ >= cut]
        if not pe5:
            pe5 = [v for _, v in series]
        cur = pe5[-1]
        pct = sum(1 for x in pe5 if x <= cur) / len(pe5) * 100
        return {"cur_pe": round(cur, 2), "pct": round(pct, 1),
                "lo": round(min(pe5), 2), "hi": round(max(pe5), 2), "n": len(pe5)}
    except Exception:
        return None

_TT = {"tried": 0, "ok": 0, "note": "", "available": None}


def _tt_probe():
    """开跑前探测一次 ttskill 是否真能用（ttskill status 不看 stderr 会误判，
    必须用一次真实 invoke 的 rc/stderr 判断；失败原因原样带回给看板标注）。

    ⚠️ "fetch failed" 是 ttskill 访问服务端的偶发网络失败（≠ 源坏）→ 按用户铁律重试 2 次。
    """
    why = ""
    for attempt in range(3):
        try:
            r = subprocess.run(["ttskill", "invoke", "TTFUND_INDEX_INFO", "--action", "query",
                                "--body", '{"index_id":"000922"}'],
                               capture_output=True, text=True, timeout=45,
                               env={"PATH": f"{API}:/usr/local/bin:/usr/bin:/bin"})
            if r.returncode == 0 and (r.stdout or "").strip():
                return True, ""
            why = (r.stderr or "").strip()[:60] or "ttskill 无输出"
        except Exception as e:
            why = repr(e)[:60]
        if attempt < 2:
            time.sleep(2.5)
    if "登录" in why or "login" in why.lower():
        return False, "ttskill 登录已过期（token 30 天，需重扫）"
    if "fetch failed" in why.lower():
        return False, "ttskill 服务端请求失败（网络异常，非登录问题）"
    return False, why


def ttskill_index_info(index_id):
    """天天基金 TTFUND_INDEX_INFO -> PE/PB 10年分位+ROE (走 router)

    ⚠️ 可选增强源：ttskill token 30 天过期，失效时返回 {}（**不报错、不阻断**）。
    看板主锚是中证官网 PE5y 分位（见 csindex_pe_pct），本函数的 PB10y 只是独立增量口径；
    缺失时看板显示「—」并在页头标注来源状态，绝不拿旧值冒充。
    """
    global _TT
    if _TT["available"] is False:
        return {}
    _TT["tried"] += 1
    try:
        d = DSR.get('cn_ttfund_index', index_id=index_id, force=True)[0]
        if not (d and d.get("ok")):
            note = str((d or {}).get("note") or "")
            if "登录已过期" in note or "expired" in note.lower():
                _TT["note"] = "ttskill 登录已过期（token 30 天，需重扫）"
            elif "登录" in note or "login" in note.lower():
                _TT["note"] = "ttskill 未登录"
            elif not _TT["note"]:
                _TT["note"] = note[:60] or "天天基金源暂不可用"
            return {}
        _TT["ok"] += 1
        return {"name": None, "pe10y": d.get("pe_pct_10y"), "pb10y": d.get("pb_pct_10y"),
                "pb": d.get("pb"), "roe": d.get("roe"), "pe_ttm": d.get("pe_ttm")}
    except Exception:
        return {}

def tencent_quote(symbol):
    """腾讯实时行情: 现价/涨跌幅 (走 router)"""
    try:
        d = DSR.get('cn_stock_quote', symbol=symbol)[0]
        return {"name": d.get("name"), "price": d.get("price"), "chg_pct": d.get("change_pct")}
    except Exception as e:
        raise ValueError(f"腾讯行情失败 {symbol}: {e}")

def tencent_kline(symbol, days=300):
    """腾讯前复权K线 -> [(date, close, high, vol)] (走 router)"""
    kl = DSR.get('cn_stock_kline', symbol=symbol, count=days)[0]
    return [(r["date"], r["close"], r["high"], r["volume"]) for r in kl]

# ---------- 雅虎数据源（标普500/纳斯达克100/黄金，腾讯美股K线不可用） ----------
YAHOO_SYM = {"%5EGSPC": "标普500", "%5ENDX": "纳斯达克100", "GC=F": "黄金"}

def yahoo_kline(symbol, start_ts=946684800):  # 2000-01-01
    """雅虎 chart API -> [(date, close, high, vol)], date为YYYY-MM-DD"""
    # ⚠️ period2 必须用「当前时间」，不能硬编码：曾硬编码 1768000000(=2026-01-09) 导致外盘K线
    #    被静默截断 9 个月，看板把 1 月的价格当"当前"显示（违反数据正确性铁律）
    end_ts = int(time.time()) + 86400
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(symbol, safe='%')}"
           f"?period1={start_ts}&period2={end_ts}&interval=1d")
    d = http_json(url, timeout=20)
    res = (d.get("chart") or {}).get("result") or []
    if not res:
        raise ValueError(f"yahoo {symbol}: 空结果")
    r = res[0]
    ts = r.get("timestamp") or []
    q = (r.get("indicators") or {}).get("quote") or [{}]
    closes = q[0].get("close") or []
    highs = q[0].get("high") or []
    vols = q[0].get("volume") or []
    rows = []
    for i, t in enumerate(ts):
        date = time.strftime("%Y-%m-%d", time.localtime(t))
        c = closes[i] if i < len(closes) and closes[i] is not None else None
        h = highs[i] if i < len(highs) and highs[i] is not None else None
        v = vols[i] if i < len(vols) and vols[i] is not None else None
        if c is not None:
            rows.append((date, c, h or c, v or 0))
    if not rows:
        raise ValueError(f"yahoo {symbol}: 无K线")
    return rows

def yahoo_quote(symbol):
    """雅虎最新价/涨跌（chart 最后一个 close + 对比前日）"""
    kl = yahoo_kline(symbol)
    price = kl[-1][1]
    prev = kl[-2][1] if len(kl) > 1 else price
    return {"name": YAHOO_SYM.get(symbol, symbol), "price": price,
            "chg_pct": (price / prev - 1) * 100 if prev else 0}

# ---------- 最大回撤指标（核心新增） ----------
def max_drawdown(kl_rows):
    """从K线算 {max_dd_pct, max_dd_date, cur_dd_pct, cur_dd_peak, dd_progress}
    max_dd = 历史最大回撤(负%)；cur_dd = 当前相对历史峰值(负%)；
    dd_progress = 当前回撤 / 最大回撤（1.0 = 回到历史最大回撤处，指汇盈抄底位）。
    """
    peak = -1e18
    peak_date = ""
    max_dd = 0.0
    max_dd_date = ""
    cur_dd = 0.0
    cur_peak = -1e18
    cur_peak_date = ""
    last_close = kl_rows[-1][1]
    for date, close, _h, _v in kl_rows:
        if close > peak:
            peak = close
            peak_date = date
        dd = (close / peak - 1) * 100
        if dd < max_dd:
            max_dd = dd
            max_dd_date = date
        # 当前回撤：相对最后一个峰值（从最新end反推）
        if close > cur_peak:
            cur_peak = close
            cur_peak_date = date
    cur_dd = (last_close / cur_peak - 1) * 100
    progress = abs(cur_dd) / abs(max_dd) if max_dd < 0 else 1.0
    return {
        "max_dd": max_dd, "max_dd_date": max_dd_date, "max_dd_peak": peak_date,
        "cur_dd": cur_dd, "cur_dd_peak_date": cur_peak_date, "dd_progress": progress,
        "kline_start": kl_rows[0][0], "kline_end": kl_rows[-1][0], "kline_n": len(kl_rows),
    }

# ---------- 指标计算 ----------
def vbias(closes, price, n=20):
    if len(closes) < n: return None
    ma = sum(closes[-n:]) / n
    return (price - ma) / ma * 100

def vi_change(closes, price, n):
    if len(closes) <= n: return None
    return (price / closes[-1-n] - 1) * 100

def build_row(w):
    if w.get("kind") == "yahoo":
        q = yahoo_quote(w["yahoo_symbol"])
        kl = yahoo_kline(w["yahoo_symbol"])
        closes = [c for _, c, _, _ in kl]
        price = q["price"]
        ma20 = sum(closes[-20:]) / 20
        dd = max_drawdown(kl)
        row = {
            "name": q["name"], "etf_code": w["yahoo_symbol"], "price": price,
            "chg_pct": q["chg_pct"], "kind": "yahoo",
            "chg5": vi_change(closes, price, 5), "chg20": vi_change(closes, price, 20),
            "bias20": vbias(closes, price, 20), "dd_hi": (price / max(c for _, c, _, _ in kl) - 1) * 100,
            "ma20": ma20, "daily_yi": None,
            "pe5_cur": None, "pe5_pct": None, "pe5_lo": None, "pe5_hi": None,
            "pe10y": None, "pb10y": None, "pb": None, "roe": None,
            "target10": ma20 * 1.10, "target15": ma20 * 1.15,
            "date": kl[-1][0],
        }
        row.update(dd)
        return row

    q = tencent_quote(w["etf_symbol"])
    # 除息/除权日腾讯行情名会带 XD/XR/DR 前缀（如「XD红利ETF易方达」）→ 剥掉，
    # 否则卡片名随除息日漂移，同一只标的一天一个名字（2026-10-18 踩到）
    disp = (q.get("name") or "").strip()
    for _tag in ("XD", "XR", "DR"):
        if disp.startswith(_tag) and len(disp) > len(_tag) + 1:
            disp = disp[len(_tag):]
            break
    # 指数(如中证红利 000922)腾讯K线可拉 2000 根(2018起)；ETF 只到上市存续
    kl = tencent_kline(w["etf_symbol"], days=int(w.get("kline_days", 2000)))
    closes = [c for _, c, _, _ in kl]
    highs  = [h for _, _, h, _ in kl]
    vols   = [v for _, _, _, v in kl]
    price = q["price"]
    ma20 = sum(closes[-20:]) / 20
    dd_hi = (price / max(highs) - 1) * 100
    daily_yi = (sum(vols[-5:]) / 5) * 100 * price / 1e8  # 5日均成交额(亿)
    val = ttskill_index_info(w["ttfund_index"])
    pe5 = csindex_pe_pct(w["csindex"])
    row = {
        "name": disp, "etf_code": w["etf_code"], "price": price,
        "chg_pct": q["chg_pct"], "kind": "tencent",
        "chg5": vi_change(closes, price, 5), "chg20": vi_change(closes, price, 20),
        "bias20": vbias(closes, price, 20), "dd_hi": dd_hi, "ma20": ma20,
        "daily_yi": daily_yi,
        "pe5_cur": pe5["cur_pe"] if pe5 else None,
        "pe5_pct": pe5["pct"] if pe5 else None,
        "pe5_lo": pe5["lo"] if pe5 else None, "pe5_hi": pe5["hi"] if pe5 else None,
        "pe10y": val.get("pe10y"), "pb10y": val.get("pb10y"),
        "pb": val.get("pb"), "roe": val.get("roe"),
        "target10": ma20 * 1.10, "target15": ma20 * 1.15,
        "date": kl[-1][0] if kl else "",
    }
    # 历史最大回撤（指数用更长K线 2000根；ETF 用全部存续K线）
    dd = max_drawdown(kl)
    row.update(dd)
    return row

def signal(r):
    # 5年PE分位为主, 优先; 无则退回回撤/BIAS
    if r["pe5_pct"] is not None and r["dd_hi"] is not None:
        if r["dd_hi"] <= -15 and r["pe5_pct"] < 50: return "加仓", "add"
        if r["dd_hi"] <= -10 and r["pe5_pct"] < 70: return "分批", "dca"
        if r["dd_hi"] >= -5 and r["pe5_pct"] >= 90: return "过热/减", "hot"
        if r["pe5_pct"] > 95: return "过热/减", "hot"
        if r["dd_hi"] <= -15 and r["pe5_pct"] < 70: return "加仓", "add"
        return "观望", "watch"
    if r["bias20"] is not None:
        if r["bias20"] > 10: return "过热/减", "hot"
        if r["bias20"] < -10: return "超跌", "dip"
    return "观望", "watch"

def view(r):
    """按当前数据生成「位置解读」三段（估值面 / 价格面 / 综合）——动态，行情变了自动跟着变，
    绝不写死观点；无数据时如实说明是「数据限制」而不是「它便宜」。"""
    o = {"valuation": "", "price": "", "take": ""}
    p, cur, lo, hi = r.get("pe5_pct"), r.get("pe5_cur"), r.get("pe5_lo"), r.get("pe5_hi")
    if p is None:
        pb10 = r.get("pb10y")
        if pb10 is not None:
            pbs = ("%.2f" % r["pb"]) if r.get("pb") is not None else "—"
            roes = ("，ROE %.1f%%" % r["roe"]) if r.get("roe") is not None else ""
            pbband = ("处近 10 年偏高位，资产端不便宜" if pb10 >= 70 else
                      "处近 10 年中位，资产端没有明显倾向" if pb10 >= 40 else
                      "处近 10 年偏低位置，资产端有安全垫")
            o["valuation"] = ("该指数无公开历史 PE 序列（非中证编制）→ **PE 口径不参与判断**。"
                              "改用资产端（PB）口径：PB 分位 %.0f%%（PB %s%s）——%s。"
                              % (pb10, pbs, roes, pbband))
        else:
            o["valuation"] = ("该指数非中证编制，公开渠道拿不到历史 PE 序列 → 估值面不参与判断。"
                              "这是**数据限制，不等于它便宜**，只能用价格位置（回撤/BIAS）替代。")
    else:
        band = ("已到近 5 年最贵的十分之一区间，此时买入等于为「稳定」付溢价" if p >= 90 else
                "处近 5 年偏高位置，安全边际不厚" if p >= 70 else
                "处近 5 年中位，估值上没有明显倾向" if p >= 40 else
                "处近 5 年偏低位置，估值端有安全垫" if p >= 10 else
                "趴在近 5 年最低区间，估值端赔率最好")
        posr = ""
        if lo and hi and hi > lo:
            posr = "（区间位置 %.0f%%）" % ((cur - lo) / (hi - lo) * 100)
        o["valuation"] = "PE %s 处近 5 年区间 %s~%s%s，分位 %.0f%%——%s。" % (cur, lo, hi, posr, p, band)
        # PE/PB 背离检测（用户要求两个估值都有后新增：单看 PE 会漏掉「盈利被压缩出来的便宜」）
        pb10 = r.get("pb10y")
        if pb10 is not None:
            gap = p - pb10
            pbs = ("%.2f" % r["pb"]) if r.get("pb") is not None else "—"
            if gap >= 25:
                o["valuation"] += ("　PB 分位 %.0f%%（PB %s），PE 比 PB 高 %.0f 个百分点——"
                                   "盈利端比资产端贵，通常对应高 ROE/轻资产，也可能是盈利正处在周期高位。"
                                   % (pb10, pbs, gap))
            elif gap <= -25:
                o["valuation"] += ("　⚠ PB 分位 %.0f%%（PB %s），**PE 比 PB 低 %.0f 个百分点**——"
                                   "资产端并不便宜，PE 低更可能是「盈利被压缩」压出来的（分母效应），"
                                   "不能只看 PE 就判定便宜。"
                                   % (pb10, pbs, abs(gap)))
            else:
                o["valuation"] += "　PB 分位 %.0f%%（PB %s），与 PE 口径一致，两者不矛盾。" % (pb10, pbs)
    dd, mx, prog = r.get("cur_dd"), r.get("max_dd"), r.get("dd_progress")
    if dd is not None:
        depth = ("已深于历史最大回撤的一半，属于周期性机会区" if (prog or 0) >= 0.5 else
                 "回撤走完不到历史最大回撤的一半" if (prog or 0) < 0.3 else
                 "回撤进度过半，接近历史级别的调整")
        o["price"] = ("现价距历史高点 %.1f%%，历史最大回撤 %.1f%%（%s），回撤进度 %.0f%%——%s。"
                      % (dd, mx or 0, r.get("max_dd_date") or "—", (prog or 0) * 100, depth))
    # 综合（估值 × 价格，两个维度交叉，不给单一结论）
    sig = r.get("sig_key")
    if p is None:
        pb10 = r.get("pb10y")
        if pb10 is not None:
            if pb10 >= 70 and (prog or 0) >= 0.5:
                o["take"] = ("**资产端偏贵 + 价格已回调**：无 PE 口径，PB 处近 10 年 %.0f%% 分位——"
                             "资产端并不便宜，价格已先跌一段，位置由 PB 能否回落确认。" % pb10)
            elif pb10 >= 70:
                o["take"] = ("**资产端偏贵 + 价格仍高**：无 PE 口径，PB 处近 10 年 %.0f%% 分位——"
                             "资产端不便宜，价格也没跌下来，两个维度都没给安全垫。" % pb10)
            elif pb10 <= 35 and (prog or 0) >= 0.5:
                o["take"] = ("**资产端偏便宜 + 价格也跌透**：无 PE 口径，PB 处近 10 年 %.0f%% 分位——"
                             "资产端有安全垫，价格端也释出空间。" % pb10)
            elif pb10 <= 35:
                o["take"] = ("**资产端偏便宜 + 价格仍高**：无 PE 口径，PB 处近 10 年 %.0f%% 分位——"
                             "资产端便宜，但价格还没反映出来。" % pb10)
            else:
                o["take"] = ("**资产端不贵不便宜**：无 PE 口径，PB 处近 10 年 %.0f%% 分位，"
                             "资产端没有明显倾向，位置主要看价格端。" % pb10)
        else:
            o["take"] = ("PE 与 PB 两个估值口径都缺失，只能按价格与均线判断：当前 %s。"
                         "价格判断的依据强度低于估值口径，位置结论的权重应相应下调。"
                         % (r.get("signal") or "—"))
    elif p >= 90 and (prog or 0) < 0.4:
        o["take"] = "**高位 + 浅回撤**：估值接近 5 年顶部、价格又没跌下来，此刻买入拿不到风险补偿。"
    elif p >= 90 and (prog or 0) >= 0.4:
        o["take"] = "**高位 + 已回调**：估值仍贵但价格已经跌了一截，属于「跌了但没跌够」，可继续等分位回落。"
    elif p < 20 and (prog or 0) >= 0.5:
        o["take"] = "**低位 + 深回撤**：估值接近 5 年最低、价格也跌透，是赔率与胜率都占优的位置。"
    elif p < 20 and (prog or 0) < 0.5:
        o["take"] = "**低位 + 浅回撤**：估值便宜但价格没怎么跌，说明基本面预期还没被完全定价。"
    elif p < 50 and (prog or 0) >= 0.6:
        # 信号（signal）在「回撤够深 + 分位<50」时就判加仓，此处措辞必须对齐，
        # 否则会出现「徽章写加仓、正文写中位区间」的自相矛盾（2026-10 港股通汽车 520600 踩到）
        o["take"] = ("**估值中低位 + 深回撤**：PE 分位 %.0f%% 还没到极端便宜那档，"
                     "但价格已走完历史最大回撤的 %.0f%%——两端口径不同，一侧给安全垫、一侧给赔率，"
                     "信号因此偏买；仓位按分批给，别当成「极端低估、一把梭」的位置。"
                     % (p, (prog or 0) * 100))
    else:
        o["take"] = "**中位区间**：估值与价格都在中间地带，没有极端值得下重手的理由，按计划分批即可。"
    return o


ACTIONS = {
    "add":   "深回撤+低估值双重买点：可一次性买入计划的 1/2，剩余按季分批，拿住等估值修复。",
    "dca":   "进入买点区：可分 3 批布局，每批 1/3，跌破 MA20 或回撤加深再加，跌破 -20% 停手。",
    "hot":   "高位区：不追高。持有可先减 1/3 锁盈，回落 PE5y<80% 或 BIAS<5% 再考虑回补。",
    "dip":   "短线超跌：可轻仓博反弹，首次反弹到 MA20 附近减仓，不恋战。",
    "watch": "数据不足或中性：暂不动，等回撤加深(≥10%) + 5年PE分位回落再看。",
}
SIG_LABEL = {"add":"加仓","dca":"分批","hot":"过热/减","dip":"超跌","watch":"观望"}

def main():
    from concurrent.futures import ThreadPoolExecutor, as_completed
    with open(os.path.join(HERE, "watchlist.json"), encoding="utf-8") as fh:
        cfg = json.load(fh)
    def work(w):
        try:
            r = build_row(w); r["signal"], r["sig_key"] = signal(r)
            r["views"] = view(r)                  # 动态位置解读（估值面/价格面/综合）
            r["meta"] = META.get(w["name"], {})   # 静态指数说明（不占运行上下文）
            return r, None
        except Exception as e:
            return None, f"{w['name']}: {repr(e)[:80]}"
    # 先探测可选源 ttskill 是否可用（不可用则整体跳过，避免 10 次无效子进程）
    avail, why = _tt_probe()
    _TT["available"] = avail
    if not avail:
        _TT["note"] = why
    rows, errs = [], []
    with ThreadPoolExecutor(max_workers=6) as ex:
        futs = [ex.submit(work, w) for w in cfg["watchlist"]]
        for f in as_completed(futs):
            r, e = f.result()
            if e: errs.append(e)
            else: rows.append(r)
    # 保持 watchlist 原始顺序 (as_completed 无序)
    order = {w.get("etf_code") or w.get("yahoo_symbol", ""): i for i, w in enumerate(cfg["watchlist"])}
    rows.sort(key=lambda r: order.get(r["etf_code"], 99))
    # 数据源状态（可选源 ttskill 是否可用 → 渲染层明示，不静默）
    tt_ok = _TT["tried"] > 0 and _TT["ok"] > 0
    if tt_ok:
        tt_note = ""
    elif _TT["available"] is False:
        tt_note = _TT["note"] or "天天基金源不可用"   # 探测阶段已知的失败原因优先
    elif _TT["tried"] == 0:
        tt_note = "本次未调用（无中证系标的）"
    else:
        tt_note = _TT["note"] or "本次全部指数未取到 PB"
    src_status = {"ttfund_ok": tt_ok, "ttfund_note": tt_note,
                  "ttfund_tried": _TT["tried"], "ttfund_ok_n": _TT["ok"]}
    return cfg, rows, errs, src_status

if __name__ == "__main__":
    # 只测试数据层, HTML生成在 generate_html.py 里(单独文件避免超大)
    cfg, rows, errs, src_status = main()
    print(json.dumps({"rows": rows, "errs": errs, "src_status": src_status}, ensure_ascii=False, indent=1))