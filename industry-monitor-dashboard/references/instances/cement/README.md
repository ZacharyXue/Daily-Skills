---
name: cement-dashboard
description: 水泥行业&海螺水泥(600585)盈利底监测看板的建设与维护 —— 注释驱动指标元数据 + 免费源取数(远程优先/失败显获败) + 自包含HTML(指标可点击看含义/来源/时间/摘要结论)。含海螺中报/年报PDF自动提取经营数据、统计局产量被IP拦走人工补录、中国水泥网指数接口丢包重试等可复用手段。触发时机：用户要更新/扩展「水泥看板」、加指标、接入博客、看行业盈利底监测。
version: 1.0.0
tags: [dashboard, cement, monitoring, free-source, html, 财报提取]
---

# 水泥行业 & 海螺水泥 盈利底监测看板

一套**行业/个股盈利底监测看板**的完整可复用范式：注释驱动 + 免费源取数 + 自包含 HTML。当前落地为 `/root/cement-dashboard`，未来挂到用户博客 ZacharyXue.github.io (Astro)。

> 同类看板还有 `etf-dashboard`（ETF 技术温度）。curator 可考虑归并到统一「监测看板」umbrella；本 skill 侧重**股票+行业盈利底**与**财报自动提取**。

## 核心设计原则（用户强偏好，经严厉纠正确立）
1. **数据正确性 > 及时性**：获取失败就标红显示「获取失败」+ 错误原因；**绝不拿旧值/seed 缓存冒充当前值**（用户明确反对 stale 冒充）。
2. **注释驱动，不反复加载 skill 上下文**：指标含义(为什么/看什么信号/来源/TTL)全存 `indicators.py` 元数据里，渲染时动态展示、可点击查看。skill 只管「怎么取数」。
3. **产出自包含 HTML**（原生 `<details>/<summary>` 可点击折叠，内嵌 CSS/SVG），不依赖飞书/浏览器，可直接作为 Astro 静态页。
4. 能自己从公开源拿的（含上市公司中报/年报），**不要过早判为需人工/外部采集**——那是最后手段。

## 项目结构
```
/root/cement-dashboard/
  scripts/indicators.py       # 指标元数据(注释驱动): 每指标 id/group/name/unit/ttl/source/meaning/signal/getter
  scripts/fetch.py            # 取数: 远程优先+重试+失败显获败; 读 cache(含 manual.json 人工补录)
  scripts/extract_report.py   # 海螺中报/年报PDF自动提取: 吨毛利/吨成本/销量/股息率
  scripts/render_html.py      # 渲染自包含HTML(含多线SVG趋势图+图例)
  cache/report_helluo.json    # 财报提取结果(extract_report 产出-> fetch 读)
  cache/manual.json           # 人工补录(统计局等被拦数据, 用户外部获取后填)
  cache/seed/<name>.json      # 历史备份(仅存档, 不作为当前值)
  prompts/collect_prompts.md  # 需外部采集指标的prompt清单
  output/cement_dashboard.html
```

## 运行流水线
```bash
cd /root/cement-dashboard
python3 scripts/extract_report.py   # 每新财报跑: 下载公告PDF->提取经营/分红数据->cache/report_helluo.json
python3 scripts/fetch.py            # 拉价格/成本/财务/估值/技术面 + 合并report/manual -> cache/dashboard_data.json
python3 scripts/render_html.py      # -> output/cement_dashboard.html
```
建议后台跑 fetch(源偶发慢)。`extract_report` / `fetch` / `render` 可 cron 定时。

## 数据源速查（本机实测）
| 需求 | 接口 | 状态 |
|---|---|---|
| 水泥价格/成本/需求代理(P.O42.5/CEMPI/熟料/混凝土/煤价指数) | `https://index.ccement.com/index/{priceindex/\|clinker/\|concrete/}...` | ⚠️ 偶发丢包→短超时+多次重试(见 pitfalls) |
| A股财务/主营 | 东财 datacenter RPT_F10_FINANCE_MAINFINADATA / MAINOP | ✅ |
| A股行情/估值(现价/PE/PB) | 腾讯 `qt.gtimg.cn` | ✅ |
| A股前复权/不复权日K | 腾讯 ifzq `fqkline` | ✅ 不复权需末尾逗号 `count,` |
| 海螺中报/年报PDF | 东财公告 `np-anotice-stock` → pdf.dfcfw.com | ✅ |
| 全国水泥产量同比 | 国家统计局 | ❌ 服务器IP被拦→人工补录 cache/manual.json |

## 财报自动提取（海螺等A股，可复用）
见 `references/cement-financial-extraction.md`：东方财富公告列表→下载PDF→提取自产品销量/收入/成本→倒算吨售价/吨成本/吨毛利，**用披露毛利率做校验**(倒算毛利率≈披露=口径对)；年报→每股派息→股息率。

