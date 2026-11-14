# ai-berkshire × TradingAgents 对比 + ai-berkshire 适配 OpenCode

ECS 实战记录（2026-08-16）：两个炒股 agent 仓库的架构评估与选定 ai-berkshire 的 opencode 适配路径。仓库位置：`/root/ai-berkshire`、`/root/TradingAgents`（均 depth-1 clone 于当日）。

## 仓库本质对比

| 维度 | ai-berkshire (xbtlin) | TradingAgents (TauricResearch) |
|---|---|---|
| 本质 | **提示词/技能库**（prompt-as-code），95.9% Markdown（2303 文件 35.7 万行），Python 仅 2847 行（14 工具） | **可执行 Python 框架**，9090 行代码 + 70+ 测试，LangGraph 状态图 |
| 架构 | 三层：Skill 层（20 入口）→ Agent 层（Team Lead 并行调度 4 大师视角 Agent，用 Claude Code Team 原语）→ 工具层（financial_rigor/report_audit 等） | START→5分析师(并行)→Bull/Bear 研究员辩论→Research Manager→Trader→风险三裁判→Portfolio Manager→END |
| 市场 | 美股+A股+台股（雪球/晨星 fair value/13F） | 美股为主（yfinance/Alpha Vantage/FRED/Polymarket/Reddit） |
| 风格 | 四大师价值投资（长线） | 多空辩论（短线博弈） |
| LLM | 绑定 Claude Code / Codex | 12+ provider 抽象 |
| 活跃度 | ⭐15.6k / 4 个月 / 日更（2026-08-15 最后 commit） | ⭐98k / 1.5 年 / 月更（2026-07-18） |
| 使用方式 | 装进 Claude Code/Codex 当 slash command | `pip install` + `tradingagents analyze NVDA` |

**判定结论（给用户的建议）**：优先扩展 ai-berkshire（方法论契合价值投资 + A股适配 + 日更活跃），TradingAgents 作 LangGraph 编排的架构参考。ai-berkshire 本身不能在 Hermes 直接跑——价值在「抄方法论」：把 20 个 skill 的研究流程、多 agent 分工、财务严谨性校验（tools/financial_rigor.py、report_audit.py）吸收进自建 skill。

## ai-berkshire 适配 OpenCode（关键发现）

1. **格式白送**：`codex-skills/*/SKILL.md`（21 个）是标准 SKILL.md 格式，opencode 原生搜索路径含 `~/.config/opencode/skills/`、`~/.agents/skills/`、`.claude/skills/`、`.agents/skills/` → 直接软链即可被发现。
2. **OpenCode 具备全部核心依赖**：内置工具 bash/edit/write/read/grep/glob/apply_patch/**skill**/todowrite/**webfetch**/**websearch**/question + MCP；permission 字段可 `allow/deny/ask` 控制（对应 Claude 的 permissions.allow 白名单）。tools/*.py 走 bash 调用，直接可用。AGENTS.md 也是 opencode 原生识别。
3. **零改造（18/20）**：单 agent 型 skill（quality-screen、industry-research、financial-data、investment-research 等）只要求 WebSearch+Bash+文件工具。
4. **需改写（2/20）**：`investment-team`、`earnings-team` 依赖 Claude Code Team 原语（TeamCreate/TaskCreate/run_in_background: true）+ `.claude/settings.local.json` 权限预检 grep。opencode 的并行机制是 subagent（内置 General 官方说 "run multiple units of work in parallel"），调用语法不同需重写；权限预检改为 grep opencode.json 的 websearch/webfetch allow。
5. **模型考量**：README 官方建议深度投研用最强模型；deepseek 跑单 agent/初筛够用，4 agent 并行重型流程质量会打折。opencode 支持按 agent 配不同模型 → 轻量 skill 用 deepseek-v4-flash、重量级换 glm-5.3 等。GitHub issue #38（"希望支持 opencode"）仍 open，作者未回应 → 自行适配，照抄仓库已有的 `## Codex adapter note` 模式写 OpenCode 版。