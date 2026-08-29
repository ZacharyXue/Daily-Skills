---
name: dashboard-style
description: 看板统一的 HTML 风格/模板 + 数据规范 + 看板索引。所有看板(行业/ETF/个股)共享这个自包含 HTML 骨架/样式(可点击折叠说明、多线SVG趋势图、批量表格、摘要达标徽章)；数据获取一律走 data-source-router.get()(只触发 kind，具体数据/脚本在 data-source-router)。触发：要做新看板、复用看板样式/模板、查询已有哪些看板。
version: 1.0.0
tags: [dashboard, style, template, html, data-router]
---

# 看板风格 & 数据规范（dashboard）

把所有「监测看板」统一到一套**共享的 HTML 风格 + 数据规范**。各看板（行业+龙头、ETF、个股）是**各自的 md/skill**，但**复用同一个 HTML 骨架样式**和**同一个数据层（data-source-router）**。

## 一、原则（所有看板通用）

1. **产物 = 自包含单文件 HTML**（内嵌 CSS/JS，无外部依赖），可直接挂 Astro 博客 `public/exports/`。
2. **注释驱动**：指标语义（`meaning` 为什么关注 / `signal` 看什么信号）放**元数据配置层**（如 `indicators.py`），渲染时动态展为**可点击折叠**（`<details>/<summary>`），**不占 skill/看板上下文 token**。
3. **数据正确性 > 及时性**（用户强要求）：远程失败 → 标「获取失败」+ 原因；**绝不拿旧值/缓存冒充当前值**；每个指标带 `source / fetched_at / latest_date / TTL` 明示。旧值仅作「上次成功@日期（非当前，仅参考）」在展开区展示。
4. **免费源偶发单次丢包 ≠ 源坏/限频**：超时后立即重试通常即恢复（实测连续 6/6 成功）。对策 = **短超时(约14s) + 重试3次**。别因一次超时判死源，也别留着"XX接口坏了"的负面断言。
5. **数据获取统一走 `data-source-router.get(kind, ...)`** —— 看板 skill 只**触发**取数（调 get），**具体的源/脚本/缓存/重试在 data-source-router**。看板不要自建 curl 重复造轮子。

## 二、数据触发规范（走 data-source-router）

看板取数一律：
```python
import sys; sys.path.insert(0, "/root/zach-skills/data-source-router")
import data_router as DSR
d, source, meta, tier = DSR.get("<kind>", **params)   # 返回 (data, source, meta, tier)
```
| 看板需要 | 用 kind | 参数 |
|---|---|---|
| 行情/K线/财报/宏观 | `cn_stock_quote` / `cn_stock_kline` / `cn_financial` / ... | symbol/code/cik |
| 行业指数(水泥网) | `cn_cement_index` | index_type=po425/cempi/coal/clinker/concrete |
| 水泥-熟料价差 | `cn_cement_spread` | — |

> 新增数据种类 → 下沉到 `data-source-router`（适配器 + ROUTES + config），看板只加一个 `DSR.get(kind)`，不重复探索。看板专属源需在 `references/dashboards-index.md` 里标注并考虑下沉。

## 三、样式索引（HTML 模板在哪）

- **主模板**：`templates/dashboard_skeleton.html`（自包含骨架：CSS + details 折叠卡片 + 多线 SVG 趋势图 + 批量表格 + 摘要达标徽章 + 来源/时间/TTL 元数据行）。复制它改数据即可。
- **完整参考实现**：`industry-monitor-dashboard/references/instances/cement/scripts/render_html.py`（水泥看板渲染，含样式细节与 signal/meaning 的展开逻辑）；ETF 参考 `instances/etf/generate_html.py`。
- **样式要点**（亮色、响应式、卡片式）：
  - 顶部摘要区：一句话结论（达标计数）+ 七维 ✓/✗ 徽章（价格/成本/量/供给/盈利/财务/估值）
  - 每个指标 = 一张 `<details>` 卡片：主行 = 指标名 + 当前值 + 状态徽章(正常/获取失败/人工/接入中)；点开 = 「为什么关注 / 看什么信号 / 来源(链接) / 更新时间 / TTL / 数据日期」+ 趋势 SVG
  - 趋势图 = **内嵌多线 SVG + 图例**（自包含，可挂博客）；月/单点指标也可补历史序列画趋势
  - 同行对比 = 批量表格（海螺等龙头高亮）；支持 `YYYY-MM` 月份日期
  - 人工补录指标 = 徽章「人工」+ 来源「人工录入@日期」，并醒目标注非当前

## 四、已有看板索引

见 `references/dashboards-index.md`（水泥、ETF，各自的 skill/工程路径/更新命令/产物位置）。

## 五、新增一个看板的流程

1. 建 `zach-skills/<name>-dashboard/`（各自 md）：SKILL.md 写「为什么盯、指标清单(meaning/signal)、信号阈值、更新命令、数据源」。
2. 工程 `fetch.py` 走 `data-source-router.get()`；`render_html.py` 复用 `templates/dashboard_skeleton.html`；指标语义放 `indicators.py` 元数据层。
3. 注册进 `references/dashboards-index.md`。
4. 生成产物 → 挂博客 `public/exports/`。

## 六、坑位（会话沉淀）

- **A股财报公告标题**：`"年度报告" in title` 会误配「半年度报告」（子串）→ 显式 `"半年度" not in title`。
- **PDF 文本正则**：列对齐+换行破坏正则 → `re.S`+`\s*`；亿 vs 亿吨 差 1e8。
- **腾讯 ifzq 不复权K线**：需 `param=code,day,beg,end,count,`（末尾逗号）。
- **接口字段名易错**（如 `Data.mjc` 实测=煤价非磨机开工率）：先 dump 一条核字段。
- **`data_router.get()` 首个参数是 kind**：子类型参数别取名 `kind`（会冲突），用 `index_type` 等。
