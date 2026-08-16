# 股票数据接口速查（实战验证）

本文件汇总 `stock-analysis` 流水线用到的**全部数据接口**，均经真实调用验证。
核心原则：
- **东方财富 datacenter** = 财务数据主力（免费、无需 key、字段全）
- **腾讯行情 qt.gtimg.cn** = 实时行情主力（东财 push2 偶发 502/拒连，用它兜底）
- 所有请求带 `User-Agent: Mozilla/5.0` + `Referer`（部分接口校验）

---

## 1. 实时行情/估值（腾讯）

```bash
curl -s "https://qt.gtimg.cn/q=sz000933" -H "User-Agent: Mozilla/5.0"
```

返回 `v_sz000933="51~神火股份~000933~25.83~25.90~25.60~..."`，按 `~` 分割：

| 索引 | 含义 | 索引 | 含义 |
|:----:|------|:----:|------|
| 1 | 名称 | 39 | PE（动态） |
| 2 | 代码 | 41 | 52周最高 |
| 3 | 现价 | 42 | 52周最低 |
| 4 | 昨收 | 45 | 总市值(亿) |
| 5 | 今开 | 46 | PB |

- 编码：`gbk`（`urllib` 读 `decode("gbk")`）
- 前缀：`6/9` 开头 → `sh`，否则 → `sz`
- 多只：`q=sz000933,sh601600` 逗号分隔
- 参考脚本：`scripts/quote_query.py`

## 2. 财务数据主力（东方财富 datacenter）

**基础 URL**：
```
https://datacenter.eastmoney.com/securities/api/data/v1/get
  ?reportName=RPT_F10_FINANCE_MAINFINADATA
  &columns=ALL
  &filter=(SECUCODE%3D%22<code>%22)
  &pageNumber=1&pageSize=30&sortTypes=-1&sortColumns=REPORT_DATE
```
- `filter` 里 `%3D` = `=`，`%22` = `"`
- 返回 `result.data[]`，含全部报告期（年报/中报/季报），按日期倒序
- **常用字段**（中文财报字段名）：

| 字段 | 含义 | 字段 | 含义 |
|------|------|------|------|
| TOTALOPERATEREVE | 营业收入 | PARENTNETPROFIT | 归母净利 |
| PARENTNETPROFITTZ | 净利同比% | TOTALOPERATEREVETZ | 营收同比% |
| EPSJB | 基本EPS | BPS | 每股净资产 |
| ROEJQ | 加权ROE | XSMLL | 销售毛利率% |
| XSJLL | 销售净利率% | MGJYXJJE | 每股经营现金流 |
| ZCFZL | 资产负债率% | REPORT_DATE_NAME | 报告期名(如"2025年报") |

**查询技巧**：
- 字段名不确定 → 先 `columns=ALL` dump 一条看 keys（字段是拼音缩写，如 GROSS_RPOFIT_RATIO 注意拼写）
- 取指定报告期：遍历 `data[]` 匹配 `REPORT_DATE_NAME == "2025年报"`
- 参考脚本：`scripts/peers_compare.py`

## 3. 主营业务构成（东财 datacenter，分产品/分行业收入+毛利率）

```
reportName=RPT_F10_FN_MAINOP
filter=(SECUCODE%3D%22<code>%22)
pageSize=30
```
- 返回 `result.data[]`，**同报告期多行**（按 ITEM_NAME 分产品/分行业/分地区）
- 字段：`ITEM_NAME`（项目名）、`MAIN_BUSINESS_INCOME`（收入）、`MAIN_BUSINESS_COST`（成本）、`GROSS_RPOFIT_RATIO`（毛利率，小数如 0.39）、`MBI_RATIO`（收入占比）
- ⚠️ 返回会混多个报告期，需按 REPORT_NAME 过滤最新一期
- 用法：拆"分产品"行 → 各业务收入占比 + 毛利率（商业模式分析的核心数据）

## 4. 股东户数（散户指标）

