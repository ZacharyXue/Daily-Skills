---
name: data-source-router
description: 统一数据源层（金融 + IT）— 数据源地图 + SQLite缓存 + Tier路由 + 合规红线。其他 skill 及未来 skill 一律通过本层取数，杜绝重复探索、拿错数据、烧 token。覆盖：A股/港股/美股行情与K线(腾讯)、A股财报(东财datacenter)、美股财报(SEC EDGAR)、宏观(统计局)、GitHub仓库/Issues/PR/Release/搜索(REST)。触发时机：任何需要拉金融或 IT 数据的任务（行情、财报、宏观、仓库元数据、issue/pr/release、仓库搜索）。
version: 1.0.0
tags: [data, finance, github, cache, api, 数据源, 行情, 财报]
related_skills: [industry-monitor-dashboard, whale-holdings, stock-analysis, github-repo-management, github-issues, github-oss-evaluation]
---

# data-source-router — 统一数据源层

## 这个 skill 解决什么

**一个数据源地图 + 缓存 + 路由的统一层，全 agent 的取数唯一入口。** 目的（用户 2026-08 定调）：
> 规范当前数据来源，其他 skill 及未来 skill 调用本 skill 获取准确数据，而不是可能拿错误数据或消耗 token 再探索数据获取。

- **不重复造轮子**：`industry-monitor-dashboard`（其下实例：水泥/ETF）/ whale-holdings / stock-analysis 等已有 skill 的原始数据抓取，**统一上移到这里**，各自只保留领域逻辑（估值分位/信号/13F解析等）。
- **不拿错数据**：本层内置**正确性校验**（多源交叉比对 + 时间戳 + metric 变更应对），实测可用才收录，不可用源在文档里标注。
- **不烧 token**：SQLite 缓存 + TTL + stale-while-revalidate，同一数据多次取不重复回源。

## 数据源地图（ECS 实测可用，2026-08 验证）

> ⚠️ **以下全部经过 ECS 真实调用验证**（不是网络猜测）。凡是未实测通过的源一律**不收录**，避免误导。

| 数据类型 | kind | 首选源 | 实测状态 | 延迟 |
|---|---|---|---|---|
| A股实时行情 | `cn_stock_quote` | 腾讯 `qt.gtimg.cn` | ✅ 200 | 实时 |
| A股日K线(前复权) | `cn_stock_kline` | 腾讯 `web.ifzq.gtimg.cn` | ✅ 200 | T+1 |
| 港股行情/K线 | `hk_stock_quote`/`hk_stock_kline` | 腾讯 | ✅ 200 | 实时 |
| 美股行情 | `us_stock_quote` | 腾讯 `usAAPL` | ✅ 200 | 实时 |
| A股财报 | `cn_financial` | 东财 `datacenter-web` | ✅ 200 | 季报后1-3天 |
| A股财报完整序列 | `cn_financial_series` | 东财 `datacenter-web`(多报告期) | ✅ 200 | 季报后1-3天 |
| 美股财报(facts) | `us_financial_sec` | SEC EDGAR `companyfacts` | ✅ 200(带UA) | 即时 |
| 美股营收提取 | `us_revenue_sec` | SEC EDGAR | ✅ 200 | 即时 |
| 宏观 | (预留) | 国家统计局 `data.stats.gov.cn` | ✅ 200 | 月度 |
| 行业指数(水泥网) | `cn_cement_index` | 中国水泥网 `index.ccement.com` | ✅ 200(丢包重试) | 日频 |
| 水泥-熟料价差 | `cn_cement_spread` | 中国水泥网(合成) | ✅ | 日频 |
| 指数PE(中证) | `cn_csindex_pe` | 中证官网 `csindex-home/perf/index-perf` 的 `peg` | ✅ 200 | 日频 |
| 指数估值(天天基金) | `cn_ttfund_index` | 天天基金 `ttskill TTFUND_INDEX_INFO` | ✅ CLI | 日频 |
| GitHub 仓库元数据 | `github_repo` | GitHub REST v3 | ✅ 200 | 实时 |
| GitHub Issues | `github_issues` | GitHub REST v3 | ✅ 200 | 实时 |
| GitHub PR | `github_pulls` | GitHub REST v3 | ✅ 200 | 实时 |
| GitHub Release | `github_release` | GitHub REST v3 | ✅ 200 | 实时 |
| GitHub 文件 | `github_file` | GitHub REST v3 | ✅ 200 | 实时 |
| GitHub 搜索 | `github_search` | GitHub REST v3 | ✅ 200 | 实时 |
| GitHub 贡献者(健康度) | `github_contributors` | GitHub REST v3 `/contributors`+Link头 | ✅ 200 | 实时 |
| GitHub 低门槛label计数 | `github_label_counts` | GitHub Search API | ✅ 200 | 实时 |

