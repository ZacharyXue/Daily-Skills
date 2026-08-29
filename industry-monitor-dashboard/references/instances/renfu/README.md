---
name: renfu-dashboard
description: 人福药业(600079·现名ST人福)财务走势+降本拆解看板 —— 用 data-source-router 的 cn_financial_series(东财 RPT_F10_FINANCE_MAINFINADATA 主财务含INTEREST_DEBT_RATIO有息负债率 + RPT_F10_FINANCE_GINCOME 利润表费用)取数，自包含HTML(快照卡+四大年度走势SVG+降本贡献度条形图/费用占比表/去杠杆双线)。含ST风险提示。触发：用户要「人福/ST人福财务看板」「看营收/ROE/负债率/有息负债率走势」「降本拆解」。
version: 1.1.0
tags: [dashboard, renfu, financial, cost-breakdown, html, 个股, data-source-router]
---

# 人福药业 (ST人福) 财务走势 + 降本拆解看板

「个股财务健康度 + 降本」监测看板，复用 `dashboard-style` 骨架 + 经 `data-source-router` 取东财免费公开源。权威自包含副本 = `industry-monitor-dashboard/references/instances/renfu/`（README + scripts + 数据一体，整体可迁移）。

## 核心结论（看板价值）

营收在收缩(2024→2025 -5.8%，2026中报 -0.0%)，但净利靠 **降本 + 去杠杆** 支撑：
- 有息负债率 36%→22.1%，资产负债率 56%→40.1%（五年降 20 点）
- 财务费用 2019 高点 8.73亿 → 2025 年报 3.03亿（2026中报 2.11亿年化约4亿）——去杠杆红利
- **矛盾点**：不是收入扩张，是典型「降本保利润」。营收未扩张是硬伤。

> ⚠️ 该股现为 **ST人福**(600079)：2026-03 出现「非经营性资金占用」专项审计 + 近五年监管处罚，属资金占用/违规帽（非经营亏损）；定增正推进(2026-08 上交所受理)。看板仅跟踪财务健康度，不代表摘帽进度。

## 运行流水线

```bash
cd /root/zach-skills/industry-monitor-dashboard/references/instances/renfu
python3 scripts/fetch.py        # 经 data-source-router 拉东财 → cache/dashboard_data.json
python3 scripts/render_html.py  # → output/renfu_dashboard.html
# 挂博客：
cp output/renfu_dashboard.html /root/ZacharyXue.github.io/public/exports/renfu-dashboard.html
```

## 数据获取（统一走 data-source-router，勿自建重复抓取）

fetch.py 里 `em_fin(secucode, report_arg)` / `em_stmt(...)` 调 `DSR.get('cn_financial_series', secucode=..., report_name=..., page=...)`。**`cn_financial_series` 已下沉到 router**（`adapters/finance.py` + ROUTES + config TTL 90天），返回东财接口原始 rows(list)，领域逻辑(滤年报/算同比/归因)留在看板。

| 看板需要 | kind | report_name | 关键字段 |
|---|---|---|---|
| 主财务(营收/净利/ROE/负债率/有息负债率) | `cn_financial_series` | `RPT_F10_FINANCE_MAINFINADATA` | `TOTALOPERATEREVE`/`PARENTNETPROFIT`/`ROEJQ`/`ZCFZL`/`INTEREST_DEBT_RATIO`(有息负债率) |
| 利润表(费用拆解/降本) | `cn_financial_series` | `RPT_F10_FINANCE_GINCOME` | `TOTAL_OPERATE_INCOME`/`OPERATE_COST`/`SALE_EXPENSE`/`MANAGE_EXPENSE`/`RESEARCH_EXPENSE`/`FINANCE_EXPENSE`/`FE_INTEREST_EXPENSE` |

- **有息负债率**直接用东财 `INTEREST_DEBT_RATIO` 字段，**不用自己从资产负债表拆分**（水泥实例踩过的手算口径）。
- **营收同比必须重算**：东财 `TOTALOPERATEREVETZ` 有 bug（如 2025年报 显示 -579%，明显错）。`fetch.get_snap`/`_rev_yoy_by_self` 按同报告期累计值重算（2026中报 -0.0%、2025年报 -5.8%）。
- **归母净利同比同样重算**（同月段去年值），别信 `PARENTNETPROFITTZ`。

## 指标设计（indicators.py 注释驱动，id 与 fetch/render 严格对齐）

- **快照组**（`snap_rev/np/roe/debt/idebt`）：最新一期(2026中报)当前值，GETTER 全调 `get_snap()`（返回同一完整 dict）。
- **走势组**（`trend_rev/roe/debt/idebt`）：年度 SVG 趋势，各 GETTER 独立。
- **降本拆解组**：`cost_struct_latest`(费用占比,最新期 vs 2025年报)、`fin_expense`(财务费用年度)、`idebt_vs_fin`(有息负债率 vs 财务费用双线)、`contrib_breakdown`(降本贡献度拆解:每+1元净利增量从哪来)。

