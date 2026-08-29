---
name: cement-dashboard
description: 水泥行业 & 海螺水泥(600585/00914) 盈利底监测看板 —— 判断水泥行业是否从「软出清+价格战磨底」走向「止跌回稳+吨毛利修复+龙头利润回升」，用于海螺买点确认。工程 /root/cement-dashboard。触发：「更新水泥看板」「水泥现状」「海螺止跌了吗」「跑水泥看板」。
version: 1.0.0
tags: [dashboard, cement, 海螺, 行业, stock, 盈利底]
related_skills: [dashboard-style, data-source-router, stock-analysis, commodity-equity-rotation]
---

# 水泥 & 海螺 盈利底监测看板（cement-dashboard）

盯「**量价 → 成本 → 吨毛利 → 利润 → 估值**」链条，判断水泥行业是否从「硬出清磨底」转向「止跌回稳、龙头利润回升」。**用于海螺买点确认**。

## 工程与产物
- **工程**：/root/cement-dashboard/（git 管理，每改动一 commit）
  - `scripts/indicators.py` — 指标元数据层（每指标 `meaning`/`signal`/`source`/`ttl`，注释驱动）
  - `scripts/fetch.py` — 取数（**数据走 data-source-router.get()**，远程优先+失败诚实+人工补录）
  - `scripts/render_html.py` — 渲染自包含 HTML（复用 `dashboard-style/templates`）
  - `scripts/extract_report.py` — 海螺中报/年报 PDF 自动提取（吨毛利/吨成本/销量/分红）
  - `cache/` 数据；`prompts/collect_prompts.md` 采集清单
- **产物**：`/root/cement-dashboard/output/cement_dashboard.html`（可挂博客 public/exports/）

## 更新（手动/可 cron）
> **代码位置**：`industry-monitor-dashboard/references/instances/cement/code`（软链 `/root/cement-dashboard`，git 管理）。触发时按此路径找代码。
```bash
cd /root/zach-skills/industry-monitor-dashboard/references/instances/cement/code
python3 scripts/extract_report.py   # 财报期跑一次(提取吨数据+分红)
python3 scripts/fetch.py            # 拉全部指标(走 data-source-router)
python3 scripts/render_html.py      # 生成 HTML
```

## 指标清单（7 组 · 各 meaning/signal 见 indicators.py，渲染时点击展开）
| 组 | 指标 | 当前读数(2026H1) | 信号 |
|---|---|---|---|
| 价格 | P.O42.5 全国/CEMPI/熟料/价差/混凝土 | 278/-12.8% 未止跌 | 站300+连涨=止跌 |
| 成本 | 煤价指数/海螺吨成本 | 吨成本183.5(<230 优势) | 吨成本≤230=成本优势 |
| 量 | 全国产量同比/海螺销量同比 | 全国-11.6% vs 海螺-3.96% | 海螺份额提升=龙头抢份额 |
| 盈利 | 吨毛利/吨售价/吨净利/归母净利/现金流比 | 吨毛利53.2(盈利底区上沿) | 40→55=底确认;55-70=反转 |
| 财务 | 负债率/股息率/货币资金/有息负债率/FCF | 负债20%、股息4.66% | 低杠杆现金奶牛 |
| 估值技术 | PB分位/均线/MACD/RSI | PB0.503(近250日分位20%) | 分位<20%低估 |
| 量(供给) | 水泥-熟料价差(供给侧代理) | 38.4 | 价差走扩=盈利弹性 |

## 七维达标计数（摘要区）
价格/成本/量/供给/盈利/财务/估值 7 类，`≥5 类达标` 触发加仓讨论、`<3 类` 继续磨底。当前 **2/7**（成本/财务达标），=「价格未止跌、行业未反转」。

## 数据获取（走 data-source-router）
```python
import sys; sys.path.insert(0, "/root/zach-skills/data-source-router")
import data_router as DSR
d,s,m,t = DSR.get("cn_cement_index", index_type="po425")   # 中国水泥网价格/成本
d,s,m,t = DSR.get("cn_cement_spread")                       # 水泥-熟料价差
d,s,m,t = DSR.get("cn_financial", code="600585")            # 东财财报
```
> 中国水泥网已下沉到 `data-source-router/adapters/finance.py`（cn_cement_index/spread）；行情/K线走 `cn_stock_quote`/`cn_stock_kline`。

## 关键判断逻辑（user 定调）
- **需求周期股 ≠ 价格周期股**：水泥价格中枢随地产需求永久下移（参考日本30年阴跌），不要套「跌了会回中枢」的老经验。用 **净资产打折 + ROE 锚定**：海螺年化ROE≈2.6%，合理PB≈ROE/要求回报≈0.37，市场给0.50(含骨料/海外/现金)已算不贵，但非便宜，是「永恒下行」基准。
- **区分两类周期**：价格周期股(铝/煤)跌到成本线停产出清、价格回中枢；需求周期股(水泥)只下不回。
- **龙头抢份额信号**：海螺销量同比(-3.96%) ≫ 全国产量同比(-11.6%) = 行业出清中龙头份额提升（CR10 上行早期信号）。
- 买点 = 价格止跌(P.O42.5 站稳300+连涨) + 吨毛利走扩(40→55+) + 全国产量降幅收窄 三者共振。

## 关联
- `dashboard-style`：HTML 骨架/样式 + 数据规范（复用）
- `data-source-router`：统一取数层（数据已下沉）
- `stock-analysis`：个股基本面深挖（同行对比/估值/芒格评估）
- `commodity-equity-rotation`：相对强弱择时（商品股 vs 商品）
- 方法论总纲：`industry-monitor-dashboard`（行业+龙头看板的通用架构）
