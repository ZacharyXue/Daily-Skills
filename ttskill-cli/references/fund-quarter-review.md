# 天天基金二季报分析工作流

## 前置

```bash
ttskill status --json  # 确认已登录（has_token=true）
```

## Step 1: 拉持仓

```bash
ttskill invoke ACCOUNT_HOLDING --action holding_list --body '{}'
```

关注：fundCode、fundName、assetValue、holdProfit、holdProfitRate、ptype（fund/tg/hqb）。

## Step 2: 近一年盈亏排名

```bash
# 亏损
ttskill invoke ACCOUNT_PROFIT --action profit_contribute --body '{"body":{"dateRange":4,"positive":false}}'
# 盈利
ttskill invoke ACCOUNT_PROFIT --action profit_contribute --body '{"body":{"dateRange":4,"positive":true}}'
```

`dateRange=4` = 近12月。关注 currentHold=true 的标的。

## Step 3: 基金详情（季报核心数据）

```bash
ttskill invoke TTFUND_BASE_INFOS --action query --body '{"fcode":"003956","nav_range":"n"}'
```

返回关键字段提取（Python）：

```python
fund = body['data'][0]
exp = body['expansion']['comprehensive_info']

# 基本信息
fund['SHORTNAME'], fund['FCODE'], fund['FTYPE'], fund['RISKLEVEL']
fund['ESTABDATE'], fund['ENDNAV']/1e8  # 规模（亿）

# 基金经理
mgr = exp['manager_information']['historyManagerInfos'][0]
mgr['SINFO']['MgrName']          # 姓名
mgr['SINFO']['FempDate'][:10]    # 任职日
mgr['PINFO'][0].get('INVESTMENTIDEAR')  # 投资理念

# 阶段收益 + 同类排名
for p in exp['period_increase']:
    p['title'] → 区间标识(Z/Y/3Y/6Y/1N/2N/3N/5N/JN/LN)
    p['syl']   → 本基金收益%
    p['avg']   → 同类平均%
    p['rank']  → 排名
    p['sc']    → 同类总数

# 资产配置
aa = exp['fund_profile_holdings']['asset_allocation_latest']
aa['GP']  # 股票仓位%
aa['GP_AVG_BTYPE']  # 同类平均

# 行业配置
sa = exp['fund_profile_holdings']['sector_allocation']
# HYMC=行业名, ZJZBL=占比%

# 前十大重仓
stocks = exp['fund_profile_holdings']['heavyweight_position_latest']['fundStocks']
# GPJC=股票名, GPDM=代码, JZBL=占比%, INDEXNAME=行业
# PCTNVCHGTYPE=增减方向(新增/增持/减持), PCTNVCHG=变化幅度

# 投资风格箱体
style = exp['fund_profile_archive']['invest_style_snapshot']
style['style_box']       # 3x3 风格箱体
style['turnover']         # 换手率
style['top10_concentration']  # 前十大集中度
```

## Step 4: 搜索基金代码

```bash
ttskill invoke TTFUND_SEARCH --action query --body '{"query":"万家价值优势","search_type":"fund","page_index":1,"page_size":5}'
```

## Step 5: 查股票分红/股息率

```bash
# 港股行情
ttskill invoke TTFUND_STOCK_PRICE_QUERY --action query --body '{"query":"06869"}'

# A股分红历史 → 浏览器访问新浪
# https://vip.stock.finance.sina.com.cn/corp/go.php/vISSUE_ShareBonus/stockid/601869.phtml
```

## 分析框架

1. **基本信息**：规模、经理、近期业绩（表格）
2. **季报宣传 vs 持仓验证**：基金经理说了什么 → 前十大是否支持
3. **风格漂移**：对比风格箱体的 current/avg_1y/avg_3y，看趋势
4. **换手率 + 集中度**：判断"动态"程度
5. **一句话总结**：给出明确判断

## 输出为博客文章

用户常要求将分析结果落盘到 Astro 博客（`/root/ZacharyXue.github.io/`）。**关键原则：文章中要保留对话中的所有数据和分析细节，不要压缩。** 对话中展示的表格、百分比、排名、风格箱体评分等全部带上，只是语言整理得更书面化。

