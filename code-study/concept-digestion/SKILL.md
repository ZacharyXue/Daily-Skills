---
name: concept-digestion
description: Use when 用户发来外部AI对话/长文让消化讲透或引用了飞书附件。取素材→认知契约(Step0预测门,先他出后我整)→反馈闭环纠偏→开放问题收尾；产出三段式(原始输出/整理稿/补了什么)。
version: 1.1.0
tags: [learning, digestion, feedback-loop, concept]
---

# 概念素材消化（外部 AI 对话 / 长文）

子皓定向学习时会把自己和豆包/元宝的对话导出 .txt 发到飞书群，要求 Hermes 帮忙「消化」——即把别人（AI）讲的内容讲透、纠正他的理解偏差、沉淀成他自己的认知。区别于 code-study（源码调用链深读）和 zach-llm-wiki（知识落库）。

## 触发条件

- 用户发来 `[Attachment: 和XXX的对话_日期.txt]` 并说「帮我消化一下知识」
- 用户复述一段自己的理解（「所以我理解是…」），要求确认/纠正
- 用户贴来长文/截图让讲透某个概念
- 用户说「帮我总结一下这部分内容」「看看这个」但**未指明素材**：不要猜 /tmp 最新文件或全局文件——先查**所在群**的消息记录定位所指（2026-09-15 教训：猜 /tmp 的 ref_agent_patterns.md 总结跑偏，被纠正「分叉群了…你看看这个群飞书消息记录」，真正目标是群里早前发的图片）
- 用户在学习群里说「回顾一下这个群学了哪些知识点 / 帮我巩固一下 / 后续提问我 / 需要反复看的整理成博客」——多轮教学的阶段复盘（见下节「阶段回顾闭环」）

## 第零步：定位「这部分内容」的所指（当用户未指明素材时）

用户说「总结这部分/看看这个」而上下文不明确时，**先查当前所在群的飞书消息记录**，确认「这部分」的真实指向（可能是早前发的图/文/附件），再动手：

```bash
# 1. 找当前群（会话标题常见，同名群可能多个，用 query 精确匹配）
lark-cli im +chat-search --query "<群名关键词>" --as user
# 2. 拉全量消息定位目标（含 system 消息建群时间、图片/file 消息）
lark-cli im +chat-messages-list --chat-id <oc_xxx> --order asc --page-all --as user \
  | python3 -c "import json,sys; d=json.load(sys.stdin); [print(m['create_time'], m.get('msg_type'), m.get('content','')[:100]) for m in d['data']['messages']]"
```

确认目标类型后：图片 → image-text-extraction 取图流程；txt/file → 下面第一步；纯文本 → 直接读消息 content。

**⚠️ user token 会过期（拉群消息必须用 user 身份，2026-10-01 实测）**：出现 `refresh_token expired` / `need_user_authorization` 时走两步设备码授权（跨轮次）：

```bash
# 第一步：拿 device_code + verification_url（--no-wait 立即返回）
lark-cli auth login --scope "im:message.group_msg:get_as_user im:message.p2p_msg:get_as_user im:chat:read" --no-wait --json
# 生成二维码：URL 是【位置参数】——`auth qrcode --url X` 会失败（无此 flag）
lark-cli auth qrcode "<verification_url>" --output lark_auth.png
# 把 URL 先、二维码后贴给用户并结束本轮（二维码必须真正贴图，只生成文件不算）
# 用户回来说「已授权」后：
lark-cli auth login --device-code "<device_code>" && lark-cli auth status   # user: ready 即成功
```

不要缓存 device_code/URL 复用（下次要重新走一遍拿新的）。

## 第一步：取素材（飞书附件）

用户引用的 Attachment **不在本地**，在飞书服务端，必须先下载（已验证工作流，2026-09）：

1. **不要**用 `+messages-search --query <文件名>` 找——搜不到 file 消息（内容只有 `name=` 属性，不参与索引）。
2. 列最近消息定位：`lark-cli im +chat-messages-list --chat-id <oc_xxx> --order desc --page-limit 50 --as user`
   - 群号从 thread 的 `chat_id` 字段拿；用户引用消息可能在主聊天而非 thread 里。
3. 找 `msg_type: "file"` 那条，从 content 解析：`<file key="file_v3_xxx" name="xxx.txt"/>`。
4. 下载：`cd /tmp && lark-cli im +messages-resources-download --message-id <om_xxx> --file-key <file_v3_xxx> --type file --output <name> --as user`（路径必须相对 cwd）。
5. 验证 `data.saved_path` + `size_bytes`，然后 read_file 读全文。

