# 组合回测 + 指数历史数据（基金分析系列三）

本文档只记录另外两份 reference 未覆盖的技术：**组合回测**、**中证指数官网历史数据接口**、**红利指数价格 vs 全收益口径**。单基金归因见 `fund-performance-attribution.md`，多基金对比/调参速查见 `single-fund-analysis.md`。

## 一、组合回测（TTFUND_GROUP_BACKTEST）

验证「xx% 基金A + yy% 基金B 长期能否达到 5% 年化」类问题。互斥参数一次只传一个 action 对象，其余步骤自动 skipped。

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

要点：
- `fundPercent` 必须为 JSON **字符串**（不是对象数组），占比和必须 =100
- 结果在 `...(steps).bt_detail_v2.body.data`：`accumProfitRate`（区间累计）、`intervalProfitRate`（intervalStartTime 起）、`intervalDrawDown`（最大回撤）、`sharpRate`、`profitRetraceRatio`（收益回撤比）、`*Percent`=同类排名百分位
- 多组合对比：Python 脚本循环 invoke + 递归提取 `profit/return/retrace/sharp/annual` 键，不要手工翻 200KB+ 回包
- 年化换算：`(1+accumProfitRate)^(1/年数)-1`，回测 5 年结果可直接和 single-fund 的长周期排名对照

## 二、中证指数官网历史数据（指数=ETF/ETF联接的底层）

`TTFUND_INDEX_INFO` 只给区间收益+估值；要**逐年/逐月点位**自己算业绩用官网：

```
https://www.csindex.com.cn/csindex-home/perf/index-perf?indexCode=931722&startDate=20160817&endDate=20260817&frequency=daily
```

- 返回 json `data[]`：`tradeDate`(YYYYMMDD)/`close`/`changePct`/`tradingVol`/`consNumber`
- **指数从基日就有回溯点位**：931722 基日 2016-08-17 基点 1000，接口直接给全历史，不需要再拼
- 其它中证端点（index-basic-info、query-index-item 等）会 404/500，用 perf 端点即可
- 算年度业绩：按 tradeDate[:4] 分组取年末 last close，逐年环比

## 三、红利指数「价格 vs 全收益」——关键认知

案例 931722 中证国新港股通央企红利（国新定制，港股通国资委央企高股息，49 成分；石油石化30%/通信21%/煤炭13%）。

- **价格指数 10 年年化仅 +2.75%**（2016 基日 1000 → 2026 约 1311），但**全收益年化约 +7.5~8.5%**（股息率常年在 5-6%）→ 红利指数回报几乎全来自股息
- 推论：① 评估红利类基金必须用全收益口径（累计净值 LJJZ/分红再投），价格指数年化会严重低估；② 买入时点（估值分位）决定体验——2020 年曾单年 -19%，2018-2020 三年累计跌 34%
- 估值判断：PE 9.26 看着便宜 ≠ 可买，看 `pe_percentile_10y`（十年分位）。931722 分位 86.6% = "便宜的贵"，追高危险；PB 分位 57.7% 相对中性
- 与固收+ 比长期收益时用全收益年化（7-8%）才公平；但风险等级 R4、近1年回撤 18%+ 意味着它不能当固收替代

## 四、2026-08 三基金案例速记（005974/012951/022719）

| 基金 | 类型 | 成立 | 成立以来年化 | 股票仓位 | 结论 |
|---|---|---|---|---|---|
| 005974 东方红配置精选A | 偏债混合 R3 | 2018-05 | 6.29% | 27.9% | 唯一 8 年实证能摸 5-6%，求稳+5% 选它 |
| 012951 汇添富鑫享添利A | 偏债混合 R3 | 2021-07 | 3.20% | 6.9% | 股票个位数→收益天花板≈3.5%，够不到 5% |
| 022719 广发港股央企红利联接A | 指数股票 R4 | 2025-01 | 7.48%（撞行情，不可外推） | ~95% | 长期潜在 6-8% 但要扛 18% 回撤；当前 PE 分位高，等回调/定投 |

判断「目标年化 5%」的硬规则：股票仓位个位数的固收+ 到不了 5%；要 5%+ 需 20%+ 股票增强或红利权益仓。