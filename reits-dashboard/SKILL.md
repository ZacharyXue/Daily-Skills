---
name: reits-dashboard
description: 保租房 REITs 看板 — 全量保租房 REITs 的分派率/P-NAV/出租率/回撤/收缴率五项「历史区间+当前位置」，数据来自定期报告原文 PDF。触发：用户说更新保租房REITs看板/季报出来了刷新/REITs有没有性价比。
version: 1.0.0
tags: [dashboard, reits, 保租房, 分红, 估值]
related_skills: [dashboard-style, data-source-router, stock-analysis]
---

# reits-dashboard — 保租房 REITs 看板

## 为什么盯这个

用户 2026-09 定：**REITs 只看保租房这一类**——「保租房生意最简单」（C 端刚需租金、需求刚性、无到期日、政策支持），
不再做全市场横向（产业园/仓储是 B 端市场租金，波动来源完全不同，不适合放一起比）。

看板的定位是**给位置、不给结论**（用户明确要求）：
每个维度都摊开「历史区间 + 当前位置 + 参考线」，让用户自己判断贵不贵，而不是一句"有性价比/没有"。

## 五项位置（核心）

| # | 指标 | 算法 | 参考线 |
|---|---|---|---|
| ① | 现金分派率 | 报告期单位可供分配金额 ÷ 报告期天数 × 365 ÷ **报告期末收盘价** | LPR 1 年期（息差越厚越好） |
| ② | P/NAV | 现价 ÷ 最新披露「基金份额净值」 | 1.0（净值） |
| ③ | 出租率 | 报告期末各不动产项目出租率平均 | 95% |
| ④ | 距近 1 年最高价回撤 | 现价 ÷ 近 365 天最高收盘 − 1 | −30% ~ 0 固定标尺 |
| ⑤ | 租金收缴率 | 报告期末实收/应收 ×100% | 95% |

卡片内附加：加权平均剩余租期、TTM 实际到手派息率、近 1 年含分红回报、逐期原始数据表。

## 覆盖范围（自动全量）

1. 枚举行情源 `sh508000-508999` / `sz180000-180999` 批量探测 → 全市场 REITs 清单（当前 101 只）
2. 名称关键词筛保租房：`租赁住房 / 保障房 / 保租房 / 安居 / 有巢 / 宽庭 / 恒泰 / 宁巢 / 昌保 / 人才公寓 / 青年公寓`
3. **新上市自动纳入**；尚无定期报告的新基金显式显示「待披露」而不是隐藏

> 用户要求「每次都要拉最新全量」——所以 fetch 每次都重新探测，不写死代码列表。

## 更新命令

```bash
cd /root/zach-skills/reits-dashboard
/root/hermes-venv/bin/python scripts/fetch.py          # 走 DSR 缓存，快
/root/hermes-venv/bin/python scripts/fetch.py --force  # 季报披露后强制回源
python3 scripts/render_html.py
cp output/reits_bt_dashboard.html /root/ZacharyXue.github.io/public/exports/reits-bt-dashboard.html
```

⚠️ **必须用 `/root/hermes-venv/bin/python` 跑 fetch.py**：PDF 解析依赖 pymupdf，系统 python3 没有。
（render_html.py 只用标准库，任意 python3 均可。）

**季报披露节点**：Q1 4/22 前后、中报 8/31 前后、Q3 10/底、年报 3/底 → 用户会在这几个时点触发「更新保租房看板」。

## 数据源（全部走 data-source-router）

| kind | 用途 | 适配器 |
|---|---|---|
| `cn_reits_list` | 全市场 REITs 清单（腾讯行情枚举） | `adapters/reits.py` |
| `cn_reits_report_list` | 定期报告清单（东财基金公告 JJGG） | 同上 |
| `cn_reits_report_data` | 单份报告解析（PDF → 指标） | 同上 |
| `cn_reits_dividend` | 已宣告分红记录（天天基金 F10） | 同上 |
| `cn_stock_kline` | 日K（前复权，回撤/波动） | `adapters/finance.py` |

PDF 落盘 `~/.hermes/dsr-reits/pdf/`，解析结果缓存 `~/.hermes/dsr-reits/parsed.json`
（已预置 2022 年至今 142 期；新报告只在首次抓取时慢，之后秒回）。

## 口径与坑（实测踩过）

1. **净值只有半年频**：REITs 只在**中报/年报**披露「基金份额净值」，季报没有 → P/NAV 曲线是半年一个点。
   想更密只能拿季报的净资产自己算，但那已经不是官方披露口径，看板不做。
2. **三代披露格式**（解析器已兼容）：
   - 2022–2023：叙述式，「文龙家园项目…出租率为97.70%」，净值字段叫「期末**基金**份额净值」，**不分派率**
   - 2024–2025：表格式，「3报告期末出租率[…]×100%%94.07」，字段加「不动产」前缀，开始披露「年化现金流分派率（%）」
   - 2025+：「本报告期的可供分配金额」表（旧版是「本报告期及近三年的可供分配金额」），分派率写成「年化现金流分派率2.76%」（无括号）
3. **数字连写的正则坑**：PDF 表格清理换行后 `%%94.0795.17` 这种两个数字连在一起，
   `([\d\.]+)` 会贪婪吃成 `92.4992.65` → 必须用 `(\d{1,3}\.\d{1,2})` 精确两位小数。
4. **报告期末日可能是非交易日**（如 12-31 周六）→ 取「≤ 期末日的最近交易日」收盘价。
5. **上市未满一年**的基金（报告期 <3）年化派息率被首期口径放大（中航北京昌保显示 14%+），
   看板标 `*` 并加 warn 徽章，**不要据此判断性价比**。
6. **同一 period_end 有两份报告**（如 Q2 报 + 中报都截止 6/30）→ 去重时优先中报/年报（覆盖期更长）。

## 与其他 skill 的分工

- 取数/缓存/重试 → `data-source-router`（本 skill 只触发 kind）
- HTML 骨架/风格 → `dashboard-style`
- 单只 REIT 背后的资产质量深挖 → `stock-analysis`
- 看板索引注册：`dashboard-style/references/dashboards-index.md` + 博客 `src/content/projects/investment-dashboard.md`
