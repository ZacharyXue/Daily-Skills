# 监测看板 · 已验证免费数据源速查

全部本机实测通过。原则：免费、结构化、正确性 > 及时性。请求统一带 `User-Agent: Mozilla/5.0`。

## 1. 中国水泥网（水泥/行业价格、成本、需求指数）★→ 看板价格/成本/量代理主源
- 域名：`index.ccement.com`（⚠️ `price.ccement.com` 被阿里云 WAF 拦 405；`cn-cement.com`/`cementren.com` 本机打不开）。头：`Referer: https://index.ccement.com/`。
- **端点前缀坑**：
  - `/index/priceindex/getPriceIndex` → `Data.cement`(dynamicIndexDate/dynamicIndexAll) = **CEMPI 全国水泥价格指数**；`Data.coal_price`(dynamicIndexAll 首97.79 末75.09,近1年-23%) = **煤炭价格指数(成本端)**。
  - `/index/priceindex/po425zsline` → `Data.dynamicIndexDate/dynamicIndex` = **P.O42.5 全国均价(元/吨)**（首318.4 末277.8, -12.7%）。
  - `/index/priceindex/cementkline` → 近一年**周K**，`Data` 是 **JSON 字符串**（len=字符数≠K线根数，需二次 `json.loads`；实测"2826字符"→48根周K），字段 `[ts,open,close,high,low,vol,chg,pct]`。
  - `/index/clinker/ClinkerPrice` → 熟料价格（**不带 priceindex/ 前缀**）。`/index/concrete/ConcretePrice` → 混凝土价格(需求代理)。
  - ⚠️ **`Data.mjc` 实测 = 与 `coal_price` 完全相同（首值均97.79，247点序列一致），是字段错乱，不是磨机开工率**。别信文档名。
- **行为**：**偶发单次丢包**（单次 HTTP 000/超时20-25s），**立即重试即恢复**（实测连续 6/6 成功 0.8-2s）。**不是限频**。对策：短超时(约14s)+重试3次。
- 用量代理（需求端）：熟料价格走强=水泥跟涨领先；混凝土价格企稳=需求不再塌方；水泥-熟料价差走扩=供给收敛/盈利弹性。

## 2. 腾讯 ifzq（A股日K）★ 技术面/估值主源
- **前复权**：`https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=sh600585,day,2024-01-01,2026-08-29,660,qfq` → `data.<code>.qfqday` `[date,open,close,high,low,vol]`。头 `Referer: https://gu.qq.com/`。
- **不复权（算 PB 历史分位）**：`param=code,day,beg,end,count,`（**末尾必须带逗号**）→ `data.<code>.day`。⚠️ 写成 `count`(无逗号) 会 `bad params` 返回空。
  - PB 历史分位做法：不复权收盘价 ÷ 每股净资产(用最新报告期 BPS) → 每日 PB 序列，取近250日分位。前复权用于比值/收益率；市值口径的 PB 用不复权。
- **单次上限约 640 根**，要更长历史分段拼接（前复权各段=恒定倍数可精确拼）。

## 3. 腾讯实时估值（qt.gtimg.cn）
`v_sh600585="1~名称~代码~现价~昨收~今开~..."` 按 `~` 分割：idx3=现价、idx39=动态PE、idx46=PB。gbk 编码。

## 4. 东财 datacenter（财务/同行对比）
`RPT_F10_FINANCE_MAINFINADATA`，`filter=(SECUCODE%3D%22600585.SH%22)`，按 `REPORT_DATE_NAME` 定位报告期（如"2026中报"）。字段：TOTALOPERATEREVE(营收)/PARENTNETPROFIT(归母净利)/PARENTNETPROFITTZ(同比)/XSMLL(毛利率)/XSJLL(净利率)/ZCFZL(负债率)/EPSJB(每股收益)/BPS(每股净资产)/MGJYXJJE(每股经营现金流)/ROEJQ。⚠️ 先 `columns=ALL` dump 一条核字段名。

## 5. 东财公告接口（拿定期报告 PDF URL）
`https://np-anotice-stock.eastmoney.com/api/security/ann?sr=-1&page_size=40&page_index=1&ann_type=A&client_source=web&stock_list=600585&f_node=1&s_node=1`
→ `data.list[].art_code` + `title` + `notice_date`，PDF URL = `https://pdf.dfcfw.com/pdf/H2_{art_code}_1.pdf`。
⚠️ 标题匹配 `"年度报告" in title` 会误配「半年度报告」（子串），必须 `"半年度" not in title`。

## 6. 要"判死"一个源前先测重试
免费源超时/空不要立即断言"不能用"。用 `间歇重试` 判断：连续请求观察是否偶发成功（=丢包，重试即恢复）vs 持续失败（=真不可用）。前者保留下限重试用，后者才换源。
