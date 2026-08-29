# Zach Skills（重要自建技能库）

薛子皓的重要 Hermes skill 集。**只收录关键、长期可复用的自建 skill**（不是所有创建的 skill 都放这里）。所有 skill 遵循 Hermes skill 规范（YAML frontmatter + Markdown）。

> 记录原则：创建**重要/关键**的 skill 时才放入本目录并登记到下方索引。普通/一次性 skill 直接建在 `~/.hermes/skills/` 下，不在此记录。

## 挂载方式

通过 Hermes 配置 `skills.external_dirs: /root/zach-skills` 挂载（external dir 模式，`skill_manage` 就地读写本仓库文件），不需要软链。若外部仓库不可用，可单独软链某个 skill：

```bash
git clone git@github.com:ZacharyXue/Daily-Skills.git zach-skills
# 或只取单个 skill
ln -sfn $(pwd)/<skill-name> ~/.hermes/skills/<skill-name>
```

## 本目录 Skill 索引

| Skill | 说明 | 触发场景 |
|-------|------|----------|
| [career-coach](career-coach/) | 职业成长教练：复盘工作/学习、判断价值、深挖技术、对齐业界、规划路径、沉淀简历 | 晚间复盘、职业困惑、学习路径规划 |
| [code-study](code-study/) | 问题驱动源码阅读系统：从用户可见行为出发追踪调用链，产出排查笔记推送飞书群 | 每日 cron 源码阅读、搞懂 bug 根因 |
| [skill-creation-guide](skill-creation-guide/) | 创建/管理重要自建 skill 的完整流程：规范、目录结构、挂载、README 维护 | 新建重要 skill、维护本仓库 |
| [skill-health-check](skill-health-check/) | Skill 健康度检查：发现重叠去重、按用户画像补盲区维度、检查引用/脚本/索引完整性 | 「看看 skill 有没有重叠」「skill 健康度检查」「按我的画像补 skill」 |
| [ETF 技术温度](industry-monitor-dashboard/references/instances/etf/README.md) | ETF 红利+行业/主题看板：5年估值分位+技术面+实时行情，双视角信号，HTML 落博客 public/exports/，手动触发更新（实例并入母纲，无独立skill） | 「更新ETF看板」「看红利该不该买/加仓」「改看板标的池」 |
| [stock-analysis](stock-analysis/) | 股票基本面深度分析：PDF 财报提取→商业模式→财务三表→利润构成→风险排查→企业道德/治理→同行对比→估值→芒格评估 | 分析个股、看商业模式/财务/同行 |
| [investment-mindset](investment-mindset/) | 投资/人生决策思维模型库：芒格(25种心理倾向/多元思维模型/能力圈/逆向)、巴菲特(价值投资四基石/护城河/安全边际/致股东信进阶概念)、李录(价值投资三基石/ROIC/文明演进/20年检验·防价值陷阱)、段永平(本分/平常心/不为清单/买股票就是买公司)、孙宇晨(另类高风险视角,警示) | 从大佬思维多角度分析投资/人生决策、避免单一视角偏颇、风险体检、四大师对撞交叉验证 |
| [whale-holdings](whale-holdings/) | 大佬持仓跟踪：SEC 13F 机构持仓披露，巴菲特/李录/Burry 等买什么、加仓、清仓 | 说「看下 XX 的持仓」「13F」 |
| [industry-monitor-dashboard](industry-monitor-dashboard/) | **看板综合母纲**：行业+龙头/ETF 监测看板的通用方法论（注释驱动指标元数据、免费源取数、自包含HTML、财报提取）；水泥/ETF 作为**实例**并入 references/instances/，不单独成 skill | 「做XX监测看板」「更新水泥/ETF看板」「看水泥/红利现状」 |
| [dashboard-style](dashboard-style/) | **看板风格模板+数据规范**：自包含HTML骨架(details折叠/多线SVG/表格/徽章)、数据走 data-source-router、看板索引(dashboards-index.md) | 「做新看板」「复用看板模板」「看有哪些看板」 |
| [data-source-router](data-source-router/) | **统一数据源层**：数据源地图 + SQLite缓存 + Tier路由 + 合规红线。其他 skill 及未来 skill 一律通过本层取数，杜绝重复探索/拿错数据/烧token。覆盖 A股/港股/美股行情与K线(腾讯)、A股财报(东财datacenter)、美股财报(SEC)、宏观(统计局)、GitHub 仓库/Issues/PR/Release/搜索/健康度(REST) | 任何需要拉金融或 IT 数据的任务 |
| [zacharyxue-blog](zacharyxue-blog/) | 维护 ZacharyXue.github.io Astro 博客：写作偏好（图标多文字少/先提纲）、技术细节、部署 | 写博客、修渲染、发文章 |
| [ttskill-headless](ttskill-headless/) | 无桌面服务器上装天天基金 ttskill CLI 并远程扫码登录 | ECS 装 ttskill、Secret Service 报错 |

## 仓库结构

```
zach-skills/
├── README.md            ← 本文件：索引 + 挂载说明
├── docs/
│   └── used-skills.md   ← 使用中的重要外部/开源 skill 记录（天天基金、微信读书等）
└── <skill-name>/        ← 每个重要自建 skill 一个目录（SKILL.md + references/ + scripts/）
```

## 开发规范

- 每个自建 skill 必须有：`name`（小写连字符）、`description`（含触发时机）、`version`
- 本仓库走 external_dirs 挂载，`skill_manage` 就地改仓库文件（不做软链）
- 修改自建 skill 直接改仓库文件，改完 `git add + commit`
- 代码只 commit 不 push，推送由用户自行决定
- 新增/删除/合并本目录 skill 必须同步更新本 README 索引表

## 相关

- Hermes 官方文档：https://hermes-agent.nousresearch.com/docs