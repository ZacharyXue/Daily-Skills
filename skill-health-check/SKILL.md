---
name: skill-health-check
description: 定期检查 /root/zach-skills 里自建 skill 的健康度——发现重叠去重、找出与用户画像脱节的盲区并按画像补维度、检查引用/脚本完整性、维护 README 索引。触发时机：用户说「看看 skill 有没有重叠/优化一下 skill」「skill 健康度检查」「按我的画像补 skill 维度」。
version: 1.0.0
tags: [hermes, skill, meta, code-review, zach-skills]
---

# Skill 健康度检查 + 按用户画像补维度

用一套固定流程审计自建 skill 集（/root/zach-skills），目标是：**去重叠、补盲区、保持与用户真实画像一致**。检查完把改动 commit 进 Daily-Skills 仓库。

## 触发场景

- 用户说「看看 skill 有没有重叠/要不要优化」
- 用户主动说往 skill 里补某个关注的维度
- 定期自查（可配 cron）：skill 数量膨胀、出现重复主题、或用户偏好变了

## 检查一：重叠去重

同一领域出现多个 skill 覆盖相同主流程时，合并为一个主干 skill。

**判断信号**：
- 两个 skill 的 description/触发场景高度重叠
- 都做同一件事（如「PDF财报→商业模式→财务→同行对比」被 3 个 skill 重复写）
- SKILL.md 里已经自己吐槽「and astro-blog both cover the same repo」

**合并步骤**：
1. 选定**最全/超集**那个作主干（比较各自含 Phase/步骤数量）
2. 把其他 skill 的**独有 references/scripts** 复制进主干：`cp -n <old>/references/* <main>/references/`
3. 干主 SKILL.md 补 `触发场景`、`流水线总览`、参考资料索引
4. `skill_manage(action='delete', absorbed_into='<main>')` 删冗余
5. 更新主干里任何「重叠 skill」注释

**验证**：`skills_list` 数数量（应减 N）、被删的消失、主干正常加载。

## 检查二：按用户画像补盲区

**画像先行**。先复盘用户在目标域的最近会话/消息，提炼真实偏好，再对照现有 skill 找缺失维度。

**提炼画像的方法**：
- 拉最近相关会话（session_search），归类用户反复问的问题/反复查的维度
- 用户自述的偏好（如「喜欢低PE低PB ROE回升分红好低杠杆」「看生意模式/财务安全/企业道德/行业格局」）
- 从用户分析的标的里反推特征

**对照找盲区**：把画像拆成「硬条件」+「定性维度」，逐个看现有 skill 是否覆盖；没覆盖的就是要补的盲区。

**补维度落地**：在主干 skill SKILL.md 加独立 Phase/章节，含：
- 该维度的 grep 锚点表（A股特有的关键词）
- 危险信号清单（🔴/🟡/🟢 分级）
- 排查要点 + 产出模板

## 检查三：引用/脚本/索引完整性

- `references/`、`scripts/` 里的文件都被 SKILL.md 索引进（grep 验证）
- 没有悬空引用（SKILL.md 提到但文件不存在）
- README.md 索引表与目录实际一致（新增/删除/合并都同步）
- 全局环境信息不泄漏进知识型 skill（应放记忆）

## 检查四：与用户画像的持久对齐

- 用户偏好变化 → 更新对应 skill；技能读取相关记忆条目的同步更新
- skill 是「流程/知识」，用户画像/环境事实放记忆

## 输出与提交

完成所有改动后：
1. `skills_list` 验证加载
2. `cd /root/zach-skills && git add -A && git commit -m "..."`（只 commit 不 push）
3. 若记忆里 skill 收敛描述过时，用 memory 更新

## 陷阱

- 合并时用 `cp -n` 避免覆盖同名文件；git 会把 rename 识别为 100% 相似（零丢失）
- 删 skill 前务必先 cp 走它独有的 references/scripts，防止数据丢失
- 别只删不复用——每个被删的独有内容都要有归属
- 用户画像变化是补维度的**主要触发**，别只看 skill 内部重叠
- README 索引是事实来源，忘了更新下次审计会缺条目