---
name: housing-rent-buy-dashboard
description: 北上广深+杭苏「租房vs买房」租售比看板——数据(创房价手机站房价/租金/售租比/分区+房天下新房趋势+LPR)已实测打通，含 fetch/render 脚本与逐月手动更新命令。触发：用户问租售比、租房还是买房划算、某城市/上海杭州分区房价租金、房产数据。
version: 1.0.0
tags: [dashboard, housing, rent, buy, 房产, 租售比, LPR]
related_skills: [dashboard-style, data-source-router]
---

# housing-rent-buy-dashboard — 租 vs 买 看板（沪杭版）

## 解决什么

评估「当前租房划算还是买房划算」，**专注上海 + 杭州**（可细到区县）：
- **租售比/售租比**：租金回报率 = 1/售租比，与 5Y LPR 对比（回报率 < 利率 = 出租跑不赢利息）
- **现金流**：100㎡ 等额本息月供 vs 同面积月租金（首付 20%、30 年可调）
- **房价趋势**：房天下新房挂牌月均价（近 6 月窗口，逐月累积成长期序列）

> 历史版本覆盖北上广深+苏州；2026-09 用户指定只关注沪杭 → `CITIES`/`CITY_CN` 收窄为 sh/hz。恢复范围只需把城市键加回两个常量（代码自动适配）。

## 数据源（2026-09 实测打通，已下沉 data-source-router，勿回退到直接爬）

| 数据 | DSR kind | 源 | 关键点 |
|---|---|---|---|
| 房价/租金/售租比/区县排行 | `cn_housing_city` | 中国房价行情 **手机站** `m.creprice.cn/city/{code}.html[?type=lease]` | ⚠️ 桌面站 `www.creprice.cn` 被验证码墙拦（ECS IP），手机站免验证码；**必须 iPhone UA**；城市代码：bj/sh/gz/sz/hz/**su**(创房价) |
| 新房月均价趋势（近6月） | `cn_housing_trend` | 房天下 `fangjia.fang.com/fangjia/common/ajaxtrenddatanew/{code}?dataType=city&Class=defaultnew` | 返回 `[[ts_ms, price],...]`；城市代码苏州=**suzhou**(房天下)；注意两源苏州代码不同 |
| LPR 历史（2019-08 至今） | `cn_lpr` | 中国银行 `bankofchina.com/fimarkets/lilv/fd32/201310/t20131031_2591219.html` | HTML 表 `td` 三元组(日期/1Y/5Y)，85 条；页面从新到旧 |

> 适配器在 `data-source-router/adapters/housing.py`，内置低频规范（间隔 >=2s 随机抖动）、TTL 1 天缓存、单域名冷却。fetch.py 只做组装。城市范围控制用 `fetch.py` 的 `CITIES` 常量。城市码映射：创房价 `{bj,sh,gz,sz,hz,su}`、房天下 `{bj,sh,gz,sz,hz,suzhou}`。

### ❌ 已验证不可用（别再试）
- 安居客 `anjuke.com/fangjia/*` → 58 antibot 验证码(纯 curl 拿不到)
- 链家/贝壳 esf/zufang 城市页 → JS 动态渲染无静态均价
- 统计局 `data.stats.gov.cn` easyquery → ECS IP 被 WAF UrlACL 403
- 房天下 esf 新闻稿 `/newsecond/news/*` → stub 页无正文

## 更新命令（手动，勿 cron —— 用户铁律）

```bash
cd /root/zach-skills/housing-rent-buy-dashboard
python3 scripts/fetch.py      # 走 DSR(force 强制回源) → data/housing_{YYYYMMDD}.json + latest.json；--cache 走缓存(调试)
python3 scripts/render_html.py  # → output/housing_rent_buy_dashboard.html（自包含，可挂博客 public/exports/）
cp output/housing_rent_buy_dashboard.html /root/ZacharyXue.github.io/public/exports/housing-rent-buy-dashboard.html
# 🔴 博客看板索引注册：`src/content/projects/investment-dashboard.md` 里本看板行已存在（新增/改名时同步）
```

## 指标与口径

- **租金回报率** = 1/售租比（官方）；交叉验证自算 = 月租金×12/房价（两口径差异 <0.1pp）
- **月供** = 等额本息 `P·r(1+r)^n/((1+r)^n−1)`，r = 5Y LPR/12，n = 360
- **售租比 vs LPR 判断**：回报率 > LPR 5Y → 「跑赢利息」（买房收租现金流成立）；否则押注资本利得
- 参数 AREA/DOWN_RATIO/LOAN_YEARS 在 render_html.py 顶部常量可调

## 看板结构（dashboard-style 规范复用）

1. 摘要：6 城回报率范围 + 0/6 跑赢徽章
2. 六城对比表：均价/环比/租金/环比/售租比/回报率/vs LPR/月供/月租/差额
3. 决策框架卡（为什么关注/看什么信号）
4. 房价趋势（房天下归一化指数，首月=100，6 城 6 线）
5. LPR 走势（1Y/5Y 双线，2019-08 起）
6. 沪/杭/苏分区表：房价/租金/售租比/回报率/vs LPR（按房价降序，gap = 回报率−LPR）

## 固化的坑（2026-09 实测）

- **创房价手机站需要 iPhone UA**（`Mozilla/5.0 (iPhone...)`），桌面 UA 到城市页会 302 到验证码
- **两源苏州代码不同**：创房价 `su` / 房天下 `suzhou`，混用会拿到上海数据（302 重定向）
- **区间价文本**：租金单价和区县均价都带小数（`96.76`），正则必须 `[\d,.]+` 否则解析失败
- **区县只披露环比无同比**：正则匹配一个 pct 即可
- 房天下趋势接口偶发 000 丢包：`http_get` 内置 tries=3 重试即恢复（免费源偶发 ≠ 源坏）
- 数据频率：创房价/房天下都是**月度挂牌**口径；首抓只有 6 月趋势，靠逐月 update 累积
- 勿把「售租比」念成「租售比」混淆：售租比 = 房价/年租金（年，越大越不划算）；租金回报率 = 1/售租比

## TODO（未来可选）
- 板块级（非区县级）精化：创房价有板块页可探索（见会话「板块级精化解释」）
- 历史趋势累积：把每次抓的 latest.json 归档即可拼长序列（data/housing_*.json 已自动留存）