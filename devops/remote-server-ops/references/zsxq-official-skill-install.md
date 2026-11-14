# 官方 zsxq skill 安装实战（2026-08-16，阿里云 ECS 47.85.183.215）

来源：https://garden.zsxq.com/skill/ （知识星球官方花园，beta）。安装指南即 `https://garden.zsxq.com/skill/INSTALL.md`，供 AI Agent 直接读并执行。

## 为什么装

用户要求参考官方页安装。本机此前是**旧版 5 个拆分技能**（zsxq-shared / zsxq-group / zsxq-topic / zsxq-user / zsxq-note，在 `~/.hermes/skills/zsxq/` 下各一子目录）。新版是**单一 `zsxq` skill（v2.1.0）**，官方设计就是 5 合一，覆盖更全面（场景模式：每日巡场、评论区运营、定时发布、负面监控、海报/视频生成等）。

## 安装步骤（实测通过）

```bash
# 1. 前置检查：node >= 18
node -v   # 本机 v26.7.0 ✅

# 2. 装 CLI（skill 的 metadata.requires.bins 依赖）
npm install -g zsxq-cli          # → /usr/local/bin/zsxq-cli，验证 zsxq-cli --version (0.5.0)

# 3. 装 skill（GitHub 优先，不通换 Gitee）
npx -y skills add https://github.com/unnoo/zsxq-skill --yes --global
# 或：npx -y skills add https://gitee.com/unnoo/zsxq-skill --yes --global
# 离线包兜底：https://garden.zsxq.com/skill/zsxq-skills.zip → npx skills add ./zsxq-skill --yes
```

**安装位置语义（关键）**：
- 实体装到 `~/.agents/skills/zsxq/`（Codex 生态的 global 目录）
- 自动 **symlink** `~/.hermes/skills/zsxq -> ../../.agents/skills/zsxq` → Hermes 立即识别
- 同名旧目录被整体替换为软链 —— 旧版 5 子目录直接被覆盖，升级前应确认无未备份自改内容
- 安装日志里 "symlinked: Hermes Agent" 表示 Hermes 链接成功；"✗ PromptScript 不支持 global" 属正常告警可忽略

结构：`SKILL.md` + `references/`（auth-errors、group-*、topic-*、note-*、user-*、scenarios/ 十几个场景文档、cli-exploration）+ `scripts/`。

## 登录（必须用户真人授权）

```bash
zsxq-cli auth login
```
- 输出浏览器授权链接 `https://garden.zsxq.com/jasmine/index.html?code=XXXX-XXXX` + 确认码
- 服务器无 xdg-open，浏览器不会自动打开 → **把链接 + 确认码发给用户手动点**
- ⚠️ **agent 不能替用户完成授权**；`auth login` 会一直轮询等待 → 用 `terminal(background=true)` 挂后台，把链接给用户，授权完成后进程自动退出（可 watch "授权成功/success" 类词）
- Token 存系统 Keychain（macOS/Keychain 或 Linux secret store），不在终端明文输出

验证：`zsxq-cli auth status`；试跑 `zsxq-cli group +list` 列出星球。

## 升级/迁移注意

- 官方的 `references/scenarios/migrate-legacy-skills.md` 规定：默认只检查只报告；移动/删除旧 skill 必须经用户显式确认
- 判定旧 skill 标准：目录名命中五旧名之一 **且** SKILL.md frontmatter `name:` 与目录名一致；禁止 `zsxq-*` 通配匹配（会误伤用户自建 skill）
- 本机安装时新版已覆盖旧目录，无残留迁移项

## 安全须知（SKILL.md 内嵌）

- 禁止输出/传播认证 token
- 所有写入操作（发帖/评论/回答/定时/精华/标签/笔记/删除）执行前必须确认用户意图
- 笔记是公开内容，任何持链者可访问，隐私勿写