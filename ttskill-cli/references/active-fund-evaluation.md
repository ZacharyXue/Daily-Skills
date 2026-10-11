# 主动基金评估（值不值得买）—— 六维框架（2026-09 六基实测：017589/202213/001122/019941/010624/009121）

子皓要评估外部主动基金「值不值得买入」时的完整流程。六维：规模与收益 / 季报言行一致 / 回撤与稳定性（夏普）/ 机构占比 / 持仓风格 / 持有人结构变化，另加费率。

> 用户术语：他说「下-p比」= **夏普比**（语音输入误写）。评估时夏普比必须给全（1年/3年/5年）。

## 流程概览

1. **TTFUND_SEARCH 验身份**（铁律）——`--action query --body '{"query":"<code>","search_type":"fund","page_index":1,"page_size":5}'`，候选在 `d['data']['raw_result']['body']['data']['candidates']`（code/name/category_name）。多基对比把 `category_name` 列出、先分类型再比。7 位误码照搜拆解（0017589→017589）。
2. **批量拉 BASE_INFOS 落盘**（nav_range=ln）：每只 ~150-470KB，**必须 subprocess + json.loads 落 `/tmp/fund_raw/<code>.json`，别灌上下文**。
3. **JSON 信封**：`d['data']['raw_result']['body']['data'][0]`（基本信息）+ `body['expansion']['comprehensive_info']`（富档案）。
4. **六维字段提取**（见下）。
5. **季报原文言行对账**（维度2核心，一手观点）——东财 JJGG 接口 + PDF §4.4。
6. **输出**：先类型表格 → 每只六维卡 → 一句话总结按用钱目的选 → 坑点说明。

## 六维字段路径速查（BASE_INFOS expansion.comprehensive_info）

| 维度 | 路径 | 字段 |
|---|---|---|
| 规模 | `data[0]` | `ENDNAV`(最新规模元) / `DWJZ` / `LJJZ` / `ESTABDATE` |
| 规模历史 | `fund_profile_archive.asset_scale_history`(list) | `NETNAV`(元)/`CHANGE`(同比%)，**按 FSRQ 排序**后看近期 |
| 份额/净申 | `fund_profile_archive.share_scale_history`(list) | `QMZFE`(期末份额)/`NETFLOW`(净申元)，负净申=赎回 |
| 收益 | `period_increase`(list) | `title` 代码(Z/Y/3Y/6Y/1N/2N/3N/5N/JN/LN) + `syl`/`rank`/`avg`(同类均)/`hs300` |
| 夏普/回撤/波动 | `unique_info[0]` | `SHARP1/3/5`、`MAXRETRA1/3/5`、`MAXRETRA_SE`+`MAXRETRA_SDATE_SE/EDATE_SE`(成立来最大回撤及区间)、`STDDEV1/3/5` |
| 机构占比 | `fund_holder_structure[0]` | `JGBL`(机构%)/`GRBL`(个人%)/`NBBL`(内部人%)/`EMPLOYEHOLD`(员工持有元)，报告期 `FSRQ` |
| 机构历史 | `fund_profile_archive.holder_structure_history`(list) | `FSRQ/JGBL/GRBL`，**排序坑见下** |
| 持仓风格 | `fund_profile_holdings` | `sector_allocation`(行业)、`asset_allocation_latest`(GP/ZQ/HB/JJ%)、`heavyweight_position_latest.fundStocks`(前10: GPJC/GPDM/JZBL/PCTNVCHGTYPE增减持)、`heavyweight_position_latest.fundfofs`(FOF持仓基金: TZJJMC/ZJZBL/FTYPE) |
| 风格箱/换手/集中度 | `fund_profile_archive.invest_style_snapshot` | `style_box`(大中小盘×价值成长分数)、`turnover`、`top10_concentration` |
| 主题历史 | `fund_profile_archive.stock_theme_history`(dict) | `{日期: [TOPICCODE/PCTNV]}`，最新日期 sorted(keys)[-1] |
| 单季业绩/净流入 | `fund_profile_archive.cash_flow_and_performance_history`(list) | `SE`(单季%)/`NETFLOW`(净流入元) |
| 费率 | `rate_info` | `MGREXP`(管理费)/`TRUSTEXP`(托管费)/`SALESEXP`(销售服务费) |
| 经理 | `manager_information.currentManagerInfos[i]` | `SINFO.FEMPDATE`(上任)/`SINFO.TOTALDAYS`/`SINFO.PENAVGROWTH`(任内收益%)/`PINFO[0].INVESTMENTIDEAR`/`RESUME` |
| 经理理念 | `manager_idea[0]` | `investmentMethod/investmentIdea/chooseStockLogic/tradeLogic/statement` |
| 一手观点 | （见下）东财 JJGG + PDF | §4.4 投资策略和运作分析 |

## 关键坑

