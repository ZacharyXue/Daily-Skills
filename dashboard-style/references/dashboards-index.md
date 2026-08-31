# 看板索引（已有哪些看板）

> **总风格/数据规范**：见 `dashboard-style/SKILL.md`（自包含 HTML 骨架 + 数据走 `data-source-router.get()`）。
> **新增看板**：`zach-skills/<name>-dashboard/SKILL.md`（各自 md）+ 注册到本文件 + 复用骨架模板。

| 看板 | 类型 | 实例详情(母纲) | 工程路径 | 数据触发 | 持续更新 | 产物 |
|---|---|---|---|---|---|---|
| **水泥 & 海螺** | 行业+龙头(盈利底) | `industry-monitor-dashboard/references/instances/cement/` (自包含可迁移) | `/root/cement-dashboard` | `cn_cement_index`/`cn_cement_spread`/`cn_financial`/`cn_stock_*` | `cd /root/zach-skills/industry-monitor-dashboard/references/instances/cement && python3 scripts/extract_report.py && python3 scripts/fetch.py && python3 scripts/render_html.py` | `instances/cement/output/cement_dashboard.html` |
| **ETF 技术温度** | ETF(红利+行业/主题) | `industry-monitor-dashboard/references/instances/etf/` (脚本；运行需 ttskill/产物ETF_OUT) | `/root/ZacharyXue.github.io/etf-dashboard` | `cn_stock_quote`/`cn_stock_kline`/`cn_csindex_pe`/`cn_ttfund_index` | `cd /root/ZacharyXue.github.io/etf-dashboard && python3 update.py` | `public/exports/etf-dashboard.html` |
| **人福药业**（财务走势+降本拆解） | 个股(财务+降本) | `industry-monitor-dashboard/references/instances/renfu/` (自包含可迁移) | 同左 | `cn_financial_series`(`report_name=RPT_F10_FINANCE_MAINFINADATA` / `RPT_F10_FINANCE_GINCOME`) — 已下沉 router，**含 `INTEREST_DEBT_RATIO` 有息负债率字段** | `cd /root/zach-skills/industry-monitor-dashboard/references/instances/renfu && python3 scripts/fetch.py && python3 scripts/render_html.py` | `public/exports/renfu-dashboard.html` |
| **白电三巨头**（美的/海尔/格力） | 行业(白电)+三龙头对比 | `industry-monitor-dashboard/references/instances/whitegoods/` (自包含可迁移) | 同左 | `cn_financial_series`(`RPT_F10_FINANCE_MAINFINADATA` + `RPT_F10_FINANCE_GINCOME`)、腾讯行情 `qt.gtimg.cn`、腾讯K线 `ifzq`、东财分红 `RPT_SHAREBONUS_DET` | `cd /root/zach-skills/industry-monitor-dashboard/references/instances/whitegoods && python3 scripts/fetch.py && python3 scripts/render_html.py` | `output/whitegoods_dashboard.html` → 手动 `cp` 到 `public/exports/whitegoods-dashboard.html` |

## 各看板要盯什么（简述）

### cement-dashboard（水泥&海螺 · 盈利底监测）
盯「水泥行业是否从软出清+价格战磨底 → 止跌回稳+吨毛利修复+龙头利润回升」，用于海螺买点确认。
- **价格组**：P.O42.5 全国均价(~278)、CEMPI、熟料、水泥-熟料价差(供给侧代理)、混凝土
- **成本组**：煤价、海螺吨成本(183.5, 成本优势)
- **量组**：全国产量同比(-11.6)、海螺销量同比(-3.96, 龙头抢份额)
- **盈利组**：吨毛利(53.2, 盈利底确认区上沿)、吨售价、吨净利、归母净利、现金流比
- **财务组**：负债率20%、股息率4.66%、货币资金343亿、有息负债率8%、FCF
- **估值/技术**：PB 0.503(分位20%)、均线、MACD/RSI
- 信号：吨毛利 40→55=盈利底确认；PB 分位<20% 低估；P.O42.5 站 300+ 连涨=止跌
- 关联 skill：`stock-analysis`(基本面深挖)、`commodity-equity-rotation`(相对强弱)

### etf-dashboard（ETF 技术温度）
盯红利 + 行业/主题 ETF 的估值分位 + 技术面，交叉给加仓/分批/过热信号。
- 5y PE 分位(中证官网 peg) + 10y PB 分位(天天基金) + 技术面(MA20/BIAS/回撤/N日涨跌)
- 信号：回撤≥15% 且 5y 分位<50% = 加仓；BIAS>10% 或 5y>95% = 过热
- 相关：`data-source-router`(腾讯行情节流)

### renfu-dashboard（人福药业 · 财务走势 + 降本拆解）
盯「人福(600079·ST) 营收收缩下净利靠降本+去杠杆支撑」的真相。
- **快照**：最新一期(中报)营收/归母净利/ROE/负债率/有息负债率
- **四大财务走势(年度)**：营收、ROE、资产负债率、有息负债率（`INTEREST_DEBT_RATIO` 字段）
- **降本拆解**：费用结构占比(销售/管理/研发/财务，最新期 vs 2025年报)、财务费用年度趋势、有息负债率 vs 财务费用双线验证
- 信号：有息负债率 38%→23.8% + 资产负债率 55.8%→40.1% = 去杠杆真实可持续；但营收收缩 =「降本保利润」非「收入扩张」
- ⚠️ 该股现为 ST人福（资金占用/违规风险帽），看板仅跟踪财务健康度，不代表摘帽进度
- 数据源：东财 `RPT_F10_FINANCE_MAINFINADATA`（主财务，含 `INTEREST_DEBT_RATIO`）+ `RPT_F10_FINANCE_GINCOME`（利润表费用）
- 关联 skill：`stock-analysis`(基本面深挖)、`data-source-router`

### whitegoods-dashboard（白电三巨头 · 美的/海尔/格力对比）
盯白电三龙头美的/海尔/格力的横向对比，定位「谁的估值性价比更高 + 谁在趋势/基本面走弱」。
- **核心指标对比总表**：现价/PE/PB/52周位置/近一年/回撤 + 营收/净利/ROE/毛利率/净利率/股息率/市场隐含回报(ROE÷PB)，三家同排
- **财务对比走势**：营收(亿)/ROE%/净利率% 各一张三家对比趋势图（近6年年报）
- **估值股息明细**：每家近5年年报每10股派息、股息率(年度口径)
- 信号：股息率 vs 3% 锚；52周位置<35%=低位；市场隐含回报越低=定价越贵(美的约6% vs 海尔约10%)
- ⚠️ **分红口径坑**：白电普遍「年度大额+中期小额」双分红，股息率基准取**最近年报(12-31期)派息**，绝不用最近一期(如中报预案)算——否则美的会算出 0.58% 的错误股息率
- 数据源：东财 `cn_financial_series`/`RPT_SHAREBONUS_DET` + 腾讯行情/K线
- 关联 skill：`stock-analysis`(基本面深挖)、`investment-mindset`(大师评估)

## 关于数据下沉
- 原始抓取一律走 `data-source-router`（统一源/缓存/重试/Tier）。
- 行业专属源（如中国水泥网 `cn_cement_index`）已下沉到 `data-source-router/adapters/finance.py` + ROUTES，看板只 `get()`。
- 非数据类逻辑（估值分位算法/信号规则/HTML渲染）留在各看板 skill。