```
reportName=RPT_HOLDERNUMLATEST
filter=(SECURITY_CODE%3D%22000933%22)
sortColumns=END_DATE
```
- 字段：`HOLDER_NUM`（户数）、`HOLDER_NUM_RATIO`（较上期变化%）
- **信号**：户数环比上升 = 筹码分散/散户进场（常出现在叙事传播期）

## 5. 机构研报/评级（东财 reportapi）

```bash
curl -s "https://reportapi.eastmoney.com/report/list?industry=*&rating=&pageSize=20&beginTime=2025-08-16&endTime=2026-08-16&pageNo=1&qType=0&code=000933"
```
- 返回 `data[]`：`publishDate`、`orgSName`（机构名）、`ratingName`（评级）、`title`、`indvObjectivePrice`（目标价，常为空）
- **用法**：数研报数量 + 评级方向（12 篇全正面 vs 有分歧）；目标价缺失 = "敢讲逻辑不敢给价"的信号

## 6. 历史 K 线（商品价格分位/周期定位）

```bash
curl -s "https://push2his.eastmoney.com/api/qt/stock/kline/get?secid=113.alm&fields1=f1,f2,f3&fields2=f51,f52,f53,f54,f55,f56&klt=101&fqt=0&beg=20230101&end=20261231&lmt=2000"
```
- `secid`：`113.` 前缀 = 国内期货（`113.alm` 沪铝主连）；股票用 `0.`（深）/`1.`（沪）如 `1.601600`
- `klt=101` 日线；`f51=日期 f52=开 f53=收 f54=高 f55=低 f56=量`
- **用途**：算商品价格历史分位 → 判断周期位置（>70% 分位警惕高位）
- 参考 `references/cycle-stock.md` 分位脚本

## 7. 期货/延迟行情（东财 push2delay）

```bash
curl -s "https://push2delay.eastmoney.com/api/qt/stock/get?secid=113.alm&fields=f43,f44,f45,f46,f47,f48,f57,f58,f60,f170"
```
- `f43` 最新价、`f170` 涨跌幅（返回 ×1，非 ×100）
- 已验证：`113.alm` 沪铝主连 返回 23945（元/吨）
- ⚠️ `push2.eastmoney.com`（实时）在部分服务器上 502/拒连，用 `push2delay` 或腾讯兜底

## 8. 备选（不稳定，慎用）

| 接口 | 用途 | 状态 |
|------|------|:----:|
| `hq.sinajs.cn` | 新浪行情 | ⚠️ 403（需 Referer，仍偶发失败） |
| `www.smm.cn` | 上海有色现货 | ⚠️ 404/需登录 |
| `futsseapi.eastmoney.com` | 期货 | ⚠️ 404 |

---

## 快速选择指南

| 需求 | 接口 | 参考脚本 |
|------|------|---------|
| 现价/PE/PB/市值 | 腾讯 qt.gtimg.cn | quote_query.py |
| 财报三表/ROE/毛利率 | 东财 datacenter MAINFINADATA | peers_compare.py |
| 分产品收入+毛利率 | 东财 datacenter MAINOP | — |
| 股东户数变化 | 东财 datacenter HOLDERNUMLATEST | — |
| 机构研报/评级 | 东财 reportapi | — |
| 商品历史K线/周期分位 | 东财 push2his | cycle-stock.md |
| 期货/商品实时价 | 东财 push2delay | — |

## Pitfalls

- **`columns=ALL` 先探字段**：东财字段是拼音缩写且有时拼错（GROSS_RPOFIT_RATIO 不是 PROFIT），先用 ALL dump 一条看实际 keys
- **filter 编码**：`(` `)` `=` `"` 必须 URL 编码，否则返回空
- **返回多报告期/多维度行**：MAINOP 同报告期多行（分产品+分行业+分地区），务必按 REPORT_NAME 过滤；财务数据按 REPORT_DATE_NAME 定位
- **接口偶发失败**：东财 push2 实时行情在部分网络环境 502，统一用腾讯行情兜底
- **限速**：批量拉多家时加 `time.sleep(0.3)`，避免被封
