# 在 Hermes 装 MCP server（Chrome DevTools MCP 实战，2026-08-16）

在 Hermes 中接入第三方 MCP server 的完整流程，以 Google 官方 chrome-devtools-mcp 为例（本机 ECS 实测成功，29 工具启用）。

## 完整命令序列

```bash
# 1. 装 MCP server 本体（npm 全局）
npm install -g chrome-devtools-mcp          # v1.7.0

# 2. 必装 mcp Python SDK —— 否则 hermes mcp add 报
#    "requires the 'mcp' Python SDK, but it is not installed"
cd /root/hermes-venv && source bin/activate
pip install 'hermes-agent[mcp]'             # 装 mcp-1.26.0 等依赖

# 3. 服务器无 Chrome 时用 puppeteer 装完整版（headless-shell 不完整，MCP 需要完整 DevTools）
npx -y @puppeteer/browsers install chrome@stable
#    → /root/hermes-venv/chrome/linux-<ver>/chrome-linux64/chrome

# 4. 添加 MCP server（--executable-path 指向本地 chrome，headless + jpeg 截图省 token）
#    交互式确认 "Enable all 29 tools? [Y/n/select]" 用 printf 管道自动确认
printf 'y\n' | hermes mcp add chrome \
  --command chrome-devtools-mcp \
  --args --headless --screenshot-format jpeg \
  --executable-path /root/hermes-venv/chrome/linux-152.0.7977.42/chrome-linux64/chrome

# 5. 覆盖已有同名校验：先 remove 再 add（add 遇已存在默认 Cancel）
printf 'y\n' | hermes mcp remove chrome

# 6. 验证
hermes mcp list                  # 名称/transport/tools/status: ✓ enabled
hermes mcp test chrome           # 列出 29 个工具即连接成功
```

## 关键坑

1. **缺 mcp SDK**：`hermes mcp add` 首次连接报 `requires the 'mcp' Python SDK`，安装 `'hermes-agent[mcp]'` 即可（同时装 mcp-1.26.0、starlette 等）。不装时还会伴随 asyncio `Event loop is closed` 崩溃，是同一根因。
2. **服务器没有 Chrome**：headless 服务器上 MCP 找不到浏览器会失败。`@puppeteer/browsers install chrome@stable` 装完整 Chrome 后，**必须**在 `--args` 里配 `--executable-path` 指向它，否则 server 启动时找不到可执行文件。
3. **交互式确认**：`hermes mcp add` 会问 "Enable all N tools? [Y/n/select]"；已存在时先问 Overwrite?。非交互环境（agent 终端）用 `printf 'y\n' |` 管道喂答案，否则永远 Cancel。
4. **agent 不能直接改 config.yaml**：`patch`/`write_file` 写 `~/.hermes/config.yaml` 会被保护拦截（"Refusing to write to Hermes config file… Agent cannot modify security-sensitive configuration"）。MCP 配置必须走 `hermes mcp add/remove` CLI。
5. **生效条件**：工具需要**新会话**才加载（"Start a new session to use these tools"）。当前会话没有新加的 MCP 工具，开新会话或重启 gateway 后才有。

## 用途

chrome-devtools-mcp 29 个工具：导航/点击/输入/滚动、截图（jpeg 省 token，配 `--screenshot-format jpeg`）、页面快照、执行 JS、网络/性能分析、文件上传等。适合网页端到端验证、抓取动态页面、UI 自动化。

## 相关

- Hermes 自带 catalog 只有 linear/n8n（`hermes mcp catalog`），chrome 需手动 add。
- 表格类 MCP（如 n8n）可直接 `hermes mcp install <name>`。
- 1G 小内存机器注意 Chrome 开销；`--isolated` 用完即焚可省内存。