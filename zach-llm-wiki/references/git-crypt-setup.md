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
