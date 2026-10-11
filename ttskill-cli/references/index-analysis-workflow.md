# 指数/ETF 深度分析与回撤测算工作流

2026-08-17 实战沉淀（931722 港股央企红利、159545/159209/515180 红利 ETF 对比）。基金对比/指数分析类任务的完整流程。

## 1. 指数身份与估值

- `TTFUND_SEARCH` 确认基金名与跟踪指数（query 基金代码）
- `TTFUND_BASE_INFOS`（fcode）拉基金档案：period_increase / fund_profile_holdings（重仓/行业）/ unique_info（夏普/回撤）/ bonus_distribution_history（分红）/ index_detail（跟踪指数代码与估值分位）
- **`TTFUND_INDEX_INFO`**：`{"index_id":"931722"}`（指数代码或名称，参数名是 index_id 不是 query）→ 返回 `index_profile`（编制方/基日描述）、`quote`（点位/年初至今）、`performance`（1d/1w/1m/3m/6m/1y/2y/3y/5y）、`valuation`（pe_ttm、**pe_percentile_10y** 十年分位）、`composition`（top_industries 行业权重 + **component_details 前十大成分股**）

## 2. NAV_INFO 的 range 参数（关键）

```json
{"fund_id":"005974","range":"ln"}
```

| range | 含义 |
|-------|------|
| y | 近1月 |
| 3y | 近3月 |
| 6y | 近6月 |
| n | 近1年（默认） |
| 2n / 3n | 近2/3年 |
| ln | 成立以来（全量，数千条） |

- items 为日线 `[FSRQ, DWJZ, LJJZ]`；**年度收益 = 年末 LJJZ ÷ 上年末 LJJZ − 1**（用累计净值，含分红）
- ⚠️ ln 返回全量日线，必须用脚本聚合（groupby 年份），不要把原始 JSON 灌入上下文
- ⚠️ 成立不足 2 年的基金用 ln 可能返回异常（如 159209 返回 27 条），改用 n 范围兜底

## 3. 中证指数官网日线（指数历史点位）

```bash
curl "https://www.csindex.com.cn/csindex-home/perf/index-perf?indexCode=931722&startDate=20160817&endDate=20260817&frequency=daily" -H "User-Agent: Mozilla/5.0" -H "Referer: https://www.csindex.com.cn/"
```

- 返回 `data[]`：`{tradeDate, close}`，可算年度收益/回撤/商品分位
- ⚠️ 官网 `/index-list/query-index-item` 接口返回 500「服务器异常」；**perf 接口可用**，直接用它

## 4. 回撤测算（自算脚本）

- 用日线 close 算峰值回撤序列；识别「峰值 → 谷底 → 恢复」事件（dd 从 0 负向加深再回到 0 为一个事件）
- 输出：最大回撤 / 平均 / 中位 / 80% 分位 / 恢复天数均值
- ⚠️ 分位数方向易搞反：显著回撤按数值升序排列后，P80 = 让 80% 的回撤不比它更深的那个值

**买入阈值参考（10 年红利指数统计）**：

| 回撤 | 频率 | 操作 |
|------|------|------|
| 5%~8% | 常态 | ❌ 不买（80% 的显著回撤不深于 ~7%） |
| 10%~15% | 10 年 3 次 | 🟡 开始分批（1/3） |
| 15%~20% | 接近大回撤区 | 🟢 加仓（2/3） |
| ≥20% | 10 年 3 次 | 🔴 重仓（叠加 PE 十年分位 ≤50% 确认） |

恢复时间规律：常态回撤中位 ~6 天、排除极端后均值 ~19 天；大回撤（-19%~-21%）25~127 天；系统性熊市（-47%）4 年+ 才回本——尾部风险必须向用户讲明。

## 5. 组合回测（TTFUND_GROUP_BACKTEST）

```json
{
  "action": "bt_detail_v2",
  "bt_detail_v2": {
    "fundPercent": "[{\"fundCode\":\"005974\",\"fundRation\":60},{\"fundCode\":\"012951\",\"fundRation\":40}]",
    "groupAmount": 10000, "modelType": 0, "rebalanceMode": 1,
    "startTime": "2021-08-01T00:00:00", "endTime": "2026-08-14T00:00:00",
    "intervalStartTime": "2024-01-01T00:00:00"
  }
}
```

- ⚠️ `fundPercent` 必须是 **JSON 字符串**（不是对象数组）；占比和必须 100；rebalanceMode 0/1/2/3/4；startTime 不早于成立日
- 关键返回：`steps.bt_detail_v2.body.data` → `accumProfitRate`（区间累计）、`intervalProfitRate`、`intervalDrawDown`（回撤）、`sharpRate`
- 组合对比法：单只 100% vs 配比组合同区间跑，看收益/回撤/夏普三列，选性价比

## 6. 红利类基金分析 Pitfall（用户立场）

- **红利质量指数（932315）的「质量」是滞后指标**：成分股高 ROE/毛利率可能来自 ① 周期顶部利润（铝/航运/煤炭）② 增长见顶的白马。验证方法：逐个拉前十大成分股的 `PARENTNETPROFITTZ`（净利同比）+ `ROEJQ`，看增长来源是周期还是质量
- 实战案例：159209 前十大里茅台净利 -1.95%（质量股转负）、招商轮船 +219%/中国铝业 +56%（周期顶部）、三七/巨人（游戏高分红但天花板明显）——「质量」一半是周期幻觉一半是下坡起点
- 股息率对比：纯中证红利（515180）5%+ > 红利质量 ~3.5-4%（茅台仅 ~2.1%）——为了质量牺牲股息
- **用户立场**：对红利质量类持怀疑，「财务好看但可能是走下坡路的起点，股息不够高，质量长期无保证」；对比红利类基金时主动做成分股质量检验，不要只报指数估值分位

## 7. 输出范式（用户确认）

- 对比类文章/报告结构：身份卡（指数/成立/规模/风险）→ 业绩（年度 + 阶段表）→ 持仓/行业 → 风险（夏普/回撤/波动）→ 估值分位 → 分红 → 按需求给结论
- 用「图标多、文字少」：表格 + emoji（🟢/🔴/🟡）分级，结论用「一句话」收尾
- 数据来源必须标注（如「数据截至 2026-08-14：基金年报原文 + 东方财富 datacenter + 腾讯行情」）
