# -*- coding: utf-8 -*-
"""
伊利股份(600887) 监测看板 —— 指标元数据层（注释驱动）
=============================================================
核心投资逻辑（2026-09 定稿）：
  伊利 = 不会炸但难大涨的成熟平台型龙头。不赚成长的钱，只等极端低估
  （股息率>6% 约 20 元）赚均值回归。验证信号：
    ① 原奶成本红利退潮后 ROE 仍稳在 17-18%（锚不塌）
    ② 营收端出现真实的量/价驱动（管我财信号）
  风险监控：负债是放大器不是炸药包（净头寸 +174亿）；澳优减值雷已拆完。

指标 = {id, group, name, unit, ttl, source, source_url, meaning, signal, getter}
所有数值只从东财 datacenter / 腾讯行情 / 中证官网自动取数，禁止 hardcode。
营收同比按「同报告期累计值」重算。
"""

GROUPS = [
    "A 估值与击球点(买不买)",
    "B 增长质量(量价驱动验证)",
    "C 成本红利与正常化盈利(一次性检验)",
    "D 盈利质量(ROE锚)",
    "E 财务健康(负债放大器)",
    "F 同行与股东回报",
]

INDICATORS = [
    # ============ A 估值与击球点 ============
    dict(id="a_price", group="A 估值与击球点(买不买)", name="现价/52周位置", unit="元/%", ttl="day",
         source="腾讯行情", source_url="https://qt.gtimg.cn",
         meaning="现价 26.66(2026-09-11)，52周位置 62%——中高位，不是极端低估区。击球点：股息率>6%(约 20 元) / >6.5%(约 18 元)。",
         signal="52周位置<35% 或 价格<20 = 进入击球区；当前 62% = 继续等",
         getter="quote"),
    dict(id="a_div", group="A 估值与击球点(买不买)", name="股息率", unit="%", ttl="quarter",
         source="东财分红+行情", source_url="https://datacenter.eastmoney.com",
         meaning="2025 年度每股分红 1.38 元(10派9+中期10派4.8)，分红率承诺≥75%。当前 1.38/26.66≈5.18%；若 2026 利润下滑按 75% 分红率则保守分红约 1.19 → 4.46%。",
         signal="股息率>6%(价格~20)=极端低估击球区；分红率守 75% = 股息底稳定",
         getter="dividend"),
    dict(id="a_pe", group="A 估值与击球点(买不买)", name="PE(TTM)", unit="倍", ttl="day",
         source="腾讯行情", source_url="https://qt.gtimg.cn",
         meaning="当前 PE(TTM)≈16.7 倍，位于历史偏低但非极低区间。隐含增速 4.8% > 实际营收 0-4%，价格略预支增长。",
         signal="PE 分位回落 + 价格下探 = 隐含增速被压缩到现实以下，安全边际变厚",
         getter="quote"),
    dict(id="a_fair", group="A 估值与击球点(买不买)", name="合理价区间(ROE锚)", unit="元", ttl="quarter",
         source="计算(合理PB=ROE/r)", source_url="https://datacenter.eastmoney.com",
         meaning="ROE 20.9%、每股净资产 8.64 元：r=8%→22.5、r=10%→18.0、r=12%→15.0。若 ROE 中枢下移至 17-18%(剔成本红利)，合理价下修至 ~20/16/13。",
         signal="价格进入 r=10% 合理价以下 = 安全边际转厚；ROE 若跌破 15%，锚整体下移",
         getter="fair_value"),

    # ============ B 增长质量 ============
    dict(id="b_rev", group="B 增长质量(量价驱动验证)", name="营收同比(最新报告期)", unit="%", ttl="quarter",
         source="东财 datacenter GINCOME", source_url="https://datacenter.eastmoney.com",
         meaning="2026H1 营收 644.9 亿 +4.13%（2025 全年 +0.1%）。剔除澳优减值后主业没问题，但增长引擎主要靠冷饮/饮料等新品类，液体乳近零增长。",
         signal="连续 2 期营收同比>4% = 复苏确认；增速回落且非季节性 = 消费降级延续",
         getter="growth"),
    dict(id="b_milk", group="B 增长质量(量价驱动验证)", name="液体乳收入同比", unit="%", ttl="quarter",
         source="东财分产品(研报口径)", source_url="https://datacenter.eastmoney.com",
         meaning="液体乳是基本盘(57%收入)。2026Q2 单季 +0.05%（量价双负：2025 全年销量-4.8亿/价格-22.9亿/结构-18亿）。管我财等量价驱动出现。",
         signal="液体乳同比转正且加速 = 量价驱动回归(关键买入信号之一)",
         getter="segment_milk"),
    dict(id="b_contrib", group="B 增长质量(量价驱动验证)", name="量/价/成本/结构四拆", unit="亿元", ttl="quarter",
         source="东财分产品(研报口径)", source_url="https://datacenter.eastmoney.com",
         meaning="Phase 4.5 增长归因：2025 液体乳收入下降 47.8 亿 = 销量-4.8 + 价格-22.9 + 结构-18.1 + 其他。价格贡献为负 = 无提价权。",
         signal="价格贡献转正 = 提价权恢复(护城河回归)；成本贡献>50% 利润增量 = 增长不可持续",
         getter="contrib"),
    dict(id="b_gm", group="B 增长质量(量价驱动验证)", name="毛利率", unit="%", ttl="quarter",
         source="东财 datacenter MAINFINADATA", source_url="https://datacenter.eastmoney.com",
         meaning="2026H1 毛利率 36.4%（+0.38pct），液体乳毛利率 34.16%（+2.4pct）——上升主因是原奶价格低位（成本红利），不是涨价。",
         signal="毛利率回落 = 成本红利退潮(预期 2026H2-2027)；毛利率稳住且收入增长 = 真改善",
         getter="growth"),

    # ============ C 成本红利与正常化盈利 ============
    dict(id="c_milkprice", group="C 成本红利与正常化盈利(一次性检验)", name="生鲜乳价格趋势", unit="—", ttl="month",
         source="行业公开数据(人工/研报)", source_url="https://www.moa.gov.cn",
         meaning="2022-2025 生鲜乳价格创纪录下行，是伊利 2024-2026 毛利率上升的来源(成本红利)。2026 年价格企稳回升，行业供需趋于平衡。",
         signal="奶价上行 = 成本红利递减(利润承压)但行业定价秩序修复(利好龙头)；奶价低位平稳 = 红利延续",
         getter="milk_price"),
    dict(id="c_adjroe", group="C 成本红利与正常化盈利(一次性检验)", name="正常化ROE(剔成本红利)", unit="%", ttl="quarter",
         source="计算(账面ROE-成本红利修正)", source_url="https://datacenter.eastmoney.com",
         meaning="账面 ROE 20.9% 含原奶成本红利；剔除后约 17-18%。估值锚用正常化 ROE 而非账面。",
         signal="锚稳：正常化 ROE 稳在 17-18% 不破 = 利润含金量过关；跌破 15% = 放弃回归逻辑",
         getter="adj_roe"),

    # ============ D 盈利质量 ============
    dict(id="d_roe", group="D 盈利质量(ROE锚)", name="账面ROE", unit="%", ttl="quarter",
         source="东财 datacenter MAINFINADATA", source_url="https://datacenter.eastmoney.com",
         meaning="2025 年报 ROE 20.9%（2024 15.8% 低谷、2023 20.2%）。行业寒冬里蒙牛 3.8%、光明亏损，伊利 ROE 20%+ 是龙头韧性的核心证据。",
         signal="ROE 连续 2 年<15% = ROE 锚下移，均值回归逻辑失效；稳 18-21% = 锚稳",
         getter="roe"),
    dict(id="d_core", group="D 盈利质量(ROE锚)", name="剔除减值后核心利润增速", unit="%", ttl="quarter",
         source="东财 datacenter GINCOME", source_url="https://datacenter.eastmoney.com",
         meaning="2026H1 归母 57.6 亿(-20%)是澳优减值 24.6 亿(商誉15.5+存货9.1)砸出的账面难看；剔除后核心经营利润 83.8 亿 +10%，创历史新高。",
         signal="核心利润增速保持 10%+ = 主业真实向好；商誉清零后报表更干净(剩 5.97亿)",
         getter="core_profit"),
    dict(id="d_impair", group="D 盈利质量(ROE锚)", name="资产减值/商誉余额", unit="亿元", ttl="quarter",
         source="东财 datacenter GINCOME/GBALANCE", source_url="https://datacenter.eastmoney.com",
         meaning="2024 减值 46.8 亿(澳优商誉30.4)、2026H1 减值 24.6 亿(商誉15.5)。累计减值 45 亿后商誉仅剩 5.97 亿，历史并购雷基本拆完。",
         signal="减值归零 + 商誉清零 = 报表轻装上阵；再出现大额减值 = 并购又踩雷(警戒)",
         getter="impairment"),

    # ============ E 财务健康 ============
    dict(id="e_netcash", group="E 财务健康(负债放大器)", name="净头寸(类现金-有息负债)", unit="亿元", ttl="quarter",
         source="东财 datacenter GBALANCE 计算", source_url="https://datacenter.eastmoney.com",
         meaning="2026H1 类现金(货币166+其他流动240+其他非流动419)=825 亿 vs 有息负债 651 亿 → 净头寸 +174 亿。高负债是低息融资+理财息差财技，不是缺钱。",
         signal="净头寸转负 = 危险信号(财务结构恶化)；维持正 = 负债只是放大器非炸药包",
         getter="net_cash"),
    dict(id="e_liq", group="E 财务健康(负债放大器)", name="流动比率/有息负债率", unit="—/%", ttl="quarter",
         source="东财 datacenter MAINFINADATA", source_url="https://datacenter.eastmoney.com",
         meaning="流动比率 0.69、有息负债率 33.4%——短期偿债依赖滚动融资，是「健康的紧张」。利率+100bp 净利约 -6~8%；利率+消费双杀是最大压力场景。",
         signal="流动比率持续<0.6 或 有息负债率>40% = 警惕；利率上行周期关注财务费用转正",
         getter="liq"),
    dict(id="e_fin", group="E 财务健康(负债放大器)", name="财务费用(利息净额)", unit="亿元", ttl="quarter",
         source="东财 datacenter GINCOME", source_url="https://datacenter.eastmoney.com",
         meaning="2026H1 财务费用 -5.26 亿(利息收入 10.7 > 利息支出 5.6)——借 1.7% 低息短融做理财吃息差，净利息为正。",
         signal="财务费用由负转正 = 息差结构失效(利率快速上行或理财收益崩)；维持负 = 财技仍在",
         getter="fin_expense"),

    # ============ F 同行与股东回报 ============
    dict(id="f_peer", group="F 同行与股东回报", name="伊利 vs 蒙牛营收增速", unit="%", ttl="quarter",
         source="公司公告(研报口径)", source_url="https://www.mengniu.com.cn",
         meaning="2026H1 伊利 +4.1% vs 蒙牛 +7.8%（蒙牛低基数+新品类鲜奶/奶酪+30%）。净利差距 37→100 亿主要是蒙牛两年减值 78 亿的节奏错位，蒙牛修复弹性更大。",
         signal="蒙牛持续双位数增速而伊利回落 = 差距收敛(老二反超苗头)；伊利增速反超 = 龙头地位强化",
         getter="peer_growth"),
    dict(id="f_div", group="F 同行与股东回报", name="每股分红/分红率", unit="元/%", ttl="quarter",
         source="东财分红接口", source_url="https://datacenter.eastmoney.com",
         meaning="2025 年度 10派13.8(每股 1.38)，2024 每股 1.22，分红率承诺≥75%，还有 10-20 亿回购注销。股息是持有者的补偿。",
         signal="分红率守 75% 承诺 + 每股分红逐年递增 = 股息底牢；下调分红 = 盈利或现金流恶化",
         getter="dividend"),
]