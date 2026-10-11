# 单基金深度分析 + 多基金对比工作流（外部基金，非用户持仓）

适用于用户给基金代码要「业绩/持仓/归因」，或要求多基金横向对比性价比（不需要查用户账户时的路径）。

## Skill 调用参数速查（实测，易错）

| Skill | body 参数 | 易错点 |
|---|---|---|
| TTFUND_SEARCH | `{"query":"005974","search_type":"fund","page_index":1,"page_size":5}` | 先确认代码→名称/类型。不要跳过：同名基金、type 完全不同（见下） |
| TTFUND_BASE_INFOS | `{"fcode":"005974","nav_range":"n"}` | 返回 ~150-220KB，必须 Python `subprocess`+`json.loads` 提取，勿灌上下文 |
| TTFUND_NAV_INFO | `{"fund_id":"005974","range":"ln"}` | ⚠️ 参数是 `fund_id` 不是 fcode；`range` 取值：y/3y/6y/n/2n/3n/ln（ln=成立以来）。BASE_INFOS 内嵌的 nav_history 只有近1年(~243条)，算年度收益必须用本 skill 的 ln |
| TTFUND_MANAGER_INFO | `{"manager_name":"孔令超"}` | ⚠️ 不是 query 字段；返回 manager_profile（resume/investment_idea/在管基金） |
| TTFUND_INDEX_INFO | `{"index_id":"931722"}` | ⚠️ 不是 query 字段；返回指数估值/区间收益/行业权重（指数基金归因用） |
| TTFUND_MACRO_DATA | `{"region":"cn","categories":"cpi,ppi,pmi,m1,m2","start_date":"2025-10-01"}` | ⚠️ `region` 必填；数据在 `body.frequencies[]`（日频/月频） |
| TTFUND_BOND_MARKET | `{}` | 债市晴雨表 markdown：利率债/信用债红绿 BP，判断债券端环境 |

## 年度收益计算（关键技巧）

- 用 NAV_INFO `range=ln` 的 items，取**累计净值 LJJZ**（不是单位净值 DWJZ，分红会跳空）
- 正确公式：**本年收益 = 年末LJJZ / 上年末LJJZ - 1**
- ⚠️ 常见错误：用「年初值/上年末值」或年初跳空做分母，会把 +14.98% 算成 -0.45%。年度表要逐行验证：2019 起每年结果应和阶段收益区间自洽
- 月度走势：每月最后一条 LJJZ 环比，可定位风格切换/暴跌反弹拐点（例：某港股红利基金 2026-06 单月 -12.4%、07 +8.0%）

## BASE_INFOS 扩展字段（业绩归因素材）

- `fund_profile_holdings.bond_invest_distribution`：债券细分（BONDTYPENEW 1=信用债/2=利率债 PCTNV）
- `fund_profile_archive.cash_flow_and_performance_history`：季度净流入 NETFLOW + 区间收益 SE → 看赎回潮/资金面
- `fund_profile_archive.asset_scale_history`：规模季度变化（CHANGE%）→ 明星基金吸金→赎回剧本
- `fund_profile_archive.stock_theme_history` / `stock_industry_sw_history`：主题/申万行业历史占比，判断风格切换（key 是日期）
- `fund_profile_archive.invest_style_snapshot`：style_box（大盘/中盘×价值/平衡/成长）、turnover（换手率）、top10_concentration
- `fund_holder_structure`：GRBL(个人%)/JGBL(机构%) → 个人占比高=赎回快
- `unique_info`：SHARPx、MAXRETRAx、STDDEVx 及同类排名

## 多基金对比的正确姿势

1. **先看基金类型再比收益**：混合型-偏债（固收+，R3）vs 指数型-股票（R4）不是同一赛道，直接比近1年收益是错的（本例 022719 港股央企红利 ETF 联接近1年 -3.58%，同类股票平均 +17.5%，但和固收+ 比没意义）
2. 对比维度：夏普（SHARP5/排名）、最大回撤、波动率、阶段排名、股票仓位、债券仓位——风险调整后收益优先
3. **指数基金性价比看指数估值**：`TTFUND_INDEX_INFO` → `valuation`（pe_ttm / pe_percentile_10y / pb / pb_percentile_10y）。案例：国新港股通央企红利 931722，PE 9.26 看着便宜，但 PE 十年分位 86.6% = "便宜的贵"，不宜追；配合近1年收益弱于同类判断风格下行期
4. 归因背景：MACRO_DATA（PPI/CPI 转正 → 无风险利率上行 → 伤债底，解释固收+ 近1年跑输）+ BOND_MARKET 晴雨表
5. 结论输出：三表格对比（画像/收益/风险）+ 按资金用途给选择建议（求稳 vs 要现金流），不要只给一个排名

## 输出规范（用户偏好）

- 业绩表：年度收益表 + 阶段排名表（含同类平均、hs300 对照）
- 归因分「长期好因 / 近期弱因」两段，再给一句话总结
- 分析完主动给后续选项（对比持仓/落盘博客），不要只交报告