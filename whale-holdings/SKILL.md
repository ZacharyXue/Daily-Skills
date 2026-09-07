---
name: whale-holdings
description: 投资参考总入口 — 大佬持仓(SEC 13F) + 大佬观点(雪球大V发言/知识星球言论)。覆盖巴菲特、李录等美股 13F 持仓对比，以及雪球鹿鼎公/段永平/管我财等 13 位大V、知识星球「人生要选对」老钱的近期观点与搜索。触发时机：用户说「看下 XX 的持仓」「大佬持仓」「13F」「鹿鼎公/段永平最近说了什么」「本周大佬观点」「雪球大V怎么说 XXX」「人生要选对 搜 XXX」。数据源走 data-source-router（雪球登录态由 site-login 管理）。
version: 2.0.0
tags: [investment, 13f, sec, holdings, whale, xueqiu, zsxq, 投资参考, 大佬观点]
related_skills: [data-source-router, site-login, zsxq, stock-analysis, whale-holdings]
---

# 投资参考（大佬持仓 + 大佬观点）

三位一体：**持仓（美股13F）** + **雪球观点** + **知识星球观点**。持仓看「买什么」，观点看「为什么买/怎么看」。

> 资源依赖：数据一律走 `data-source-router`（`adapters/xueqiu.py` 的雪球通道；SEC 由本层提供）；雪球登录态由 `site-login` skill 管理（state 在 `~/.cache/data-source-login/xueqiu_state.json`），失效报 `login_ok=false` 时提示重扫，**不伪造数据**。

## 一、大佬持仓（SEC 13F，美股）

> 数据源规范：SEC EDGAR 的 HTTP 访问统一由 data-source-router 提供（`us_financial_sec`/`us_revenue_sec`）。本 skill 只保留 13F XML 解析（`scripts/fetch_13f.py`）。

### 核心概念
- **13F**：SEC 要求管理美股资产超 1 亿美元的机构每季度（45 天内）披露美股多头持仓。
- **限制**：只披露美股多头；港股/A股持仓（如李录的腾讯、比亚迪）不在 13F 里。
- **延迟**：报告期结束后约 45 天披露。如 2026Q2（6/30 截止）约 8 月中披露。
- 空头/期权不披露；部分持仓可申请 confidential treatment 隐藏。

### 工作流

```bash
# 搜索机构 CIK
python3 scripts/fetch_13f.py search "Himalaya Capital"
# 最新持仓（终端表格 / JSON）
python3 scripts/fetch_13f.py fetch --cik 0001709323
python3 scripts/fetch_13f.py fetch --cik 0001709323 --json
# 季度对比（加仓/减仓/清仓/新增）
python3 scripts/fetch_13f.py diff --cik 0001709323
python3 scripts/fetch_13f.py diff --cik 0001709323 --json
```

### 常用机构 CIK 速查表

| 机构 | CIK | 状态 |
|------|-----|------|
| ★ Himalaya Capital（李录/喜马拉雅） | 0001709323 | ✅ 已验证 |
| ★ Berkshire Hathaway（巴菲特） | 0001067983 | ✅ 已验证 |
| H&H International（段永平） | 需查(见 search) | ⚠️ 可用 search 确认 |
| Scion Asset Management（Michael Burry） | 0001649339 | ✅ 已验证 |
| Pershing Square（Bill Ackman） | 0001336528 | 待验证 |
| Bridgewater Associates（桥水） | 0001350694 | 待验证 |
| Baupost Group（Seth Klarman） | 0001061768 | 待验证 |
| Greenlight Capital（David Einhorn） | 0001079114 | 待验证 |
| Appaloosa（David Tepper） | 0001029305 | 待验证 |
| Hillhouse Capital（高瓴） | 0001700066 | 待验证 |

### 13F 分析要点
1. 新增/清仓 = 最强观点变化；2. 股数变化 vs 市值变化（区分主动交易与股价波动）；3. 持仓集中度变化。

## 二、雪球大佬观点（脚本：scripts/fetch_xueqiu.py）

