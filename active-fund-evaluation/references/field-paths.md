# TTFUND_BASE_INFOS 信封与字段路径速查

实测于 2026-09（富国稳健增长 010624 等多只主动基金）。**先把 200-470KB JSON 落盘 /tmp，用 Python 提取，绝不灌上下文。**

## 信封层级（先看这个）

```
d['data']['raw_result']['body']
 ├── data[0]                    # 基金基础信息（扁平 dict，F盘老字段）
 ├── expansion
 │   └── comprehensive_info     # ★ 全档案核心
 │       ├── period_increase          (list 10)  阶段业绩
 │       ├── period_increase_expansion(dict)     
 │       ├── unique_info              (list 1)  ★ 夏普/回撤/波动/机构
 │       ├── rate_info                (dict)     费率
 │       ├── rate_info_expansion      (dict)     
 │       ├── fund_holder_structure    (list 1)   ★ 持有人结构(机构占比)
 │       ├── manager_information      (dict)     经理(history/current)
 │       ├── manager_idea             (list 1)   经理理念/选股逻辑
 │       ├── fund_profile_holdings    (dict 11)  ★ 持仓
 │       ├── fund_profile_archive     (dict 14)  ★ 档案(主题/规模/份额/持有人历史)
 │       ├── announcements            (list)     公告(近期, 无定期报告)
 │       └── fund_profile_overview    (dict 21)  概览(ENDNAV/BENCH)
 └── performance_benchmark
```

## data[0] 关键字段

| 字段 | 含义 |
|---|---|
| SHORTNAME / FULLNAME | 简称 / 全称 |
| ESTABDATE | 成立日期 |
| ENDNAV | **最新规模(元)**（asset_scale_history 可能滞后，最新规模用它） |
| DWJZ / LJJZ | 单位净值 / 累计净值 |
| TTYPE / TTYPENAME | 基金类型（⚠️ 部分基金 TTYPENAME 是空或错位如"中特估"，以 TTFUND_SEARCH 的 category_name 为准） |

## period_increase[]（阶段业绩，title 是缩写）

| title | 区间 | | title | 区间 |
|---|---|---|---|---|
| Z | 近1周 | | 1N | 近1年 |
| Y | 近1月 | | 2N | 近2年 |
| 3Y | 近3月 | | 3N | 近3年 |
| 6Y | 近6月 | | 5N | 近5年 |
| JN | 今年来 | | LN | 成立以来 |

字段：`syl`(收益%) / `rank`(同类排名) / `avg`(同类平均) / `hs300`(沪深300) / `benchmark`(基准)。
⚠️ 不同基金的同类样本数不同，raw rank 横向不比，结合 avg 定性。

## unique_info[0]（维度3 数据源）

| 字段 | 含义 |
|---|---|
| SHARP1/3/5 | 夏普比率 1/3/5 年 |
| MAXRETRA1/3/5 | 最大回撤 1/3/5 年 |
| MAXRETRA_SE / MAXRETRA_SDATE_SE / MAXRETRA_EDATE_SE | 成立来最大回撤 + 起止日期 |
| STDDEV1/3/5 | 年化波动率 |
| JGBL | 机构占比（与 fund_holder_structure 冗余） |

## fund_holder_structure[0]

`FSRQ`(报告期) / `JGBL`(机构%) / `GRBL`(个人%) / `NBBL`(内部人%) / `EMPLOYEHOLD`(员工持有额) / `ZFE`(总额)

## manager_information

```
currentManagerInfos[]:
  SINFO: MGRNAME / FEMPDATE(任职日期) / TOTALDAYS(任职天数) / PENAVGROWTH(任内收益%)
  PINFO[0]: MGRNAME / INVESTMENTIDEAR(投资理念) / RESUME(完整履历)
historyManagerInfos: 同结构（历史经理）
```
⚠️ **换帅归因铁律**：业绩/言行只算现任 FEMPDATE 之后的；2024Q3 报告若经理 2024-10 上任则是前任写的，剔除。

