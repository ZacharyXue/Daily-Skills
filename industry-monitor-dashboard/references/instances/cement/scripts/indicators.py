# -*- coding: utf-8 -*-
"""
水泥行业 & 海螺水泥 盈利底监测看板 —— 指标元数据层
=====================================================
「注释驱动」核心：每个指标自带 meaning / signal / source / ttl，
渲染时动态展示为「可点击查看」，不加载任何 skill 上下文。
原则：全部免费公开源，正确性 > 及时性，日/周/月/季分级缓存。

指标 = {
  id, group                分组
  name, unit               展示名、单位
  ttl                      'day'|'week'|'month'|'quarter' 缓存分级
  source                   数据源名称(人读)
  source_url               数据源链接(可溯源)
  meaning                  为什么关注这个指标(一句话)
  signal                  看什么信号/阈值(可写多级)
  getter                   fetch.py 中对应的取数函数
  needed_calc             是否需二次计算(True=由其它指标合成)
}
"""

# 分组顺序
GROUPS = ["价格组", "成本组", "量组", "供给/出清组", "盈利组", "财务安全垫组", "估值/技术闸门组"]

INDICATORS = [
    # ============ ① 价格组（最优先·周度） ============
    dict(id="po425", group="价格组", name="P.O42.5 全国均价", unit="元/吨", ttl="week",
         source="中国水泥网", source_url="https://index.ccement.com/index/priceindex/po425zsline",
         meaning="水泥终端价格。价格止跌是盈利修复的起点，没有价格先验，一切免谈。",
         signal="现行~278 → 站稳300+且周环比连涨2-3周=止跌；320+且提价落地率>70%=修复确认",
         getter="po425_price"),
    dict(id="cempi", group="价格组", name="全国水泥价格指数 CEMPI", unit="指数点", ttl="week",
         source="中国水泥网", source_url="https://index.ccement.com/index/priceindex/getPriceIndex",
         meaning="全国综合水泥价格指数，行业价格景气度的宏观读数。",
         signal="一年下行-12.7%；止跌=指数止跌回升，不再创年内新低",
         getter="cempi_index"),
    dict(id="clinker", group="价格组", name="熟料价格", unit="元/吨", ttl="week",
         source="中国水泥网", source_url="https://index.ccement.com/index/clinker/ClinkerPrice",
         meaning="水泥半成品，领先指标。熟料先涨通常预示水泥跟涨。",
         signal="熟料领先走强=需求/供给边际改善",
         getter="clinker_price"),
    dict(id="cempi_clinker_spread", group="价格组", name="水泥-熟料价差", unit="元/吨", ttl="week",
         source="计算(中国水泥网)", source_url="",
         meaning="水泥价-熟料价。价差走扩=供给收敛/盈利弹性，是供给侧代理。",
         signal="价差走扩=盈利改善领先信号；价差收窄=价格战加剧",
         getter="spread_calc", needed_calc=True),
    dict(id="concrete", group="价格组", name="混凝土价格", unit="元/吨", ttl="week",
         source="中国水泥网", source_url="https://index.ccement.com/index/concrete/ConcretePrice",
         meaning="终端需求镜像，量端的间接验证（成交驱动）。",
         signal="混凝土价企稳=需求不再塌方；持续阴跌=需求仍弱",
         getter="concrete_price"),

    # ============ ② 成本组（月度/季度·防增收不增利） ============
    dict(id="coal", group="成本组", name="煤炭价格指数", unit="指数点", ttl="week",
         source="中国水泥网", source_url="https://index.ccement.com/index/priceindex/getPriceIndex",
         meaning="水泥成本大头是煤。水泥涨价+煤稳/跌=真弹性；煤同涨吃掉吨毛利=伪回升。",
         signal="近1年煤价-23%；水泥涨+煤不涨=盈利弹性打开",
         getter="coal_index"),
    dict(id="ton_cost", group="成本组", name="海螺单季吨成本", unit="元/吨", ttl="quarter",
         source="海螺财报PDF提取", source_url="https://pdf.dfcfw.com",
         meaning="水泥单位成本，成本优势在不在的验证(燃料动力/原材料/折旧/人工)。",
         signal="维持≤230=成本优势在位；上破=成本优势侵蚀",
         getter="rep_ton_cost"),

    # ============ ③ 量组（月度·验证止跌回稳而非增长） ============
    dict(id="national_output", group="量组", name="全国水泥产量同比", unit="%", ttl="month",
         source="国家统计局(待换通道)", source_url="",
         meaning="需求最直接的量。产量同比收窄到0附近=止跌回稳；仍在-8%=塌方未止。",
         signal="-8%收窄到-3%~0%=止跌回稳",
         getter="national_output_yoy", pending=True),
    dict(id="helluo_sales", group="量组", name="海螺自产品销量同比", unit="%", ttl="quarter",
         source="海螺财报PDF提取", source_url="https://pdf.dfcfw.com",
         meaning="海螺自身销量拐点，量端验证（止跌回稳而非增长）。",
         signal="回0~+3%=量拐点；仍负=需求未止",
         getter="rep_sales_yoy"),

    # ============ ⑤ 盈利组（季度核心·经营杠杆兑现） ============
    dict(id="ton_gross_margin", group="盈利组", name="海螺单季吨毛利", unit="元/吨", ttl="quarter",
         source="海螺财报PDF提取", source_url="https://pdf.dfcfw.com",
         meaning="盈利底的直接证据。吨毛利修复=涨价没被成本吃掉，落地为利润。",
         signal="40→55元=盈利底确认；55-70=反转区；70+=双击",
         getter="rep_ton_gm"),
    dict(id="helluo_np", group="盈利组", name="海螺归母净利同比", unit="%", ttl="quarter",
         source="东财 datacenter", source_url="https://datacenter.eastmoney.com",
         meaning="财务端总验证，吨毛利改善的最终变现。",
         signal="净利同比由负转正=盈利拐点确认",
         getter="helluo_np_yoy"),
    dict(id="cashflow_ratio", group="盈利组", name="经营现金流/净利", unit="x", ttl="quarter",
         source="东财 datacenter", source_url="https://datacenter.eastmoney.com",
         meaning="利润含金量。>1.5x=赚的是真钱不是应收账款。",
         signal=">1.5x=含金量足；<1=盈利质量存疑",
         getter="cashflow_ratio"),
    dict(id="ton_price", group="盈利组", name="海螺吨售价", unit="元/吨", ttl="quarter",
         source="海螺财报PDF提取", source_url="https://pdf.dfcfw.com",
         meaning="单价端验证：吨售价回升=价格修复传导到公司。",
         signal="290→310+=海螺端验证；<250=仍深陷价格战",
         getter="rep_ton_price"),
    dict(id="ton_np", group="盈利组", name="海螺吨净利", unit="元/吨", ttl="quarter",
         source="海螺财报PDF提取", source_url="https://pdf.dfcfw.com",
         meaning="归母净利/销量，最薄一层利润，盈利底确认的进阶信号。",
         signal="吨净利回升=盈利底确认进阶",
         getter="rep_ton_np"),

    # ============ ⑥ 财务安全垫组（季度） ============
    dict(id="debt_ratio", group="财务安全垫组", name="海螺资产负债率", unit="%", ttl="quarter",
         source="东财 datacenter", source_url="https://datacenter.eastmoney.com",
         meaning="出清期能不能熬。负债率低=价格战里能扛。",
         signal="稳<30%(当前~20%)=安全垫厚",
         getter="debt_ratio"),
    dict(id="dividend_yield", group="财务安全垫组", name="海螺股息率", unit="%", ttl="day",
         source="计算(腾讯+财报)", source_url="https://qt.gtimg.cn",
         meaning="高股息防守逻辑的天平。股息率>无风险利率=防御资金会进场。",
         signal="股息率>10年国债=估值有防守底",
         getter="dividend_yield_calc"),
    dict(id="monetary", group="财务安全垫组", name="海螺货币资金", unit="亿元", ttl="quarter",
         source="东财资产负债表", source_url="https://datacenter.eastmoney.com",
         meaning="出清期现金储备，能否熬过价格战的弹药。",
         signal="货币资金不缩水(当前~343亿)=安全垫厚",
         getter="monetary"),
    dict(id="idebt", group="财务安全垫组", name="有息负债率", unit="%", ttl="quarter",
         source="东财资产负债表", source_url="https://datacenter.eastmoney.com",
         meaning="有息负债/总资产(短借+长借+应付债)，杠杆健康度。",
         signal="低有息负债=现金奶牛；高=价格战里被动",
         getter="idebt"),
    dict(id="fcf", group="财务安全垫组", name="自由现金流 FCF", unit="亿元", ttl="quarter",
         source="东财现金流量表", source_url="https://datacenter.eastmoney.com",
         meaning="经营现金-资本开支，真金白银的造血能力。",
         signal="FCF 为正=造血；转负=扩张或恶化",
         getter="fcf"),

    # ============ ⑦ 估值/技术闸门组（日度·仅入场确认） ============
    dict(id="pb", group="估值/技术闸门组", name="海螺 PB / 历史分位", unit="x / 分位", ttl="day",
         source="腾讯行情+东财", source_url="https://qt.gtimg.cn",
         meaning="破净锚定。当前0.50(深度破净)，用历史分位判断是否极端低估。",
         signal="PB分位<20%=极端低估区；>80%=修复到位",
         getter="pb_percentile"),
    dict(id="ma", group="估值/技术闸门组", name="均线 MA20/60", unit="元", ttl="day",
         source="腾讯ifzq(前复权K线)", source_url="https://web.ifzq.gtimg.cn",
         meaning="趋势确认。站上20/60日线=短中期趋势走强。",
         signal="站上20日线(MACD零下金叉)=第一笔；突破60日线+放量=第二笔",
         getter="ma_calc"),
    dict(id="macd_rsi", group="估值/技术闸门组", name="MACD / RSI", unit="—", ttl="day",
         source="腾讯ifzq(前复权K线)", source_url="https://web.ifzq.gtimg.cn",
         meaning="动量确认，避免拿基本面数据做高频交易。",
         signal="MACD零轴下金叉+RSI回升=动能转强",
         getter="macd_rsi_calc"),
    dict(id="kdj", group="估值/技术闸门组", name="KDJ", unit="—", ttl="day",
         source="腾讯ifzqK线", source_url="https://web.ifzq.gtimg.cn",
         meaning="短线超买超卖。", signal="KDJ金叉且J低位回升=动能转强；J>80超买",
         getter="kdj_calc"),
    dict(id="boll", group="估值/技术闸门组", name="布林带 BOLL(20,2)", unit="元", ttl="day",
         source="腾讯ifzqK线", source_url="https://web.ifzq.gtimg.cn",
         meaning="波动区间：中轨=20日均线，上下轨=±2σ。", signal="站上中轨=趋势转多；贴近下轨=超跌",
         getter="boll_calc"),
    dict(id="vol", group="估值/技术闸门组", name="量能(量比)", unit="x", ttl="day",
         source="腾讯ifzqK线", source_url="https://web.ifzq.gtimg.cn",
         meaning="回踩量能：突破要放量、回踩要缩量。", signal="突破量比>1.5=有效；回踩量比<0.8=健康",
         getter="vol_calc"),
    dict(id="gm", group="盈利组", name="海螺毛利率", unit="%", ttl="quarter",
         source="东财 datacenter", source_url="https://datacenter.eastmoney.com",
         meaning="盈利能力主口径，同行对比的锚。", signal="毛利率回升=价格/成本改善",
         getter="gm_rate"),
    dict(id="payout", group="财务安全垫组", name="分红率", unit="%", ttl="quarter",
         source="海螺财报PDF提取", source_url="https://pdf.dfcfw.com",
         meaning="分红/归母净利，股东回报意愿。", signal="35%→45-50%=分红提升可信",
         getter="payout_rate"),
]
# 供 fetch 使用的 getter 集合(需在 fetch.py 实现)
GETTERS = sorted({i["getter"] for i in INDICATORS})
