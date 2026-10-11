# ttskill Installation Session — 2026-07-27

## Environment
- OS: WSL Linux x64
- Install method: API resolve → download zip → install.sh
- Base version: 0.1.2
- PATH: `~/.local/bin/ttskill`

## Platform Detection
- Detected: linux / x64
- Resolve API: `https://skills.tiantianfunds.com/ai-smart-skill-service/openapi/base-package/resolve?platform=linux&arch=x64&env=prod`
- Download URL: `https://skills.tiantianfunds.com/ttskill/packages/base/0.1.2/linux/x64/ttskill-base-linux-x64-0.1.2.zip`
- Package size: 42MB (43869205 bytes)

## Install Steps

### 1. Base package
- Downloaded to `/tmp/ttskill-base.zip`
- Extracted to `/tmp/ttskill-extract/ttskill-base-linux-x64-0.1.2/`
- Ran `install.sh` → installed to `~/.local/share/ttfund/ttskill-base/ttskill-base-linux-x64-0.1.2/`
- Symlink: `~/.local/bin/ttskill` → `.../bin/ttskill`

### 2. Agent entry bootstrap
```bash
ttskill agent-entry bootstrap --env prod
```
Output written to:
- `~/.hermes/skills/ttfund-skill.md` (Hermes)
- `/root/ZacharyXue.github.io/AGENTS.md` appended section (OpenCode)

### 3. Business skill sync
- List API returned 33 packages
- Batch installed via Python subprocess calling `ttskill skill install`
- All 33 installed successfully

### 4. Route refresh
```bash
ttskill agent-entry refresh --env prod
```
Result: 7 groups, 33 installed skills.

### 5. Login attempt (BLOCKED)
```bash
ttskill login --env prod
→ "Linux 桌面安全凭证存储需要 secret-tool，请安装 libsecret-tools"
```
`sudo apt-get install -y libsecret-tools` requires user password.
User needs to run this manually, then `ttskill login --env prod`.

## Dual-agent setup
User wanted both Hermes and OpenCode to access ttskill:
- CLI binary in shared PATH (`~/.local/bin/`)
- Hermes: skill entry in `~/.hermes/skills/`
- OpenCode: ttskill section appended to blog repo's `AGENTS.md`
