---
name: opencode-go-model-selection
description: 为 Hermes/opencode 挑选最优 opencode-go 模型并排 429 配额错误 —— 配额机制($12/5h+$30/周+$60/月)、模型性价比(便宜→请求多)、多模态判定、切换主模型(hermes config set)、429 GoUsageLimitError 排查。触发：对话报「iteration/retry backoff」「429 配额用尽」、问「哪个模型省钱/多模态」「切换主模型」。
---

# opencode-go 模型选择 · 配额与 429 排错

针对 opencode-go 网关（`provider: opencode-go`）的**模型性价比选择** + **配额耗尽(429) 排查**。核心：模型越便宜，订阅配额内请求越多；多模态贵，纯文本日常最省。

## 触发语
- 对话报 `iteration 1/150, error retry backoff` / `429 GoUsageLimitError`
- 「哪个模型性价比高 / 省钱 / 有多模态」
- 「切换主模型到 X」

## 配额机制（决定一切）
- **Go 订阅 $10/月**，按美元价值配额：**5h $12 / 周 $30 / 月 $60**
- 各模型不同**多倍率**：经典经测 ≈6x（Qwen3.7-Plus/GLM-5.2/Kimi K2.7 Code/MiMo-V2.5/Hy3/Muse），新模型或无批量折扣 ≈1.5x（GPT-5.6 Luna/GLM-5.3/Kimi K3/Qwen3.8 Max/Grok 4.5/MiMo-Pro）
- **推论：模型越便宜/越经典，配额内请求越多；贵旗舰买不到几次。**

## 🚨 429 排错（本次实战根因）
**症状**：多个对话同时报 `iteration 1/150, error retry backoff (1/3)` → 3 次 backoff 后 `API call failed after 3 retries`。

**根因**：`error_type=RateLimitError / HTTP 429 / 'type':'GoUsageLimitError' / limitName:'weekly'` = **opencode-go 周配额 $30 用尽**，**不是模型坏、不是网关挂**。

**排查链**（别乱猜，翻日志实锤）：
```bash
# 1. 看网关/agent 日志里的 429
tail -30 ~/.hermes/logs/errors.log | grep -iE "429|GoUsageLimit|weekly|rate"
# 2. 确认是配额不是模型
grep -i "limitName.*weekly" ~/.hermes/logs/agent.log | tail -3
```

**处置**：
- **立即**：`hermes config set model.default <更省配额的模型>`（当前多模态主力 `deepseek-v4-flash-vision-exp` 贵，切纯文本 `deepseek-v4-flash` 立马缓解）
- **等配额**：周配额在剩余 ~17h 后自动重置（报错里 `Resets in 17hr`）
- **可选**：opencode 控制台开 `Use balance` 让 Go 用 Zen 余额兜底，不再 block（文档提过）

## 🏆 性价比表（月配额内约请求数，越高越划算）
| 模型 | 倍率 | 月配额 | 约请求/月 | 多模态 |
|---|---|---|---|---|
| **MiMo-V2.5** | 6x | $60 | **150,400** | 否 |
| **Muse Spark 1.2** | 6x | $60 | **226,600** | 全模态 |
| **DeepSeek V4 Flash** | ~3x | $30 | **37,800** | 否(纯文本) |
| Qwen3.7-Plus | 6x | $60 | 21,600 | image |
| Hy3 | ~8x | $60 | 21,500 | 否 |
| MiniMax M3 | 6x | $60 | 16,000 | image |
| GLM-5.2 | 6x | $60 | 4,300 | image |
| Kimi K2.7-Code | 6x | $60 | 6,750 | image |
| GPT-5.6 Luna | 1.5x | $15 | 10,250 | image |
| GLM-5.3 | 1.5x | $15 | 1,080 | 否 |
| Qwen3.8-Max | 1.5x | $15 | 810 | 全模态 |
| Grok 4.5 | 1.5x | $15 | 600 | image |
| Kimi K3 | 1.5x | $15 | 490 | image |
| DeepSeek V4 Pro | 1.5x | $15 | 5,200 | 否 |

> DeepSeek 系区分 Peak/Off-Peak：off-peak 价 ≈ 一半（省一半配额）。

## 🎯 推荐配置（已采纳）
- **日常文本主力**：`deepseek-v4-flash`（off-peak）—— 能力近闭源旗舰、单请求 ~$0.0008、月 37,800 次，**最省且够强**
- **要更强文本**：`qwen3.7-plus`（6x 里请求量大、编程扎实）
- **多模态(看图/视频)**：`glm-5.3-flash` 或 `qwen3.8-max`（旗舰级 image+video+pdf）；**便宜看图**用 `minimax-m3` / `kimi-k2.7-code`
- ⚠️ **别切** Grok / GPT-5.6 Luna / Qwen3.8 Max（1.5x 性价比陷阱）

## 切换主模型
```bash
hermes config set model.default <model-id>   # 只改 default，保留 provider/base_url
hermes config get model                       # 确认
# 注意：当前会话仍用旧模型，重启 gateway 或新会话才生效
```

## 多模态判定（models_dev_cache）
- 纯文本：`deepseek-v4-flash`（⚠️ 主力是纯文本！）、`glm-5.3/5.1/5`、`longcat-2.0`、`hy3`
- image+video+pdf：`qwen3.8-max`、`glm-5.3-flash`
- 全模态(+audio)：`muse-spark-1.2-contributor`、`mimo-v2-omni`
- image：`deepseek-v4-flash-vision-exp`、`minimax-m3`、`kimi-k2.7-code`

## Pitfalls
- **模型列表每次重新拉 `/models`**，别凭上次印象（会随官方测试变动）
- **vision 版吃图像 token**，一张图转成一堆 input token 计费，配额消耗比纯文本快一个量级——多对话带图特别容易打爆周配额
- **`deepseek-v4-flash-vision-exp` 不在 opencode.json 显式配置里**也能用（网关直通），但它贵，别当日常主力
