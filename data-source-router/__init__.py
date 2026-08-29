"""data-source-router — 统一数据源层 (数据源地图 + 缓存 + 路由器 + 适配器)

规范：其他 skill 及未来 skill 通过本包取数，杜绝重复探索/拿错数据/烧 token。
数据源（实测可用，详见 SKILL.md 数据源地图）：
  - A股/港股/美股行情+K线 → 腾讯 qt.gtimg.cn / web.ifzq.gtimg.cn
  - A股财报 → 东财 datacenter-web（或 akshare.stock_financial_abstract）
  - 美股财报 → SEC EDGAR (companyfacts/submissions)，需带 User-Agent
  - GitHub 读/搜 → REST API v3，未认证 60/hr
  - 宏观 → 国家统计局 data.stats.gov.cn
"""
import os
DR = os.path.dirname(os.path.abspath(__file__))
DSR_DIR = DR
