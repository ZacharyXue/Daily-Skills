# 指数分析 + 回撤统计工作流（2026-08 验证）

面向「查一只指数的编制逻辑/估值/成分股/收益历史，并做回撤统计」这类任务。
会话实例：931722 国新港股通央企红利指数完整分析。

## Step 1: 指数基本面与估值（ttskill）

```bash
ttskill invoke TTFUND_INDEX_INFO --action query --body '{"index_id":"931722"}'
```

**参数注意**：TTFUND_INDEX_INFO 的 body 字段是 `index_id`（代码或中文名），
不是 `query`！传错报 `缺少参数: index_id`。

返回结构（`data.raw_result.body.data`）：
- `index_profile`：代码、全名、编制方、`description`（编制逻辑原话）、基日相关字段
- `quote`：当前点位 `current_point`、`ytd_return`
- `performance`：`return_1y/2y/3y/5y`（注意是"近N年"非年度收益）
- `valuation`：`pe_ttm`、`pe_percentile_10y`（十年估值分位！判断贵贱关键）、`pb`、`pb_percentile_10y`、`roe`
- `composition.top_industries`：行业权重（`INDUSTRY_NAME` + `WEIGHT_RATIO` + `SAMPLE_NUM`）
- `composition.component_details`：前十大成分股表（`SECURITY_NAME_ABBR`、`DERIVE_SECURITY_CODE`、`INDUSTRY`、`CLOSE_PRICE`）

**估值分位解读**：`pe_percentile_10y=86.6` = PE 处于近十年 86.6% 高位。
"绝对 PE 便宜 + 分位高"是常见陷阱（低估指数被炒高），买点判断必须看分位。

## Step 2: 指数成立以来年度收益（中证官网日线）

```bash
# 直接 curl，无需登录
curl "https://www.csindex.com.cn/csindex-home/perf/index-perf?indexCode=931722&startDate=20160817&endDate=20260817&frequency=daily"
```

返回 `data[]`：`tradeDate`(YYYYMMDD) + `close`(点位)。
- 用每年最后一个交易日点位算年度收益、区间年化
- **价格指数口径不含股息**。高股息指数（红利类）必须同时给"全收益估算"：
  年化 ≈ 价格年化 + 股息率（股息率来自 valuation/编制说明）。文章要写明这是估算口径。

## Step 3: 回撤统计

直接跑脚本（更稳定，已封装官网拉取 + 回撤算法）：

```bash
python3 ~/.hermes/skills/research/ttskill-cli/scripts/index_drawdown.py 931722 20160817 20260817
```

输出：全部回撤阶段、显著回撤(≥5%)分布与分位、恢复时间、当前状态。
阅读要点：
- 显著回撤中位数 ~8% → 日常 5-8% 回撤不构成买点
- 大回撤（-15%+）是稀缺事件，十年一般 2-4 次，恢复 1-4 个月
- 极端 -47% 那种（系统性熊市）恢复 4 年+，是尾部风险必须单列

**买入阈值呈现（用户验证过的框架）**：回撤 5-8% 不买 / 10-15% 分批 1/3 /
15-20% 加仓 2/3 / ≥20% 重仓。进阶：叠加"回撤≥15% 且 PE 分位≤50%"双条件。

## 历史估值回测：PE 分档买入的 1/3/5 年回报（2026-08 验证）

