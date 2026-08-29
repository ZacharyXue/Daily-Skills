---
name: renfu-dashboard
description: 人福药业(600079·现名ST人福)财务走势+降本拆解看板 —— 东财主财务(RPT_F10_FINANCE_MAINFINADATA,含INTEREST_DEBT_RATIO有息负债率)+利润表(RPT_F10_FINANCE_GINCOME费用)，自包含HTML(快照卡+四大年度走势SVG+降本拆解表/双线验证)。含ST风险提示。触发：用户要「人福/ST人福财务看板」「看营收/ROE/负债率/有息负债率走势」「降本拆解」。
version: 1.0.0
tags: [dashboard, renfu, financial, cost-breakdown, html, 个股]
---

# 人福药业 (ST人福) 财务走势 + 降本拆解看板

「个股财务健康度 + 降本」监测看板，复用 `dashboard-style` 骨架 + 东财免费公开源。权威自包含副本 = `industry-monitor-dashboard/references/instances/renfu/`（README + scripts + 数据一体，整体可迁移）。

## 核心结论（看板价值）
营收在收缩(2024→2025 -5.8%)，但净利靠 **降本 + 去杠杆** 支撑：
- 有息负债率 38%→23.8%，资产负债率 55.8%→40.1%（五年降 20 点）
- 财务费用 2025年报 3.03亿（其中利息费用 2.71亿）
- **矛盾点**：不是收入扩张，是典型「降本保利润」。

> ⚠️ 该股现为 **ST人福**(600079)：2026-03 出现「非经营性资金占用」专项审计 + 近五年监管处罚，属资金占用/违规帽（非经营亏损）；定增正推进(2026-08 上交所受理)。看板仅跟踪财务健康度，不代表摘帽进度。

## 运行流水线
```bash
cd /root/zach-skills/industry-monitor-dashboard/references/instances/renfu
python3 scripts/fetch.py        # 拉东财 → cache/dashboard_data.json
python3 scripts/render_html.py  # → output/renfu_dashboard.html
# 挂博客：
cp output/renfu_dashboard.html /root/ZacharyXue.github.io/public/exports/renfu-dashboard.html
```

## 数据源速查（本机实测）
| 需求 | 接口 | 字段 | 状态 |
|---|---|---|---|
| 主财务(营收/净利/ROE/负债率/有息负债率) | 东财 `RPT_F10_FINANCE_MAINFINADATA` | `TOTALOPERATEREVE`/`PARENTNETPROFIT`/`ROEJQ`/`ZCFZL`/**`INTEREST_DEBT_RATIO`** | ✅ |
| 利润表(费用拆解) | 东财 `RPT_F10_FINANCE_GINCOME` | `TOTAL_OPERATE_INCOME`/`OPERATE_COST`/`SALE_EXPENSE`/`MANAGE_EXPENSE`/`RESEARCH_EXPENSE`/`FINANCE_EXPENSE`/`FE_INTEREST_EXPENSE` | ✅ |
| 行情/估值 | 腾讯 `qt.gtimg.cn`（未启用） | — | 可选 |

主财务接口直接带 `INTEREST_DEBT_RATIO`（有息负债率），**不用自己从资产负债表拆分**。报告期用 `REPORT_DATE_NAME`（如"2026中报"），趋势只取「年报」点避免半年轴抖动。

## 指标设计（indicators.py 注释驱动）
- **快照组**：snap_rev/np/roe/debt/idebt —— 最新一期(中报)当前值，GETTER 全调 `get_snap()`（返回同一完整 dict）。
- **走势组**：trend_rev/roe/debt/idebt —— 年度SVG趋势；各 GETTER 独立。
- **降本拆解组**：cost_struct_latest（费用占比表 + 2025年报对比）、fin_expense（财务费用年度）、idebt_vs_fin（有息负债率 vs 财务费用双线）。

## Pitfalls（本会话踩过）
- **`urllib.request` 未导入**：fetch.py 用 `_get()` 需 `import urllib.request`，漏了会报 `name 'urllib' is not defined`（脚本顶部补上）。
- **`_series()` 的 `filt` 语义是「跳过」**：传 `filt=lambda x: True` 会过滤掉全部 → 点数=0。不需过滤就**别传 filt**。
- **`_series(scale=1e8)` 已做单位换算**：外层**别再除一次** 1e8，否则数值变 0.0 或极小（财务费用字段踩过）。
- **字段口径易混**：`FINANCE_EXPENSE`(财务费用)≠`FE_INTEREST_EXPENSE`(利息费用)。人福 2025年报 财务费=3.03亿、利息费=2.71亿。写文案要分开，别混用。
- **render 里取 value 用实际 indicator id**：id 是 `snap_rev` 不是 `snap`，`cost_struct_latest` 不是 `cost_struct`；取错 key 会得到空 dict（卡片数值全 MISS）。
- **`fnum` 默认1位小数**：ROE/负债率/有息负债率/财务费用这类精度敏感值要用 `fnum(x, 2)`，否则 6.82 被截成 6.8。
- **趋势图空点**：`trend_ref` 先 `_series` 再过滤「年报」，若某字段当年无值会少点，渲染时需容错（len<2 不画）。

## 验证工具
- 无头浏览器截图：`/root/hermes-venv/chrome/linux-152.0.7977.42/chrome-linux64/chrome --no-sandbox --headless --disable-gpu --screenshot=/tmp/x.png --window-size=980,2400 file://.../output/renfu_dashboard.html`
- 截图后 `vision_analyze` 检查数值注入 + 排版。

## 关系
复用 `dashboard-style`（风格/骨架/索引）、`data-source-router`（统一取数——目前 renfu 用东财 raw API，因 router 的 `cn_financial` 仅返回单条最新、无完整历史序列与 `INTEREST_DEBT_RATIO` 字段；如需下沉可加 `cn_financial_series` kind）。`stock-analysis` 可对同一标的做基本面深挖。
