# 白电三巨头看板（美的 / 海尔 / 格力）

三家白电龙头的**横向对比监测看板**。定位：一眼看清三家核心财务、估值、行情、股息的当前值，并给出「谁便宜 / 谁走弱 / 谁质量高」的信号。

## 为什么盯这个
- 白电是「用不死的刚需生意」，但三家分化明显：**美的**质量最贵(PE 14.8/隐含回报6%)、**海尔**便宜但中报净利承压(-14%，需辨汇兑假摔 vs 趋势)、**格力**最便宜股息最高(PE 7.8/股息5.1%)。
- 共同变量：海外占比带来的关税/汇率（海尔52%最重）+ 国内地产链 + 铜铝原材料。

## 指标清单（meaning/signal 语义放渲染层可点击展开）

| 组 | 指标 | 信号 |
|---|---|---|
| 核心总表 | 现价/PE/PB/52周位置/近一年/最大回撤 | 52周位置<35%=低位，70%+=高位 |
| 财务 | 营收/归母净利/同比/ROE/毛利率/净利率/有息负债率 | ROE 稳住=便宜是机会，下滑=陷阱 |
| 估值 | 股息率/市场隐含回报(ROE÷PB) | 隐含回报低=定价贵、高=便宜 |
| 走势 | 营收(亿)/ROE%/净利率% × 三家对比趋势 | 看谁在趋势走高/走弱 |

## 工程
```
instances/whitegoods/
├── scripts/fetch.py       # 循环3家：财务序列 + 腾讯行情 + K线位置 + 东财分红 → cache/dashboard_data.json
├── scripts/render_html.py # 三家对比总表 + 每指标三家对比趋势图 → output/whitegoods_dashboard.html
└── output/whitegoods_dashboard.html
```

## 更新命令（手动，勿设 cron 定时）
```bash
cd /root/zach-skills/industry-monitor-dashboard/references/instances/whitegoods
python3 scripts/fetch.py
python3 scripts/render_html.py
# 发布到博客：
cp output/whitegoods_dashboard.html /root/ZacharyXue.github.io/public/exports/whitegoods-dashboard.html
```

## 数据源（全部免费公开，走 data-source-router / 腾讯直连）
| 数据 | 源 |
|---|---|
| 财务序列 | 东财 datacenter `RPT_F10_FINANCE_MAINFINADATA`（经 router `cn_financial_series`）|
| 行情 | 腾讯 `qt.gtimg.cn`（现价/PE/PB/市值）|
| K线/52周位置/回撤 | 腾讯 `web.ifzq.gtimg.cn` |
| 分红 | 东财 `RPT_SHAREBONUS_DET` |

## Pitfalls（本实例踩过）
- ⚠️ **分红口径**：白电普遍「年度大额+中期小额」双分红。股息率基准取**最近年报(12-31期)派息**，绝不用最近一期(如2026中报预案派5)算——否则美的会算出 0.58% 的错误股息率(实为4.41%)。
- **苏州数据口径**：52周位置/回撤基于日线自算(近250交易日)，非行情直读。
- **表格超出宽屏**：核心总表15列，必须包 `.table-wrap`(overflow-x:auto) +表格 min-width 840px，否则移动端撑破页面。
- **财务走势对比**：每指标一张三家对比图，三家年报序列 x 轴一致(如"2023年报")，需按指标分组重组(从每家 tr.charts 提取同名序列)。

## 关联
- `stock-analysis`：个股基本面深挖（含 ROIC/Gordon 安全边际、汇率假摔识别）
- `investment-mindset`：把三家对比结果做大师五维评估
- `dashboard-style`：共享 HTML 骨架 + 看板索引