---
name: active-fund-evaluation
description: 主动基金评估（值不值得买）——六维评估（规模收益/季报言行一致/回撤夏普/机构占比/持仓风格/费率和持有人结构）+ 经理任期内近三年「观点→调仓→结果」时间线言行一致性验证。触发：用户给主动基金代码/名称让评估值不值得买、对比几只主动基金、分析基金经理言行是否一致、季报说的和做的对不对。
version: 1.0.0
tags: [基金, 主动基金, 投资, ttskill, eastmoney]
---

# 主动基金评估（active-fund-evaluation）

## 核心铁律（先读）

1. **先验身份**：任何基金代码先用 `TTFUND_SEARCH --action query --body '{"query":"<code>","search_type":"fund"}'` 验证 code→name→category_name，核对大类无误再 proceed（6 位代码极易口误，按错码拉到的是完全不同物种）。搜索结果信封：`d['data']['raw_result']['body']['data']['candidates']`。
2. **先分类型再谈性价比**：FOF/偏股/灵活/偏债/固收+ 收益基准完全不同，横向比夏普/回撤前先分组。
3. **数据落盘再提取**：`TTFUND_BASE_INFOS` 返回 150-470KB JSON，必须用 Python 脚本落盘 /tmp 再提炼，绝不整包灌上下文。
4. **换帅归因**：基金的历史净值/最大回撤只属于当任经理。看现任经理 `FEMPDATE`（任职日期），只分析其任期内表现，别把前任的坑算到现任头上（实测：富国稳健增长 010624，成立来 -16.4% 是前任肖威兵，范妍 2024-10 接手后任内 +27%）。
5. **言行一致性必须看三年时间线**：单季度「说了→做了」是噪音。拉现任经理任期内近三年全部季报/中报原文，逐期对照才能识别风格定力、追热点漂移、口是心非。
6. 免费源偶发丢包 ≠ 源坏：短超时 + 重试即恢复，别判死源。

## 六维评估框架

| 维度 | 数据来源 | 关键字段 |
|---|---|---|
| 1. 规模与收益 | BASE_INFOS | `data[0].ENDNAV`(最新规模) / `period_increase`(阶段业绩+同类排名) / `asset_scale_history`+`share_scale_history`(规模份额趋势，连续负净申=赎回) |
| 2. 季报言行一致 | 定期报告 PDF（**BASE_INFOS 拿不到经理亲述季报观点**，只有二手 AI 摘要） | 「报告期内基金的投资策略和运作分析」原文 vs 主题/行业占比变化 vs 当期业绩 |
| 3. 回撤与稳定性 | `unique_info[0]` | `SHARP1/3/5`(夏普) / `MAXRETRA1/3/5`(最大回撤) / `STDDEV1/3/5`(年化波动) / `MAXRETRA_SE`(成立来最大回撤+起止日) |
| 4. 机构占比 | `fund_holder_structure[0]` + `holder_structure_history` | `JGBL`(机构%) / `GRBL`(个人%) / `NBBL`(内部人%)；⚠️ 看历史趋势，单季跳变（如 010624 机构 2024-12 从 0→72%）= 机构冲品牌而来 |
| 5. 持仓风格 | `fund_profile_archive.invest_style_snapshot` + `fund_profile_holdings` | `style_box`(风格箱) / `turnover`(换手率) / `top10_concentration`(集中度) / `fundStocks`(前十大，FOF 看 `fundfofs`) / `stock_theme_history`(主题历史 dict) / `asset_allocation_latest`(股债现金配比) |
| 6. 费率+持有人结构 | `rate_info` + `holder_structure_history` | `MGREXP`(管理费) / `TRUSTEXP`(托管费) / `SALESEXP`(销售服务费)；持有人结构历史 |
| 附加：经理画像 | `manager_information.currentManagerInfos[].PINFO[0]` + SINFO + `manager_idea[0]` | `INVESTMENTIDEAR`(理念) / `RESUME`(履历) / `FEMPDATE`(任职日) / `TOTALDAYS`(任职天数) / `PENAVGROWTH`(任内收益%) / `chooseStockLogic`(选股逻辑) |

## 执行流程

### Step 1: 验证身份（每只必做）

```bash
export PATH="$HOME/.local/bin:$PATH"
ttskill invoke TTFUND_SEARCH --action query --body '{"query":"010624","search_type":"fund"}'
# 信封: d['data']['raw_result']['body']['data']['candidates'][0] → code/name/category_name
```

### Step 2: 拉 BASE_INFOS 全档案落盘

```bash
ttskill invoke TTFUND_BASE_INFOS --action query --body '{"fcode":"010624","nav_range":"ln"}'
# 信封: d['data']['raw_result']['body'] → data[0](基本信息) + expansion.comprehensive_info(全档案)
# 全部字段路径速查见 references/field-paths.md
```

### Step 3: 提取六维数据

