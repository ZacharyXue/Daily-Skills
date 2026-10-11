---
name: ttskill-cli
description: Install, configure, and use the TianTian Fund ttskill CLI — base package installation, business skill sync, agent entry distribution (Hermes + OpenCode), and login.
---

# 天天基金 ttskill CLI

安装和配置天天基金 `ttskill` CLI 工具（v0.1.2+），包括基础包安装、33 个业务 Skill 包同步、路由刷新、扫码登录。支持 Hermes 和 OpenCode 双 Agent 使用。

## Triggers

- "install ttskill" / "安装天天基金 CLI"
- "ttskill login" / "ttskill invoke"
- 用户询问基金账户、持仓、收益、选基、行情等天天基金相关问题
- 需要为新 Agent（如 OpenCode）配置 ttskill 入口

## 架构概览

```
ttskill CLI (~/.local/bin/ttskill)
  ├── 基础包: ~/.local/share/ttfund/ttskill-base/
  ├── 业务 Skills: ~/.local/share/ttfund-skills/skills/
  ├── Agent 路由入口: ~/.local/share/ttfund-skills/agent-entry/ttskill-router-entry.md
  └── 凭证存储: Linux Secret Service (libsecret-tools)
```

## 安装

### Step 1: 获取基础包下载地址

```bash
curl -sL "https://skills.tiantianfunds.com/ai-smart-skill-service/openapi/base-package/resolve?platform=linux&arch=x64&env=prod"
```

从响应的 `data.download_url` 获取 zip 包地址。当前正式环境版本：`0.1.2`，包大小 ~42MB。

### Step 2: 下载并安装

```bash
# 下载
curl -sL --max-time 120 -o /tmp/ttskill-base.zip "<download_url>"

# 解压并运行安装脚本
unzip -qo /tmp/ttskill-base.zip -d /tmp/ttskill-extract
cd /tmp/ttskill-extract/ttskill-base-linux-x64-<version>
bash install.sh
```

安装脚本会：
- 安装到 `~/.local/share/ttfund/ttskill-base/`
- 创建 `~/.local/bin/ttskill` 软链接

### Step 3: 写入 Agent 入口 Skill

```bash
# 生成入口内容
ttskill agent-entry bootstrap --env prod
```

将输出的 Markdown 写入两个位置：

1. **Hermes**: `~/.hermes/skills/ttfund-skill.md`
2. **OpenCode**（如果用户需要）: 写入项目目录的 `AGENTS.md` 末尾（或创建 `.ttfund/ttskill-entry.md`）

这样 Hermes 加载 skills 时发现、OpenCode 在项目目录工作时也能发现。

### Step 4: 同步业务 Skill 包

```bash
# 获取业务包列表
curl -sL "https://skills.tiantianfunds.com/ai-smart-skill-service/openapi/skill-package/list?env=prod"
```

批量安装（33 个包）：

```python
# 用 Python 批量调用 ttskill skill install
for item in data['data']['items']:
    subprocess.run(['ttskill', 'skill', 'install', item['skill_id'],
                    '--env', 'prod', '--version', item['version']])
```

验证：

```bash
ttskill skill list --json   # 或 ttskill status --json 查看 installed_count
```

### Step 5: 刷新路由

```bash
ttskill agent-entry refresh --env prod
```

路由文件生成到 `~/.local/share/ttfund-skills/agent-entry/ttskill-router-entry.md`。

### Step 6: 登录

```bash
ttskill login --env prod          # 已是登录态会直接返回 already_logged_in
ttskill login --env prod --force  # token 过期时**必须加 --force**，否则不会重新走扫码
```

**token 30 天过期**（`expires_in: 2592000`），且 ttskill 0.1.2 **不使用 refresh_token** → 过期只能重扫。
判定登录态的可靠姿势（2026-10 实测）：
- `ttskill status --json` 看 `auth.expires_at` / `is_expired`；⚠️ **过期后 `is_expired` 字段可能直接消失**，只靠它会误判
- 最可靠：跑一次真实 `invoke`，看 **returncode 与 stderr**（失败原因在 stderr，stdout 为空；直接 `json.loads(stdout)` 会把真因盖成 "Expecting value"）

