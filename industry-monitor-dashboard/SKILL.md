---
name: industry-monitor-dashboard
description: 为「行业/商品 + 龙头公司」搭建并维护**定期刷新的监测看板**（价格趋势/盈利底/成本/量/估值/技术面多维度盯一个标的）。核心组件：注释驱动的指标元数据层 + 免费数据源取数(远程优先+失败诚实+人工补录) + 自包含HTML渲染(多线SVG趋势图+可点击折叠说明) + A股财报PDF经营数据提取。参考实现 /root/cement-dashboard。触发：用户要"监控某行业/公司是否止跌/盈利见底"、"做个定期看板"、"把XX指标接进看板"、"看下当前XX行业现状"。
version: 1.0.0
tags: [dashboard, monitoring, data-source, html-render, a-share-report, commodity]
---

# 行业/公司 监测看板（定期刷新的数据面板）

怎么把一个「行业 + 龙头公司」做成可持续、可刷新的看板，以及这 class 任务的高频坑。参考实现 `/root/cement-dashboard`（git 管理，每独立改动一 commit）。

## 触发场景
- 「监控某行业/某龙头是否止跌、盈利见底」
- 「做个看板 / 定期更新行业走势 / 把XX指标接进看板」
- 需要把价格/成本/量/盈利/财务/估值/技术面多维度盯住一个标的（如水泥+海螺）

## 架构（4 件套）
1. **指标元数据层**（如 `scripts/indicators.py`）：每个指标一个 dict = `{id, group, name, unit, ttl(缓存分级:day/week/month/quarter), source, source_url, meaning(为什么关注), signal(看什么信号), getter}`。
   - **注释驱动原则（用户偏好）**：meaning/signal 是静态元数据，放配置层、渲染时动态展示（可点击展开），**不依赖 skill 上下文**。skill 只存"怎么取数"的过程，指标语义不占每次运行的 token。
2. **取数层**（`scripts/fetch.py`）：每个 getter 一个函数，远程优先；输出 `cache/dashboard_data.json`，每指标带 `status(ok/failed/pending/manual)` + `fetched_at` + `latest_date` 供溯源。
3. **渲染层**（`scripts/render_html.py`）：读 json → **自包含单文件 HTML**（内嵌 CSS/JS），原生 `<details>/<summary>` 实现指标「可点击看意义」，顶部摘要达标计数 + 七维 ✓/✗ 徽章；趋势图用**内嵌多线 SVG + 图例**（自包含、可直接挂 Astro 博客）。
4. **补充源**：财报PDF提取（`scripts/extract_report.py`）+ 人工补录（`cache/manual.json` → status=manual，来源标「人工录入@日期」）。

## 数据正确性铁律（用户强要求，首要）
- **绝不拿旧值/缓存冒充当前值**。远程失败就标「获取失败」+ 原因；历史值仅作"上次成功@日期（非当前，仅参考）"在展开区展示。正确性 > 及时性。
- **免费源偶发单次丢包 ≠ 源坏了/限频**：超时后**立即重试通常即恢复**（实测连续 6/6 成功 0.8-2s）。对策 = **短超时(约14s) + 重试3次**。不要因一次超时判死一个源，也不要留着"XX接口坏了"的负面断言。
- 每指标带 `status`/`fetched_at`/`latest_date` 明示；老数据要醒目标"示旧+日期"，绝不含糊当当前值。

## 已验证免费数据源
见 `references/data-sources.md`（中国水泥网水泥/成本/需求指数接口、腾讯 ifzq 前复权+不复权K线、腾讯实时估值、东财公告 PDF）。**能自动拿的尽量自动，别叫用户去别处问**；拿不到的（如统计局产量被服务器 IP 拦）才转人工补录。

## A股财报PDF提取经营数据
见 `references/report-pdf-extraction.md`：从公开定期报告提取吨售价/吨成本/吨毛利/分红，并**用披露毛利率核验**（实测吨毛利/吨售价=22.47% vs 披露22.46%，吻合才可信）。中报/年报都能自己拿，**别误判成"需人工"**。