> 数据通道：data-source-router 的 `xueqiu_user_posts`（playwright + site-login 登录态）。**取数慢是正常的**（每页间隔 2-4s 反限流）；批量拉多位大佬时若报 10022 = 触发风控，等 2-5 分钟冷却再跑，别高频连跑。

### 雪球大佬清单（user_id 记录在此，增删改这里）

| 代号 | 雪球昵称 | user_id | 风格标签 |
|------|---------|---------|---------|
| 鹿鼎公 | 超级鹿鼎公 | 8790885129 | 周期:煤炭/电力/电解铝/银行, 游戏仓月更 |
| 段永平 | 大道无形我有型 | 1247347556 | 价值投资/美股/苹果茅台 |
| 管我财 | 管我财 | 9650668145 | 港股价值, 低估逆向 |
| 张翼轸 | 张翼轸 | 3559889031 | ETF/资产配置/指数化, EarlETF |
| 丹书铁券 | 丹书铁券 | 9742512811 | 长期价投/私募基金 |
| 安娜2012 | 安娜2012 | 3045776970 | 股债平衡, 集中持仓 |
| 大树 | 孥孥的大树 | 8592131633 | 股市实战/基金/宏观 |
| 紫金陈 | 紫金陈 | 6515752937 | 悬疑作家, 散户视角/回撤规律 |
| 郭荆璞 | 郭荆璞 | 7571730629 | 行业分析师视角 |
| jiancai | jiancai | TBD | 待补充 |
| qzy69 | qzy69 | 1205946512 | 低产高信噪比 |
| 狗不叫 | 狗不叫 | TBD | 待补充 |
| 指汇盈 | 指汇盈 | 5941996397 | 基金策略/行情复盘 |

> TBD = 待查证 user_id。查证方式：雪球网页搜索用户（登录态下 `https://xueqiu.com/query/v1/search/status.json?q=<昵称>`）或 web 搜索 `xueqiu.com/u` 主页。改完记得同步 `scripts/fetch_xueqiu.py` 里的 `GURUS` 字典。

### 用法

```bash
cd scripts
# 全部大佬近7天发言
/usr/bin/python3 fetch_xueqiu.py
# 近30天 / 只看部分大佬
/usr/bin/python3 fetch_xueqiu.py --days 30
/usr/bin/python3 fetch_xueqiu.py --gurus 鹿鼎公,段永平
# 只保留提到关键词的发言（如"铝"/"神火"/"华能"）
/usr/bin/python3 fetch_xueqiu.py --gurus 鹿鼎公 --keywords 铝,神火
# JSON 输出（管道给分析）
/usr/bin/python3 fetch_xueqiu.py --gurus 鹿鼎公,段永平 --days 7 --json
```

**注意**：
- 脚本必须用 `/usr/bin/python3` 跑（playwright 装在系统 Python）
- **低频规范（data-source-router「模拟人类低频」）**：默认每页间隔 15-60s 随机，全量 13 位 × 3 页 ≈ 30-40 分钟；批量任务**拆成多轮**（`--gurus` 每次 3-4 位）或先看重点大佬。`--fast` 仅调试，禁止正式批量
- `--days` 是时间窗口过滤；`--max-pages` 控制翻页上限（每页 20 条，默认 3），发帖多的老大多翻几页
- 拉完的原始文本给 LLM 做概括/对比/提炼，脚本只负责取数

## 三、知识星球观点（人生要选对 · 老钱）（脚本：scripts/fetch_whale_posts.py）

订阅源清单：

| 星球(group_id) | 关注用户(user_id) | 内容特征 |
|---|---|---|
| 人生要选对 (222588821821) | 老钱 (8444584182) | 投资观点:美债/美股/A股/个股、宏观、趋势 |

### 用法

```bash
cd scripts
python3 fetch_whale_posts.py                    # 最近30条（兼容旧行为）
python3 fetch_whale_posts.py --days 7           # 近一周发言
python3 fetch_whale_posts.py --days 14 --json
python3 fetch_whale_posts.py --search 铝        # 星球内全文搜索（RAG 语义匹配）
python3 fetch_whale_posts.py --search 神火,云铝 --json
```

