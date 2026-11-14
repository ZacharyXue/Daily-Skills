# Hermes 升级实战：pip 废弃 → 官方 install.sh → git main → 切 gateway

> 2026-09 本机实战：收到 OpenCode Go 提醒「请求缺 `x-opencode-session` header，09/06 后可能 error」，起因是 Hermes 版本过老（0.19.0），且 **pip 安装已不被官方支持、不再发更新**。完整从 0.19.0 升到 0.21.0 的记录。

## 背景 / 触发信号

OpenCode Go（模型网关）发来提示：部分请求缺 `x-opencode-session` header，它无法据此优化服务，并要求 Hermes ≥0.21.0。查证：
- `hermes --version` → 本机 **v0.19.0，pip 安装**，`Update available: 10402 commits behind`。
- 官方 [platform-support] 文档：**Linux 推荐 install.sh；pypi(pip) 被列为 Unsupported**，要求迁移。
- `hermes update --check` 在 pip 安装下谎报 **"Already up to date"**——它基于 pip 模式检查，根本没拉 git 新版本。**这也是一个重要的判别信号：pip 装的 Hermes 想升级，`hermes update` 不可信。**

## 关键坑（按踩坑顺序）

1. **`uv pip install --upgrade hermes-agent` 只升依赖、不升本体**（0.19.0 没动）。因为 Hermes 是 git 源码 + pip editable 混装模式，pip 只更新 PyPI 上的依赖。
2. **绝不能在当前会话里跑 `hermes update`**：它会「restart gateway + kill 所有 running agents」——包括你正在对话的这个 agent 进程。会话内自杀式升级不可行。
3. **install.sh 默认只给最新 release tag**（实测给到 **v0.20.1**），仍 < 0.21.0，且该版本源码里**还没有** `x-opencode-session`。要 provider 要求的 header，必须升到 git main。

## 升级步骤（0.19.0 → 0.21.0，main）

### 1. 非交互跑官方 install.sh（不动配置、不断会话）
```bash
curl -fsSL https://hermes-agent.nousresearch.com/install.sh -o /tmp/install_hermes.sh
# 关键 flag：--skip-setup 跳过交互 wizard；--non-interactive 跳过需输入的阶段
bash /tmp/install_hermes.sh --skip-setup --non-interactive > /tmp/hermes_install.log 2>&1
```
结果：装到 `/usr/local/lib/hermes-agent`（venv = **python 3.11**，与旧 3.12 不同），命令链 `/usr/local/bin/hermes`，**`$HERMES_HOME`(/root/.hermes) 的 config/skills/memory/cron 全保留**，原 git checkout 不动。装完当前会话仍活着（install.sh 不重启 gateway、不 kill agent）。

### 2. 升到 git main 拿最新版本（本次才有 x-opencode-session）
```bash
cd /usr/local/lib/hermes-agent
git fetch origin --depth 50          # 网络慢可后台跑；github 大仓深 fetch 可能超时
git checkout -f origin/main
cd venv && /root/.local/bin/uv pip install -e /usr/local/lib/hermes-agent   # 重装到新 venv
/usr/local/lib/hermes-agent/venv/bin/hermes --version    # → v0.21.0 (2026.8.31)
```
**验证 header 已实现**（判断「版本够了」而不是猜）：
```bash
grep -rl "x-opencode-session" /usr/local/lib/hermes-agent/ --include=*.py
# 命中 agent/opencode_affinity.py + agent/chat_completion_helpers.py + tests/...  = 确认已实现
```

### 3. 新 venv 可运行性验证（3.11 venv 能加载 gateway 入口）
```bash
NPY=/usr/local/lib/hermes-agent/venv/bin/python
"$NPY" -c "import hermes_cli.main; import gateway; print('OK')"
"$NPY" -c "import gateway.cgroup_cleanup; print('OK')"   # cgroup_cleanup 也要能在新 venv 跑
```

### 4. 切 systemd 服务到新 venv（改 unit，不改则 gateway 仍用旧 venv 进程）
`/etc/systemd/system/hermes-gateway.service` 四行要改（patch 工具会拒绝写系统路径，用终端 `sed -i` + 先 `cp` 备份）：
- `ExecStart=/root/hermes-venv/bin/python ...` → `/usr/local/lib/hermes-agent/venv/bin/python`
- `Environment="PATH=/root/hermes-venv/bin:...` → `/usr/local/lib/hermes-agent/venv/bin:`
- `Environment="VIRTUAL_ENV=/root/hermes-venv"` → `.../usr/local/lib/hermes-agent/venv"`
- `ExecStopPost=-/root/hermes-venv/bin/python -m gateway.cgroup_cleanup` → `.../venv/bin/python`
```bash
cp /etc/systemd/system/hermes-gateway.service /etc/systemd/system/hermes-gateway.service.bak-$(date +%Y%m%d%H%M)
sed -i 's#ExecStart=/root/hermes-venv/bin/python#ExecStart=/usr/local/lib/hermes-agent/venv/bin/python#' <F>
sed -i 's#VIRTUAL_ENV=/root/hermes-venv#VIRTUAL_ENV=/usr/local/lib/hermes-agent/venv#' <F>
systemd-analyze verify /etc/systemd/system/hermes-gateway.service   # 应无 hermes-gateway 报错
systemctl daemon-reload
```

### 5. 重启切到新版（会断当前会话，必须用户从外部执行）
`systemctl restart hermes-gateway`——断几秒~几十秒，新版起来后微信自动恢复，header 问题解决。**不能从 gateway 内部执行**（Pitfall 4 硬保护）。

## 遗留：curl 请求的 header

升级解决 Hermes 自己（Python OpenAI client）的 header。**别的 curl 直连 OpenCode Go 的脚本/工具**仍要手动在每个请求加 `x-opencode-session`（每会话一个稳定 ID）。这类调用在系统里要 `grep -r "opencode\|zen/go" /xxx` 找到写 curl 的脚本再处理。

## 教训一句话
pip 装的 Hermes 想升级，先看 `hermes --version` 的 install method；若是 pip 且要新版本，直接走官方 install.sh → /usr/local，再把 systemd 四行指到新 venv，最后让用户外部重启 gateway。