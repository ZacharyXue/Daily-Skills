---
name: whale-holdings
description: 大佬持仓跟踪 — 拉取 SEC 13F 机构持仓披露，看巴菲特、李录(喜马拉雅)、Michael Burry、Bill Ackman 等大佬美股买了什么、加仓了什么、清仓了什么，支持季度对比。触发时机：用户说"看下 XX 的持仓"、"大佬持仓"、"13F"、"李录/巴菲特最近买了什么"。
version: 1.0.0
tags: [investment, 13f, sec, holdings, whale]
---

# 大佬持仓跟踪（SEC 13F）

拉取 SEC EDGAR 上的 13F 机构持仓披露（美股多头），看大佬买了什么、加仓了什么、清仓了什么。数据公开免费，通过 EDGAR 接口获取，无需 API key。

## 核心概念

- **13F**：SEC 要求管理美股资产超过 1 亿美元的机构投资者，每季度（报告期结束后 45 天内）披露其美股多头持仓。
- **关键限制**：13F **只披露美股多头**。港股/A 股持仓（如李录的腾讯、比亚迪）**不在 13F 里**，所以 13F 只反映大佬的美股一面。
- **延迟**：报告期结束到披露有约 45 天延迟。例如 2026Q2（6/30 截止）约 8 月中才披露。
- 空头、期权、做空仓位不披露；部分持仓可能被申请 confidential treatment 隐藏。

## 工作流

三步：搜 CIK → 拉持仓 → 季度对比。

### Step 1: 搜索机构 CIK

```bash
python3 scripts/fetch_13f.py search "Himalaya Capital"
# → Himalaya Capital Management LLC: 0001709323
```

如果已知 CIK 可跳过此步（见下方速查表）。

### Step 2: 拉取持仓

```bash
# 最新一期持仓（终端表格）
python3 scripts/fetch_13f.py fetch --cik 0001709323

# JSON 输出（可管道给其他工具）
python3 scripts/fetch_13f.py fetch --cik 0001709323 --json
```

### Step 3: 季度对比

```bash
# 最近两期对比（加仓/减仓/清仓/新增一目了然）
python3 scripts/fetch_13f.py diff --cik 0001709323

# JSON 输出
python3 scripts/fetch_13f.py diff --cik 0001709323 --json
```

## 常用机构 CIK 速查表

| 机构 | CIK | 备注 |
|------|-----|------|
| Himalaya Capital Management（李录/喜马拉雅） | 0001709323 | ✅ 已验证 |
| Berkshire Hathaway（巴菲特） | 0001067983 | ✅ 已验证 |
| Scion Asset Management（Michael Burry） | 0001649339 | |
| Pershing Square（Bill Ackman） | 0001336528 | |
| Bridgewater Associates（桥水） | 0001350694 | |
| Baupost Group（Seth Klarman） | 0001061768 | |
| Greenlight Capital（David Einhorn） | 0001079114 | |
| Appaloosa（David Tepper） | 0001029305 | |
| Hillhouse Capital（高瓴） | 0001700066 | |

> 除喜马拉雅、伯克希尔外未经本轮逐一验证。若 `fetch` 报错或结果不符，先用 `search` 重新确认 CIK（机构改名、CIK 变更、多实体时常见）。

## 直接 curl 手动流程（脚本不可用时）

```bash
# 1. 搜 CIK
curl -s -H "User-Agent: Research research@example.com" \
  "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&company=Himalaya+Capital&type=13F&dateb=&owner=include&count=40&output=atom"

# 2. 列 13F filing 列表（取 accession number）
curl -s -H "User-Agent: Research research@example.com" \
  "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0001709323&type=13F-HR&dateb=&owner=include&count=40&output=atom"

# 3. 打开 filing index 页，找 infoTable XML 文件名
curl -s -H "User-Agent: Research research@example.com" \
  "https://www.sec.gov/Archives/edgar/data/1709323/000204358526000022/0002043585-26-000022-index.htm"

# 4. 下载 infoTable XML（持仓明细）
curl -s -H "User-Agent: Research research@example.com" \
  "https://www.sec.gov/Archives/edgar/data/1709323/000204358526000022/13fhciq226.xml"
```

## Pitfalls

- **User-Agent 必填**：SEC 要求请求带 `User-Agent` header（含联系邮箱），否则返回 403。脚本已内置。
- **限速**：SEC 要求不超过 10 req/s。批量拉取多机构时脚本内置 0.2s 间隔。
- **titleOfClass 措辞不一致**：同一标的在不同季度可能写 "SPON ADS" vs "SPONSORED ADS"，甚至名字带前导空格（如 " TENCENT MUSIC ENTMT GROUP"）。**解析时用 CUSIP 做主键**，不要用 name+title 组合，否则会把同一持仓拆成两行、误判为"新增+清仓"。
- **同一标的多 share class**：如 Alphabet 有 CL A 和 CL C 两个持仓，CUSIP 不同，属于两个独立持仓条目，不要合并。
- **accession number 去横线**：EDGAR 目录路径用 `000204358526000022`（无横线），filing 列表返回的是 `0002043585-26-000022`（有横线），构造 URL 时要去掉横线。
- **13F-HR/A 是修订版**：列表里 `13F-HR/A` 是对前一份的修订。diff 时注意报告期，别拿修订版和原版比同一季度。
- **value 是美元**：XML 里 `<ns1:value>` 是持仓市值（美元），`sshPrnamt` 是股数。别把两者搞混。
- **CIK 前导零**：EDGAR URL 里 CIK 要保留 10 位前导零（`0001709323` 而非 `1709323`），但 `data/{cik}` 目录路径里要去掉前导零（`data/1709323/`）。脚本已处理。

## 分析建议

拿到 diff 后重点看：
1. **新增/清仓**：完全新建或清空某标的 = 大佬最强的观点变化。
2. **股数变化 vs 市值变化**：股数不变但市值涨 = 纯股价波动（被动）；股数变化 = 主动交易（真正的观点）。区分这两者，避免把"股价涨了"误读成"加仓"。
3. **持仓集中度**：持仓数骤减（如喜马拉雅 14→8 只）= 向核心仓位集中、做减法。
