# OpenCode CLI 安装 + opencode-go Provider 配置 + 模型探测

ECS 实战（2026-08）：opencode v1.18.18 安装、opencode-go provider 接入、主模型探测。

## 1. 安装（npm >= 11 的 allow-scripts 坑）

```bash
# npm >= 11 默认拦截 postinstall 脚本 → 二进制不落地，opencode 命令不存在
# 必须显式 --allow-scripts：
npm i -g --allow-scripts=opencode-ai opencode-ai@latest

opencode --version          # 验证，本机输出 1.18.18
which opencode              # /root/.npm-global/bin/opencode
```

版本语义（npm dist-tags）：
- `latest` = v1.x 稳定版（当前 1.18.18）
- v2 仍在 `0.0.0-beta-*`（未发布）→ **装 @latest，不装 @beta**

连通验证：
```bash
cd /tmp && opencode run 'Respond with exactly: OPENCODE_SMOKE_OK'
# 期望输出 OPENCODE_SMOKE_OK；报 "Missing API key" 说明 provider 没配好
```

## 2. Provider 配置（用户偏好：key 入配置文件，不入 env）

**用户明确偏好**：opencode 的 API key 写进 opencode 自己的配置文件，**不要 export 到环境变量 / bashrc**。
（opencode 加载 `~/.config/opencode/opencode.json` 里的 `apiKey`；`~/.config/opencode/.env` 不一定被读，别依赖。）

配置文件：`~/.config/opencode/opencode.json`（写完 chmod 600）：

```json
{
  "$schema": "https://opencode.ai/config.json",
  "provider": {
    "opencode-go": {
      "npm": "@ai-sdk/openai-compatible",
      "name": "OpenCode Go",
      "options": {
        "baseURL": "https://opencode.ai/zen/go/v1",
        "apiKey": "sk-……（从 ~/.hermes/.env 的 OPENCODE_GO_API_KEY 复制，注意 secret redaction 读不到原文，用 stdin 重定向或 cat 拷贝）"
      },
      "models": {
        "deepseek-v4-flash": { "name": "DeepSeek V4 Flash" },
        "deepseek-v4-pro": { "name": "DeepSeek V4 Pro" },
        "glm-5.3": { "name": "GLM 5.3" },
        "glm-5.2": { "name": "GLM 5.2" },
        "glm-5.1": { "name": "GLM 5.1" },
        "qwen3.8-max": { "name": "Qwen 3.8 Max" },
        "qwen3.7-max": { "name": "Qwen 3.7 Max" },
        "qwen3.7-plus": { "name": "Qwen 3.7 Plus" },
        "kimi-k3": { "name": "Kimi K3" },
        "kimi-k2.7-code": { "name": "Kimi K2.7 Code" },
        "minimax-m3": { "name": "MiniMax M3" },
        "minimax-m2.7": { "name": "MiniMax M2.7" },
        "grok-4.5": { "name": "Grok 4.5" },
        "hy3": { "name": "Hy3" },
        "gpt-5.6-luna": { "name": "GPT 5.6 Luna" }
      }
    }
  },
  "model": "opencode-go/deepseek-v4-flash"
}
```

备注：
- Hermes 侧同源网关：`~/.hermes/config.yaml` 里 `provider: opencode-go`、`model.default: deepseek-v4-flash`、base_url `https://opencode.ai/zen/go/v1`——opencode-go 与 Hermes 用的是同一套 API key 和模型。
- 改动后无重启概念，`opencode run` 每次读配置。

## 3. 可用模型清单（GET /v1/models，2026-08 实测）

```
minimax-m3, minimax-m2.7, minimax-m2.5
kimi-k3, kimi-k2.7-code, kimi-k2.6, kimi-k2.5
glm-5.3, glm-5.2, glm-5.1, glm-5
deepseek-v4-pro, deepseek-v4-flash
qwen3.8-max, qwen3.7-max, qwen3.7-plus, qwen3.6-plus, qwen3.5-plus
mimo-v2-pro, mimo-v2-omni, mimo-v2.5-pro, mimo-v2.5
hy3, hy3-preview
gpt-5.6-luna
grok-4.5
```

## 4. 主模型探测（选哪个模型更优）

⚠️ **关键坑**：`opencode run` 指定模型必须用 `--model "provider/model"`；
把模型名当位置参数（`opencode run "provider/model" ...`）会打印 CLI help 并秒退，探测脚本输出全是 2s 完成的假象。

```bash
MODELS="deepseek-v4-flash deepseek-v4-pro glm-5.3 qwen3.8-max kimi-k3 grok-4.5"
TASK='你的探测任务（写文件+跑测试的完整工具链）'
for m in $MODELS; do
  rm -rf /tmp/probe && mkdir -p /tmp/probe
  echo "========== [$m] START $(date +%H:%M:%S) =========="
  START=$(date +%s)
  timeout 240 opencode run "$TASK" --model "opencode-go/$m" 2>&1 | tail -6
  echo "---------- [$m] 耗时: $(( $(date +%s) - START ))s"
  # 产出检查：ls /tmp/probe/*.py && pytest
  echo "========== [$m] END =========="
done
```

推荐探测任务（模拟投研 agent 的多步工具调用链）：写 dividend_yield.py（接收股价、年股息输出股息率两位小数）+ pytest 测试验证 100/3 = 3.00%，跑 pytest 通过。对比维度：任务是否完成、pytest 是否通过、耗时。

## 5. 实测结果（2026-08-16）

任务同上（写脚本+pytest 验证），opencode-go 网关 6 模型实测：

| 模型 | 结果 | 耗时 | 测试数 |
|---|---|---|---|
| glm-5.3 | ✅ | **30s（最快）** | 2 passed |
| deepseek-v4-pro | ✅ | 48s | 1 passed |
| kimi-k3 | ✅ | 48s | 2 passed |
| deepseek-v4-flash（当前默认） | ✅ | 62s | **3 passed（最全）** |
| qwen3.8-max | ❌ `Endpoint is unavailable` | 93s | — |
| grok-4.5 | ❌ `Endpoint is unavailable` | 84s | — |

结论：
- 4 个可用模型都能独立完成「写代码→写测试→运行验证」全链路 → opencode-go 主流模型可支撑投研 skill 工具调用模式。
- **qwen3.8-max / grok-4.5 是网关路由未通，不是模型质量问题**——日后重试或联系 gateway，不要据此否定模型。
- **用户决定：默认保持 deepseek-v4-flash（与 Hermes 一致，稳妥优先）**；想提速时 `--model opencode-go/glm-5.3` 切换。