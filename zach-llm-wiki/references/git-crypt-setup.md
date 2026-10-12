# git-crypt 加密 + 恢复全流程（zach-wiki 实测）

## 初始化（一次性）
```bash
cd /root/wiki
git init -b main
git-crypt init            # 生成密钥，存 ~/.git-crypt/keys/default
```

`.gitattributes` 全量加密（只留自身明文）：
```
* filter=git-crypt diff=git-crypt
.gitattributes !filter !diff
```

## 密钥备份（三级冗余）
```bash
# 1. 导出明文密钥
cd /root/wiki && git-crypt export-key /tmp/wiki-gitcrypt-key

# 2. 用 SSH 公钥 age 加密（终极钥匙 = 用户天天在用的 id_ed25519）
mkdir -p ~/wiki-backup
age -R ~/.ssh/id_ed25519.pub -o ~/wiki-backup/wiki-gitcrypt-key.age /tmp/wiki-gitcrypt-key

# 3. 验证闭环：公钥加密 / 私钥解密 内容一致
age -d -i ~/.ssh/id_ed25519 ~/wiki-backup/wiki-gitcrypt-key.age > /tmp/verify
cmp /tmp/wiki-gitcrypt-key /tmp/verify && echo OK

# 4. 异地备份：打包恢复包发用户（微信 MEDIA 或 /tmp 路径）
mkdir -p /tmp/wiki-recovery
git-crypt export-key /tmp/wiki-recovery/wiki-gitcrypt-key
cp ~/.ssh/id_ed25519 /tmp/wiki-recovery/id_ed25519
# 写 RECOVERY.md 指导后：
tar czf /tmp/zach-wiki-recovery.tar.gz -C /tmp/wiki-recovery .
```

恢复包三件套：明文 git-crypt key（可直接 unlock）+ SSH 私钥 + RECOVERY.md。提醒用户：含 SSH 私钥，微信内别长期躺，下载后删聊天文件。

## 验证加密生效（每次 commit 后可查）
```bash
git show HEAD:concepts/investing/xxx.md | head -c 60   # 应为 GITCRYPT 密文
head -5 concepts/investing/xxx.md                      # 工作区明文
```

## 新机器恢复（用户 / 换机场景）
```bash
apt install git git-crypt age
mkdir -p ~/.ssh && cp id_ed25519 ~/.ssh/ && chmod 600 ~/.ssh/id_ed25519
ssh -T git@github.com                                   # 验证 Hi ZacharyXue!
git clone git@github.com:ZacharyXue/zach-wiki.git ~/wiki
cd ~/wiki && git-crypt unlock /tmp/wiki-gitcrypt-key    # 或 age -d 解备份后再 unlock
head -5 SCHEMA.md                                       # 明文即成功
```

## 关键认知
- git-crypt 无口令概念：密钥是随机生成的 256 位文件，用户零记忆负担；风险只在「密钥文件丢失」
- 密钥丢失 = 云端密文永久无法解密（数据等效丢失）→ 必须 ≥2 处备份
- 用用户现有的 SSH 私钥做终极恢复钥匙 = 零新增密钥管理,人不会丢自己在天天用的东西
- GitHub 私有仓库本身是「围墙」,git-crypt 是「保险柜」:防账号被盗 / 误转公开 / 平台侧明文

---

## 把已有明文历史的仓库改造成加密仓库（2026-10-13 实测）

场景：`career-data` / `social-data` 原本是明文历史的独立仓，要用**同一把 wiki 密钥**加密后备份到 `zach-wiki` 的其他分支。

### ❌ 不要用 filter-branch 重写历史
`git filter-branch --tree-filter '...写 .gitattributes...'` **会漏加密**：git 会复用 index 里已有的 blob，部分历史版本不会重新过 filter。
实测：174 个 blob 只加密了 70 个，**104 个仍是明文**。

### ✅ 逐提交重建（可靠做法）

```bash
# 0. 备份 + 保底分支
tar czf /root/backup-$(date +%s).tar.gz -C /root/zach-skills career-data
git branch -f backup-orig-history HEAD

# 1. 复用同一把 key（不要 init 出新的）
git-crypt unlock /path/to/wiki-gitcrypt-key

# 2. 收集原历史（旧→新）：sha|author|email|date|subject
git log --reverse --format='%H|%an|%ae|%aI|%s' master

# 3. 切 orphan 分支，逐个提交重建
git checkout --orphan encrypted-history
git rm -r --cached . -q
#   对每个 sha 循环：
#     git read-tree --reset -u $sha          # 检出该版本到工作区+index
#     git rm -r --cached . -q                # ★ 清空 index，强制后续 add 重新过 filter
#     printf '* filter=git-crypt diff=git-crypt\n.gitattributes !filter !diff\n' > .gitattributes
#     git add -A                             # 走 clean filter → 加密
#     git commit --allow-empty -q -m "$msg" --author="$an <$ae>" --date="$ad"

# 4. 验证内容一致后，让 master 指向新历史
git checkout -f encrypted-history
git branch -f master encrypted-history
git push origin master:career-data
```

耗时参考：56 个提交约 12 秒。

### ⚠️ 清理明文历史：光删分支没用

`filter-branch` 会留下 **`refs/original/refs/heads/master`** 备份引用 —— 它让旧（明文）对象**仍然可达**，`git gc` 清不掉。
实测：删掉保底分支后，对象库里仍有 **76 个明文 blob** 可达。

彻底清理三步：

```bash
git for-each-ref --format='%(refname)' refs/original/ | xargs -n1 git update-ref -d
git reflog expire --expire=now --expire-unreachable=now --all
git gc --prune=now --quiet
```
实测对象数 607 → 409，明文 blob 归零。

### 验证清单

- [ ] 新历史与原历史的工作区内容一致（逐文件 md5 比对）
- [ ] 对象库全量扫描：`git cat-file --batch-all-objects --batch-check='%(objectname) %(objecttype)'`，逐个 blob 检查前缀是否 `\0GITCRYPT\0`
- [ ] 只允许 `.gitattributes` / `README.md` 明文；**tree/commit 对象本就不加密，别误判为泄露**
- [ ] 远端验证：不带 key 克隆，读出来必须是密文

## 一个仓库多分支备份多个数据集

`zach-wiki` 用三个分支存三类数据：`main`（wiki）/ `career-data`（职业）/ `social-data`（社交），**共用同一把密钥**。

- 各数据目录仍是**独立 git 仓**（各自有 .git 历史），只是 remote 都指向同一个仓库
- 推送：`git push origin master:career-data`（本地分支名 → 远端目标分支）
- 设置 upstream 后可直接 `git push`：`git branch --set-upstream-to=origin/career-data master`
- 每个分支都放一份明文 `README.md`（加密/解密说明），`.gitattributes` 里加 `README.md !filter !diff`
- ⚠️ **密钥保护范围扩大 = 备份重要性提升**：一把 key 丢了，三份数据全部无法解密
