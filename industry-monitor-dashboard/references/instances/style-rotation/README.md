---
name: style-rotation-dashboard
description: 成长 vs 价值 风格轮动 + 配置比例看板 — 国证成长100(980080/易方达成长ETF 159259) vs 国证价值100(980081/易方达价值ETF 159263)。含估值/ROE/PE十年分位、行业分布、技术温度、以及可落地的配置比例引擎(权重偏移式, 非二值切换)。生成自包含HTML落博客。触发：用户说「更新成长价值看板」「成长价值怎么配置」「跑配置比例引擎」。
version: 2.0.0
tags: [风格轮动, 成长价值, 配置比例, 引擎, 看板]
---

# 成长 vs 价值 · 风格轮动 & 配置比例 看板

国证成长100(980080) vs 国证价值100(980081) 的风格监测 + 配置比例引擎。

- **成长** = 国证成长100(980080)，易方达成长ETF 159259
- **价值** = 国证价值100(980081)，易方达价值ETF 159263

⚠️ **指数代码纠正（2026-09-04）**：之前 CAR-z 回测误用 sz399357/sz399371 当成长/价值（实为环渤海/1000价值），**该回测结论作废**。真实代码：
  成长100=**980080**、价值100=**980081**（TTFUND index_profile.index_code 确认，点 12201/4541）。成长100 位点远高于 399357，证明此前的回测用了错误标的。

## 为什么做（调研结论）

配置比例**不该**靠动量/估值单信号二值切换（CAR-z 回测 + tradethepool 皆证伪动量切换）。有效驱动分层：
1. **盈利增速差**(成长-价值净利同比) —— 第一性，广发「短期风格看增速差」
2. **ROE 中枢差** —— 长期风格锚，「长期风格看 ROE 中枢」
3. **估值价差**(成长PE10y分位-价值) + **行业拥挤度** —— 安全边际(必要条件非充分)
4. **宏观**(10Y利率方向/PMI) —— 方向闸门，防误切(本看板暂未接, 留接口)
5. 温和动量 —— 仅极端预警，权重最低

**引擎算法**：基准50/50 → 各信号加权偏移(权重 roe.30/val.25/growth.25/crowd.12/mom.08) → 限幅[40%,70%] → **信号并聚** (净同向≥2 才明显偏移, 否则收敛±12pt) → 不做二值切换。输出成长配置权重% + 每信号读数/方向(可追溯)。

## 代码位置

- **工程**：`/root/zach-skills/industry-monitor-dashboard/references/instances/style-rotation/`
  - `scripts/fetch.py` — 取数(TTFUND估值/ROE/行业分布 + 腾讯ETF K线技术温度) → cache/dashboard_data.json
  - `scripts/engine.py` — **配置比例引擎**(纯函数, 可单测)
  - `scripts/render_html.py` — HTML 渲染(自包含)
  - `scripts/growth_precompute.py` — 盈利增速差预计算(成分等权聚合净利/营收同比, 月度后台跑)
- **产物**：`output/style-rotation-dashboard.html` → `/root/ZacharyXue.github.io/public/exports/`

## 更新流程（手动，偏好看板不设cron）

```bash
cd /root/zach-skills/industry-monitor-dashboard/references/instances/style-rotation
# (可选, 盈利增速差第一性信号, 约1分钟/月度)
/root/hermes-venv/bin/python scripts/growth_precompute.py
python3 scripts/fetch.py         # 取数 + 引擎 → cache/dashboard_data.json
python3 scripts/render_html.py   # → output/style-rotation-dashboard.html
cp output/style-rotation-dashboard.html /root/ZacharyXue.github.io/public/exports/
cd /root/ZacharyXue.github.io && git add public/exports/style-rotation-dashboard.html && git commit -m "update style rotation dashboard $(date +%F)"
# push 由用户定(默认只commit)
```

## 数据源

| 数据 | 源 | 说明 |
|------|----|------|
| 估值/ROE/PE/PB十年分位 | 天天基金 TTFUND_INDEX_INFO(index_id=成长100/价值100) | 已下沉 router `cn_ttfund_index`(现含行业分布+多期收益) |
| 行业分布 | TTFUND composition.top_industries | 电子58%(成长) vs 银行36%+家电22%(价值), 带权重/年内涨跌 |
| 多期收益/点位/YTD | TTFUND quote+performance | — |
| 技术温度(MA20/BIAS/回撤) | 腾讯 ETF K线(159259/159263) | ⚠️次新ETF历史短(~1年), 仅短期温度 |
| 盈利增速差 | 成分等权聚合(东财财务序列, 重算同比) | growth_precompute.py |

## 引擎输入/输出

输入 growth/value 各: roe, pe_ttm, pe_pct_10y, top_industries, return_6m(可省)。输出:
`{growth_w_pct, value_w_pct, bias_pts, signals, directions, confluence, caveats}`。

**当前读数(2026-09-03)**：ROE差+2.5pp(成长11.0 vs 价值8.5)、PE比5.9x、PE分位差-1.6pp、行业拥挤度 电子58% → 引擎给 成长47~50% / 价值50~53%（信号并聚不足自动收敛，偏价值为主）。

## 坑位

- **指数K线不可得**：国证980080/980081 在腾讯/新浪无K线(返回空)。技术温度只能用**次新ETF**K线；估值/基本面用 TTFUND(指数口径足矣)。别再去腾讯要 9800xx K线。
- **指数代码**：成长100=980080、价值100=980081。勿用 399357/399371(是环渤海/1000价值, 之前回测的错源)。
- **盈利同比必须重算**：东财 TOTALOPERATEREVETZ/PARENTNETPROFITTZ 有 bug，一律 "同报告期累计÷去年同报告期−1"。同报告期=按 中报/年报/季报 类型归类，跨年同季归一组。
- **TTFUND 缓存**：cn_ttfund_index 改了解析器后旧缓存不失效(缓存键只含params)。要刷新需清 ~/.hermes/data-cache.db 的 `T1:ttfund:cn_ttfund_index` 行。
- **引擎不二值切换**：成长大时代别靠动量反复下车(已证伪)；估值高≠切换，须盈利增速差配合(第一性)。
- **行业权重是自由流通口径**：FREEMV_RATIO。拥挤度看前3行业占比。

## 关系 & 统一
- 复用 dashboard-style 骨架 + data-source-router（cn_ttfund_index 已扩展行业分布）。
- 已注册 dashboards-index.md。总纲 industry-monitor-dashboard。