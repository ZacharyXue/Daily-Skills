# 伊利股份 (600887) 监测看板

> 等击球点 · 验证 ROE 锚 —— 买入决策用，不是跟踪股价用。

## 目的

伊利 = **好公司、差价格**。不赚成长钱（日本乳业前车之鉴），只等**极端低估击球区（股息>6% ≈ 20 元）赚均值回归**。本看板把"等什么"翻译成可观测指标，**每季财报后对照核一遍**。

## 两个验证信号（买入前提）

1. **正常化 ROE 稳在 17-18%**（账面 20.9% − 原奶成本红利修正）——成本红利退潮后锚不塌
2. **营收端出现真实量价驱动**（液体乳同比转正加速/价格贡献转正）——管我财信号

**否决条件（任一出现即放弃回归逻辑）**：正常化 ROE 跌破 15% 或 净头寸转负。

## 指标线（6 组 18 项）

| 组 | 盯什么 | 当前快照 (2026-09) |
|---|---|---|
| A 估值与击球点 | 现价/52周位置、股息率、PE、合理价 | 26.66 / 62.2% / 5.18% / 16.7x / 合理 22.5-15 |
| B 增长质量 | 营收同比、液体乳量价、四拆、毛利率 | +4.1% / 液体乳Q2 +0.05% / 36.4% |
| C 成本红利一次性 | 生鲜乳价格、正常化ROE | 企稳回升 / 17.9% |
| D 盈利质量 | 账面ROE、核心利润、减值/商誉 | 20.9% / 82.2亿+9% / 商誉剩5.97亿 |
| E 财务健康 | 净头寸、流动比率/有息负债率、财务费用 | 174.4亿 / 0.62/41.6%⚠️ / -5.26亿 |
| F 同行与股东回报 | 伊利vs蒙牛、每股分红/分红率 | 4.1%vs7.8% / 1.38元 / ≥75%承诺 |

## 更新命令（手动，勿 cron）

```bash
cd /root/zach-skills/industry-monitor-dashboard/references/instances/yili
python3 scripts/fetch.py          # 自动：行情/财报/估值（12 项）
python3 scripts/render_html.py    # 渲染
cp output/yili_dashboard.html /root/ZacharyXue.github.io/public/exports/yili-dashboard.html
```

**人工补录 3 项**（每季财报后更新 `scripts/fetch.py` 里 g_segment_milk/g_contrib/g_milk_price）：
- 液体乳 Q2 同比（研报口径）
- 量/价/成本/结构四拆（研报口径）
- 生鲜乳价格趋势（农业农村部/研报）

## 数据源

东财 `cn_financial_series`（MAINFINADATA / GINCOME / GBALANCE）+ 腾讯行情 + 研报口径人工补录，统一走 `data-source-router`。

## 已知坑

- 选渲染：indicators 的 `id` 与 fetch 的 getter 名是两套 key，取数用 getter 名（详见 dashboard-style SKILL 坑位清单）
- 2026中报有息负债率 41.6% > 年报 33.4%（短借 647 亿）——**杠杆在上升，E 组持续盯**
- 相关 skill：`stock-analysis`（Phase 4.5 增长归因+一次性检验）、`investment-mindset`（大师视角）、`dashboard-style`（骨架）