**前置依赖**：Linux 需要 `libsecret-tools`（用于 Secret Service 安全凭证存储）。

```bash
sudo apt-get install -y libsecret-tools   # Debian/Ubuntu
```

登录后会打开浏览器或终端显示二维码，用户扫码授权后即可使用。验证：

```bash
ttskill status --json   # 检查 has_token 是否为 true
```

## 业务 Skill 包一览

当前正式环境 33 个业务包：

| 分类 | Skill ID | 用途 |
|------|----------|------|
| 账户 | ACCOUNT_HOLDING | 持仓查询（活期宝/黄金/养老金/总览） |
| 账户 | ACCOUNT_PROFIT | 收益查询（基金收益/阶段收益/收益贡献） |
| 账户 | SUBACCOUNT | 子账户管理（资产/银行卡/交易记录） |
| 交易 | CONDITION_ORDER | 条件单（计划列表/记录） |
| 交易 | RATION_PLAN | 定投计划（列表/结果） |
| 交易 | TRADE_QUERY | 交易查询（详情/列表/银行卡/现金日历） |
| 交易 | TTFUND_SIM_TRADE | 模拟交易 |
| 选基 | TTFUND_CONDITION_SELECT | 条件选基 |
| 选基 | TTFUND_EVENT_SELECT | 事件选基 |
| 选基 | TTFUND_FAVOR_ZX | 自选基金 |
| 选基 | TTFUND_SEARCH | 基金搜索 |
| 选基 | TTFUND_SIMILAR_FUND_SELECT | 相似基金推荐 |
| 选基 | TTFUND_THEME_SELECT | 主题选基 |
| 信息 | TTFUND_BASE_INFOS | 基金基本信息 |
| 信息 | TTFUND_HOLDING_INFO | 持仓详情 |
| 信息 | TTFUND_INDEX_INFO | 指数信息 |
| 信息 | TTFUND_MANAGER_INFO | 基金经理信息 |
| 信息 | TTFUND_NAV_INFO | 基金净值 |
| 信息 | TTFUND_STOCK_PRICE_QUERY | 股票价格查询 |
| 市场 | TTFUND_BOND_MARKET | 债券市场 |
| 市场 | TTFUND_GOLD_INFO | 黄金信息 |
| 市场 | TTFUND_HUOQIBAO_LIST | 活期宝列表 |
| 市场 | TTFUND_MACRO_DATA | 宏观数据 |
| 市场 | TTFUND_CHIP_INDEX_QUOTE | 芯片指数行情 |
| 市场 | TTFUND_DIVIDEND_TEMPERATURE | 红利温度 |
| 市场 | TTFUND_INNOVATIVE_PHARMA | 创新药 |
| 市场 | TTFUND_NONFERROUS_INDEX_QUOTE | 有色金属指数行情 |
| 分析 | TTFUND_GROUP_BACKTEST | 组合回测 |
| 分析 | TTFUND_PORTFOLIO_ANALYSIS | 组合分析（CAPM/IRR/牛熊/资产配置） |
| 研究 | TTFUND_RESEARCH_SEARCH | 研报搜索 |
| 研究 | TTFUND_RESEARCH_VIEW | 研报观点 |
| 策略 | TTFUND_STRATEGY_INFO | 策略信息 |
| 主题 | TTFUND_THEME_INFO | 主题信息 |

## 调用方式

登录完成后使用 `ttskill invoke`：

```bash
ttskill invoke <skill_id> --action <action> --body '<json>'
```

分类只用于理解和路由，不是可调用 Skill。最终必须选择具体原子 `skill_id`。

## 常用命令

```bash
ttskill --version                     # 版本信息
ttskill status --json                 # 状态检查（凭证、已安装 Skill、版本）
ttskill login --env prod              # 登录
ttskill logout                        # 登出
ttskill skill list --json             # 已安装业务 Skill 列表
ttskill skill info <skill_id> --json  # Skill 详情
ttskill agent-entry show              # 查看路由内容
ttskill agent-entry refresh --env prod # 刷新路由
ttskill invoke <skill_id> --action <action> --body '<json>'  # 调用
ttskill skill update <skill_id> --env prod   # 业务包版本落后（HTTP 409 skill_version_required）时更新
```