### 博客发布流程

1. 写完 markdown 正文，frontmatter 含 title/date/tags/description
2. 放入 `src/content/blog/YYYY-MM-DD-slug.md`
3. `npm run build` 验证通过
4. 如需从首页隐藏：frontmatter 加 `hide_from_home: true`（已在 config.ts schema 中定义）

### 标签选择

用户偏好简洁的标签，不堆砌技术关键词。使用基金经理名、主题词（红利、理财）等有实际检索意义的标签。避免「二季报」「持仓验证」「安全边际」这类过于通用的描述词——用户会明确指定要哪些。

## Step 6: 拉基金定期报告PDF提取经理原文（市场观点/运作分析）

用户要「基金经理自己叙述的市场观点与仓位操作」时，`TTFUND_BASE_INFOS` 的 `holding_ai_summary`（fund_profile_archive 下）只是**衍生 AI 摘要**，不是经理亲述。经理原话在**基金定期报告（季报/中报/年报）PDF**里。可靠路径（2026-08 实测，天天基金 JJGG API 对服务器返回 0，走不了）：

1. **用浏览器（playwright）打开 fundf10 定期报告页**拿中报链接：
   - URL：`https://fundf10.eastmoney.com/jjgg_<6位代码>_3.html`（第3页=定期报告，菜单里「定期报告」）
   - `page.goto(url, {waitUntil:'networkidle'})` → JS 渲染后 `#ggtable table tr td a` 取标题+`href`
   - 匹配 `/中期报告|半年报/` 那条 → href 形如 `https://fund.eastmoney.com/gonggao/<code>,AN....html`
2. **进公告页找 PDF**：同样浏览器拿 `a[href*='.pdf' ]`，能拿到 `https://pdf.dfcfw.com/pdf/H2_AN..._1.pdf?...`（基金定期报告 PDF 在 pdf.dfcfw.com）
3. **下载 + pymupdf 提取**：
   ```python
   import urllib.request, pymupdf
   data = urllib.request.urlopen(urllib.request.Request(pdf_url, headers={"User-Agent":"Mozilla/5.0"}), timeout=60).read()
   text = "\n".join(p.get_text() for p in pymupdf.open(io.BytesIO(data)))
   ```
4. **定位经理观点段**（正文，不是目录）：
   - 「运作分析」/「投资策略和运作分析」→ 经理本季**仓位操作**（买了/卖了什么、超配什么）
   - 「对宏观经济、证券市场及行业走势的简要展望」→ 经理**后市观点**
   - ⚠️ 锚点会先命中**目录**（后面是 `..... 12` 页码），要跳过目录取正文：匹配「价值与成长风格相比」这类正文特有短语，或往前 rfind「展望」；或用「运作分析」后紧跟正文而非页码的实例。

**关键点**：季报/中报 PDF 都含「运作分析 + 简要展望」两段，是经理第一手观点；`holding_ai_summary` 只能作补充不能当经理原话。

## 常见陷阱

- 天天基金港股 F10 页面不可用，用浏览器看新浪财经分红页
- `profit_contribute` 返回包含已清仓标的，需过滤 `currentHold=false`
- 投顾产品（tg）的 holdProfit 为 `--`，需单独处理
- `TTFUND_BASE_INFOS` 返回数据量大（30万字符），用 Python 提取关键字段
- **规模历史/份额历史在 `fund_profile_archive.asset_scale_history`/`share_scale_history`，是 list（最新在前），不是 dict**：`[]` 取头几条=最新，字段 `NETNAV`(规模元)/`CHANGE`(同%)/`QMZFE`(期末份额)/`NETFLOW`(净申)。最新规模用 `ENDNAV/1e8`（单期最准）。
- **历史配置字段是 dict{报告日期:[rows]}**：`asset_allocation_history`/`sector_allocation_history`/`stock_theme_history` 都是 dict，键=日期，值=rows 列表（`GP`股票%/`HYMC`行业/`TOPICCODE`主题+`PCTNV`占比）。遍历用 `for d, rows in x.items()`，别当 list 切片。
- 风格箱体数据在 `fund_profile_archive` 而非 `fund_profile_holdings`