## 人工补录集成（拿不到的指标）
对真正拿不到的指标，生成**可复制 prompt 清单**（如 `prompts/collect_prompts.md`：每个指标 = 问题 + 口径 + 期望字段），用户拿去别的软件问；答案回来写入 `cache/manual.json` → fetch 合并为 status=manual → 看板展示。保证正确性：要它注明口径+数据日期，别信孤零零一个数。

## Pitfalls（本会话踩过）
- **A股财报公告标题匹配**：`"年度报告" in title` 会误配「半年度报告」（子串）→ 必须显式 `"半年度" not in title`。
- **PDF 文本列对齐+换行破坏正则**：用 `re.S` + `\s*` 适配；亿 vs 亿吨差 1e8（亿=1e8 元，亿吨=1e8 吨）。
- **腾讯 ifzq 不复权K线需末尾逗号**：`param=code,day,beg,end,count,`（返回 `data.code.day`）；写 `count` 无逗号 → `bad params` 空。详见 references/data-sources.md。
- **同源端点前缀不同**（中国水泥网 `/index/priceindex/` vs `/index/<name>/`），用错 → 404。
- **接口字段名易错**（如水泥网 `Data.mjc` 实测=煤价数据，非磨机开工率）：先 `columns=ALL`/dump 一条核字段，别信文档名。
- **源间歇丢包**：取数脚本跑后台（前台超时会被杀）；每端点独立 try + 短超时重试，避免单点拖垮整批。

## 参考实现状态
✓ `/root/cement-dashboard`：指标元数据 + fetch + render + extract_report + 人工补录全链路。当前指标几乎全自动（价格/成本/盈利/财务/估值/技术/量），唯一待人工 = 全国水泥产量同比（统计局拦 IP，用 prompt 采集）。

## 关系 & 统一结构（2026-08 用户定调）

**用户偏好的看板组织**：一个共享「HTML 风格模板」（`dashboard-style`）+ 每个看板各自一份 md（`cement-dashboard`/`etf-dashboard`）+ **数据统一在 data-source-router**，看板类 skill 全部落 `zach-skills`。不要把所有看板揉进一个大 skill。
- `dashboard-style`（zach-skills）：样式/骨架模板 + 数据规范 + 看板索引（`references/dashboards-index.md`），复用 `templates/dashboard_skeleton.html`。
- `cement-dashboard`（zach-skills）：水泥&海螺各自 md（引用 /root/cement-dashboard 工程）。
- `etf-dashboard`（zach-skills）：ETF 看板，挂 dashboard-style 风格 + data-source-router 数据层。
- **数据获取一律 `data-source-router.get(kind)`**：看板只触发，具体源/脚本/缓存/重试在 router，**不自建 curl 重复造轮子**。行业专属源（中国水泥网 → `cn_cement_index`/`cn_cement_spread`）已下沉 router。

## 消费 data-source-router 的坑
## 看板家族（本纲涵盖的具体看板）
本 skill 是「行业 + 龙头/ETF 监测看板」的**综合母纲**，涵盖以下看板实例（各自独立 md/skill）：

| 看板 | 实例详情 | 类型 |
|---|---|---|
| 水泥 & 海螺 | `references/instances/cement/README.md` (+ `cement/` 含全部工程代码，自包含可迁移) | 行业 + 龙头(盈利底) |
| ETF 技术温度 | `references/instances/etf/README.md` (+ `etf/` 含脚本；运行需 ttskill/产物可配 ETF_OUT) | ETF(估值 + 技术) |

- **风格模板** → 复用 `dashboard-style/templates/dashboard_skeleton.html`（自包含 HTML 骨架：details 折叠/多线 SVG/表格/徽章）
- **数据获取** → 一律走 `data-source-router.get()`（行情/K线/财报/中国水泥网/中证PE/天天基金分位/GitHub 已统一下沉）
- **新增看板** → 见 `dashboard-style/SKILL.md` 五步流程 + 注册进 `dashboard-style/references/dashboards-index.md`

## 关系
数据接口细节与 `commodity-equity-rotation`/`stock-analysis` 有重叠；本 skill 侧重「看板/监测」这一层（架构 + 数据正确性 + HTML 渲染 + 报表提取），数据库接口共享（走 `data-source-router`）。
