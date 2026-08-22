# Markdown-Resume 隐私架构

## 问题

简历存储在 GitHub 公开仓库中（`ZacharyXue/Markdown-Resume`），`Resume.md` 包含手机号、邮箱、真实工作经历等敏感信息，任何人可见。

## 方案：公开/私有分离

```
公开仓库 github.com/ZacharyXue/Markdown-Resume
├── Resume.example.md        ← 脱敏模板（张三，占位数据）
├── resume.css               ← 样式（公开）
├── assets/                  ← SVG 图标（公开）
├── scripts/generate_resume.py  ← 构建脚本（公开）
├── dist/                    ← gitignored（本地生成产物）
└── .gitignore               ← 排除 Resume.md, dist/

私有本地 ~/.local/resume/
├── Resume.md                ← 真实简历（不公开）
└── .git/                    ← 独立 git 管理版本历史
```

## 关键决策

1. **公开仓库只放模板 + 代码**，不含任何真实个人信息
2. **真实简历本地 git 管理**：`~/.local/resume/` 独立仓库，完整版本历史
3. **脚本自动路由**：`generate_resume.py` 检查 `~/.local/resume/Resume.md` → fallback 到项目内 `Resume.md`
4. **构建产物隔离**：HTML/PDF 输出到 `dist/`，gitignored

## generate_resume.py 关键逻辑

```python
RESUME_PATH = os.environ.get("RESUME_PATH")
if RESUME_PATH:
    RESUME_MD = Path(RESUME_PATH)
else:
    local_resume = Path.home() / ".local" / "resume" / "Resume.md"
    if local_resume.exists():
        RESUME_MD = local_resume
    else:
        RESUME_MD = PROJECT_DIR / "Resume.md"  # fallback to example
```

## 博客端集成

博客项目页 `src/content/projects/markdown-resume.md` 指向 GitHub 仓库，**不嵌入简历内容**。描述中加上：

```markdown
> 📄 完整简历内容请查看 GitHub 仓库。
```

## 设置流程（新机器）

```bash
# 1. 恢复真实简历
mkdir -p ~/.local/resume
cd ~/.local/resume
# 从私有备份恢复 Resume.md
git init && git add Resume.md && git commit -m "init"

# 2. 克隆公开仓库
git clone git@github.com:ZacharyXue/Markdown-Resume.git
cd Markdown-Resume

# 3. 生成
python scripts/generate_resume.py
# → dist/Resume.html  + dist/Resume.md
```
