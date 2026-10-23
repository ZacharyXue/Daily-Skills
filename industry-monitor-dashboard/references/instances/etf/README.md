---
name: etf-dashboard
description: ETF 技术温度看板（红利 + 行业/主题）的维护与更新 — 综合 5 年估值分位(中证官网历史PE自算) + 10年PB分位(天天基金) + 技术面(MA20/BIAS/回撤/N日涨跌) + 实时行情，交叉生成加仓/分批/过热减仓信号，生成 HTML 落到博客 public/exports/。触发时机：用户说「更新ETF看板」「跑一下看板」「改动看板标的池」「加/换ETF标的」。
version: 1.3.0
tags: [etf, 红利, 看板, valuation, technical]
---

# ETF 技术温度看板（红利/行业/主题 · 维护与更新）

一套「技术温度 + 估值」双视角 ETF 看板系统：**5 年 PE 分位（主锚）+ 10 年 PB 分位 + 技术面（回撤/MA/BIAS）**交叉，输出加仓/分批/过热/观望信号，并给「此刻该怎么做」动作。覆盖红利、行业（如电池）、主题（如港股通红利低波）。产物静态 HTML，部署在 ZacharyXue.github.io 博客。

## 代码位置

- **看板工程**：`/root/ZacharyXue.github.io/etf-dashboard/`
  - `watchlist.json` — **标的池配置**（增删/替换品种改这里）
  - `generate.py` — 数据层（拉数据 + 算指标 + 信号）
  - `generate_html.py` — HTML 渲染
  - `update.py` — **一键更新入口**
- **产物**：`/root/ZacharyXue.github.io/public/exports/etf-dashboard.html`（博客可访问：`/exports/etf-dashboard.html`）
- **项目卡片**：`/root/ZacharyXue.github.io/src/content/projects/etf-dashboard.md`（首页项目卡跳转）

## 更新流程（手动触发）

> ⚠️ **必须用博客生产目录运行**：`update.py` 里的 `../public/exports/` 是相对路径，只有以 `/root/ZacharyXue.github.io/etf-dashboard` 为 cwd 才会落到博客 `public/exports/`。**skill 副本目录跑会落错位**（写到 instances 下）。工程源 `/root/ZacharyXue.github.io/etf-dashboard`（博客 repo，含部署）。

```bash
cd /root/ZacharyXue.github.io/etf-dashboard
python3 update.py
# 每日收盘后跑一次; 产物已更新 博客 public/exports/etf-dashboard.html
cd /root/ZacharyXue.github.io
git add etf-dashboard public/exports/etf-dashboard.html src/content/projects/etf-dashboard.md
git commit -m "update etf dashboard $(date +%F)"
# push 后 GitHub Pages 自动部署 (按惯例只 commit + push 时机由用户定)
```

更新 `watchlist.json`：
```json
{ "watchlist": [ { "name":"中证红利","csindex":"000922","ttfund_index":"000922","etf_symbol":"sh515180","etf_code":"515180" } ] }
```
字段：`csindex`=中证官网指数代码、`ttfund_index`=天天基金指数ID、`etf_symbol`=腾讯行情代码、`etf_code`=国内显示代码。

## 数据源（已验证稳定，2026-10 复核）

> **统一规范**：本看板的原始数据抓取底层走 `data-source-router` skill（腾讯行情/`ifzq` K线、中证官网PE、天天基金）。若需扩展标的或排查抓取，先看 `data-source-router` 的数据源地图，勿另起炉灶。
> **🔴 主锚不依赖登录（2026-10 用户定调）**：估值主锚 = **中证官网 PE5y 分位**（`cn_csindex_pe_series` → `/perf/indexCsiDsPe`），**无需任何登录**；天天基金的 PE/PB 10y 是**可选增强源**，token 过期时返回空、看板显示「—」并在页头橙色标注，**绝不阻断、绝不拿旧值冒充**（方案 2）。

| 数据 | 源 | kind | 必需性 | 说明 |
|------|----|------|--------|------|
| **5年 PE 分位 + PE 区间** | 中证官网 `/perf/indexCsiDsPe` | `cn_csindex_pe_series` | **主锚（必需）** | 2011 年至今日频历史PE，自算 5y 分位与 lo~hi 区间；非中证系指数返回 ok=False |
| PE/PB 十年分位、ROE | 天天基金 `TTFUND_INDEX_INFO`（ttskill） | `cn_ttfund_index` | 可选增强 | 需 `ttskill login`（token 30 天过期）；失效时静默跳过 + 页头标注 |
| 10Y 国债收益率 | akshare `bond_zh_us_rate` | `cn_macro_10y_rate` | 可选 | 估值分位的无风险利率锚，不依赖 ttskill |
| ETF 实时价/涨跌 | 腾讯 `qt.gtimg.cn` | `cn_stock_quote` | 必需 | 实时 |
| K线(算MA/BIAS/回撤) | 腾讯 `web.ifzq.gtimg.cn fqkline` | `cn_stock_kline` | 必需 | 前复权 |
| 外盘(标普/纳指/黄金) | 雅虎 chart API | 直连（看板内 `yahoo_kline`） | 必需 | ⚠️ `period2` 必须传当前时间戳，见坑位 |