### ❌ 实测不可用（不要用，写进这里避免重蹈）

| 源 | 状态 | 原因 |
|---|---|---|
| AKShare 实时/历史K线 | ❌ ECS 断连 | `stock_zh_a_spot_em` / `stock_zh_a_hist` → `ConnectionError`，走东财 push2 被断连。**AKShare 仅 `stock_financial_abstract`(东财财报) 可用** |
| Yahoo / yfinance | ❌ 429 | ECS IP 被 Yahoo 限流；Stooq 也被 JS 墙。**美股行情用腾讯 `usAAPL` 替代** |
| 新浪 `hq.sinajs.cn` | ❌ 403 | 封了，别用 |
| FRED | ⚠️ 需 key | 要注册 API key，非"免key"，用国家统计局替代 |
| 深交所 `szse.cn` | ❌ 000 | 连不上；港股披露易 302 |
| GitHub GraphQL | ⚠️ 未认证=0 | 未认证 GraphQL 不可用，**统一走 REST** |

### SEC EDGAR 关键坑（whale-holdings 早踩过）
- **必须带 `User-Agent` 含邮箱**，否则 403。env `SEC_USER_AGENT`，默认已内置。
- **CIK 要 10 位前导零**（`0000320193`），URL 路径去零但 `submissions/CIK{:010d}` 处要补回。适配器 `_pad_cik()` 已处理。
- **限速 ≤10 req/s**，批量拉多机构时保持间隔。
- **metric 名会随准则变更**：Apple 2018 起 `Revenues` 停止更新，新版是 `RevenueFromContractWithCustomerExcludingAssessedTax`。**`sec_latest_revenue` 对多个候选 metric 取 end 日期最新的一条**，否则会拿到 2018 的过期营收（实测踩过，正确性>及时性）。
- **reporting scope 混排**：同一 metric 的 series 里累计值(TTM)/单季值会混着，取数后要按 `form`/`frame` 或报告期判断口径，别直接当单季。

## 目录结构

```
zach-skills/data-source-router/
├── SKILL.md        ← 你在这里。数据源地图 + 手册 + 合规
├── config.yaml     ← TTL/速率/开关/环境变量
├── config_loader.py
├── cache.py        ← SQLite 缓存 + TTL + SWR + 交叉校验 + 冷却
├── data_router.py  ← 路由入口 get(kind, **params) + CodeAct 声明式入口
├── codeact.py      ← ★ CodeAct 层：意图解析/成功判定/摘要+指针/确定性失败链
├── selfcheck.py    ← CodeAct 层自检（真实取数）
└── adapters/
    ├── __init__.py
    ├── finance.py  ← 腾讯行情/K线 + 东财财报 + SEC EDGAR
    └── github.py   ← REST 读/搜 + 速率控制
```

## 调用方式（推荐：CodeAct 声明式入口）

> ★ 新代码优先用 CodeAct 声明式入口 `achieve()`，它自动做 4 件 CodeAct 优化，
> 比 `get()` 更省注意力、更抗上下文衰减（详见下方"CodeAct 层"）。