## Pitfalls

- **`libsecret-tools` 缺失**: 在 WSL/Linux 上 `ttskill login` 报 `secret-tool 需要 libsecret-tools`。需要 `sudo apt-get install -y libsecret-tools`。如果无 sudo 密码，提示用户手动安装。
- **登录后 `has_token` 仍为 false**: 确认用户已在浏览器中完成扫码授权；确认 Secret Service / D-Bus session 可用（`echo $DBUS_SESSION_BUS_ADDRESS`）。
- **路由过期**: 安装新业务包后必须 `ttskill agent-entry refresh --env prod`，否则新包不会出现在路由中。
- **分类不是 Skill**: `ttskill agent-entry show` 输出的分类（groups）只用于理解，不能直接调用。必须选择原子 `skill_id`。
- **不要给 Agent 目录复制业务包本体**: 业务包由 `ttskill-cli` 管理在 `~/.local/share/ttfund-skills/skills/` 下，Agent 只需入口文件即可引导。
- **`TTFUND_RESEARCH_SEARCH` 不能查基金季报**: 它返回的是第三方行业研报/新闻，不会命中具体基金的定期报告。查基金季报持仓、行业配置、重仓股 → 用 `TTFUND_BASE_INFOS`（一次调用返回完整档案）。
- **`TTFUND_BASE_INFOS` 返回体积极大** (~300KB JSON)：必须用 Python `subprocess` + `json.loads` 提取关键字段，不要把原始输出灌入上下文。
- **港股 F10 页面不可用**：东方财富天天基金港股 F10（分红/财务页面）频繁返回"无F10资料"，查港股分红历史改用新浪财经（`vip.stock.finance.sina.com.cn/corp/go.php/vISSUE_ShareBonus/stockid/`）。
- **基金代码必须先用 TTFUND_SEARCH 验证身份再拉数据**：6 位基金码极易口误/笔误一位（如 012651 vs 012951），按错码拉到的是完全不同物种的基金（偏债 vs 半导体主题），整份对比会跟着跑偏。铁律：**任何对比/单基分析第一步永远是 `TTFUND_SEARCH` 确认 code 对应的真实 `name` 与 `category_name`（混合型-偏债/股票型/……），核对大类无误后再 proceed**。多基金对比时把每只的 `category_name` 一并列出，先分类型再谈收益。参考案例速查见 `references/fund-comparison-and-index.md` 第三节。
- **风格箱体在 `fund_profile_archive`**：不是在 `fund_profile_holdings` 下，路径是 `expansion.comprehensive_info.fund_profile_archive.invest_style_snapshot.style_box`。
- **指数估值：PE 有免费的 5y 自算口径，PB 只有天天基金的 10y**（2026-10 复核，含系统实测）：
  - `TTFUND_INDEX_INFO` 的 valuation 返回 `pe_ttm` / `pb`（绝对值）+ `pe_percentile_10y` / `pb_percentile_10y`（**仅 10y 分位**）+ `roe`，**无 5y 分位、无历史序列**
  - **5y PE 分位自算**：中证官网 `/csindex-home/perf/indexCsiDsPe?indexCode=<code>&startDate=YYYYMMDD&endDate=YYYYMMDD` —— **2011 年至今全历史 PE，支持日期区间**，比 `index-perf` 更全更稳（端点名从官网前端 `app.js` 里挖出来）。已下沉 DSR：**`cn_csindex_pe_series`**
  - **PB 没有免费历史序列**（2026-10 全量实测：中证官网只发 PE，`dataService/PERatio`、`exportExcel/indexAll` 均 404/500；乐咕乐股 legulegu 401/404；申万宏源证书链异常+JS 壳；巨潮 cnindex 404；东财指数估值 `f164/f167/f23` 对指数全返回 0）→ 要 PB 分位**只能**走 TTFUND_INDEX_INFO 的 10y 口径
  - ⚠️ **PE 5y 与 PB 10y 窗口不同，交叉比较必须留容差**（看板里取 25 个百分点），否则会把口径差误读成信号