> 搜索是 RAG 语义匹配：可能漏召/误召；搜股票名建议用个股简称+公司全名多试几个关键词（如"神火"没命中就试"000933"）。`--days` 与 `--search` 互斥。

## 四、典型用法（给 LLM 的组合）

- **「本周大佬都在聊什么」**：雪球全部大佬 `--days 7` + 星球 `--days 7`，合并后按主题归类（周期/美股/宏观/个股），输出一个摘要。
- **「鹿鼎公怎么看电解铝/神火」**：`--gurus 鹿鼎公 --keywords 铝,神火,云铝`，再拉对应个股的行情（data-source-router `achieve('quote')`）对照。
- **「段永平最近的观点」**：`--gurus 段永平 --days 14`；他的 13F（H&H International）用 `fetch_13f.py` 同步看。
- **「巴菲特/李录最新持仓变化」**：`fetch_13f.py diff --cik 0001067983 / 0001709323`。
- **「人生要选对里关于美债/黄金的讨论」**：`fetch_whale_posts.py --search 美债` / `--search 黄金`。

## 直接 curl 手动流程（脚本不可用时）

```bash
# 1. 搜 CIK
curl -s -H "User-Agent: Research research@example.com" \
  "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&company=Himalaya+Capital&type=13F&dateb=&owner=include&count=40&output=atom"
# 2. 列 13F filing 列表（取 accession number）
curl -s -H "User-Agent: Research research@example.com" \
  "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0001709323&type=13F-HR&dateb=&owner=include&count=40&output=atom"
# 3. 打开 filing index 页找 infoTable XML 文件名
curl -s -H "User-Agent: Research research@example.com" \
  "https://www.sec.gov/Archives/edgar/data/1709323/000204358526000022/0002043585-26-000022-index.htm"
# 4. 下载 infoTable XML
curl -s -H "User-Agent: Research research@example.com" \
  "https://www.sec.gov/Archives/edgar/data/1709323/000204358526000022/13fhciq226.xml"
```

## Pitfalls

### 13F / SEC
- User-Agent 必填（含邮箱），否则 403；限速 ≤10 req/s
- `titleOfClass` 措辞不一致：**用 CUSIP 做主键**，别用 name+title，否则同持仓拆两行误判新增+清仓
- 同一标的多 share class（Alphabet CL A/CL C）是两个独立条目
- accession number 去横线；`13F-HR/A` 是修订版，diff 别拿修订版和原版比同一季度
- `value` 是美元市值，`sshPrnamt` 是股数；CIK 前导零 10 位

### 雪球（fetch_xueqiu.py）
- **必须 `/usr/bin/python3` 运行**（系统 Python 才有 playwright）
- **10022 = 风控/登录态失效**：先 `python3 scripts/xueqiu_login.py --check`；若 state 有效，就是 IP 风控，等 2-5 分钟冷却，降低批量规模/拉长间隔再跑
- **IP 风控会连 page=1（公开数据）一起拦**：任何 user_timeline API 都返回阿里云 WAF HTML 挑战页（响应体是 `<!DOCTYPE html>` 而非 JSON）。此时**只能等**（10-60 分钟），重试无效且可能延长风控。判断标准：`check_login` 返回 false 且裸 page=1 也失败 → 等冷却
- 一次会话内 API 请求数控制在 ~30 次以内，间隔 ≥2s（xueqiu_fetch 已内置 2-4s 随机间隔，**不要在外部再加并行**）
- 批量拉多位大佬时**不要并发/高频**，按脚本串行即可
- 登录二维码若导出 0B 属正常抖动，旧 state 可能仍有效（以 `--check` 为准）

### 知识星球（fetch_whale_posts.py）
- `--limit` 上限 30，超出报 `无效的count`
- 搜索为 RAG 语义匹配，结果需人工复核相关性
- 依赖 zsxq-cli（`~/.config/zsxq-cli/config.json`）

## 合规红线

- 不伪造身份/绕过付费墙；雪球登录态只用于读取公开可见发言，不批量下载版权内容
- key/token（雪球 state、SEC UA）不入 git、不打日志；state 权限 600