- **历史 list 排序不可靠**：`holder_structure_history` 等 list 各基金顺序不一（有的最新在前有的最老在前），`[-8:]` 会取到最老数据。统一：`seen[FSRQ]=row` 去重 → `sorted(seen.values(), key=FSRQ)` → 取最后 N 期。
- **业绩归因按现任经理任期**：`period_increase` 的 LN(成立以来) 可能属于前任经理（010624 富国稳健增长：成立来 -16.4% 是肖威兵时代，范妍 2024-10 接手后任内 +26.96%）。「值不值得买」看 `SINFO.PENAVGROWTH` + 经理风格，别被历史净值骗。
- **排名横向不可直接比**：同类型基金数量不同（FOF 同类几十只 vs 偏股混合上千只），rank 是原始名次，横向对比要用「超过同类均 avg」做定性。
- **FOF 特殊**：持仓在 `fundfofs` 不是 fundStocks；基金占净值 80-90%；有双重收费（底层基金费用另算），评估时单独提示；风格箱照常给。
- **「稳」≠「夏普高」**：偏债/FOF 波动 5-6% 回撤小但收益也低；用户重夏普/回撤非单看收益（长期目标年化 5%+）。

## ⚠️ 言行一致性必须看现任经理任职期近三年（用户 2026-09 明确纠偏）

> 用户原话：「不仅看一个季度，去年、前年，只要这个基金经理在职的，可能近三年都需要看一下，然后根据这三年的行情，以及他自己的言行、它的调仓这样去看，而不是仅看最近一个季度的。」

**单季度「说了→做了」只是噪音**（如 2026Q1 美伊冲突的临时避险）。三年跨度验证三件事：
1. **风格定力**：在小微盘危机/9.24 政策爆拉/AI 大爆发/极致科技行情等不同市场里，经理是坚持框架还是追热点漂移。
2. **言行闭环**：每一期「经理说看好 X」→ 下期持仓是否真加 X → X 后来表现如何。连续十几期看，真假自现。
3. **换帅归因**：现任经理任职起点（`SINFO.FEMPDATE`）之前的一切业绩/回撤都是前任的，别算到现任头上。

工作流（多基金量级）：
- 用 JJGG 接口拉**现任经理任职起点以来全部**季报/中报（分页 pageIndex=1..3、pageSize=50，过滤 TITLE 含「季度报告/中期报告/年度报告」）；中文数字标题坑：`二0二六年中期报告` ≠ `2026年中期报告`，两种写法都要匹配。
- 全部下载提取 §4.4 原文落盘 `/tmp/report_timeline/<code>/<披露日>.txt`（76 份约 3 分钟）。
- 叠加两份证据：① `stock_theme_history` 逐期主题占比（=实际操作）；② 手工写的市场背景速览（2023 AI 启动、2024 小微盘危机/9.24、2025 AI 爆发、2026 美伊冲突/AI 极致）。
- **并行子代理**：一只基金一个 agent，喂「原文目录 + 主题历史 + 市场背景 + 硬数据」，要求输出逐期时间线表（报告期→观点→调仓→当期结果→✅/⚠️/❌）+ 总评（风格定位/言行一致 1-5 分/亮点/雷点/适合投资者）。6 只基金 6 个并行，结果回来再汇总，别自己逐篇读（上下文爆炸）。
- ⚠️ 注意范妍类换帅基金：跳过任职起点前的旧报告（010624 的 2024-10-25.txt 是范妍上任前的 2024Q3，是前任写的，从 2025-01-22.txt 开始读）。
- 输出结论按**言行一致性排序**而不是收益排序——收益会骗人，言行一致不会。

## 季报原文（一手观点）——东财 JJGG 接口

BASE_INFOS 拿不到经理逐字季报观点（只有 holding_ai_summary 二手 AI 摘要 + manager_idea 理念标签）。要季报原文：

```bash
curl -s --max-time 20 -H "Referer: https://fundf10.eastmoney.com/" -H "User-Agent: Mozilla/5.0" \
  "https://api.fund.eastmoney.com/f10/JJGG?fundcode=<代码>&pageIndex=1&pageSize=30&type=3"
```

→ `Data[]` 每项：`TITLE`(如「富国稳健增长混合…二0二六年第2季度报告」)、`PUBLISHDATEDesc`(2026-07-21)、`ID`(=artcode 如 AN202607211827193920)。批量取 6 只一次跑完。

PDF 直链：`https://pdf.dfcfw.com/pdf/H2_<artcode>_1.pdf`（curl 下载，~200-600KB）。

提取：venv + pymupdf，跑 `scripts/extract_report.py <pdf>` 取 §4.4（自动识别最后一处「投资策略和运作分析」=正文，避开目录）。

### 言行一致硬对账

把季报原文的操作描述 ↔ 前十大增减持(PCTNVCHGTYPE)/行业配置/sector_allocation 逐条对。例：
- 南方核心竞争：原文「增电子/通信/机械，减基础化工/有色」↔ 持仓中际旭创/新易盛/长川均为新增或增持 ✅
- 中泰FOF：原文自认「踏空科技股是本季度最大败因、风险平价失效」——敢认错的经理是加分项（言行一致的最高形态）。