## 素材是「公众号长截图 + 原文链接」（2026-10-01 实测）

用户会说「我刚在群里发了一张长图，再往上是原文链接，你读一下概括，然后我会提问」。五个要点：

1. **定位**：`+chat-messages-list --chat-id <oc> --order desc --page-limit 30` 一屏就同时看到今天的 image 消息 + 早几天发的原文 text 链接（本次：图 22:11、链接 09-27）。图消息 content 形如 `[Image: img_v3_xxx]`，`img_v3_xxx` 就是 file_key：
   ```bash
   cd /tmp && lark-cli im +messages-resources-download --message-id <om_xxx> --file-key <img_v3_xxx> --type image --output xx.png --as user
   ```
2. **原文优先，但不恋战**：公众号 mp 链接常被风控（空壳页「环境异常/去验证」），Wayback 无快照、Jina 未配 key 时→**立即转「切片喂 vision」逐屏读图**（配方见 image-text-extraction；1812×74484 长图 → 25 屏）；**别在本机跑 OCR**（2 核机器会拖死 Hermes，已被用户 kill 过）。
3. **转录落盘**：逐屏读图时顺手写 `/tmp/<主题>_transcript.md`（AI 摘要 + 各章表格 + 图转 ASCII）——用户随后会**连续多轮提问**，手上有原文才答得准；单纯靠记忆概括会在追问时崩。
4. **概括结构**（群里不渲染 mermaid → ASCII 图 + 表格）：① 素材确认（谁写的/评什么/原文链接状态）→ ② 痛点 → ③ 主框架表（如「五层/四步/三阶段」各回答什么）→ ④ 核心机制（保留原文给的实证数字，如位置偏差 96%→50%）→ ⑤ 一句话记忆。图多、少长段。
5. **用户说「然后我会提问」时：概括完交还控制权，不要抢着出验证题**（区别于下面默认的「开放式问题收尾」反馈闭环）——他要自己主导提问，硬出题等于打断他的节奏。

## 第二步：消化输出结构（反馈闭环 + 认知契约）

**认知契约（先你出、后我整，2026-10 新增）**——本 skill 的目标是"他理解"，不是"我有产出"：

1. **Step 0 预测门（在讲透之前）**：读完素材后**先别讲**，先让他用自己的话说三句：这篇材料在讲什么 / 他现在的理解 / 他觉得哪里最反直觉。**AI 只许追问，不许代答。**
   预测与他的原话**原样落盘**——落点要**持久**，不要用 `/tmp`（会话结束即失效，而预测的价值恰在跨会话复盘）：
   - 学习/概念类 → 直接进 wiki 页的 `## 原始输出留档` 段，或 /root/wiki/queries/ 下的持久文件
   - 其他类（基金/个股/项目复盘） → 各自 skill 的私有数据目录（如 `zach-skills/<skill>/data/predictions/`，gitignore + 独立私有仓）
   - 写进 `/tmp` 的预测 = 下次会话找不到 → 无法做「预测误差」对照，predict-first 退化成走流程
2. **产出三段式**：`一、我的原始输出`（一字不改）→ `二、整理稿`（AI 补结构/衔接/术语）→ `三、本次补了什么`（列出 AI 加了哪些衔接句/小标题）。**硬边界：不生成他没说过的观点句。**
3. 面向他自己回看，所以"文风是否像他"不是目标，**"三个月后能不能一眼看懂"才是**——AI 补可读性是收益，不是污染。
4. 素材涉及对外发布时（博客对外篇）才单独收紧：观点句与行文逻辑由本人写，AI 只做事实采集与校对。

读完全文后按此结构输出（禁止单向灌输、禁止「懂了吗」）：

1. **✅ 对的部分**：先肯定用户理解中正确的内容，列清楚
2. **🔧 纠偏**：对偏差逐条给出「原话 → 为什么不对/不完整 → 更准的表述」。
   - 优先抓**概念分界线**（如：不是「程序读 vs 人读」，而是「能不能被 selector 筛选」）
   - 用户概括太笼统时拆开讲（如 Helm 同时用 label 和 annotation，各管一摊）