```python
import sys; sys.path.insert(0, '/root/zach-skills/data-source-router')
from data_router import achieve, fetch_detail

# 高意图名 + 高层字段，codeact 自动路由到正确 kind+params（LLM 不记魔法串）
r = achieve("quote", symbol="600519")              # 行情摘要 {name,price,pe,pb}
r = achieve("kline", symbol="600519", count=250)   # 行情返回摘要，全量在 r.data_ref
d = fetch_detail(r.data_ref)                        # 需要全量K线才二次加载
r = achieve("financial", code="600519")
r = achieve("financial_series", code="600519", report_name="RPT_F10_FINANCE_GINCOME")
r = achieve("dividend", code="000333")              # 分红
r = achieve("us_finance", cik="0000320193");  r = achieve("us_revenue", cik="0000320193")
r = achieve("gh_repo", owner="volcano-sh", repo="volcano")
r = achieve("gh_issues", owner="volcano-sh", repo="volcano", state="open")
r = achieve("gh_search", q="kubernetes language:go")
```

**`achieve()` 返回 `AchieveResult`**：
- `r.ok` / `r.reason`：取数是否成功 + 原因（失败链已自动走过）
- `r.summary`：结构化摘要（**直接进 LLM 上下文用这个**，不塞全量）
- `r.data`：进上下文的轻量数据（大 payload 时 = 摘要）
- `r.data_ref`：全量数据落盘路径，需要时 `fetch_detail(r.data_ref)`
- `r.source` / `r.chain`：数据源 / 实际走过的取数链
- `r.as_dict()`：上下文安全 dict（大 payload 只含摘要+指针）

## 底层调用方式（老接口，兼容）

```python
import sys; sys.path.insert(0, '/root/zach-skills/data-source-router')
# 注意：zach-skills 在外部目录，见下"路径说明"

from data_router import get

# 行情
data, source, meta, tier = get('cn_stock_quote', symbol='sh600519')
data, source, meta, tier = get('cn_stock_kline', symbol='sh600519', count=120)
data, source, meta, tier = get('hk_stock_quote', symbol='hk00700')
data, source, meta, tier = get('us_stock_quote', symbol='usAAPL')

# 财报
data, source, meta, tier = get('cn_financial', code='600519')
data, source, meta, tier = get('cn_financial_series', secucode='600079.SH', report_name='RPT_F10_FINANCE_MAINFINADATA', page=40)  # 多报告期完整序列; report_name 常用 MAINFINADATA(含INTEREST_DEBT_RATIO有息负债率)/GINCOME(利润表费用拆解)
data, source, meta, tier = get('us_financial_sec', cik='0000320193')
data, source, meta, tier = get('us_revenue_sec', cik='0000320193')  # 自动选最新metric

# GitHub
data, source, meta, tier = get('github_repo', owner='volcano-sh', repo='volcano')
data, source, meta, tier = get('github_release', owner='volcano-sh', repo='volcano', limit=5)
data, source, meta, tier = get('github_issues', owner='prometheus', repo='prometheus', state='all', limit=100)
data, source, meta, tier = get('github_pulls', owner='volcano-sh', repo='volcano', state='all', limit=100)
data, source, meta, tier = get('github_search', q='kubernetes language:go', limit=20)
data, source, meta, tier = get('github_contributors', owner='volcano-sh', repo='volcano', top_n=10)
data, source, meta, tier = get('github_label_counts', owner='volcano-sh', repo='volcano')
```

**返回元组说明**：`(data, source, meta, tier)`
- `data`：实际数据（dict/list）
- `source`：用的数据源名（tencent/eastmoney/sec_edgar/github_api）
- `meta`：dict，`stale_while_revalidate`(是否命中旧缓存返旧值)、`cooldown`/`error`(失败标记)
- `tier`：`T1` 等，当前都是 T1（API）

