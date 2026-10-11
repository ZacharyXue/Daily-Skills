# ttskill invoke 返回的 JSON 信封结构（BASE_INFOS 实测 2026-09）

`ttskill invoke` 的输出外层是统一信封，与 skill 正文提到的 `expansion.comprehensive_info.*` 路径之间隔了几层。**不按本文档解包会反复踩 `'list' object has no attribute keys'` / `data` 类型判断错这类坑**。

## 信封层级（拿基金数据必经之路）

```
ttskill invoke ... > out.json
解读路径:
  d                      -> {code, message, data}
  d['data']              -> Dict {skill_id, skill_name, raw_result, field_interpretations, resolution_info}
  d['data']['raw_result']['body']      -> {success, errorCode, ..., data, expansion, performance_benchmark, jf}
  body['data']           -> **List**（长度 1，不是 dict！）
  body['data'][0]        -> 基金**基本信息**：FCODE/SHORTNAME/FULLNAME/FUNDTYPE/RISKLEVEL/JJGS/ESTABDATE/DWJZ(单位净值)/LJJZ(累计净值)/RZDF/SYL_*/FSRQ/ENDNAV(最新规模元)/BENCHRATIO
  body['expansion']      -> 完整档案（业绩/持仓/风格/经理/历史），走这里 NOT data[0]
  body['expansion']['comprehensive_info'] -> 21 keys 的富档案
```

## 关键判定

- **`body['data']` 是 List**：先 `item = body['data'][0]`，别直接 `.keys()`（会报 `'list' has no 'keys'`）。
- **富档案在 `body['expansion']`，不在 `data[0]` 里**：`comprehensive_info` 下才有 `manager_information`、`fund_holder_structure`、`manager_idea`、`fund_profile_holdings`、`fund_profile_archive`、`nav_history`、`period_increase`、`rate_info` 等。看到某字段不在 `data[0]`，就去 `expansion.comprehensive_info` 翻。

## comprehensive_info 21 个 key（实测）

`fund_xt_change_info` / `company_info` / `period_increase` / `rate_info` / `relate_theme` / `fund_tag` / `index_detail` / `manager_information` / `relate_theme_info` / `unique_info` / `fund_holder_structure` / `manager_idea` / `period_increase_expansion` / `rate_info_expansion` / `core_diy_data` / `fund_profile_holdings` / `fund_profile_archive` / `nav_history` / `announcements` / `announcement_total_hits` / `fund_profile_overview`

## 常用字段速查

| 数据 | 路径 | 关键字段 |
|---|---|---|
| 阶段业绩 | `comprehensive_info.period_increase[]` | `title`(Z/Y/1N/2N/3N/5N/JN/LN) + `syl`(收益%) + `avg`(同类均) + `rank/sc`(排名/总数) |
| 前十大重仓 | `comprehensive_info.fund_profile_holdings.heavyweight_position_latest.fundStocks[]`（报告期 `heavyweight_position_report_date`） | `GPJC`(名称)/`GPDM`(代码)/`JZBL`(占比%)/`PCTNVCHGTYPE`(新增/增持/减持)/`INDEXNAME`(行业) |
| 资产配置 | `fund_profile_holdings.asset_allocation_latest` | `GP`(股票%)/`ZQ`(债券%)/`HB`(现金%)/`JZC`(净值) |
| 行业配置 | `fund_profile_holdings.sector_allocation[]` | `HYMC`(行业)/`ZJZBL`(占比%) |
| 经理 | `comprehensive_info.manager_information.currentManagerInfos[0].SINFO`（MGRNAME/FEMPDATE/TOTALDAYS/PENAVGROWTH）+ `PINFO[0]`（RESUME/INVESTMENTIDEAR） | |
| 规模历史 | `fund_profile_archive.asset_scale_history`(list,最新在前) | `NETNAV`(元)/`CHANGE`(同比%)/`FSRQ` |
| 份额+净申 | `fund_profile_archive.share_scale_history`(list) | `QMZFE`(期末份额)/`NETFLOW`(净申额,可空)/`ZFEBDL`(份额变动%) |
| 持有人结构 | `comprehensive_info.fund_holder_structure[0]` | `GRBL`(个人%)/`JGBL`(机构%)/`NBBL`(内部人持有%)/`EMPLOYEHOLD`(内部人金额)/`ZFE`(总份额) |
| 单季业绩/Q现金流 | `fund_profile_archive.cash_flow_and_performance_history`(list) | `SE`(单季收益%)/`NETFLOW` |
| AI 持仓解读 | `fund_profile_archive.holding_ai_summary` / `_latest` | `text_summary`(二手观点,非经理原文) |
| 投资风格 | `fund_profile_archive.invest_style_snapshot.style_box.current` | `large_cap/mid_cap/small_cap` 各 `value_score/growth_score` |

## 迷你基金/次新基金坑

- 成立不足一年的基金：`SYL_1N/2N/3N/5N` 是空串（无一年历史），阶段业绩表里对应排名也空。别当"数据缺失"报错，是成立时间短。
- `asset_scale_history` 期数少（可能仅 2-3 期）且 `NETNAV` 持续缩水 + `share_scale_history.NETFLOW` 连续为负 = 份额持续赎回 → 迷你基金清盘风险信号（规模 <5000 万逼近清盘线）。
- `JJGS`(公司)/`ESTABDATE`(成立日) 在 `body['data'][0]` 顶层；规模最新值也在那（`ENDNAV`），规模历史在 expansion。