## manager_idea[0]

`managerName` / `investmentIdea` / `investmentMethod` / `chooseStockLogic` / `tradeLogic` / `statement` — 经理自述理念（**一手但非季报原文**，季报原文要去 PDF）

## fund_profile_holdings

| 键 | 结构 | 用途 |
|---|---|---|
| heavyweight_position_latest | {fundStocks:[], fundfofs:[], fundboods:[]} | 前十大股票 / FOF持仓基金 / 债券 |
| asset_allocation_latest | {FSRQ, GP(股票%), ZQ(债券%), HB(现金%), JJ(基金%), JZC(净值)} | 股债配比 |
| sector_allocation | list[H YMC/SZ/ZJZBL] | 最新行业配置 |
| stock_invest_distribution | list[TOPICCODE/PCTNV] | 最新主题分布 |

FOF：`fundStocks` 只有个别股票（占比个位数），**真正持仓在 `fundfofs`**（TZJJMC/TZJJDM/FTYPE/ZJZBL/PCTNVCHGTYPE）。

## fund_profile_archive

| 键 | 结构 | 注意 |
|---|---|---|
| stock_theme_history | **dict{报告日期: [rows TOPICCODE/PCTNV]}** | 主题历史=操作证据 |
| stock_industry_sw_history | **dict{报告日期: [rows]}** | 申万行业历史 |
| sector_allocation_history | dict{日期:[rows]} | 行业配置历史（常只有最新一期） |
| asset_allocation_history | dict{日期:[rows]} | 资产配置历史 |
| asset_scale_history | **list** [FSRQ/NETNAV/CHANGE] | 规模历史（可能滞后,最新用 ENDNAV） |
| share_scale_history | **list** [FSRQ/QMZFE(份额)/NETFLOW(净申)] | 连续负净申=赎回 |
| holder_structure_history | **list** [FSRQ/JGBL/GRBL/NBBL] | 机构占比历史 |
| cash_flow_and_performance_history | **list** [FSRQ/SE(单季收益%)/NETFLOW] | 单季业绩+资金流 |
| invest_style_snapshot | dict | style_box(风格箱)/turnover(换手)/top10_concentration(集中度) |
| holding_ai_summary_latest | list[text_summary] | **二手AI摘要**（非经理原文） |

⚠️ **list 排序方向不一**（有的最新在前有的最老在前）→ 一律按 FSRQ 升序排序后取最近 N 期。dict 直接用 `for date, rows in d.items()`。

## 定期报告获取（经理亲述季报 = 一手观点）

- 公告列表 API（需 Referer）：
  `https://api.fund.eastmoney.com/f10/JJGG?fundcode=<code>&pageIndex=1&pageSize=50&type=3`
  → `Data[].TITLE / Data[].ID(artcode) / Data[].PUBLISHDATEDesc`
- PDF 直链：`https://pdf.dfcfw.com/pdf/H2_<artcode>_1.pdf`
- 提取：pymupdf（`/tmp/pdfenv/bin/python`），定位「报告期内基金的投资策略和运作分析」段落（排除目录行）
- 批量流程见 scripts/pull_report_narratives.py

## 提取模板骨架（execute_code 内）

```python
import json
raw = json.load(open(f"/tmp/fund_raw/{code}.json"))
ci = raw["expansion"]["comprehensive_info"]
ui = ci["unique_info"][0]
pi = {p.get("title"): p for p in ci["period_increase"]}
fpa = ci["fund_profile_archive"]
# 历史序列按 FSRQ 排序
def sorted_recent(dlist, datekey, n=8):
    seen = {}
    for r in dlist:
        d = str(r.get(datekey) or "")[:10]
        if d and d not in seen: seen[d] = r
    return sorted(seen.values(), key=lambda r: str(r.get(datekey) or ""))[-n:]
```