### 路径说明（很重要）
skill 在外部目录 `/root/zach-skills/`（external_dirs），Hermes 默认 `skill_manage` 可能拒绝改外部 skill → **直接改文件**。运行脚本时用绝对路径：
```python
sys.path.insert(0, '/root/zach-skills/data-source-router')
```

## 速率限制（内置，不用手动管）

| 源 | 限制 | 适配器做法 |
|---|---|---|
| GitHub 未认证 | 60/hr | 请求间隔 1.5s + 每小时计数，超 55 抛 `RateLimitExceeded` |
| GitHub 认证(可选 token) | 5000/hr | 设 `GITHUB_TOKEN` env 自动升级 |
| SEC | ≤10 req/s | 适配器串行调用 |
| 单域名(浏览器兜底) | ≤1 req/s | 留接口，默认不装 |

## 缓存策略（config.yaml 集中定义）

| 数据类型 | TTL | 说明 |
|---|---|---|
| 日K线 | 24h | T+1，够用 |
| 实时行情(A/港/美) | 5-10min | 非高频，可接受 |
| A股财报 | 90天 | 季报后更新 |
| SEC 财报 | 30天 | 即时披露，30天足够 |
| GitHub 仓库元数据 | 7天 | 低频 |
| GitHub Issues/PR | 1天 | 追踪更新 |
| GitHub Release | 7天 | 低频 |
| GitHub 搜索 | 1小时 | 搜索常变 |
| 宏观 | 30天 | 月度 |

`stale_while_revalidate`：命中过期缓存先返旧值，后台线程异步刷新，不阻塞调用方。
**冷却**：同域名连续失败 ≥3 次 → 24h 内不再尝试（`record_failure`/`domain_cooldown`），记录在 `failures` 表。
**幂等**：cache key 是 `namespace + 参数JSON的sha256`，重复调用不重复抓取。

## 正确性保障

1. **多源交叉校验**：关键数据（股价/财报）≥2 独立源比对，不一致标记 conflict。`verify_multi()` 已实现。
2. **时间戳强制记录**：每条数据带 `source + fetched_at + ttl`，过期自动刷新。
3. **metric 变更应对**：SEC 营收取最新 metric（如上），避免过期数字。
4. **单位坑**（沿用之前踩过的）：
   - 腾讯K线 `vol` 单位=**手**(100股)，算成交额 ×100。
   - 东财 datacenter 金额单位是**元**（显示除1e8）；`MAINOP` 毛利率是**小数**（×100）。

## Tier 降级链（规范）

`T1(API) 失败 → T2(搜索摘要) → T3(浏览器，仅合规兜底) → 标记"数据不可用"`

- **T1** 永远优先，禁为 API 能覆盖的数据开浏览器。
- **T2** 搜索摘要兜底，仅当 T1 无此数据类型。
- **T3** 浏览器（playwright/selenium）**默认不装**，因 ECS 上多数数据已有可用 API。若确需，须合规（见下）。
- 每次失败记录原因到 `failures` 表；连续 3 次同域名失败 → 24h 冷却。

## 合规红线（硬性）

1. **不伪造身份绕过付费墙**
2. **不突破 robots.txt Disallow**
3. **不批量下载版权内容**（禁整站镜像）
4. **Token/Key 用环境变量**（`SEC_USER_AGENT`/`GITHUB_TOKEN`），不写进代码或日志
5. **单域名 ≤1 req/s；GitHub 未认证 ≤60 req/h**
6. 检测到合规风险立即停止并报告

> 若将来启用浏览器兜底：正常 UA（非 HeadlessChrome）、`--disable-blink-features=AutomationControlled`、覆盖 `navigator.webdriver`、页面停留 3-8s 随机、滚动/点击间隔 500-2000ms 随机、尊重 robots.txt；遇 Cloudflare/验证码 → 暂停让用户人工接管；403/429 → 指数退避(1s/2s/4s)，3 次失败标记不可用切备选。