输出三层区分：**持仓增减=硬数据、AI摘要=二手观点、季报原文=一手观点**。

## 输出格式（用户偏好）

1. 先类型表：`FOF-稳健 / 偏股 / 股票 / 灵活 / 偏债` 分类 + 一句话定性
2. 每只基金一张六维小表（维度|数据）+ 「值不值」段落
3. 一句话总结：按用钱目的（要稳/要进攻/价值卫星/不推荐）给选择
4. 坑点声明：排名基数、前任/现任经理归因、FOF 双重收费

配色/emoji 定性：🟢 推荐 / 🟡 有条件 / 🔴 当下不推荐，给出可证伪的弃买理由（如「同伴 001122 在夏普/回撤/费率三维全面碾压 009121」）。

## 话少型经理验证三件套（报告短 ≠ 调仓少，用户 2026-09 要求必看换手率）

经理季报/年报「运作分析」写得很短（<1000B，如 202213 南方核心竞争平均 1983B、最短 400B）时，**文字覆盖不了真实调仓**，必须三件套交叉验证：

1. **换手率**：`fund_profile_archive.invest_style_snapshot.turnover.current`（>100% = 高换手，报告必然没写全）；`peer_rank*` 看同类分位。⚠️ 用户原话：「换手率确实要看」——评估维度 3 的补充，任何言论说停立刻有数据反驳。
2. **前十大换血率**：从多期报告 PDF 提取「5.3.1 报告期末按公允价值…前十名股票投资明细」表格（该 PDF 文本格式：**每个字段单独一行**——序号/代码/名称/数量/市值/占比%，不是一行一个股票的表格），对比 N 期前十大存活率。高换手下每季换掉一大半=正常（202213 四年只活 2 只：宁德时代/生益科技）。
3. **调仓成本与效果**：
   - 成本：中报/年报 PDF「10.7 券商交易单元」表 → 股票成交总额 + 实付佣金 → 佣金费率（2024.7 佣金改革后应 <0.05%，202213 实测 0.043%）+ 佣金占净值比（0.07%/半年）。高换手 + 低佣金 + 小规模（<10 亿）= 摩擦可控。
   - 效果：`cash_flow_and_performance_history` 的 `SE`（单季收益）对照同期沪深300 估值算单季胜率（202213 为 5/6 跑赢、两次大跌防守为正）；再对照长期 rank（近1/3/5年），换手换来了超额还是白折腾。

**判读**：报告短 + 换手高 + 前十大换血快 = 说少做多型（言行验证看行业方向表达，不看个股）；高换手 + 长期 rank 靠后 = 无效折腾。规模长大（30亿+）要警惕冲击成本侵蚀超额。

## 多产品复制识别（买小产品 ≠ 买专注）

深挖资深经理时（`TTFUND_MANAGER_INFO --body '{"manager_name":"<名>"}'`，注意参数是 manager_name 不是 query），对比她/他在管多只产品的**前十大重合度**：同经理旗舰 vs 标的资产若高度同构，说明标的是复制策略的一环，买它≠买到经理的专注。实测：张芊（广发固收总监）的广发招享 009121 vs 旗舰广发聚鑫 000118，前十大重合 8/10（北方华创/汇川/晶泰控股/腾讯/平安/新和成/达梦/中微全重复）→ 招享只是复制品；且 27 只在管、610 亿规模、2026-08 一口气增聘 5 只新基金——精力分散是资深经理的真实风险，评估时量化呈现（在管数/总规模/单季增聘数）。

## 实测样例速查（2026-09，报告期 2026-06-30）

| 代码 | 结论 | 关键数字 |
|---|---|---|
| 001122 鹏华弘利A(灵活) | 🟢 稳健打底首选 | 夏普1年1.63/3年1.05，回撤5.1%，管理费0.6%（6只最低），规模21.6亿 |
| 202213 南方核心竞争(偏股) | 🟢 AI进攻 | 卢玉珊10年任内+199.67%，近1年19.33%，言行一致最强，波动19.3% |
| 010624 富国稳健增长A(偏股) | 🟡 机构重仓 | 范妍任内+26.96%（成立来-16.4%是前任），机构74.5%，风格轮动 |
| 019941 富国洞见价值A(股票) | 🟡 价值逆风 | 近1年-7.55%但机构63.2%逆势加仓，白冰洋明牌不漂移 |
| 017589 中泰天择FOF | 🟡 低波但踏空 | 90%基金+ETF，Q2 -2.18% vs 基准+3.98%，经理坦诚自省，规模一年+40倍 |
| 009121 广发招享A(偏债) | 🔴 不如同伴 | 近1年-2.06%，夏普1年-0.53，被001122全面碾压 |
