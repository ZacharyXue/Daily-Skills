---
name: site-login
description: 网页数据源登录管理 — headless 守护式扫码登录、登录态持久化与复用。站点适配器：雪球（xueqiu）。触发时机：爬虫/工具报登录失效（10022/30022）、需要登录的数据源首次使用、用户问「雪球爬虫怎么登录/登录态在哪」。state 统一存 ~/.cache/data-source-login/。
version: 1.0.0
tags: [login, xueqiu, headless, playwright, scan-qrcode, state-management]
---

# Site Login — 网页数据源登录管理

在**无桌面服务器（ECS）**上为需要登录的网页数据源建立登录态，供爬虫/取数工具复用。

## 为什么需要这个 skill

- 雪球等数据源必须登录才能调 API（unlogged 会被 WAF/API 拒绝，如 user_timeline page>=2 报 10022）
- ECS 无显示器，无法 headful 交互登录 → 必须 **headless 出码 + 用户手机 App 扫码**
- 登录态（playwright storage_state）可持久化复用，避免每次扫码

## 核心链路（一次登录）

```
headless 浏览器保持打开（绝不中途关闭！）
  → 打开站点登录页 → 点「二维码登录」
  → canvas.toDataURL() 导出纯二维码（不能用坐标截图，会混入文字）
  → 发用户 → 用站点 App 扫码（雪球=雪球App「我的→设置→扫一扫」）
  → 轮询「需登录接口」判定成功（雪球=user_timeline page=2，未登录返回 10022）
  → context.storage_state() 落盘到 ~/.cache/data-source-login/<site>_state.json
  → 同会话再验证一次，确认 state 有效
```

**三个死记的坑（实测踩过）：**
1. **登录判定必须用「需要登录的接口」**——雪球 user_timeline **page=1 是公开数据**，未登录也返回 → 假阳性；只有 page=2 未登录才报 10022
2. **浏览器必须保持打开直到登录成功**——一次性脚本导出二维码后关闭，扫码结果无人接收 = 白扫
3. **导出二维码用 canvas.toDataURL()**——屏幕坐标截图会把 canvas 上方提示文字截进图里

## 站点适配器

| 站点 | 登录脚本 | 取码方式 | 登录验证接口 | state 文件 |
|------|---------|---------|-------------|-----------|
| 雪球 xueqiu | `scripts/xueqiu_login.py` | canvas.toDataURL | `user_timeline.json?page=2`（10022=未登录） | `~/.cache/data-source-login/xueqiu_state.json` |

### 新增站点流程（借鉴现有适配器）

1. 复制 `scripts/xueqiu_login.py` → 站点名
2. 改四处：登录页 URL、取码 JS（找站点二维码的 canvas/img）、登录验证接口（未登录必有特征响应）、state 文件名
3. 用 `template` 选项确认骨架不变（保持浏览器打开→出码→轮询→落盘→复验）

## 使用方式

```bash
# 登录（新登录/重新登录，交互式：会输出二维码给用户扫）
python3 scripts/xueqiu_login.py

# 复用登录态（登录脚本内置：state 有效直接退出；无效重新走扫码）
python3 scripts/xueqiu_login.py --force   # 强制重新登录

# 检查登录态是否有效（不弹浏览器）
python3 scripts/xueqiu_login.py --check
```

**注意：所有脚本用 `/usr/bin/python3` 运行**（Hermes venv 未装 playwright；系统 Python 3.12 已装 playwright + chromium 1234）。

## 登录态目录约定

- **所有 state 统一放 `~/.cache/data-source-login/`**（系统缓存目录，不进 git、不随 skill 打包）
- 命名：`<site>_state.json`（如 `xueqiu_state.json`）
- 权限：每登录完成后 chmod 600
- state 有效性规则：**失效特征 = 爬虫报 10022/30022 或 --check 返回无效** → 重跑登录脚本重新扫码，不要手动改 state

## 与其他工具衔接

- **雪球爬虫**：`python3 xueqiu_scraper.py --state-path ~/.cache/data-source-login/xueqiu_state.json ...`
- **未来站点**：东部财富、HKEX、SEC、天天基金…… 各站点爬虫统一接 `--state-path ~/.cache/data-source-login/<site>_state.json`

## Pitfalls

- **pip 安装**：host 有 PEP 668，`pip install playwright` 需 `--break-system-packages`（已装，勿重复）
- **playwright 浏览器**：版本 1234（`~/.cache/ms-playwright/`），`playwright install chromium` 跳过已存在版本
- **UA/指纹**：使用 Mac Chrome UA + `Object.defineProperty(navigator,'webdriver',...)` 伪装，否则 WAF 拦
- **window 变量**：每次登录窗口期约 10 分钟，超时要重出码
- **手机扫码**：雪球二维码要**雪球 App** 的「扫一扫」，不是微信