## 降本拆解设计（动态取数为主 + 中报披露明细补充）

① **贡献度条形图** `contrib_breakdown`：2026中报 vs 2025中报，归母净利 +1.75亿。营业成本 -2.39亿(+137%)/研发 -1.03亿(+59%)/管理 -0.63亿(+36%) 是贡献(绿)，销售 +1.41亿(-81%)/财务 +0.90亿(-52%) 是拖累(红)。数值 = 费用变化的相反数(费用降=+贡献)；条形图符号用「利润贡献 pc」的符号，不是费用变化符号。
② **费用结构占比表** `cost_struct_latest`：销售/管理/研发/财务费用率 + 营业成本率，最新期 vs 2025年报。财务费用率最低(1.8%)是去杠杆红利。
③ **财务费用年度** `fin_expense`：2019 8.73亿→2024 3.5亿→2025 3.03亿。
④ **去杠杆双线** `idebt_vs_fin`：有息负债率 vs 财务费用同向下行，互证去杠杆真实可持续。**只显示近5年(2021-2025)**（`_series_of(...)[-5:]`，避免2016年起的长序列稀释视线）。
⑤ **研发费用明细表**（中报披露，非自动接口）：职工薪酬3.09/3.05亿、耗用材料0.62/1.33亿、临床试验费2.38/2.44亿、其他直接费0.60/0.88亿；资本化0.83<0.88亿→证明不是费用转资本化美化。
⑥ **可持续性判断表**：营业成本[强]/管理[中]/研发[弱]/销售财务[弱]——毛利(高毛利工业占比↑)可持续、管理是组织红利有天花板、研发不可复制、营收未扩张是硬伤。

> ⚠️ ⑤⑥ 是**公司中报附注披露**的明细（真实、可溯源），非东财自动接口字段。渲染时必须标注「来源：公司中报披露（非自动接口）」。用户明确要求保留这两块（研发明细是「降本拆解重中之重」），不要因「动态取数」原则删掉。

## Pitfalls（本会话重新踩过，排列按重要性）

- **id 必须与 fetch/render 三方对齐**：indicators.py 的 id 是 `snap_rev`/`cost_struct_latest`(不是 `snap`/`cost_struct`)，fetch GETTER_MAP 用 getter 名(`snap`/`cost_struct`)，render 取 value 用 **indicator 的 id**。取错 `v("cost_struct")` 会得到空 dict → 渲染显示"费用数据缺失"。README 里子 agent 曾记过，但仍易踩。
- **`_series_of` 必须按年份升序**：东财返回按 REPORT_DATE 倒序(最新在前)，不 sort 时取 `points[-1]` 拿到的是**最早**(2006年报)，导致 `latest_date` 显示"2006年报"、latest=0.52 这种错误。`out.sort(key=lambda x: x["d"])` 后 `[-1]`=最新。
- **营收同比别信东财字段**：`TOTALOPERATEREVETZ` 有 bug(2025年报=-579%)。必须重算。
- **`extract_report` 口径**：中报=上半年累计，同比要与去年同报告期(月段)比，别跟全年比。
- **ST 股估值失真**：PB/技术面参考价值低，本看板主作财务健康度跟踪，估值闸门慎用。
- **hardcode 明细仅限「公司定期报告披露」字段**：研发职工薪酬/耗用材料拆分、资本化金额等东财 GINCOME 接口取不到，但若是**公司中报/年报附注披露**（真实、可溯源），可写进 HTML，必须在卡片标注「来源：公司中报披露（非自动接口）」。**绝不能**凭空捏造或把外部猜测写成数据——数据正确性铁律的底线是「不编造」，中报披露的明细是真实数据不违反；只有捏造与凭空冒充实测数据才违规。曾有一次因「动态取数」原则误删中报披露的研发明细（子agent），用户明确要求保留。

## 验证工具

无头浏览器截图核验（数值注入 + 排版）：
```bash
/root/hermes-venv/chrome/linux-152.0.7977.42/chrome-linux64/chrome --no-sandbox --headless --disable-gpu --window-size=980,3400 --screenshot=/tmp/x.png file://.../output/renfu_dashboard.html
# 然后 vision_analyze /tmp/x.png 检查数值+排版
```

## 关系

复用 `dashboard-style`（风格/骨架/索引）、`data-source-router`（统一取数 `cn_financial_series`）。`stock-analysis` 可对同一标的做基本面深挖。同类看板：`cement-dashboard`(行业+龙头盈利底)、`etf-dashboard`(ETF估值+技术)——均走 data-source-router 取数 + dashboard-style 模板。