- **PE/PB 背离是有效信号（两个估值都拿到后才能做）**：PE 分位显著低于 PB 分位 → 资产端并不便宜，PE 低更可能是「**盈利被压缩**」压出来的（分母效应）。实测游戏ETF PE 5y 1% vs PB 10y 49%（差 48pt）；红利ETF 97%/97% 口径一致不误报。制造业/周期主题尤其要查这个。
- **`TTFUND_INDEX_INFO` 的 `index_id` 支持传名称**让服务端解析（如"沪深300"、"中证红利"），不必先查代码；**但国证/恒生系指数**（如国证成长100 `980080`、恒生港股通高股息低波动 `987016`）中证官网查不到 PE，只能吃天天基金的 10y 口径。
- **`profit_contribute` 含已清仓标的**：`currentHold=false` 的是历史持仓，分析当前持仓时需过滤。
- **BASE_INFOS 的 `asset_scale_history`/`share_scale_history` 是 list 且可能滞后**：规模用 `NETNAV`(元)/`CHANGE`(同比%)、份额用 `QMZFE`(期末份额)/`NETFLOW`(净申购)，**最新在前**；但该列表可能是早期快照（如富国稳健 2021-22 那是成立初期），**最新规模要看 `data[0].ENDNAV`（最新报告期）**。规模短期趋势用 `share_scale_history` 近 6 期（QE 净申连续为负 = 份额赎回）。
- **`holding_ai_summary` 是天基金 AI 对持仓的解读摘要（聚焦赛道+重仓股）**，非基金经理逐字叙述。要看经理**亲述的季报市场观点/仓位操作**（"本季回顾+后市展望"），BASE_INFOS 拿不到——需去基金定期报告（中报/季报 PDF 或天天基金季报页）提取。分析时区分：持仓增减=硬数据，AI 摘要=二手观点，基金原文=一手观点。
- **读持仓基金清单用 `ACCOUNT_HOLDING --action holding_list --body '{}'`**：返回全部持仓（含基金/投顾/活期宝），字段 `pType`(fund/tg/hqb)，过滤投顾(tg, 名如"星际穿越")和 hqb 才能得到纯基金清单。`--action query` 或传 `fund_id` 都不是正确姿势。
- **无桌面服务器（ECS）部署/登录**：本 skill 假设桌面环境；headless 场景见 **`ttskill-headless`** skill，含：凭证文件化 patch、**cloudflared 隧道扫码登录（用户只需点链接 + 扫码，无需 SSH 隧道）**、token 过期重扫。
  ⚠️ 关键机制：`ttskill login` 的回调是**浏览器发起的 POST**（不是 GET 重定向），所以「让用户复制地址栏 URL」不可行——必须让浏览器能连通到服务器上的 8765 回调服务。
- **`skill_version_required` 报错**：invoke 返回 `HTTP 409 {"code":"skill_version_required"}` = 该业务的 Skill 包版本落后于服务端。先重试一次（常是偶发），仍失败再 `ttskill skill update <SKILL_ID> --env prod`。

## 分析工作流