用户问「现在估值分位高/低，历史上这个位置买入的回报如何」时的解法。\n\n**关键发现：中证官网 index-perf 接口的 `peg` 字段就是历史 PE(TTM)**！\n\n```bash\ncurl "https://www.csindex.com.cn/csindex-home/perf/index-perf?indexCode=000922&startDate=20080101&endDate=20260817&frequency=daily"\n# data[] 每条含 tradeDate + close(点位) + peg(历史PE)\n```\n\n- 早期年份（如 2012 前）可能 peg 为空 → 过滤 `peg` 非空的行再回测\n- **点位分位 ≠ PE 分位**：点位含盈利增长，点位分位会系统性高估\"贵\"。\n  要回答估值问题必须用 PE（peg），不能用点位近似。\n\n回测方法（按买入当天 PE 档位分组，统计之后 252/756/1260 交易日回报）：\n\n```python\n# series = [(date, close, pe), ...] 仅含 peg 非空行\ndef future_return(i, n):\n    return (series[i+n][1] / series[i][1] - 1) * 100 if i+n < len(series) else None\n# PE 分档: 5-6.5 / 6.5-7.5 / 7.5-8.5 / 8.5-9.5 / 9.5-11 / >11，每档统计均值+正收益占比\n# 去重相邻日（同一连续高/低位区段只取首日），否则同区段样本重复计数\n```\n\n**红利指数的回测结论（2026-08，000922 中证红利）**：\n- PE>11（极高）：1 年 -18%、正收益仅 10% → 唯一\"追高必死\"区\n- PE 9.5-11（高）：1 年大概率亏，3 年 +24%、5 年 +35% → 短期难受长期还行\n- PE<9.5（含当前 8.2）：3 年正收益概率 60-100%，**红利指数是\"弱择时\"资产**\n- 原因：股息率 5%+ 每年垫底 + 盈利缓慢增长，估值波动只是 ±30% 噪音\n- ⚠️ 回测是**价格指数**回报，不含股息；实际持有回报要再加每年股息率\n\n**口径冲突提醒**：TTFUND_INDEX_INFO 的 `pe_percentile_10y`（如 89.6%）\n与官网静态 PE 分位（如 52%）可能不一致——TTFUND 可能用更短窗口或动态 PE。\n两种口径都给，用官网 PE 绝对值分档回测最稳。\n\n## 组合回测（ttskill TTFUND_GROUP_BACKTEST）

比较"该买哪只/组合配比"时用，body action=bt_detail_v2：

```json
{
  "action": "bt_detail_v2",
  "bt_detail_v2": {
    "fundPercent": "[{\"fundCode\":\"005974\",\"fundRation\":60,\"fundName\":\"005974\"},{\"fundCode\":\"012951\",\"fundRation\":40,\"fundName\":\"012951\"}]",
    "groupAmount": 10000, "modelType": 0, "rebalanceMode": 1,
    "startTime": "2021-08-01T00:00:00", "endTime": "2026-08-14T00:00:00",
    "intervalStartTime": "2024-01-01T00:00:00"
  }
}
```

- `fundPercent` 必须是 JSON **字符串**（不是对象数组），占比和=100
- 关键结果在 `...steps.bt_detail_v2.body.data`：`accumProfitRate`（区间累计）、
  `intervalDrawDown`（最大回撤）、`sharpRate`（夏普）、`profitRetraceRatio`
- **查询类（bt_detail_v2）不需要 confirm_write**；bt_create/bt_change_* 才需要

## 年度收益自算替代

ttskill 的 TTFUND_NAV_INFO 返回净值日线（range=ln 成立以来），
可对基金算"年末/上年末-1"年度收益。注意：LJJZ 是累计净值口径（含分红再投资），
比 DWJZ（单位净值）适合算长期收益。ttskill 阶段收益表 period_increase 直接给
排名同业对比，优先用。

## 常见坑

- **回撤分位数方向陷阱**：回撤是负值（-47.5 < -19.8），`sorted()` 升序后**最深的在最前面**。算「80% 分位」时若直接取 `sorted(dds)[int(len*0.8)]` 会得到浅回撤（如 -6.9%），而用户要的语义是「80% 的回撤比这个浅」→ 应取 `sorted(dds)` 的 **80% 处（从最浅往上数）或直接按 -19% 这种「大回撤阈值」表述**。脚本输出解读文案不要硬编码（曾在 print 里写错「80%分位=-19.8%」导致自相矛盾），要么输出原始排序列表、要么让解读跟着分位数值走。
- **恢复时间受极端值污染**：平均恢复天数会被 -47% 那次（1523 天）拉爆，必须同时给「中位数」和「排除极端后均值」两个口径，否则 6 天 vs 77 天的结论对不上。
- TTFUND_INDEX_INFO 用 `index_id`，TTFUND_SEARCH 用 `query`
- 中证官网接口偶发 500（服务器异常）：重试即可，不是参数错
- 指数官网 API 是 httpx 不兼容的老接口，urllib/curl 都行，保持 UA header
- 判断"红利指数贵不贵"：PE 分位比绝对 PE 重要；红利指数价格年化低是正常属性，
  别把"价格年化 2.7%"当成失败——全收益才是持有人真实体验