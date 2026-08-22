# 微信读书 Agent API 参考

## 来源

仓库：`Tencent/WeChatReading`（GitHub），版本 `1.0.4`

博客仓库 `skills-lock.json` 中引用，首次使用需 clone：
```bash
git clone --depth 1 https://github.com/Tencent/WeChatReading.git /tmp/WeChatReading
```

## API Key

位置：`~/.bashrc`
```bash
export WEREAD_API_KEY='wrk-TNSMscD2SIm1OPCXzjqYpQAA'
```

## 统一入口

```
POST https://i.weread.qq.com/api/agent/gateway
Authorization: Bearer $WEREAD_API_KEY
Content-Type: application/json
```

每次请求必须带 `"skill_version": "1.0.4"`。回包中如有 `upgrade_info` 字段，暂停操作并按指引升级。

## 读书笔记生成所需接口

### 1. `/store/search` — 搜索书籍获取 bookId

```json
{"api_name":"/store/search","keyword":"关键对话","count":5,"skill_version":"1.0.4"}
```
返回 `results[].books[].bookInfo.bookId`

### 2. `/book/getprogress` — 阅读进度

```json
{"api_name":"/book/getprogress","bookId":"3300052436","skill_version":"1.0.4"}
```
关键字段：`book.progress`（0-100整数），`book.finishTime`，`book.recordReadingTime`（秒）

### 3. `/book/info` — 书籍信息

```json
{"api_name":"/book/info","bookId":"3300052436","skill_version":"1.0.4"}
```
关键字段：title, author, translator, publisher, category, newRating, newRatingCount

### 4. `/book/bookmarklist` — 个人划线

```json
{"api_name":"/book/bookmarklist","bookId":"3300052436","skill_version":"1.0.4"}
```
返回 `updated[]`（划线数组，含 markText、chapterUid）和 `chapters[]`（章节映射）

### 5. `/review/list/mine` — 个人想法/点评

```json
{"api_name":"/review/list/mine","bookid":"3300052436","count":100,"skill_version":"1.0.4"}
```
返回 `reviews[].review`（含 content、abstract、chapterName、chapterUid）

### 6. `/book/chapterinfo` — 章节目录

```json
{"api_name":"/book/chapterinfo","bookId":"3300052436","skill_version":"1.0.4"}
```
返回 `chapters[]`（含 chapterUid、title、level、chapterIdx）

## 数据组装逻辑

1. 用 `chapters` 建立 `chapterUid → {title, level}` 映射
2. 将 `bookmarklist` 的划线按 `chapterUid` 分组
3. 将 `review/list/mine` 的想法按 `chapterUid` 分组
4. 对每条想法，通过 `abstract` 字段匹配对应划线原文
5. 按章节 number 排序输出

## 输出格式

```markdown
> 划线原文

💭 *个人想法*

> 划线原文（无匹配想法则不加 💭）
```

## 注意事项

- 所有时间戳（createTime、finishTime、updateTime）展示时转为 YYYY-MM-DD
- 阅读时长字段单位为秒，展示时转为"X小时Y分钟"
- 业务参数必须平铺在 body 顶层，不要包在 `params` 里
- `/review/list/mine` 的参数是 `bookid`（小写），不是 `bookId`
- `progress` 100 且有 `finishTime` 才表示读完
- `reviewCount` 已包含个人点评，计算总笔记数时不要重复加
- 笔记总数 = `reviewCount + noteCount + bookmarkCount`

## 关键陷阱

### 禁止合并/压缩划线

生成读书笔记时，**每条划线必须是独立的 `>` 引用块**。41 条划线 = 41 个 `>` 块。
绝对不要做的事情：
- ❌ 将相似划线合并为一条
- ❌ 将划线整理成结构化表格或要点列表
- ❌ 用自己的话总结划线内容
- ❌ 觉得某个章节划线太多就"精简"

用户会逐章逐条审阅，自己决定保留哪些。合并 = 数据丢失。如果文件被意外压缩，
从 `/tmp/wr_*.json` 重新生成。