- **基金季报分析**（持仓/风格/重仓/行业配置）：参考 `references/fund-quarter-review.md`，含完整 5 步工作流 + Python 字段提取模板
- **基金业绩归因分析**（年度收益/阶段排名/季度拐点/宏观结合/赎回压力）：参考 `references/fund-performance-attribution.md`
- **单基金深度分析 / 多基金对比**（外部基金、非持仓；指数基金估值判断、先看类型再比收益、输出规范）：参考 `references/single-fund-analysis.md`
- **基金经理深度研究**（背景业绩/投资理念/言行一致验证/机构认可度/最新季报观点，manager-deep-dive）：参考 `references/manager-deep-dive.md`——含东财中报 PDF 提取经理一手观点、言行一致硬对账表、机构认可 JGBL 判断
- **主动基金评估**（外部主动基金值不值得买：规模收益/季报言行一致/夏普回撤/机构占比/持仓风格/持有人结构变化/费率）：参考 `references/active-fund-evaluation.md`——含六维字段路径 + 东财 JJGG 公告接口批量取季报原文（§4.4）方法；提取季报 PDF 直接跑 `scripts/extract_report.py <季度报告.pdf>`；⚠️**言行一致性必须覆盖现任经理任职期近三年**（逐期观点→调仓→结果闭环，非只看最新季度），批量时间线分析用并行子代理
- **组合回测 / 指数历史点位 / 红利指数价格 vs 全收益**（验证收益目标、拉中证官网逐日数据、股息逻辑）：参考 `references/fund-comparison-and-index.md`
- **指数分析 + 回撤统计**（编制逻辑/估值分位/成分股/年度收益/回撤阈值指导）：参考 `references/index-and-drawdown-analysis.md`；回撤直接跑 `scripts/index_drawdown.py <指数代码> <起始日YYYYMMDD> <结束日>`（拉中证官网免费日线并输出回撤事件/分位/恢复时间）
- **历史估值回测**（当前估值分位买入的历史 1/3/5 年回报）：参考 `references/index-and-drawdown-analysis.md` 的「历史估值回测」节——**中证官网 index-perf 的 `peg` 字段就是历史 PE(TTM)**，按买入日 PE 分档统计后续回报；点位分位≠PE 分位，估值问题必须用 peg 不能用点位近似
- **多基金/多指数对比分析**（同逻辑对比：身份卡→业绩→持仓→风险→估值分位→分红→按需求结论；红利质量指数陷阱与成分股质量检验；组合回测 bt_detail_v2）：参考 `references/index-analysis-workflow.md`
- **A股个股基本面分析**：走 `stock-analysis` skill（外部只读，用 `skill_view` 读它与它的 references）；README 之外的方法见下两条
- **需求周期股估值**（水泥/钢铁/地产链，低ROE重资产）：参考 `references/demand-cycle-valuation.md`——先分价格周期vs需求周期；需求周期用净资产ROE锚定（合理PB=长期ROE÷要求回报率），别用"近N年平均净利"当正常化盈利
- **医药公司新药管线分析 / ST摘帽判断**：参考 `references/pharma-rd-pipeline.md`——新药各阶段累计上市概率与投入占比、II期是最易失败坎、存量垄断业务才是价值锚、ST摘帽靠解决资金占用而非新药临床
- **其他高频操作**（选基、回测等）：参考 `references/fund-analysis-workflows.md`

## 关键 Skill 调参速查

调用前先 `export PATH="$HOME/.local/bin:$PATH"`（本机 ~/.local/bin 不在默认 PATH，非交互 shell 直接调 ttskill 会 command not found，`which` 却能看到）。

## 读持仓基金清单 & 深挖持仓基金（2026-09 实测）

- **读当前持仓**：`ttskill invoke ACCOUNT_HOLDING --action holding_list --body '{}'` → `body.holding_list_result[]`，字段 `fundName/fundCode/assetValue/pType(基金fund/投顾tg/活期宝hqb)/holdProfit/holdProfitRate`。**过滤掉 pType=tg（投顾，名如"星际穿越"）和 hqb（活期宝）** 才得到纯基金清单。
- **一次拿全档案**（业绩/持仓/风格/经理/历史）：`TTFUND_BASE_INFOS --body '{"fcode":"<code>","nav_range":"ln"}'` 一次返回完整档案，笨重但最全。
- **JSON 信封解包（先看这个）**：`ttskill invoke` 输出的真实数据在 `d['data']['raw_result']['body']['data']`（List）与 `body['expansion']`（富档案）两层，且 `body['data']` 是 List 不是 dict、富档案在 `expansion` 不在 `data[0]`。完整信封层级 + 常用字段速查见 `references/base-infos-json-envelope.md`——**不按它解包会反复报 `'list' has no keys` 和字段找不到**。
- **三件事在 BASE_INFOS 的字段路径**：
  - 阶段业绩 → `expansion.comprehensive_info.period_increase`（title 映射区间名）
  - 前十大重仓 → `fund_profile_holdings.heavyweight_position_latest.fundStocks`（GPJC/GPDM/JZBL/PCTNVCHGTYPE增减持）
  - 经理背景/投资理念 → `manager_information.historyManagerInfos[0]` + `PINFO[0].INVESTMENTIDEAR`