**5年分位算法**（中证官网 PE 序列自算）：
```python
# cn_csindex_pe_series -> series=[(tradeDate, peg), ...]
pe5 = [v for d_, v in series if d_ >= (today - 5年)]      # 近5年
pct = sum(1 for x in pe5 if x <= pe5[-1]) / len(pe5) * 100  # 当前 PE 的历史分位
lo, hi = min(pe5), max(pe5)                                  # 5年 PE 区间（定位离底/顶多远）
```

## 信号规则（5年PE分位 为主锚）

```
加仓:   回撤≥15% 且 5y分位<50%
分批:   回撤≥10% 且 5y分位<70%
过热/减: (回撤≥-5% 且 5y分位≥90%) 或 5y分位>95%
观望:   其余
(无5y分位时退回: BIAS>10%过热 / BIAS<-10%超跌 / 回撤≥15%加仓)
```

## 指标含义速查（看板底部已内嵌）

- **MA20** = 20日均线，现价在其上=趋势偏多
- **BIAS** = (现价−MA20)/MA20，衡量涨跌是否过度（>10%过热 / 负值超跌）
- **PE5y分位** = 当前PE在近5年百分位（主锚）；PE/PB10y 为天天基金口径
- **目标价** = MA20 抬到 BIAS 10%/15% 的挂单价

## 坑位

- **🔴 手动更新必须 `force=True` 绕过 router 缓存**（2026-10-23 踩实）：`generate.py` 里 `cn_stock_quote` / `cn_stock_kline` / `cn_csindex_pe_series` 原先没传 `force`，DSR 缓存会把**几天前的行情/K线**当「当前」返回，而页头 `K线截止` 仍显示最新日期 → **日期看着新、数值是旧的**。实测 515180 BIAS 显示 +0.92%（实际 -2.03%）、近5日 -0.4%（实际 -3.0%），港股通红利 520900 的信号因此从**加仓**错判成**分批**。
  修复：模块级 `FORCE = os.environ.get("ETF_FORCE_REFRESH","1") != "0"`，传给 quote/kline/csindex 三个 get；另加护栏——`K线截止` 距今 >5 自然日时页头**红字警告**（「K线已 N 天未更新」），绝不静默。
  **验收方法**：更新后用独立调用复算一只标的的 BIAS/近5日，与页面数值比对，不一致就说明拿到了缓存旧值。
- **🔴 外盘 K 线 `period2` 绝不能硬编码**（2026-10 踩实，静默 9 个月）：`yahoo_kline` 曾写死 `period2=1768000000`（=2026-01-09），导致标普500/纳指100/黄金的行情与K线**全部停在 1 月 9 日**，而看板把 1 月价格当"当前"显示（标普 6966 vs 实际 7629）。这种 bug 不会报错、不会有"获取失败"标记，**只能靠核对「K线截止」日期发现**。凡带时间窗口参数的接口，参数一律用当前时间计算。
- **估值主锚不要绑在有登录态的源上**：ttskill（天天基金）token 30 天过期，一旦过期 `TTFUND_INDEX_INFO` 全空 → 若主锚依赖它，看板会整体退化。现方案：主锚走中证官网（无登录），ttskill 仅作 PB10y 可选增强，失效时页头橙色标注。
- **中证官网无 PB 历史**：`index-perf` / `indexCsiDsPe` 都只有 PE(peg) 字段，**没有任何 PB**；测过的替代源全部不可用（详见下方）。PB 只有天天基金 10y 口径。
- **`indexCsiDsPe` vs `index-perf`**：两者都能给 PE，但 `indexCsiDsPe` 支持 `startDate/endDate` 区间参数、返回更全（2011 年至今），是首选；`index-perf` 走默认窗口。端点名从官网前端 `app.js` 里挖（`csindex-home/perf/indexCsiDsPe`）。
- **`peg` 偶发为 None**：过滤非空行再算分位；最新交易日 peg 可能未更新（用上一日）。
- **腾讯K线单位**：`fqkline` 的 vol 单位是**手**(100股)，算成交额要 ×100
- **TTFUND_INDEX_INFO 用 `index_id`**（不是 query），传错报缺少参数
- **信号双视角重要性**：红利指数"绝对 PE 便宜 + 分位高"是常见陷阱——买点判断必须以**分位**为准，别只看绝对 PE
- 中证官网接口偶发 500，重试即可
- **改 HTML 模板后**：编辑 `generate_html.py` 的 CSS/结构，重跑 update.py 生效。样式用亮色（用户偏好：不要暗色），做响应式（手机可看）
- **PB 只有 10y，无 5y**（2026-08 复核）：csindex index-perf 只返回 `peg`(=历史PE)，**无 PB 字段**；天天基金 valuation 只有 `pe_percentile_10y`/`pb_percentile_10y`。要 PB 分位只能 **10y 口径**（别叫 PB5y，无数据源）
- **非中证官网指数**（国证/恒生系）：`csindex_pe_pct()` 返回 None → 看板 PE5y 显示"—"，信号**退化到 BIAS/回撤**，估值用天天基金 10y（pe10y/pb10y）。典型=港股通红利低波 **987016**（159545 恒生红利低波ETF易方达），maker=深圳证券信息（国证指数）
- **查指数代码用名称搜**：`ttskill TTFUND_SEARCH --action query --body '{"query":"港股通红利低波","search_type":"index"}'` 得候选（987016 等）；`TTFUND_INDEX_INFO` 的 `index_id` 支持**传名称**让服务端解析（如"沪深300"），勿只传一个乱码 code
- **PB 替代源探测结论（2026-10，全部实测）**：乐咕乐股 legulegu → 401/404（接口已改或需 cookie）；申万宏源指数估值 → 证书链异常 + 页面是 JS 壳；巨潮 cnindex → 404；东财指数估值（`f164/f167/f23`）→ 指数代码全返回 0，只有个股有值。**结论：全网免费公开源没有 PB 历史序列，中证官网只有 PE。** 别再重复探测，除非用户愿意接付费源。
- **看板已不限红利**：加行业/主题 ETF 用同一管线，只需 etf_symbol/csindex/ttfund_index 填对。e.g. 电池ETF汇添富(159796) = 中证电池主题 **931719**（csindex/ttfund 都能出 5y 分位 + ROE）
- **用户决策(2026-08)：5y 源捞不到就用 10y，不接付费源**。PB 分位统一 10y 口径；中证系指数保留中证官网 PE5y，非中证系(国证/恒生)用天天基金 10y + 技术面退化。后续别再为凑 5y 折腾外部源（全网免费公开接口无日频 PB 历史，已系统性验证：中证官网仅 PE 无 PB、天天基金仅 10y 分位、东财指数估值字段为 0/个股报表、国证官网 SPA 无数据）

