# 基金业绩归因分析工作流（外部基金，非自持仓）

用于回答「这只基金近几年业绩如何、为什么涨/跌」类问题。区别于 `fund-quarter-review.md`（持仓/风格拆解），本工作流聚焦**业绩时间序列 + 归因**。

## Step 1: 确认标的

```bash
ttskill invoke TTFUND_SEARCH --action query --body '{"query":"005974","search_type":"fund","page_index":1,"page_size":5}'
```

拿到 code/name/type。注意同名不同份额（A/C/ETF），确认用户指哪个。

## Step 2: 拉 BASE_INFOS 全档案（存文件，勿灌上下文）

```bash
ttskill invoke TTFUND_BASE_INFOS --action query --body '{"fcode":"005974","nav_range":"n"}' > /tmp/<fcode>_base.json
```

必须用 Python `subprocess` + `json.loads` 提取（返回 160K-300K JSON）。关键字段路径：

```python
fund = body['data'][0]
exp = body['expansion']['comprehensive_info']
arch = exp['fund_profile_archive']

# 基本信息：fund['SHORTNAME'/FCODE/FTYPE/RISKLEVEL/ESTABDATE], ENDNAV/1e8 规模(亿)
# 阶段收益+排名：exp['period_increase']（title: Z/Y/3Y/6Y/1N/2N/3N/5N/JN/LN）
#   注意：Z=近1周 Y=近1月 3Y=近3月 6Y=近6月 1N=近1年 2N=近2年 3N=近3年 5N=近5年 JN=今年以来 LN=成立以来
#   每项含 syl(本基金)/avg(同类平均)/rank/sc(同类总数)/hs300(同期沪深300)/benchmark
# 基金经理：exp['manager_information']['historyManagerInfos']（SINFO.MgrName/FempDate, PINFO[0].INVESTMENTIDEAR）
# 资产配置：exp['fund_profile_holdings']['asset_allocation_latest']（GP股票/ZQ债券/HB现金）
# 前十大重仓：...['heavyweight_position_latest']['fundStocks']（GPJC/GPDM/JZBL/PCTNVCHGTYPE/PCTNVCHG）
# 风格箱体：arch['invest_style_snapshot']（style_box current/avg_1y/avg_3y → 是否风格漂移；turnover 换手率；top10_concentration）
# 持有人结构：exp['fund_holder_structure']（GRBL个人/JGBL机构）
# AI 持仓摘要：arch['holding_ai_summary_latest']（text_summary 快速理解持仓主题）
```

## Step 3: 年度收益（关键！用累计净值）

```bash
ttskill invoke TTFUND_NAV_INFO --action query --body '{"fund_id":"005974","range":"ln"}'
```

**range 必用 ln（成立以来）**——BASE_INFOS 内嵌的 nav_history 和 range=n 都只有近1年。items 约 1960 条（2018→今）。

```python
year_last = {}
for it in items:
    fsrq = it['FSRQ'] or ''
    ljjz = float(it['LJJZ'] or 0)   # 累计净值，含分红再投
    if ljjz: year_last[fsrq[:4]] = (fsrq, ljjz)  # 最后赋值=年末
prev = None
for y in sorted(year_last):
    if prev: print(f"{y}: {(val/prev[1]-1)*100:+.2f}%")
    prev = year_last[y]
```

**陷阱**：用 `DWJZ` 单位净值 + 「年末/年初」会因分红/拆分跳空（本次实例 2019 年初 0.9701→年末 1.1205，若用年初跳空会算成 -0.45% 而非 +14.98%）。**必须用 LJJZ + 年末/上年末**。

## Step 4: 季度拐点 + 资金流（定位业绩转弱区间）

```python
rows = arch['cash_flow_and_performance_history']   # 每季一条，最多30条
# SE     = 单季区间收益%（数值型，直接是%，非净值）
# NETFLOW= 季度净申购额（负=赎回）
# 配合 arch['asset_scale_history']（NETNAV 规模, CHANGE 环比%）
```

- 连续 2-3 个负 SE → 业绩转弱区间，标注精确季度
- 规模骤降 + NETFLOW 大负 → 赎回负反馈（本次 005974 2026Q2 净赎回 4.38 亿、规模 -27.8%）
- 年度收益表里「当年收益 vs 各季度 SE」可交叉验证哪几个季度贡献/拖累

## Step 5: 宏观/债市归因佐证

```bash
# 通胀/流动性（判断利率方向）
ttskill invoke TTFUND_MACRO_DATA --action query --body '{"region":"cn","categories":"cpi,ppi,pmi,m1,m2,usdcny","start_date":"2025-10-01"}'
# 债市晴雨表
ttskill invoke TTFUND_BOND_MARKET --action query --body '{}'
```

归因逻辑：
- **高债券仓位（>70%）基金**：PPI 转正/CPI 上行 → 利率上行 → 债价下跌 → 净值承压（本次：PPI 从 -2.1% 转正到 +4.1%，恰好对应 2025Q4-2026Q2 连续三季负 SE）
- **股票增强部分**：对比 period_increase 的 hs300 vs syl：股票仓位不高增强不足时，基金涨不过大盘属正常；若重仓行业与市场风格错配（价值 vs 成长），放大差距
- **赎回负反馈**：业绩差→机构/个人赎回→规模缩→被动卖券→再压制净值

## Step 6: 分析框架与结论形态

1. 业绩全景：年度收益表（含背景注释：牛/熊/债牛/震荡）
2. 阶段排名快照：近1年 rank vs 近5年 rank（短期落后但长期优秀 = 近年风格错配或宏观转向）
3. 持仓验证：前十大 + 风格箱体 + 换手率（低换手=持有型，风格漂移=竞品风险）
4. 归因三因子：债端（利率周期）× 股端（风格错配）× 资金端（赎回）
5. 一句话总结 + 风险提示（固收+ 的定位是稳健理财替代，非进攻品种）

## 本次实例 (005974 东方红配置精选混合A)

- 定位：固收+（债券83.74%/股票27.91%），孔令超（2024-03 起单独管理），规模 11.74 亿
- 年度：2019 +14.98% / 2020 +14.13% / 2024 +10.02% / 2025 +7.52% / 2022 -0.83% / 2026至今 +0.25%
- 阶段：近1年 +1.16% 后16%（1058/1255）↔ 近5年 +22.35% 前14%（103/754）→ 典型「长期好近期差」
- 归因：2025Q4起连续三季负 SE（-1.17%/-0.58%/-0.84%）；同期 PPI 转正→利率上行→83.74% 债券仓位拖累；股票端大盘平衡/港股消费未跟上成长行情；2026Q2 大规模赎回放大负反馈