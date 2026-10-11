# 天天基金分析工作流速查

## 持仓表现扫描（"哪些表现差"）

```
# 1. 拿持仓列表
ttskill invoke ACCOUNT_HOLDING --action holding_list --body '{}'

# 2. 近12月亏损/盈利贡献（dateRange: 0=本月,1=今年,2=近3月,3=近6月,4=近12月,7=开户以来）
ttskill invoke ACCOUNT_PROFIT --action profit_contribute --body '{"body":{"dateRange":4,"positive":false}}'
ttskill invoke ACCOUNT_PROFIT --action profit_contribute --body '{"body":{"dateRange":4,"positive":true}}'

# 3. 交叉对比：将 holding_list 的 currentHold 与 profit_contribute 的 fundCode 做 join
```

profit_contribute 返回所有有交易的基金（含已清仓），通过 `currentHold` 字段过滤。

## 基金季报 / 二季报分析

**核心 Skill：`TTFUND_BASE_INFOS`**（不需要 `TTFUND_RESEARCH_SEARCH`）

```bash
ttskill invoke TTFUND_BASE_INFOS --action query --body '{"fcode":"003956","nav_range":"n"}'
```

一次调用返回：
- `data[]` — 基本信息、规模、净值、阶段收益（含同类排名）
- `expansion.comprehensive_info.manager_information` — 基金经理、理念、任期收益
- `expansion.comprehensive_info.period_increase[]` — 各阶段收益+同类均值+排名
- `expansion.comprehensive_info.fund_profile_holdings.asset_allocation_latest` — 股/债/现仓位
- `expansion.comprehensive_info.fund_profile_holdings.sector_allocation[]` — 行业配置
- `expansion.comprehensive_info.fund_profile_holdings.heavyweight_position_latest.fundStocks[]` — 前十大重仓（含增减持）

用 Python 提取关键字段效率最高：

```bash
python3 -c "
import json, subprocess
result = subprocess.run(['ttskill', 'invoke', 'TTFUND_BASE_INFOS', '--action', 'query',
    '--body', '{\"fcode\":\"003956\",\"nav_range\":\"n\"}'],
    capture_output=True, text=True, timeout=60)
data = json.loads(result.stdout)
# 从 data['data']['raw_result']['body']['expansion']['comprehensive_info'] 取各模块
"
```

## 基金搜索

```bash
ttskill invoke TTFUND_SEARCH --action query --body '{"query":"万家价值优势","search_type":"fund","page_index":1,"page_size":5}'
```

返回 candidates 包含 `code`（基金代码）、`name`、`category_name`。

## 基金经理信息（TTFUND_MANAGER_INFO）

⚠️ **参数是 `manager_name`，不是 `query`**（传 `query` 会 HTTP 400 "至少提供以下参数之一: manager_id、manager_name"）。

```bash
ttskill invoke TTFUND_MANAGER_INFO --action query --body '{"manager_name":"孔令超"}'
```

返回 `manager_profile`（简历/任职/投资理念/在管规模）+ `managed_funds[]`（所有在管基金业绩，可用于横向看经理能力）。

## 基金历史净值（TTFUND_NAV_INFO）

⚠️ **参数是 `fund_id`，不是 `fcode`**（传 `fcode` 会 HTTP 400 "缺少参数: fund_id"）。

```bash
ttskill invoke TTFUND_NAV_INFO --action query --body '{"fund_id":"005974","range":"ln"}'
```

`range` 枚举：`y`=近1月, `3y`=近3月, `6y`=近6月, `n`=近1年, `2n`=近2年, `3n`=近3年, `ln`=成立以来（默认 n）。`ln` 返回全部历史净值，可算年度收益。

### 用 NAV 算年度收益（避免误用年初/年末跳空）

```python
# items: [{FSRQ: "2026-06-30", DWJZ: ..., LJJZ: ...}]
year_last = {}
for it in items:
    ljjz = float(it.get('LJJZ') or 0)
    if ljjz:
        year_last[it['FSRQ'][:4]] = (it['FSRQ'], ljjz)  # 最后赋值=年末
for y in sorted(year_last):
    if prev: chg = (year_last[y][1] / prev[1] - 1) * 100
```