3. **图解**：2 条以上链路的场景必须画图（mermaid 为主；用户偏好图内文字勿重叠）
4. **一句话记住**：给一个可背诵的心智模型（如「Label=身份证，Annotation=快递单备注——程序读，不参与认领」）。⚠️ 比喻陷阱：用户会把 Annotation 概括成「便利贴」（人看的便签），纠偏后仍会滑回（2026-09-13 连续两次）——便利贴带偏成「给人看备注」；必须主动换比喻并点破：**主力读者是外部程序**（CCM/ingress-nginx/cert-manager/Helm/kubectl 自身 last-applied）
5. **开放式问题收尾**：给 1-2 个判断题 + 1 个「为什么」深问题，逼用户用自己的话复述/推理，等他的回答再纠正（反馈闭环）
6. **衔接落库（可选）**：消化讲透后用户可能直接说「帮我总结到 llm wiki」——走 zach-llm-wiki ingest（查 index/SCHEMA → 建/更新概念页 → index+log → commit 不 push）。用户**跳过验证题直接要求落库**时不卡流程：落库并把验证题/自测题写进 wiki 页（`## 自测` 段落），闭环以可复习形式保留
   - **同一会话既落库又成文时（2026-10-02 实测）**：顺序=**先落 wiki 再成文**（成文要引用原文措辞，wiki 先行可锁定认知）。落库时对相邻已有页做**交叉链接 + 补小节**而非重复建页（本次 3 新页 + 2 更新：把「Judge 是代理指标」「harness 决定可交付性」分别并进两页旧页）；成文后把**博客 URL 回填进 wiki 页 `sources:` 与 log 条目**，wiki 页 `## 自测` 直接用本轮纠正点，log 里记下「本轮纠正点」3 条（复习时知道当时错在哪）。
   - 素材是**外部公众号长截图**时，wiki 页 `sources:` 同时挂**原文 URL + 自家博客 URL**，并在页内注明「原文站被风控、内容以长图为事实源」，避免日后误以为引用的是抓取到的原文全文。

## 阶段回顾闭环：多轮教学累积 → 出题巩固 → 落库/成文（2026-09-15 实测）

场景：学习群（如「计算机网络学习」）里已多轮讲过概念，用户说「回顾一下群里聊了什么、看看学了哪些知识点，帮我巩固，之后提问我，必要的整理进 llm wiki，需要反复看的整理成博客」。

流水线（顺序照做）：

1. **拉群全量历史**（第零步命令 `--order asc --page-all`）+ 取回群里发过的图/附件 → 得到完整教学轨迹
2. **知识点清单表**：`# | 知识点 | 核心一句话 | 状态`，逐条对应群里的轮次。这张表是后续出题与落库的骨架
3. **一轮批量出题**：约 5 题覆盖清单**全部**知识点，题面标号 ↔ 清单编号，一次抛给用户（他说「能答多少答多少」也接受）
   - 题干要**条件化 / 反推式**：「掩码从 /18 改成 /24 还能 ping 通网关吗」「打破哪个前提才会轰垮」——易蒙对的是非题没用
   - 用户能答出条件化版本（如「不一定，看网关是否落在新范围」）= 真懂；只答单一因素 = 需要补全（见下）
4. **逐条点评**：✅ 吸收到位 / ⚠️ 偏差，**先肯定对的部分**再补缺口。两种典型偏差形态：
   - ① 机制方向颠倒：「环回不会到内核」→ 实为「内核干到底，只是不出物理网卡」
   - ② 只抓单因素：「别人不响应所以不轰垮」→ 补全「广播仍强制到货：靠缓存复用 + 小包 + 低频」
5. **落库**：只把确认吸收的写进 wiki（走 zach-llm-wiki ingest）；答错/未确认的点不硬建页，纠偏确认后再落
6. **成文**：反复看价值高的主线（如「出网全流程」）提炼成博客（走 zihao-blog，多图少长段）

**实测证据法（讲网络/系统类概念的默认姿势）**：

- 讲之前先跑用户机器上的**只读**命令取真实证据，边讲边对证据：`ip addr` / `ip route`（注意 `proto dhcp`）/ `ip neigh` / `ss -lntp` / `/run/systemd/netif/leases/*` / `journalctl -u systemd-networkd` / `/etc/machine-id`
- 数值一律**工具算**（`ipaddress` / `hashlib`），别心算；外部事实查证（IANA PEN 43793 = systemd 这类）
- 证据写进 wiki 页与博客，未来 agent 或复习时可直接复用（本次网络 6 页都带用户机器真实输出）
- **自造对照实验 > 引用结论（2026-10-01 实测）**：讲校验/编码/协议这类可用代码复现的机制时，用 `execute_code` 现场跑实验当证据，比背结论有说服力得多。本次 CRC 三连：① **逐步演算**（模2除法逐位打印中间状态，用户卡在「模2」就是靠这个讲通的）② **统计实验**（20000 次随机翻转统计检出率，用数据证伪用户「多位错误查不出」的误解）③ **负例实验**（改数据重算校验 → 验证通过，直观证明「无密钥防不了篡改」）。实验输出直接进讲解稿与 wiki 页。

