# -*- coding: utf-8 -*-
"""
人福药业 (600079 · 现名 ST人福) 财务走势 + 降本拆解看板 —— 指标元数据层
=======================================================================
「注释驱动」：每个指标自带 meaning / signal / source / ttl，渲染时动态展示为可点击查看。
原则：免费公开源(东财 datacenter)，正确性 > 及时性。

结构说明：
  - group='走势'   ：四大财务指标(营收/ROE/资产负债率/有息负债率)的【年度】趋势
  - group='快照'   ：最新一期(中报/季报)的当前值快照
  - group='降本拆解'：费用结构占比 + 财务费用去杠杆红利
"""

# 分组顺序
GROUPS = ["快照", "走势", "降本拆解"]

INDICATORS = [
    # ============ ① 快照（最新一期·当前值） ============
    dict(id="snap_rev", group="快照", name="营收(最新一期)", unit="亿元", ttl="quarter",
         source="东方财富 datacenter", source_url="https://datacenter.eastmoney.com",
         meaning="最新报告期营业总收入，看当期经营规模。",
         signal="同比由负转正 = 收入端止跌；继续负增长 = 降本保利润而非收入扩张",
         getter="snap"),
    dict(id="snap_np", group="快照", name="归母净利(最新一期)", unit="亿元", ttl="quarter",
         source="东方财富 datacenter", source_url="https://datacenter.eastmoney.com",
         meaning="最新报告期归母净利，确认当期是否真盈利。",
         signal="净利同比 > 0 = 利润在改善",
         getter="snap"),
    dict(id="snap_roe", group="快照", name="ROE(最新一期)", unit="%", ttl="quarter",
         source="东方财富 datacenter", source_url="https://datacenter.eastmoney.com",
         meaning="最新报告期加权 ROE，资本回报率。",
         signal="年化口径参考；剔权后对比同行",
         getter="snap"),
    dict(id="snap_debt", group="快照", name="资产负债率(最新一期)", unit="%", ttl="quarter",
         source="东方财富 datacenter", source_url="https://datacenter.eastmoney.com",
         meaning="总负债/总资产。持续下行 = 去杠杆中。",
         signal="持续下行 = 资产负债表修复",
         getter="snap"),
    dict(id="snap_idebt", group="快照", name="有息负债率(最新一期)", unit="%", ttl="quarter",
         source="东方财富 datacenter", source_url="https://datacenter.eastmoney.com",
         meaning="有息负债/总资产(短借+长借+应付债)，杠杆健康度。",
         signal="从36%→22% = 去杠杆红利显著释放",
         getter="snap"),

    # ============ ② 走势（年度趋势·四大财务指标） ============
    dict(id="trend_rev", group="走势", name="营收(年度)", unit="亿元", ttl="quarter",
         source="东方财富 datacenter", source_url="https://datacenter.eastmoney.com",
         meaning="历年营业总收入（年报口径），看规模扩张还是收缩。",
         signal="2024→2025 收缩 -5.8%：收入端在收缩，需警惕",
         getter="trend_rev"),
    dict(id="trend_roe", group="走势", name="ROE(年度)", unit="%", ttl="quarter",
         source="东方财富 datacenter", source_url="https://datacenter.eastmoney.com",
         meaning="历年加权 ROE，资本回报能力的中枢。",
         signal="2021→2025：10.9→10.2，中枢约 8-13%，稳定",
         getter="trend_roe"),
    dict(id="trend_debt", group="走势", name="资产负债率(年度)", unit="%", ttl="quarter",
         source="东方财富 datacenter", source_url="https://datacenter.eastmoney.com",
         meaning="历年总负债率，五年降 20 点(56%→40%)是核心亮点。",
         signal="55.8→40.1：去杠杆显著，安全垫加厚",
         getter="trend_debt"),
    dict(id="trend_idebt", group="走势", name="有息负债率(年度)", unit="%", ttl="quarter",
         source="东方财富 datacenter", source_url="https://datacenter.eastmoney.com",
         meaning="历年有息负债率。38%→23.8%，去杠杆持续降息，财务费用负担减轻。",
         signal="有息负债率下行 = 财务费用(利息)压力减轻 = 去杠杆红利",
         getter="trend_idebt"),

    # ============ ③ 降本拆解（费用结构 + 去杠杆红利） ============
    dict(id="cost_struct_latest", group="降本拆解", name="费用结构占比(最新一期)", unit="%占营收", ttl="quarter",
         source="东方财富 datacenter", source_url="https://datacenter.eastmoney.com",
         meaning="销售/管理/研发/财务费用各占营业总收入%，看钱花在哪、哪里在省。",
         signal="费用率下行(尤其财务费/管理费) = 降本见效",
         getter="cost_struct"),
    dict(id="fin_expense", group="降本拆解", name="财务费用(年度)", unit="亿元", ttl="quarter",
         source="东方财富 datacenter", source_url="https://datacenter.eastmoney.com",
         meaning="历年财务费用(利息+汇兑等)。去杠杆最直接的现金体现。",
         signal="2022→2025：4.77→2.71亿，利息负担减半",
         getter="trend_fin_exp"),
    dict(id="idebt_vs_fin", group="降本拆解", name="有息负债率 vs 财务费用", unit="% / 亿元", ttl="quarter",
         source="东方财富 datacenter", source_url="https://datacenter.eastmoney.com",
         meaning="去杠杆红利双验证：有息负债率降 → 财务费用降。",
         signal="两条线同向下行 = 降本真实且可持续",
         getter="trend_idebt_fin"),
]