## 扩展标的

- 加 A 股 ETF：csindex 代码（H30269/000922 等）+ 腾讯 sh/sz 前缀 + ttfund index_id
- 港股 ETF（520900 等）：同 csindex 931722，腾讯 sh520900
- 国证/恒生系指数（非中证官网，如 159545 港股通红利低波=987016）：csindex 填指数代码即可，`csindex_pe_pct` 会**安全返回 None** → PE5y="—"，估值用天天基金 10y（pe10y/pb10y），信号退化 BIAS/回撤。先用 `ttskill TTFUND_SEARCH search_type=index` 按名称搜到 code
- 新增后跑 update.py，确认 5y 分位能算出（若 csindex 查不到该指数，显示"—"并退回归/BIAS 信号）

## PIL 渲染坑（旧版画 PNG 用，踩过记得；HTML 版无此问题）

若回退到 PIL 画图（非 HTML）：
1. **emoji/特殊符号崩**：wqy-zenhei 无 📌🔴🟡⚪、`×→≥≤` → `getmask` 错误。换 `[文字]`、`x`、`-`、`>=`。
2. **`d.text` 必须命名参**：封装 `txt(x,y,s,sz,fill)` 内 `d.text((x,y),s,font=F(sz),fill=fill)`，别裸写第3位置参当 fill。
3. 徽章对比度：亮徽章深字 / 深徽章白字。
4. **布局溢出**：画布宽 > 卡片宽留边距（卡1640/画布1720），块宽累计对齐卡片右界，超长ETF名按名长缩字号，像素采样自检最右列。

## 推飞书（发看板图/文字到"炒股理财"群，⚠️ 必须 lark-cli user 身份）

Hermes 飞书 **bot adapter 发图/消息常失败**（`99992402`）。推进群用 lark-cli user 身份：
```bash
export PATH="$HOME/.npm-global/bin:$PATH"; cd /tmp
lark-cli im +messages-send --chat-id <群oc_xxx> --image "./xxx.png" --format json   # 发图
lark-cli im +messages-send --chat-id <群> --markdown "<文字>" --format json           # 发文字
```
- 群根发 `+messages-send`；附 topic 用 `+messages-reply --message-id`
- 配 cron 推送：prompt 让 agent 跑脚本→lark-cli 发图文字→**最终回复只输出 `[SILENT]`** 抑制 bot 自动投递
- 群 chat_id 从 `~/.hermes/channel_directory.json`（platforms.feishu）取

## 关系 & 统一（2026-08 对齐）

- **风格复用**：本看板产物（自包含 HTML）与 `dashboard-style/templates/dashboard_skeleton.html` 同源（亮色、可点击、响应式）。复用该骨架/样式，勿另起一套。
- **数据层走 `data-source-router`**：腾讯行情/K线（`cn_stock_quote`/`cn_stock_kline`）、**中证官网 PE（`cn_csindex_pe`）、天天基金分位（`cn_ttfund_index`）** 已全部下沉到 data-source-router，本看板**只触发 get()**，不自建抓取。
- **已注册**到 `dashboard-style/references/dashboards-index.md` 看板索引（含工程路径/更新命令/产物）。
- **总纲**：`industry-monitor-dashboard`（行业+龙头/ETF 看板通用架构），本看板是它在「ETF 估值+技术」上的实现。