- **经理"市场观点/仓位操作"原文 = 定期报告，不是 BASE_INFOS**：BASE_INFOS 只给 `fund_profile_archive.holding_ai_summary`（天天基金对该期持仓的 **AI 解读摘要**：聚焦赛道+重仓股），非经理逐字叙述。要经理亲述的"本季回顾+后市展望"，去基金季报/中报（PDF 或天天基金季报页）读。分析时区分三层：**持仓增减=硬数据、AI摘要=二手观点、基金报告原文=一手观点**。
- **规模/份额历史（BASE_INFOS `fund_profile_archive`）**：
  - `asset_scale_history`(list, 最新在前)：`NETNAV`(元规模)+`CHANGE`(同比%)。⚠️ 可能是早期快照（滞后），**最新规模用 `data[0].ENDNAV`**。
  - `share_scale_history`(list, 最新在前)：`QMZFE`(期末份额)+`NETFLOW`(净申额)。**连续负净申 = 份额赎回信号**，用在管基金判断规模崩塌。
  - 两者取值用正序 `[:6]` 看近期（list 最新在前），别误取最老。
- **主题历史看"仓位/方向变化"最好**：`fund_profile_archive.stock_theme_history` = **dict{报告日期: [rows]}**，rows 字段 `TOPICCODE`(科技/新能源/医药/周期/金融)+`PCTNV`(占比%)。近 5 期主题占比变化直观看出经理怎么调仓，比单看前十大更全面。
- **历史字段 dict vs list 陷阱**：`stock_theme_history`/`sector_allocation_history`/`asset_allocation_history` 是 **dict{日期:[rows]}**（`for d,rows in d.items()`），而 `asset_scale_history`/`share_scale_history`/`cash_flow_and_performance_history` 是 **list**。混用断言会报 `list has no .items()`。
- **数值多是字符串 + 可能空**：`NETFLOW` 可能是空串，`float()` 前判空；`SE`(单季收益%) / `NETFLOW`(季度净流入) 在 `cash_flow_and_performance_history`（list）。
- **历史序列(list)原始顺序不可靠，必须按 FSRQ 排序去重再取**：`holder_structure_history`/`asset_scale_history`/`share_scale_history`/`cash_flow_and_performance_history` 虽是 list，但各基金内部排序不一致（有的最新在前、有的最老在前），直接 `[-8:]` 会取到最老 8 期（2026-09 实测 202213 取到 2013-2016 数据）。正确姿势：`seen[FSRQ]=row` 去重 → `sorted(seen.values(), key=FSRQ)` → 取最后 N 期。
- **夏普/回撤/波动/机构占比字段在 `unique_info[0]`**：`SHARP1/3/5`(夏普)、`MAXRETRA1/3/5`(最大回撤%)、`MAXRETRA_SE`+`MAXRETRA_SDATE_SE/EDATE_SE`(成立来最大回撤及区间)、`STDDEV1/3/5`(年化波动%)、`JGBL`(机构占比%)。机构占比最新值也可看 `fund_holder_structure[0]`（`JGBL/GRBL/NBBL/EMPLOYEHOLD`），历史看 `fund_profile_archive.holder_structure_history`。
- **费率在 `rate_info`**：`MGREXP`(管理费%)/`TRUSTEXP`(托管费%)/`SALESEXP`(销售服务费%)。
- **经理任职信息在 `manager_information.currentManagerInfos[i]`**：`SINFO`（`FEMPDATE` 上任日期/`TOTALDAYS` 任职天数/**`PENAVGROWTH` 任内收益%**）+ `PINFO[0]`（`INVESTMENTIDEAR` 理念/`RESUME` 履历）。⚠️ **业绩归因按现任经理任期**：成立以来收益可能属于前任（010624 富国稳健增长成立来 -16.4% 是肖威兵时代，范妍 2024-10 接手后任内 +26.96%），判断现任经理能力看 `PENAVGROWTH` 而不是成立以来。
- **经理自述理念在 `manager_idea[0]`**：`investmentMethod/investmentIdea/chooseStockLogic/tradeLogic/statement`（一手观点但非季报原文）。
- **季报原文用东财 JJGG 接口拿，别靠 web_search 碰运气**：`https://api.fund.eastmoney.com/f10/JJGG?fundcode=<code>&pageIndex=1&pageSize=30&type=3`（带 `Referer: https://fundf10.eastmoney.com/`）→ `Data[]` 含 `TITLE/PUBLISHDATEDesc/ID(artcode)`；PDF 直链 `https://pdf.dfcfw.com/pdf/H2_<artcode>_1.pdf`；提取 §4.4「投资策略和运作分析」。❌ `np-anotice-stock/fund.eastmoney.com` 返回空、`FundArchivesDatas.aspx?type=jjbg` 返回空、天天基金公告页是 JS 渲染——都不要用。
- **TTFUND_SEARCH 的候选在 `body.data.candidates`**（不是 BASE_INFOS 的 `data` list）：`ttskill invoke TTFUND_SEARCH --action query --body '{"query":"<code>","search_type":"fund"}'` → `d['data']['raw_result']['body']['data']['candidates']`，字段 `code/name/category_name/is_buyable`。**7 位代码照搜也能防错**：用户把 017589 打成 0017589（7 位），逐候选拆解验证后确认是 017589，别替他猜。

## 业务 Skill 包一览

| Skill | body 参数 | 要点 |
|-------|-----------|------|
| TTFUND_NAV_INFO | `{"fund_id":"005974","range":"ln"}` | 字段是 fund_id 不是 fcode/query；range：y=近1月/3y=近3月/6y=近6月/n=近1年(默认)/2n/3n/ln=成立以来；算年度收益必用 ln |
| TTFUND_MANAGER_INFO | `{"manager_name":"孔令超"}` | 字段是 manager_name 不是 query；返回经理画像/在管基金/阶段业绩 |
| TTFUND_MACRO_DATA | `{"region":"cn","categories":"cpi,ppi,pmi,m1,m2","start_date":"2025-10-01"}` | region 必填(cn/us)，缺失报 HTTP 400；不传 categories 则全量；月频数据在 `frequencies` 数组 |
| TTFUND_BOND_MARKET | `{}` | 债市晴雨表（利率债/信用债 BP 变动 + AI 观点 markdown） |
| TTFUND_STOCK_PRICE_QUERY | `{"query":"06869"}` | A/港股行情 |
| TTFUND_SEARCH | `{"query":"港股通红利低波","search_type":"index"}` | search_type 必填: fund/index/manager/strategy。**按名称找指数 code**：只知 ETF/指数名时用它搜 code(如"港股通红利低波"→987016)，再进 TTFUND_INDEX_INFO；基金用 search_type=fund 先验身份(见铁律) |
| TTFUND_INDEX_INFO | `{"index_id":"931722"}` | 字段是 index_id 不是 query！**index_id 可传名称**让服务端解析(如"沪深300"/"恒生红利低波")；返回 index_profile(编制逻辑)/valuation(pe_ttm + pe_percentile_10y + pb_percentile_10y，**只有10y分位、无5y、无历史序列**)/composition.top_industries(行业权重)/composition.component_details(前十大成分股) |

## 业绩归因分析（外部基金，快速版）

- **年度收益**：拉 NAV range=ln 全量净值 → 用 `LJJZ`(累计净值) 按「年末/上年末-1」计算，避开分红/拆分扰动；用 `DWJZ` 单日算年度会因分红跳空出错
- **季度拐点**：`fund_profile_archive.cash_flow_and_performance_history` 的 `SE` 字段 = 单季区间收益%，连续负 SE 即业绩转弱区间；`NETFLOW` = 季度净流入（赎回压力）
- **短期 vs 长期**：对比 period_increase 的近1年 rank 与近5年 rank，立刻看出「长期好近期差」还是相反
- **宏观归因**：PPI 转正/CPI 回升 → 无风险利率上行 → 高债券仓位基金净值承压；用 MACRO_DATA + BOND_MARKET 佐证
- **历史序列字段结构**：asset_allocation_history / sector_allocation_history / stock_industry_sw_history / stock_theme_history 均为 **dict{报告日期: [rows]} 而非 list**，须 `for date, rows in d.items()` 遍历；（一个 list 直接切片会报 slice 错误）
- **净值历史默认仅近1年**：BASE_INFOS 里的 nav_history 与 NAV_INFO range=n 都只有近1年，要算多年年度收益必须显式 range=ln