用 execute_code 落盘 /tmp 后提取（模板见 references/field-paths.md 末尾）。核心字段易错点：
- `period_increase[].title` 是缩写：Z=近1周 Y=近1月 3Y=近3月 6Y=近6月 1N=近1年 2N=近2年 3N=近3年 5N=近5年 JN=今年来 LN=成立以来
- 历史序列（share_scale_history/holder_structure_history/cash_flow_and_performance_history 等）**排序方向不一**（有的最新在前有的最老在前），一律按 FSRQ 排序升序后再取最近 N 期
- `ENDNAV` 是最新规模（asset_scale_history 可能滞后/是早期快照）
- FOF 的 `fundStocks` 只有少量股票，真正的持仓在 `fundfofs`（TZJJMC 基金名/ZJZBL 占比）
- 主题历史 `stock_theme_history` 是 **dict{报告日期:[rows]}** 不是 list

### Step 4: 拉定期报告列表（东财 F10 API，实测可用）

```python
# 需要 Referer 头
import urllib.request, json
url = f"https://api.fund.eastmoney.com/f10/JJGG?fundcode={code}&pageIndex=1&pageSize=50&type=3"
req = urllib.request.Request(url, headers={"Referer": "https://fundf10.eastmoney.com/", "User-Agent": "Mozilla/5.0"})
# Data[].TITLE / Data[].ID(=artcode) / Data[].PUBLISHDATEDesc
# PDF 直链: https://pdf.dfcfw.com/pdf/H2_<artcode>_1.pdf
```

### Step 5: 下载+提取经理原文（三年时间线）

跑 `scripts/pull_report_narratives.py`：
1. 传基金代码 + 现任经理任职起点日期
2. 自动拉公告列表 → 下载 N 期季报/中报 PDF → 提取「投资策略和运作分析」段落存 /tmp/report_timeline/<code>/<date>.txt
3. 提取内核：pymupdf（venv `/tmp/pdfenv/bin/python`，execute_code 沙箱无 fitz 必须用 venv python）；定位段落时排除目录行（点线结尾）

**报告期筛选**：从经理任职起点（FEMPDATE）起取每季度报告 + 最新中报。跳过上一任经理写的报告（如范妍 2024-10 上任，2024Q3 报告是前任写的要剔除）。

### Step 6: 言行一致性分析（并行子代理）

N 只基金 → N 个并行 subagent，每个独立读一只的时间线（/tmp/report_timeline/<code>/）。给每只的 context 包含：
- 报告 txt 路径（按日期排序读完）
- `/tmp/fund_theme_hist.json` 对应基金的 `theme`（主题配置历史 = 操作证据）
- 市场季度背景速览（2023 AI 启动 / 2024 小微盘危机+9.24行情 / 2025 AI 爆发 / 2026 Q1 美伊冲突+Q2 AI极致行情）
- 产出：逐期时间线表（报告期→经理观点/动作→当期结果→言行一致✅/⚠️/❌）+ 总评（风格定位/言行一致分 1-5/亮点/雷点/适合谁）

### Step 7: 交叉验证 + 输出

- **多产品复制识别**：同一经理旗舰 vs 标的产品前十大重合度（实测张芊 广发招享 vs 广发聚鑫 重合 8/10 → 复制策略，买小产品≠买专注）
- 输出：六维表 → 三年时间线 → 言行一致评分 → 「按资金目的分层」的买入建议（稳/攻/风格卫星/不推荐）

## 关键坑（实测踩过）

- `TTFUND_MANAGER_INFO` 的 body 参数是 `{"manager_name":"张芊"}`，不是 query/fcode
- 市场观点要区分三层：**持仓增减=硬数据 / holding_ai_summary=二手AI摘要 / 定期报告原文=一手观点**。言行一致性只认一手观点
- 免费搜索后端（web_search）不稳定会报 Keyless Exa 错误 → 换东财 F10 API（api.fund.eastmoney.com/f10/JJGG）拉公告列表，别依赖搜索找 PDF
- 公告标题中文数字（「二0二六」）与阿拉伯数字（「2026」）并存，按标题过滤时两种都要匹配
- execute_code 内核没有 pymupdf；下载/提取用 terminal 调 `/tmp/pdfenv/bin/python`
- 中报/年报的运作分析比季报长，但季度粒度更细，两者都要
- 价值和「固收+」的言行一致性要拆开看：张芊债券部分 4.5/5、权益部分 2/5（权益仓位 30↔10↔29↔15% 剧烈择时=变相追涨杀跌）

## 数据保存（私有性说明）

本 skill 不保存私有数据，分析产物（基金档案、报告原文）只在 `/tmp/fund_raw/`、`/tmp/report_timeline/`、`/tmp/report_pdf/` 等临时目录，会话结束即失效，不随公开仓 push。所有数据来自公开接口（天天基金 ttskill / 东财 F10 / 证监会定期报告 PDF），无个人持仓信息。若做「我的持仓基金体检」需把持仓清单视为隐私，不写入 skill 仓库。