## 人工补录机制（处理被拦数据）
统计局产量、需会员/公告的数据 → 生成 prompt 让用户外部获取 → 用户贴回答案 → 我解析写 `cache/manual.json`（格式 `<id>:{value:{latest,latest_date,note,charts},date,note}`）→ fetch 读入标 `status=manual`，渲染「人工录入@日期(外部软件)」。采集 prompt 生成见 `extract_report.py` 同目录思路或 `prompts/collect_prompts.md`。

## Pitfalls（多轮踩过的坑，新手先看）
- **index.ccement.com 不是限频，是偶发丢包**：单次请求可能超时，但**重试即恢复**。`_cget` 用 `timeout=14, retry=3`，失败才回退(绝不冒充)。别误判为被墙、别用 seed 冒充。
- **东财 push2 实时行情本机不通**(记忆印证)——A股行情统一走腾讯 `qt.gtimg.cn` + ifzq。
- **腾讯 ifzq 不复权参数**：`param=code,day,start,end,count,`(末尾逗号)才返回 `day`；不带逗号/加 `,qfq` 返回前复权 `qfqday`。算 PB(市值口径)必须不复权。
- **`list_ann("年度报告")` 会误配「半年度报告」**（标题含"年度报告"子串）→ 需显式排除 `"半年度" not in t`。
- **月格式日期喂给 `datetime.fromisoformat` 会崩**：趋势图点数日期若为 `YYYY-MM`，render 需 `to_date()` 补 `-01`。
- **东财 datacenter 金额单位元**(显示除1e8)、MAINOP 毛利率小数(乘100)——易量级错误。
- **fetch 卡死**：某免费源偶发慢，用 `timeout 400` 后台跑 + `notify_on_complete`，别前台干等。
- **腾讯 ifzq K线字段顺序**：返回 `[date, open, close, high, low, vol]` → `r[3]=H`、`r[4]=L`。算 KDJ/RSV 时正确是 `lo=min(r[4])`、`hi=max(r[3])`；**取反会让 RSV 分母为负、K/D/J 累积爆炸**（实测 K 算成 315、J 437，远超 0-100）。布林/均线用 `r[2]=close`、量能用 `r[5]=vol` 无此坑。
- **render 的 `fmt_val` 需特化「无 `latest`/`close` 的 dict 值」**：指标 value 含 `np`/`K`/`mid` 等但**无 `latest/close`** 时，默认回退显示「待接入/未接入」（即使数据在）。给这类加特化分支——净利→`{np}亿·同比%`、KDJ→`K/D/J`、布林→`收/中轨/上轨/下轨`、MACD→`RSI6·RSI14·MACD`。否则会被误判成「没接入」反复排查。
- **`data_router.get()` 首个参数是 kind**：子类型参数别取名 `kind`（与首参冲突报 "got multiple values for argument 'kind'"），用 `index_type` 等（如 `get('cn_cement_index', index_type='po425')`）。
- **迁移可用路径**：脚本别写死 `/root/zach-skills/data-source-router`，用 `_zach_root()` 从脚本 `__file__` 向上定位含 `data-source-router` 的目录（找不到回退 `ZACH_SKILLS` 环境变量），`zach-skills/` 整体搬走即可跑。

## 工程归属（2026-08 重构后）
权威自包含副本已并入母纲 → **`industry-monitor-dashboard/references/instances/cement/`**（README + scripts + cache + output 一体，整体可迁移）；`/root/cement-dashboard` 仅作 git 源/开发仓库。更新命令：`cd <skill>/references/instances/cement && python3 scripts/extract_report.py && python3 scripts/fetch.py && python3 scripts/render_html.py`。

## 指标覆盖 & 人工采集闭环（2026-08）
- **27 指标**：26 自动（价格/成本/量/盈利/财务/估值/技术全齐）+ 1 人工（全国产量同比）。
- **技术面已补齐**：均线 MA20/60、MACD/RSI6/RSI14、KDJ、布林(20,2)、量比；估值：PB+历史分位。
- **财务细项**：货币资金/有息负债率/FCF/毛利率/分红率。
- **人工采集闭环**：`prompts/collect_prompts.md` 列自动源拿不到的 **8 类**（分区域价/提价函/产能利用率/地产新开工/基建/专项债/供给出清组 CR10&市占率&错峰/电价），每项带 JSON 回填模板 + 末尾「一键复制」prompt。用户更新看板时发给别的 agent，拿回贴给我 → 解析写 `cache/manual.json` → 看板标「人工@日期」。

## 与 stock-analysis 的关系
`stock-analysis` 是**个股基本面深挖**流水线(含 data-apis.md、cycle-stock.md)。本 skill 是**行业/个股盈利底监测看板**的持续维护范式，两都共享东财/腾讯/公告PDF接口。财报公告PDF提取接口(via list_ann)可回填进 stock-analysis 的 data-apis.md。
