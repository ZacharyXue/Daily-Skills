# Hermes 性格 / prompt 定制调查（2026-08-16，ECS 47.85.183.215）

用户问「当前 Hermes 是不是性格还没有添加，还有哪些 prompt 设置」。以下为调查结论，供后续继续定制时直接用，不必重新调查。

## 现状结论（2026-08-16 晚更新：SOUL.md 已定制完成）

1. **`~/.hermes/SOUL.md` 已定制写入**（2026-08-16，用户确认「可以」后写入），不再是默认模板。内容为四节：身份与语言（中文、直接务实）、工作方式（proactive、动手优先、commit 不 push、中文 git message）、子皓的背景（Python/K8s/Go、量化、知识库）+ 交互偏好（学习先讲原理、交易信息投飞书「用户687528」）。SOUL.md 是唯一「身份」文件，**每次会话必注入系统提示**，改动影响全局；**写入后对新会话生效**（当前会话仍用旧身份，需开新会话或重启 gateway 才切换）。
2. **`agent.personalities` 有 14+ 内置预设**（config.yaml 第 10-46 行：helpful/concise/technical/creative/teacher/kawaii/catgirl/pirate/shakespeare/surfer/noir/uwu/philosopher/hype），但**一个都没激活**（`display.personality` 为空）→ 默认会话 = 基础行为。临时换风格用 `/personality 名`。
3. 其余 prompt 相关配置：`compression` 已开（threshold 0.5）、`memory` 已开（2200/1375 上限）、`agent.max_turns=150`、`reasoning_effort=medium`。

## 五条定制路径（按价值排序）

| 路径 | 机制 | 适用 |
|------|------|------|
| **① SOUL.md** | `~/.hermes/SOUL.md`，每次会话注入 | 全局身份/性格/工作方式，收益最大 |
| **② `/personality 名`** | config `agent.personalities` 预设，会话内切换 | 临时换风格；也可在 config 里加自定义条目 |
| **③ 项目级 AGENTS.md / .hermes.md** | 项目根目录，cwd 在该项目时自动加载 | 每项目规则（构建命令、代码规范）。注意优先级：.hermes.md 走父目录上溯到 git root，AGENTS.md 仅 cwd |
| **④ quick_commands** | config 里定义 `/xxx` 快捷指令 | 高频操作一键触发 |
| **⑤ channel_prompts** | 按平台定制（如飞书单独一套） | 渠道隔离 |

## 已拟 SOUL.md 草稿（用户未确认，待续）

用户画像（配合 memory 使用）：薛子皓，程序员，中文交流，Python 为主，管理知识库（博客/读书笔记/知识星球）+ 炒股量化（xtquant/天天基金），偏好 proactive 主动建议，学习时先讲透原理（博客是副产品），关键操作先确认，代码只 commit 不 push。

```markdown
# SOUL.md — 子皓的 Hermes 助手
你是薛子皓（子皓）的个人编程助手，运行在他的阿里云 ECS 上。
- 用中文交流，直接、务实，不废话
- 程序员助手：Python/Go/K8s/量化交易，主动提建议（proactive），不等被问
- 帮他管理知识库（博客/读书笔记/知识星球）和炒股代码（xtquant/天天基金）
- 他学习时：先讲透原理让他学会，博客是副产品
- 关键操作先确认，代码只 commit 不 push（他决定何时推送）
```

## 待办（更新后）

- ✅ SOUL.md 已写入 `~/.hermes/SOUL.md`，**新会话生效**；当前会话仍是旧身份（gateway 会话需重启才切换，见 Pitfall 4）
- 可选：① 给 /root 下项目（volcano、pytest、博客仓库）配 AGENTS.md / .hermes.md（项目级规则：构建命令、代码规范）；② 配 quick_commands（如 `/复盘` 快捷指令）；③ `/personality technical` 临时切技术专家模式
- 写入 SOUL.md 用 write_file 直接写 `~/.hermes/SOUL.md`（不是 config.yaml，无安全保护拦截）；写后可用 `python3 -c "from agent.prompt_builder import load_soul_md; print(load_soul_md())"` 验证（在 hermes-agent 源码目录下）