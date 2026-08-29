# -*- coding: utf-8 -*-
"""
人福药业(600079 / ST人福) 财务走势 + 降本拆解看板 —— 指标元数据层
=============================================================
「注释驱动」核心：每个指标自带 meaning / signal / source / ttl，
渲染时动态展示为「可点击查看」，不加载任何 skill 上下文。
原则：全部免费公开源，正确性 > 及时性。

⚠️ 数据正确性铁律：
  - 本看板所有数值只来自东财 datacenter(GINCOME/MAINFINADATA) 自动取数。
  - 禁止 hardcode 任何无法从数据源取到的明细数字（如研发职工薪酬/耗用材料拆分）。
  - 营收同比按「同报告期累计值」重算，不信任东财 TOTALOPERATEREVETZ 字段(有 bug)。

指标 = {
  id, group,            分组
  name, unit,           展示名、单位
  ttl,                  缓存分级
  source, source_url    数据源名称(人读)、链接(可溯源)
  meaning,              为什么关注(一句话)
  signal,               看什么信号/阈值
  getter,               fetch.py 中对应的取数函数
}
"""

GROUPS = ["快照(最新一期)", "四大财务走势(年度)", "降本拆解(费用结构)", "去杠杆红利验证"]

INDICATORS = [
    # ============ 快照：最新一期(2026中报)四个核心 ============
    dict(id="snap_rev", group="快照(最新一期)", name="营业总收入", unit="亿元", ttl="quarter",
         source="东财 datacenter", source_url="https://datacenter.eastmoney.com",
         meaning="最新报告期(2026中报)累计营收。人福 2025年报 239.6亿→2026中报 120.6亿，处于收缩轨道。",
         signal="营收同比转正=重回扩张；增速持续为负=靠降本保利润而非收入扩张(当前 -0.0%)",
         getter="snap"),
    dict(id="snap_np", group="快照(最新一期)", name="归母净利", unit="亿元", ttl="quarter",
         source="东财 datacenter", source_url="https://datacenter.eastmoney.com",
         meaning="最新报告期归母净利。2026中报 13.30亿(+15.1%)，逆营收收缩而增长——靠降本+去杠杆。",
         signal="净利同比>0 且营收同比<0 = 典型降本驱动(当前正是)；两者同增=健康扩张",
         getter="snap"),
    dict(id="snap_roe", group="快照(最新一期)", name="ROE(加权)", unit="%", ttl="quarter",
         source="东财 datacenter", source_url="https://datacenter.eastmoney.com",
         meaning="最新报告期加权 ROE(2026中报 6.82%)。年度中枢约 8-13%，资本回报中上。",
         signal="ROE 站稳 10%+ = 盈利质量修复；<8% = 净资产回报偏弱",
         getter="snap"),
    dict(id="snap_debt", group="快照(最新一期)", name="资产负债率", unit="%", ttl="quarter",
         source="东财 datacenter", source_url="https://datacenter.eastmoney.com",
         meaning="最新报告期总负债率(2026中报 39.66%)。五年从 56%→40%，去杠杆核心亮点。",
         signal="持续下行=资产负债表修复；ST 后需鉴别是否因剥离资产被动下降",
         getter="snap"),
    dict(id="snap_idebt", group="快照(最新一期)", name="有息负债率", unit="%", ttl="quarter",
         source="东财 datacenter(INTEREST_DEBT_RATIO)", source_url="https://datacenter.eastmoney.com",
         meaning="有息负债/总资产(短借+长借+债券等)。2026中报 22.1%，是降本(财务费用)的根源。",
         signal="36%→22% 大幅去杠杆 = 利息负担显著下降(降本红利)；上行=重新加杠杆",
         getter="snap"),

    # ============ 四大财务走势（年度 SVG） ============
    dict(id="trend_rev", group="四大财务走势(年度)", name="营收(年度)", unit="亿元", ttl="quarter",
         source="东财 datacenter", source_url="https://datacenter.eastmoney.com",
         meaning="历年营业总收入(年报口径)。2016 123亿→2024 254亿峰值→2025 239.6亿回落。",
         signal="2024→2025 -5.8%：收入端在收缩，是「降本保利润」叙事里最需警惕的信号",
         getter="trend_rev"),
    dict(id="trend_roe", group="四大财务走势(年度)", name="ROE(年度)", unit="%", ttl="quarter",
         source="东财 datacenter", source_url="https://datacenter.eastmoney.com",
         meaning="历年加权 ROE(年报口径)。2022 高位 17.6%→2024 低点 7.7%→2025 回升 10.2%。",
         signal="ROE 中枢约 8-13%；回升=盈利质量修复，跌破 8% 需警惕",
         getter="trend_roe"),
    dict(id="trend_debt", group="四大财务走势(年度)", name="资产负债率(年度)", unit="%", ttl="quarter",
         source="东财 datacenter", source_url="https://datacenter.eastmoney.com",
         meaning="历年资产负债率(年报口径)。2019 60%→2025 40.1%，五年降 20 点，去杠杆核心。",
         signal="55.8→40.1 连续下行 = 资产负债表安全垫加厚；ST 下需关注剥离/处置影响",
         getter="trend_debt"),
    dict(id="trend_idebt", group="四大财务走势(年度)", name="有息负债率(年度)", unit="%", ttl="quarter",
         source="东财 datacenter(INTEREST_DEBT_RATIO)", source_url="https://datacenter.eastmoney.com",
         meaning="历年有息负债率(年报口径)。2020 43.4%近期高点→2025 23.8%，是降本(财务费用)的直接来源。",
         signal="36%→23.8% 连续下行 = 去杠杆红利兑现在财务费用端",
         getter="trend_idebt"),

    # ============ 降本拆解（费用结构，核心） ============
    dict(id="cost_struct_latest", group="降本拆解(费用结构)", name="费用占比(最新一期)", unit="%", ttl="quarter",
         source="东财利润表 GINCOME", source_url="https://datacenter.eastmoney.com",
         meaning="2026中报销售/管理/研发/财务费用占营收比。医药销售费用是最大费用项(19.5%)，研发 5.3%，财务费 1.8%——财务费最低是去杠杆红利。",
         signal="销售费用率下行=营销效率提升；财务费用率==1.8%低点=去杠杆见效；研发费用率稳=未来蓄力",
         getter="cost_struct"),
    dict(id="fin_expense", group="降本拆解(费用结构)", name="财务费用(年度)", unit="亿元", ttl="quarter",
         source="东财利润表 GINCOME", source_url="https://datacenter.eastmoney.com",
         meaning="历年财务费用(年报口径)。2019-2020 高点 8-9亿→2024 3.5亿→2025 3.03亿，去杠杆红利核心证据。",
         signal="财务费用从 9亿→3亿 大幅腰斩 = 有息负债减少+利率下降双重贡献",
         getter="trend_fin_exp"),
    dict(id="idebt_vs_fin", group="降本拆解(费用结构)", name="有息负债率 vs 财务费用(双线)", unit="—", ttl="quarter",
         source="计算(东财)", source_url="https://datacenter.eastmoney.com",
         meaning="有息负债率(左轴)与财务费用(右轴)同向下行，互证「去杠杆→少付利息」的真实性与可持续性。",
         signal="两条线同向下行=去杠杆真实且可持续——这解释了营收收缩但净利仍增长",
         getter="trend_idebt_fin"),
    dict(id="contrib_breakdown", group="降本拆解(费用结构)", name="降本贡献度拆解(同比)", unit="亿元", ttl="quarter",
         source="东财利润表 GINCOME", source_url="https://datacenter.eastmoney.com",
         meaning="2026中报 vs 2025中报，归母净利 +1.75亿 的每一分增量从哪来：营业成本-2.39亿/研发-1.03亿/管理-0.63亿是贡献，销售+1.41亿/财务+0.90亿是拖累，净+1.75亿。",
         signal="绿色(降本)=救利润，红色(费用增)=吞噬利润。头号功臣=营业成本，最需警惕研发(利润种子)",
         getter="contrib_breakdown"),
]
