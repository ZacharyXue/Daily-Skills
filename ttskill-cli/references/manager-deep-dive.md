# 基金经理深度研究工作流（业绩/理念/言行一致/机构认可/最新观点）

用户给一只基金要「挖这个经理的背景业绩、投资理念、对市场适应、是否言行一致、机构认可度、最新观点」时的路径。基于郑玲（国联价值均衡 024658）实测。

## 数据源与步骤

1. **TTFUND_SEARCH** 验证基金身份（铁律，防代码口误）
2. **TTFUND_BASE_INFOS**（`{"fcode":"<code>","nav_range":"ln"}`）→ 结构 `data.raw_result.body.data[0]` + `expansion.comprehensive_info`。本次用 Python 脚本把 200KB JSON 提取到 /tmp，逐层探索再汇总（别灌上下文）。
3. **TTFUND_MANAGER_INFO**（`{"manager_name":"郑玲"}`）→ 一次性给 `manager_profile`（resume/投资理念/customTag）、`managed_funds`（在管12只）、`historical_managed_funds`（历史2只）、`performance_overview`（年化/回撤/夏普/波动率，含同类排名）

## 经理画像关键字段

- `manager_profile.customTag`：一针见血的标签（如「军工投资专家 擅长逆向投资 以守为攻」）——理解风格钥匙
- `manager_profile.profile_summary`：完整履历 + 在管基金清单
- `manager_profile.investment_idea`：官方投资理念一句话
- 独任 vs 共管：`manager_information.currentManagerInfos` 看是否独自管理、任职天数、任内收益

## 言行一致性验证（核心：理念→持仓→净值硬对账）

把经理**宣称的理念**和**持仓/风格/仓位/净值的硬数据**逐条对：

| 承诺 | 看哪里验证 |
|---|---|
| 均衡配置 | `fund_profile_holdings.sector_allocation` 行业分散度 |
| 价值/低估值 | `fund_profile_archive.invest_style_snapshot.style_box`（大盘/中小盘×价值/成长） |
| 仓位管理/控波动 | `fund_profile_holdings.asset_allocation_latest`（GP股票%/ZQ债券%）；`unique_info` 波动率同类排名 |
| 逆向/左侧 | 前十大 `PCTNVCHGTYPE`（新增/增持）是否集中在低位板块 |
| 理念drift | 对比不同基金同期的持仓（旗舰 vs 低波动版）看是否一致表达 |

对照结果用✅/⚠️标注，逐条列出才算「验证过言行」。

## 机构认可度

- `fund_holder_structure`：`JGBL`(机构%) / `GRBL`(个人%) / `NBBL`(内部人持有%)
  - 旗舰机构 85%+ = 强机构背书
  - **内部人持有 10%+（`NBBL` 或 `EMPLOYEHOLD`）是很强信号**：基金经理/员工真金白银跟投自家产品（杨锐文 260111 内部人 12.5%），比机构配置更说明经理自己信
  - 次新迷你基金机构 1.9%、个人 98% = 未获机构配置
- ⚠️ 结合 `fund_profile_archive.share_scale_history` 看 NETFLOW 季度净申购——机构可能单季巨额赎回（获利了结），别只看一个时点的 JGBL

## 最新观点（一手，经理亲述季报）

ttskill 的 manager_idea 只有二手 AI 摘要/理念标签，**拿不到经理逐字季报观点**。要一手原文：

1. **web_search** `基金经理名 公司 年份 二季报/中期报告 观点`，命中东财公告页（`qcloud.fund.eastmoney.com/gonggao/<code>,AN<id>.html`）
2. **web_search 命中「新浪基金/搜狐基金工作室」的二季报点评**（如 "2026年上半年跑赢基准X% 景顺长城××混合杨锐文"）直接含经理最新观点原文节选 + 阶段业绩表，省去 PDF 提取——搜到直接 web_extract 即可（杨锐文 260111 实测可用）
3. 东财公告页 HTML 是 JS 渲染，正文抓不到——**直接拼 PDF**：`https://pdf.dfcfw.com/pdf/H2_<artcode>_1.pdf`（artcode=公告里的 AN 编号），如 `H2_AN202608311828749398_1.pdf`
4. 装 pdf 工具（venv + `pip install pymupdf`）后提取「§4 管理人报告」：
   - `4.4` = 本报告期投资策略和运作分析（经理实际操作复盘）
   - `4.5` = 宏观经济、证券市场及行业走势展望（最新观点）

## Pitfalls

- **曾任的明星基金现在可能已换人**：中邮风格轮动郑玲管时 +74%，但她 2022-04 离任，现在是别人管（半导体风格）——归因业绩前必须 `manager_information.currentManagerInfos` 确认当前经理，别把现任持仓算到旧人头上
- **明星经理多产品精力分散**：杨锐文在管 13 只（A/C 合计计）——"多产"经理要提示产品多、精力分散的风险，看单只时确认那一只是否他独立管/与别人共管（`currentManagerInfos` 多条 = 共管）
- **旗舰 vs 新发版的仓差**：同一经理的「旗舰」可能 83% 股票，新发"低波动"版只有 40% 股票——能力圈是逆向选股，低仓位下超额打折；买新发小基金 ≠ 买到经理完整能力
- 迷你基金（规模 <1亿）有清盘风险，且大多是个人持有——即使经理本人很强，产品层面也要提示
- BASE_INFOS 返回体积极大，逐层探索（先打 keys 再深入），用脚本落盘 /tmp

## 输出结构（用户偏好）

履历地位 → 历史业绩（分任职期，带同期基准）→ 理念&言行一致表 → 机构认可 → 最新观点（原文+解读）→ 对该基金的启示（经理强≠产品强）。主动给后续选项（对比旗舰/查拐点判断）。