✅ **用 LJJZ（累计净值）且用「年末/上年末-1」**；别用「年初/上年末-1」——分红或估值调整会造成年初跳空，算出假收益。

## 指数分析（TTFUND_INDEX_INFO）

```bash
ttskill invoke TTFUND_INDEX_INFO --action query --body '{"index_id":"931722"}'
# index_id 支持代码或名称（沪深300、国新港股通央企红利）
```

返回（一次拿全，非常强）：
- `index_profile` — 定义/编制方/成立相关基金
- `performance` — 1d/1w/1m/3m/6m/1y/2y/3y/5y 涨跌幅
- `valuation` — PE(TTM)/PB + **十年分位**（判断贵贱的关键）
- `composition.top_industries` — 行业权重；`composition.component_details` — 前十大成分股（含 SECURITY_NAME_ABBR/DERIVE_SECURITY_CODE/INDUSTRY）

## 组合回测（TTFUND_GROUP_BACKTEST）

```bash
ttskill invoke TTFUND_GROUP_BACKTEST --action query --body '{"action":"bt_detail_v2","bt_detail_v2":{"fundPercent":"[{\"fundCode\":\"005974\",\"fundRation\":60},{\"fundCode\":\"012951\",\"fundRation\":40}]","groupAmount":10000,"modelType":0,"rebalanceMode":1,"startTime":"2021-08-01T00:00:00","endTime":"2026-08-14T00:00:00","intervalStartTime":"2024-01-01T00:00:00"}}'
```

- `fundPercent` 必须是 JSON 字符串，占比和=100
- 结果在 `data.raw_result.body.data.steps.bt_detail_v2.body.data`：`accumProfitRate`（区间累计）、`intervalDrawDown`（区间最大回撤）、`sharpRate`（夏普）、`profitRetraceRatio`
- 适合对比不同基金/配比的历史表现（多方案循环调用直接出对比表）

## 指数日线/回撤测算（ttskill 之外，中证官网）

中证指数官网（无需登录，基日 2016-08-17 起有数据）：
```bash
curl -s "https://www.csindex.com.cn/csindex-home/perf/index-perf?indexCode=931722&startDate=20160817&endDate=20260817&frequency=daily"
# data[]: tradeDate(YYYYMMDD), close(点位)
```

配合 `scripts/index_drawdown.py`（本 skill 自带）可得：最大/平均回撤、显著回撤分位数（50/75/80/90%）、每次回撤的恢复耗时。

## 港股股票数据（ttskill 之外的 fallback）

`TTFUND_STOCK_PRICE_QUERY` 只返回价格/成交量，没有分红历史、PE、股息率。

### 港股实时行情 + 股息率

```bash
# secid 格式：116.{港股代码}，例如 116.06869
curl -s "https://push2.eastmoney.com/api/qt/stock/get?secid=116.06869&fields=f43,f57,f58,f60,f116,f162,f167,f170"
```

关键字段：`f43`=最新价(hkd), `f116`=总市值, `f167`=股息率(%), `f162`=PE(TTM)

### A股分红历史

新浪财经分红页面（稳定、无需反爬）：
```
https://vip.stock.finance.sina.com.cn/corp/go.php/vISSUE_ShareBonus/stockid/{code}.phtml
```

例如 `601869.phtml`，页面含完整历史分红表格（公告日期、每10股派息、除权除息日）。

## Pitfalls

- **`TTFUND_RESEARCH_SEARCH` 不适合查基金季报**：它搜的是第三方研报/新闻，几乎不会命中某只基金的具体定期报告。查季报持仓 → 用 `TTFUND_BASE_INFOS`。
- **`profit_contribute` 的 body 必须嵌套**：`--body '{"body":{"dateRange":4,"positive":false}}'`，不是 `--body '{"dateRange":4,...}'`。
- **港股价格单位**：eastmoney API 返回的 `f43` 已经是港元（不是分），直接可用。
- **`TTFUND_BASE_INFOS` 输出极大**（~300KB），务必用 Python 提取关键字段，不要把原始 JSON 灌入上下文。