## 给其他 skill 的分工边界（防重叠）

| skill | 它拥有什么 | 与本层关系 |
|---|---|---|
| `industry-monitor-dashboard`(实例 etf) | ETF 估值分位/信号/HTML（领域逻辑） | 原始抓取（腾讯行情/K线、中证PE、天天基金）**本层不重复做**；若其内部逻辑可复用则调用本层。见其 SKILL → 本层 |
| `whale-holdings` | SEC 13F XML 解析（领域专属） | SEC 原始 HTTP 访问**由本层提供**（`us_financial_sec`/`us_revenue_sec` 或直调 `adapters.finance`），其脚本引用 |
| `stock-analysis` | 基本面深度分析（商业模式/三表） | 财报数字来自本层（`cn_financial`/`us_financial_sec`），分析逻辑自留 |
| `github-*` 系列 | GitHub **写操作**（建repo/PR/release/管理） | 本层只做**读/搜**（`github_repo`/`_issues`/`_pulls`/`_release`/`_search`/`_file`），两者不重叠 |
| `github-oss-evaluation` | 5维度健康度**判读方法论**（pushed_at风险/厂商集中度/bot剔除/label缺失） | `repo`/`contributors`/`release`/`label计数` 抓取**本层提供**（`github_contributors`/`github_label_counts`），其只保留解读 |
| `open-source-contribution` | 介入流程/候选项目路径/AI贡献政策 | 甄别真社区数据**本层提供**（同上 `github_contributors` 等），只保留判读阈值 |

## CodeAct 层（4 个优化点，对照广发《AI投研》report data-gateway 案例）

让 LLM 只"声明要什么"，把取数/失败/判定全部下沉到确定性代码。`achieve()` 自动完成：

**[1] 意图地图 DSL** `resolve_intent()`：LLM 报简洁意图名（quote/kline/financial/...），
代码路由到正确 kind + 填好魔法串参数（report_name/page/秒内代码前辍等），LLM 不记 API 细节。

**[2] 成功判定 DSL** `validate()`：每 kind 一个校验器（quote价格>0、kline非空且含字段、
财报ok、SEC营收非null、GitHub有结果）。数据不合格 → 视为失败触发失败链，绝不把脏数据静默上交。

**[3] 摘要+指针（抗 Context Rot）** `summarize()` / `fetch_detail()`：大 payload
（SEC facts、完整财务序列、K线、GitHub列表）只回结构化摘要 + data_ref 落盘路径，
需要全量才 `fetch_detail(data_ref)` 二次加载 → 避免几 MB 原始数据把模型上下文打散。

**[4] 确定性失败链** `FAILOVER_KINDS`：某 kind 失败时按固定顺序试语义等价备选
（cn_financial→cn_financial_series，us_revenue_sec→us_financial_sec，
cn_ttfund_index→cn_csindex_pe），指数退避/源切换写法都在代码，模型永不参与"下一步试哪个源"。

> 设计红线：新 skill 取数**一律走 `achieve()`**；`get()` 仅作老接口兼容。摘要进上下文、全量走 data_ref。

## 快速自检

```bash
cd /root/zach-skills/data-source-router && python3 selfcheck.py   # ~14 项真实验证, 退出码0=通过 | 快检:
python3 -c "
import sys; sys.path.insert(0,'.')
import data_router as R
r = R.achieve('quote', symbol='600519'); print('行情', r.summary.get('name'), r.summary.get('price'))
r = R.achieve('financial', code='600519'); print('财报', r.summary.get('name'))
r = R.achieve('us_revenue', cik='0000320193'); print('SEC营收', r.summary.get('end'), r.summary.get('val'))
r = R.achieve('gh_repo', owner='volcano-sh', repo='volcano'); print('GH', r.summary.get('full_name'))
"
```
预期输出 4 行真实数据（茅台行情 / 财报 / Apple 最新季营收 / volcano 仓库），全部命中可用源。
