# 子皓博客 → Wiki 源映射（2026-09-05 盘点，已落库投资线）

> 首次对话用户说「笔记在 ./out」实际指博客文章；全盘 find 浪费了时间。
> 涉及子皓「笔记/知识/wiki」任务时源材料优先查博客 repo，勿盲目全盘搜。

## 源 repo

- 博客仓库：`/root/ZacharyXue.github.io`（Astro content collections，master，干净）
- `src/content/blog/*.md` 24 篇 + `src/content/projects/*.md` 3 篇 = 27 篇
- blog frontmatter: `title/date/tags[]/description/draft`；projects: `title/url/tags[]/status`
- 原始 tags ~92 个（Python×7、算法×6、红利×3、Agent×3、架构×4…）→ taxonomy 收敛是第一动作

## 五大主题域与篇目

1. **投资研究**（9 篇，**已落库 2026-09-05**）: fund-q2-review、dividend-etf-comparison、
   931722-hk-soe-dividend-index、hailuo-cement-cycle-stock、shenhuo-000933-cycle-stock、
   renfu-st-ma-turning-point、midea-vs-haier + projects/investment-dashboard
2. **K8s/云原生**（3 篇，待落库）: volcano调度笔记、containerd原理剖析与实战笔记、linux-ops-commands
3. **LLM/Agent 工程**（6 篇，待落库）: loop-engineering、codex-agent-team、llm-as-judge-self-iteration、
   opencodereview-llm-half、opencodereview-hermes-context-compression、fastapi-deep-dive
4. **算法/LeetCode**（7 篇，待落库）: min-stack、stone-game-ii-dp-pattern、twin-prime-sieve、
   德州扑克算法、frequency-monitor-monotonic-queue、玩具称重 等
5. **读书/软技能/杂项**（待落库）: 关键对话-读书笔记、hello-world、projects/daily-skills、markdown-resume

## 落库后的分层（2026-09-05 已执行）

- `concepts/investing/`：周期股分析框架、红利资产风险分层、估值锚定体系、财务质量验证法、
  伪质量红利识别、价值陷阱与困境反转判别、基金研究框架（7 页）
- `entities/`：神火股份、海螺水泥、人福医药、港股央企红利指数931722（4 页）
- ⚠️ 企业对比（白电双雄/红利四选一）→ **归博客原文**，wiki 不建对比页（2026-09-05 子皓纠偏）
- 待落库：云原生线（gang调度/namespace-cgroup/容器运行时）、LLM线（Loop/上下文压缩）、
  算法线（DP题型谱系/单调队列/数论）
- data 位置：`/root/wiki/`（git-crypt 加密，栈内 commit 不 push；推送由子皓决定/建仓后）