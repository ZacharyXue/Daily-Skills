# 东方财富 datacenter API — 同行财务对比配方

免费、无 key、无需登录。返回 JSON。用于拉 A 股公司的财务摘要做同行对比（"看看同行"类请求）。

## 请求配方

```
https://datacenter.eastmoney.com/securities/api/data/v1/get
  ?reportName=RPT_F10_FINANCE_MAINFINADATA
  &columns=ALL
  &filter=(SECUCODE%3D%22<code>%22)        # URL 编码的 (SECUCODE="000933.SZ")
  &pageNumber=1
  &pageSize=30                              # 必须 ≥20，否则只返回最新 1-2 期，拿不到年报
  &sortTypes=-1
  &sortColumns=REPORT_DATE
```

Headers: `User-Agent: Mozilla/5.0` + `Referer: https://emweb.securities.eastmoney.com/`。

## 返回结构

`result.data[]` 按报告期倒序，每条含 `REPORT_DATE_NAME`（如 "2025年报"/"2026一季报"/"2026中报"）、`REPORT_DATE`、财务字段。

## 字段字典（常用）

| 字段 | 含义 |
|------|------|
| TOTALOPERATEREVE | 营业总收入 |
| PARENTNETPROFIT | 归母净利润 |
| EPSJB | 基本每股收益 |
| BPS | 每股净资产 |
| MGJYXJJE | 每股经营现金流 |
| XSMLL | 销售毛利率 % |
| XSJLL | 销售净利率 % |
| ZCFZL | 资产负债率 % |
| ROEJQ | 加权 ROE（最新期口径，历史期有时为空） |
| TOTALOPERATEREVETZ | 营收同比 % |
| PARENTNETPROFITTZ | 归母净利同比 % |

> ROE 补充算法：`EPSJB / BPS × 100` 在所有报告期都可用（ROEJQ 历史期常为 null）。

## 对比口径规则（易错点）

1. **必须同报告期对比**。不同公司最新披露期不同（A 出了中报、B 只出一季报），直接比最新一期会失真（半年 vs 3个月）。
2. 常规做法：统一取 **2025年报** 各字段（`REPORT_DATE_NAME == "2025年报"`），再看 **2026一季报** 看景气拐点。8 月底中报出齐后再补 2026中报。
3. 每家公司拉 pageSize=30（覆盖 2-3 年），用 `find(rows, "2025年报")` 定位，别依赖第 0 条。

## 完整脚本骨架

```python
import json, urllib.request

def fetch(secucode, page_size=30):
    url = ("https://datacenter.eastmoney.com/securities/api/data/v1/get"
           "?reportName=RPT_F10_FINANCE_MAINFINADATA&columns=ALL"
           f"&filter=(SECUCODE%3D%22{secucode}%22)"
           f"&pageNumber=1&pageSize={page_size}&sortTypes=-1&sortColumns=REPORT_DATE")
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://emweb.securities.eastmoney.com/"})
    d = json.loads(urllib.request.urlopen(req, timeout=20).read().decode())
    return d.get("result", {}).get("data", [])

def find(rows, key):  # key 如 "2025年报"
    for r in rows:
        if r.get("REPORT_DATE_NAME") == key:
            return r
    return None
```

## 实例：电解铝同行 2025 全年（2026-08-16 拉取）

| 公司 | 营收(亿) | 归母净利(亿) | 毛利率% | 净利率% | 每股CF | 负债率% |
|------|--------:|-----------:|-------:|-------:|-------:|-------:|
| 神火股份 000933 | 412.4 | 40.1 | 23.4 | 11.1 | 3.89 | 42.2 |
| 中国铝业 601600 | 2411.3 | 126.7 | 18.0 | 8.9 | 1.99 | 46.0 |
| 云铝股份 000807 | 600.4 | 60.5 | 16.8 | 12.2 | 2.43 | 19.8 |
| 天山铝业 002532 | 295.0 | 48.2 | 24.4 | 16.3 | 1.74 | 45.4 |
| 南山铝业 600219 | 346.2 | 47.4 | 25.2 | 16.8 | 0.65 | 19.3 |
| 明泰铝业 601677 | 351.4 | 19.6 | 7.1 | 5.6 | 1.16 | 28.4 |

**解读要点**：
- 神火每股经营CF 3.89 遥遥领先 → 煤电铝一体化现金流质量最好（防守属性）
- 明泰是加工厂（毛利率 7%），与矿企不是同一物种，别直接对标
- 南山 2026Q1 掉队（净利 11 亿 vs 2025Q1 17 亿）→ 氧化铝自给率低 + 铝加工占比高，铝价上涨传导弱
- 云铝 ROE 最高（18.9%）但纯水电看天吃饭，弹性大稳定性差

## 利润拆解实例：神火 2026H1（归母口径传导链）

- 归母净利 47.81 亿（同比 +151%），但子公司汇总净利 ≈ 60.9 亿
- 少数股东损益 12.96 亿 ← 主要是云南神火（持股仅 **58.25%**，少数股东 41.75% 拿走 12.89 亿）
- 子公司拆解：云南神火净利 30.87 亿（+214%）、新疆煤电 26.43 亿（+114%）、神火新材 ~1.07 亿（+354%）、煤炭两家合计 ~2.4 亿、新疆炭素 1.04 亿
- 驱动：收入 +21.4% 但营业成本 **-3.3%**（售价涨 + 氧化铝降 + 低价电）→ 毛利 40.7→89.7 亿翻倍；三费合计降（销售 -42%、财务 -46%）；所得税 16.38 亿（+124%）吃掉一大块
- 教训：看神火利润，合并净利会高估股东能拿到的钱，必须盯归母 + 云南神火占比