**媒介规则**：飞书群**不渲染** mermaid → 群里讲课用 ASCII 图 + 表格；长文成博客再用 mermaid（博客原生渲染，见 zihao-blog）。用户偏好「图多、少长段」（长段文字他自己说「记忆起来更麻烦」），一次讲一个机制、配一张图。

## 覆盖度盘点补缺（「看群消息，把还没落 wiki 的一起落」— 2026-10-01 实测）

区别于「阶段回顾闭环」：不是出题巩固，而是**审计已有素材的沉淀覆盖度**。用户会在一轮轮落库之后突然说「看群消息，把没落的一起落一下」。

1. **拉全量源**（含此前拉过的全部轮次）：`--order asc --page-all`，用 python 压成「#序号 [时间] 发送者 (类型) len=… | 前 100 字」目录再逐条读（长会话可达上百条，别整页贴 JSON）
2. **逐条扫「用户提问 → 知识点」**，与 `index.md` 比对（必要时 search_files 奲断是否已在他页覆盖）
3. **产出三列表给用户**：

   | 源里讲过 | wiki 现状 | 处理意向 |
   |---|---|---|
   | ARP 机制（含广播为何不焋垮 + ARP 风暴 + 无认证可欺骗） | 仅在 layer2-switching 提了「问谁」 | 🆕 独立成页 |

4. **只补真缺口**：已在他页覆盖的用**交叉链接 + 补写小节**收口（如「受限广播 vs 子网广播」进 DHCP 页、「绑定地址=目标 IP 过滤规则」进环回页），**不重复建页**；这是 wiki 单一事实来源铁律的直接应用
5. 落库 → 跑 `scripts/wiki_lint.py` → commit

本轮实测：163 条消息 → 3 个真缺口（`arp-mechanism` / `dns-resolution` / `user-kernel-network-path`）+ 3 处补丁，网络线从 7 页到 10 页。

## 落库账实核对（2026-10-01 实测踩坑，每次 ingest 必做）

学习群对话**跨天/跨周持续**（「计算机网络学习」群 9/19 → 9/27 → 10/1 分三批落库），落库时极易账实不符。三条硬规则：

1. **日期以 `date` 为准，不是会话起始日**：页面 frontmatter 的 `created`/`updated` 必须是落库**当天**真实日期。本次三批页面被误写成会话起始日 2026-09-15（实际 9/19、9/27、10/1），事后只能按 `git log --format="%h %ad %s"` 的 commit 时间逐页回改。**落库第一步先 `date`**；仅被修改的旧页只改 `updated`。
2. **总页数实点，禁止心算 +1**：
   ```bash
   find concepts entities queries -name "*.md" | wc -l   # 实际页面数
   grep -cE "^- \[\[" index.md                            # index 登记条目数
   ```
   两者相等、且与 `index.md` 头部声明的「总页数」一致才交付。本次声明 38 而实点 39。
3. **/root/wiki 是多会话共享仓**：写 `index.md` 前**重读**（patch 会警告 `modified by sibling subagent ... never read it`）；别的 session 可能在你两次 commit 之间落了新页（本次「实际利率与黄金的定价锚」就插在两次 commit 中间）→ 页数/摘要重新推导，不要沿用上次记忆的数字。

**发现账实不符就修 + 留痕**：同步修正 frontmatter 日期、`index.md` 总页数与「最后更新」、`log.md` 里错误的日期标记，并追加一条 `## [<真实日期>] fix | 日期与页数勘误` 记录改了什么、依据什么。log 虽 append-only，但**错误标记本身可以改**，前提是留下勘误条目——比让错误日期永久留在知识库好。

**收尾自检（30 秒）**：`date` ✓ → 页数 = 文件数 = index 条目数 ✓ → log 日期与今天一致 ✓ → `git status --short` 无杂散文件 ✓ → `python3 scripts/wiki_lint.py`（断链/index 完整性/frontmatter/页数一致性 一次判绿，exit 1 = 有问题）→ commit（不 push，push 由子皓决定）

范例与产出清单见 `references/group-learning-consolidation.md`。

## 参考

- `scripts/wiki_lint.py` — wiki 落库自检脚本（断链 / index 完整性 / frontmatter+出链 / 页数一致性），`python3 scripts/wiki_lint.py [wiki_root]`，可直接跑
- `references/k8s-label-annotation.md` — K8s Label vs Annotation 消化范例（完整纠偏结构 + mermaid 图），可当模板
