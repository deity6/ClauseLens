# 全量审查报告 · 2026-11-07

> 审查代理 Reviewer。只读审查；唯一写入的是本报告，以及为了复跑而被脚本重写的产物（见 §3，已核对与原文件逐字节一致，模型文件已还原为备份）。
> 后端在 8799 端口临时启动，审查结束时已关闭（`curl` 确认端口不再响应）。
> 依据：AGENTS.md §6/§7、docs/design/contract.md、frontend.md、frontend-impl.md。

## 总评：**有条件通过**

- 本机自用 / 演示：可以用。训练与评测**按站点划分，未发现 test 泄漏**；中英文报告数字**复跑逐字节一致**；前端等待态确实由 SSE 事件驱动；有免责声明。
- **对外部署前必须先修严重问题 S1、S2**（SSRF 的 DNS 重绑定、总超时失效）。
- **S3–S5 直接影响结论的可信度**（查 baidu.com 拿到的是别的产品的条款；模型单独命中时贴出负面标签，但证据并不支持），违反 AGENTS §5「宁可未发现也不乱贴负面标签」。

## 严重问题（必须修）

| # | 问题 | 证据 |
|---|---|---|
| S1 | **SSRF：DNS 重绑定 / 先检查后使用（TOCTOU）**。`_is_public_host` 先解析一次，`requests` 连接时再解析一次，两次解析可以拿到不同的 IP。攻击者可以用重绑定域名打到 127.0.0.1、169.254.169.254 等地址。精准模式下，如果内网响应 ≥600 字且「像条款」，正文会出现在 `result.texts` 里返回；否则是盲 SSRF（AWS IMDSv1 这类只要一个 GET 的接口照样能打到）。 | `backend/clauselens/net.py:60-69`（解析校验）与 `:115-119`（`sess.get(cur)` 重新解析）；`parse_query` 接受任意形似公网的域名（实测 `127.0.0.1.nip.io` 能通过解析，只是被第一次解析拦下，重绑定能绕开）。**可利用性**：服务只要对外开放就能被利用，本机自用风险低。修法：把校验过的 IP 钉死后再连接（自定义 HTTPAdapter / `socket.create_connection` 指定 IP，带上 Host/SNI），或者在连接建立后检查 `sock.getpeername()`。 |
| S2 | **单页总超时 20s 实际不生效**。`iter_content(65536)` 要攒满 64KB 或者读超时（10s）才返回一次，所以对方每 <10s 发 1 个字节就能一直占住线程；`DEADLINE=40` 只在两次抓取之间才检查。 | 实测：本地慢速服务器每秒发 1 字节，`net.fetch` **用了 60.0s** 才因对方断开而退出（`TOTAL_TIMEOUT=20`），抛出的还是没被捕获的 `ChunkedEncodingError`（不是 `FetchError`，会走到 api.py 的 `internal`）。`net.py:16-17,131-138`。**可利用性**：任何能部署网页的人都能让分析线程无限期挂住；限流是每 IP 10 次/分钟，多个 IP 就能耗尽线程。修法：设 `iter_content(chunk_size=较小)` + 用 socket 级 deadline，或单独线程计时后强制 `r.raw._fp.close()`；同时捕获 `requests.exceptions.ChunkedEncodingError`。 |
| S3 | **baidu.com 的分析对象搞错了产品**。registry 给 baidu.com 收录的是「百度地图开放平台 隐私合规文档」和「百度手机卫士用户服务协议」，命中 registry 后就不再翻首页。用户查「百度」，拿到的却是手机卫士和地图开放平台（面向开发者）的条款，例如 user-indemnifies 的第 3 条证据「开发者负责给予平台方全额赔偿」。 | SSE 结果 `documents`：`lbsyun.baidu.com/docs/pcsa?title=compliance/openprivacy`、`shoujiweishi.baidu.com/static/html/agreement.html`；`data/processed/registry.json["baidu.com"]`；`pipeline.py:143-152`（有快照就跳过首页）。PROGRESS.md 里原先实测的 `/duty → 隐私权保护声明` 这条路径被覆盖了。建议：registry 的条目要人工审核主站文档；子域产品不得冒充主域；结果页要显示文档来自哪个子域。 |
| S4 | **模型单独命中时，用不支持结论的证据贴出负面标签**。`fuse()` 允许模型在 p≥max(th,0.6) 时独立命中，但对句子长度、标题、导航文本没有任何过滤。 | bilibili `terms-change-no-notice`（坏，权重 8）的唯一证据是「我们可能使用您的信息向您的设备发送电子邮件、新闻或推送通知」，和改条款无关；而同一份文档结尾写的是「实质减少权利时……在修订生效前……通知您」，**极性正好相反**。reddit `tracks-across-sites`（坏）的三条证据是越南语、他加禄语的导航链接「Thông báo về cookie」「Paunawa ng Cookie」；`personalized-ads` 的证据是小标题「Third-Party Content, Advertisements, and Promotions」；`contact-dpo` 的证据是「If you have any questions about these Terms, please contact us.」。位置：`detect.py:145-146`。建议：模型独立命中时要求句长 ≥ N、排除纯标题和导航行、提高阈值；对负面标签，只有模型单独命中时降为「待确认」或不参与评分。 |
| S5 | **英文 `sole discretion` 被当成「解释权归平台」，还附带中国法律判断**。`final-interpretation`（坏，权重 7）的英文正则匹配 `sole discretion`，explain_zh 却写着「在中国这类表述通常属于无效格式条款」。只要英文站点出现 sole discretion 就会触发，github、reddit 都中了。 | `taxonomy.py:201-205`。reddit 证据「Reddit may … assign any of our rights … at its sole discretion」「overturn any action of a moderator … in its sole discretion」，都和「最终解释权」无关；github 证据「GitHub, in our sole discretion, will determine abuse … of the API」。另外 explain_zh 的「无效格式条款」是法律定性，和 §7「只写条款写明/未找到」冲突（见 §7）。 |

## 一般问题

1. **同一结果里混了多种语言的文档，却统一按一种语言处理**。`detect()` 只用前 200 句判断语言（`detect.py:158`），`check(jur, texts, zh)` 也只用一个 zh 标志（`pipeline.py:243-261`）。github 抓到了 en+zh 各两份同内容的文档（d2/d3 是中文），中文句子走的是英文正则和英文模型；而且中英文内容哈希不同，去不了重，`read_minutes=129`、`clauses=1486` 被重复计数。
2. **提取正文时混进了导航和语言切换菜单**（reddit d1 包含几十种语言的菜单项），是 S4 的诱因之一。`discover.py:376-401`。reddit 两份文档都不是隐私政策（registry 里的隐私链接没抓到），结果页也没有提示「缺少隐私政策」。
3. **中文规则的误报**：zhihu `ai-training` 的证据是「您不得利用……生成式人工智能……制作、发布虚假新闻」，这是禁止用户做的事，不是平台拿你的内容训练模型（`taxonomy.py:262` 第二条正则）。taobao `collects-beyond-service` 只因为出现了「包括但不限于」就判定「超出必要」，名称的断言比证据强。
4. **证据的质量**：同一个标签下混着无关的证据，例如 github cross-border 第 3 条「minimum age may be older」、bilibili liability 第 2 条「cookies … 向您提供相关广告」。reddit 有 15 个标签的证据句重复（同一句话在文档中出现了两次），抽取时没有按 quote 去重（`detect.py:177`）。
5. **反馈接口**：没有限流，`domain` 不校验（任意 ≤253 字符的字符串），没有每个 IP 只能投一票的约束，可以刷票；`feedback.jsonl` 无上限增长；`summary()` 每次请求都持锁读全文件，复杂度 O(n)（`api.py:83-116`）。JSON 序列化本身没有注入问题。
6. **资源**：取消或断开连接后，后端 worker 线程照样跑完抓取（`api.py:61-69`）；每次请求新建一个 `ThreadPoolExecutor(1)` 且不 shutdown（`pipeline.py:136`）；限流表 `_hits` 的 key 从不清理；`nocache=1` 是公开参数，任何人都能绕开缓存。
7. **SSRF 的次要项**：`::127.0.0.1`（IPv4 兼容地址）和 `64:ff9b::7f00:1`（NAT64）在 Python 3.14 下 `is_global=True`，会被放行（只在特定网络环境下有意义）；不限制端口（`https://example.com:22/x` 能通过解析），可以拿来探测公网主机端口。
8. **可复现性的缺口**：`site_eval.md` 生成于 01:21:57，`score_params.json` 生成于 01:21:05，但 `detect.py` 在 01:23:48、`clause_model_zh.pkl` 在 01:46:42 又改过，站点级数字未必对应当前代码。`calibrate_score.py:31-34` 缓存的 `site_hits_train.json` 在模型变化后不会失效，复跑时会悄悄沿用旧的命中结果。没有锁定版本的 requirements 文件（本机是 sklearn 1.9.0 / numpy 2.4.2 / fastapi 0.162.0）。`.gitignore` 没有排除 `data/processed`（326MB）和 `data/models`（39MB）。`eval_sites.py` 文件头写着 `calibrate|eval|all`，实际 `all` 不做标定（只剩 `calibrate-legacy`）。
9. **轻微的跨数据集重叠**：英文 test 中有 81/4154 句与 train 句完全相同（其中 34 句带标签；ToS;DR 的共享模板），英文脚本没有像中文脚本那样做去重。中文训练/dev 站点 `lofter.com`、`mi.com` 落在了 ToS;DR 站点评测的 test 划分里。lofter 是中文文档，会被中文模型处理，影响 443 站中的 1 站，可以忽略，但应当在报告里注明。
10. **中文规则对 dev 过拟合**：规则层 dev F1 0.772，test 0.453（`zh_eval_dev.md` / `zh_eval_test.md`）。这是允许的调参方式，但 README 只报了融合后的 0.59，应同时注明 dev 与 test 之间的差距。
11. **前端小 bug**：`TagWall.jsx:104` 只认 `model` 和 `tosdr`，所以 `rule+model` 被显示成「规则匹配」；`Waiting.jsx:44` 把端口写死成 8787（服务换端口后提示就不对了）。
12. **首个请求冷启动**：第一次调用要加载约 40MB 的 pkl，实测首次 detect 11.7s，之后 100 万字约 1.7s、300 万字约 5.1s。

## 建议

- 只有模型单独命中的负面标签，UI 上单独标为「程序推测，待确认」，不进 TL;DR；评分时降权。
- favicon 走 `google.com/s2/favicons` 会把用户查的域名透露给 Google，建议改成后端代理或自取 `/favicon.ico`（`pipeline.py:255`）。
- registry 的条目加一个 `verified` 字段，未审核的条目不跳过首页发现。
- 写 `requirements.txt`（锁版本），评测报告里记下生成时的代码和模型哈希，站点评测缓存以模型哈希作 key。
- 截图形态仍需人眼复核（本环境的 Read 读图返回 `[image omitted]`，我也没法看图，只做了 DOM 审计）。

---

## 清单逐条结论与证据

### 1. 正确性 —— 有条件（12 条抽样：正确 8 / 存疑 3 / 错误 1，另有非抽样错误见 S4/S5/一般 3）

方法：`curl -sN "http://127.0.0.1:8799/api/analyze?q=<site>&nocache=1"`，6 站并行跑。耗时 baidu 3.2s、taobao 3.1s、bilibili 3.0s、github 5.9s、zhihu 3.1s、reddit 11.5s（中文站都命中了 registry 快照，或者直链抓取很快）。每站用 `random.seed(20261107)` 随机抽 2 个标签。

| 站 | 标签 | 判定 | 依据 |
|---|---|---|---|
| baidu | minors-protection（好） | 正确 | 「如果您是未满14周岁的未成年人……在征得监护人同意的前提下……」；高亮区间偏了（「儿童个人信息保护声明》，并在征得监护人」），不影响结论。注意文档是地图开放平台的（S3）。 |
| baidu | user-indemnifies（坏，model） | 正确（第 3 条证据存疑） | 「违反…导致百度…损害…您自行承担…诉讼费、律师费」，支持结论；第 3 条「开发者负责给予平台方全额赔偿」说的对象是开发者。 |
| taobao | can-export-data（好，model） | 正确 | 「您可以通过以下方式复制您的信息」「查询后复制您的个人信息」。 |
| taobao | collects-sensitive（坏） | 正确 | 「证件号码等证件信息或面部识别信息……属于敏感个人信息」。 |
| bilibili | broad-liability-waiver（坏） | 存疑 | 第 1、3 条只是对「第三方使用信息、第三方 cookies」免责，和 explain「即使服务出错、数据丢失也可能不赔」相比被放大了；第 2 条「cookies…提供相关广告」无关。 |
| bilibili | gov-disclosure（中性，model） | 正确 | 「遵守法院命令或其他法律程序的规定；遵守相关政府机关的要求」（列表项，缺上下文，但意思对）。 |
| github | cross-border-transfer（中性） | 正确（第 3 条证据错） | 「GitHub stores and processes Personal Data in … the United States, and other countries」；第 3 条「minimum age may be older」无关。 |
| github | no-tracking（好） | 存疑 | 唯一证据是「如果浏览器发送 DNT，就不设置非必要 cookie」，这是有条件的承诺，泛化成「不追踪」说过头了；同一结果里还同时命中了 tracks-across-sites。 |
| zhihu | broad-content-license（坏） | 正确 | 「全世界范围免费的、永久性的、不可撤销的、非独家、可转让和可再授权的许可」，逐字支持。 |
| zhihu | minors-protection（好） | 正确 | 「我们如何处理未成年人的个人信息」章节 + 监护人联系条款。 |
| reddit | final-interpretation（坏，rule） | **错误** | 见 S5；而且两条证据完全相同（重复）。 |
| reddit | gov-disclosure（中性） | 存疑 | 三条证据都是导航链接「Guidelines for Law Enforcement」，没有任何一条写了「会向机关提供数据」。 |

额外核对：6 站一共 303 条标签证据和 46 条合规证据，`texts[doc][start:end]` 与 quote **全部对得上**（偏移正确）。

### 2. 泄漏 —— 通过（有两处轻微重叠，见一般 9）

- `split.json`：train 2257 / test 562，**交集 0**；22,497 条 point 都有 domain，全部落在划分内；每个 service 只对应一个 domain。`sentence_eval.json` 的 `leak_check_overlap_sites=0`。
- `train_model.py`：词表和分类器只在 train 上拟合（`:125-128`）；阈值在 train 内部按站点切出 20% 验证集选取（`:131-153`）。`vec_v = vec` 用的是全 train 词表，没碰 test。test 只用于最终评测（`:160`）。
- `train_model_zh.py`：断言训练/dev 域名与 test 无交集（`:63`）；剔除与训练句完全相同的句子、同一 sha1 文档的共享站点（alipan/baidu/v.qq 被剔除，400→330）；阈值只用 dev（`:88-100`）。我另外核对：zh 训练和 dev 的域名与 `zh_split.test` 交集为 0；`zh_gold.jsonl` 中 test 部分的文本集合与 `zh_gold_test.jsonl` 相同。
- `calibrate_score.py`：只读 `site_hits("train")`；缓存的 `site_hits_train.json` 共 1752 站，与 test **交集 0**；`score_params.fit.n_train_sites=1752`。
- `eval_sites.py`：`evaluate()` 只 load("test")。
- **中文正则是否照着 test 调出来**：脚本把 taxonomy 里所有中文正和否正则（含 NEG_ZH_COMMON）分别跑在 test 标注句、train+dev 标注句、dev 站点全文、test 站点全文上。
  - 只在 test 标注句里命中、train/dev 标注句里没命中的正则只有 2 条（data-minimization、terms-change-notice），而它们在 dev 站点全文里分别出现 8 次和 17 次，属于通用表述。
  - 抽出正则里所有 ≥4 个汉字的字面片段：**没有任何一个片段「dev 全文里没有、却出现在 test 里」**。特殊措辞（「宗教政策」88 次、「指一旦泄露」62 次、「协议签订地」60 次、「个性化的第三方推广」5 次、「无需因此承担」5 次）在 dev 全文里都常见，有的在 test 里根本没出现。
  - 结论：**没有发现照着 test 调规则的迹象**。限制：仓库没有任何 commit，无法从历史上核实调参过程。

### 3. 可复现 —— 中英句子级通过；站点级未复跑且可能过期

复跑前把 `eval/reports/*`、`data/models/*`、`labeled_sentences.jsonl`、`case_tag_map.json` 备份到临时目录，复跑后用 `cmp` 比较：

| 命令 | 结果 |
|---|---|
| `python scripts/train_model_zh.py` | `zh_model_eval.md/json` **逐字节一致**（fused P 0.646 / R 0.546 / F1 0.592） |
| `python scripts/eval_zh.py test` | `zh_eval_test.md/json` **逐字节一致** |
| `python scripts/train_model.py`（22.9s） | `sentence_eval.md/json`、`labeled_sentences.jsonl`、`case_tag_map.json` **逐字节一致**（fused P 0.773 / R 0.702 / F1 0.736） |

复跑后已用备份还原 `clause_model.pkl`、`clause_model_zh.pkl`、`score_params.json`（`cmp` 确认一致）。按要求没有复跑 calibrate/eval_sites，它们的时间戳问题见一般 8。README 里有复跑命令，但没有 requirements，「从空目录」开始还需要先跑 harvest（数据 800MB+ 的原始文件）。

### 4. 安全

| 项 | 结论 | 证据 |
|---|---|---|
| 内网 IP（直接输入） | 拦住了 | `localhost`、`127.0.0.1`、`[::1]`、`0x7f000001` 都被 `_DOMAIN_RE` 拒绝；`127.0.0.1.nip.io` 被 `_is_public_host` 拒绝 |
| 重定向 | 拦住了（每一跳都重新校验） | `net.py:111-130`，`allow_redirects=False` |
| IPv6 | 基本拦住了 | `::ffff:127.0.0.1`、`fe80::`、`fc00::`、`::1` 都是 `is_global=False`；`::127.0.0.1` 和 NAT64 例外（一般 7） |
| DNS 重绑定 | **没防住** | S1 |
| file:// 等其他 scheme | 拦住了 | `parse_query` 返回「只支持 http / https」；fetch 里也校验了 scheme |
| 超大响应 | 拦住了 | 超过 5MB 就 break（解压后计数），最多多读 64KB |
| 慢速响应 | **没防住** | S2，实测 60s |
| 输入校验 | 通过 | 长度 ≤2000，IDNA 编码 + 域名正则 |
| 限流 | 弱 | 每 IP 10 次/分钟，在内存里；没有清理；反向代理后面所有人共用一个 IP；反馈接口不限流 |
| 静态文件路径穿越 | 通过 | `--path-as-is` 实测 `/../../AGENTS.md`、`/..%2f..%2fAGENTS.md`、`/%2e%2e/…`、`/C:/Windows/win.ini`、反斜杠写法，全部返回 index.html；代码里有 `DIST in f.resolve().parents` 检查（`api.py:126`） |
| 反馈写入 | 无注入；体积上没有总量上限 | pydantic 限长（comment ≤200），`tag_id` 走白名单，`json.dumps` 写入；问题见一般 5 |
| load_snapshot | 通过 | `resolve()` 后检查父目录（`pipeline.py:45-46`）；ref 来自本地 registry，不来自用户输入；snapshots 目录目前不存在，实际只用内联快照（298 条） |
| XSS | 通过 | 前端没有 `dangerouslySetInnerHTML`；站名、证据都由 React 转义 |

### 5. 用户可读 —— 基本通过

- 36 个 name_zh 都很口语（「可以随时封你的号」「你要替平台赔偿」「打官司要去平台所在地」），没有术语堆砌。
- 负面标签的 explain_zh 大多说清了后果，例如「泄露后伤害更大」「你维权成本更高」「你需要承担平台的损失和律师费」。**只描述了行为、没说对你意味着什么的**：`collects-contacts-device`（只说可能读取哪些东西）、`personalized-ads`、`default-consent`、`ai-training`。建议各补半句后果。
- `tracks-across-sites` 里的「像素、SDK」对普通人仍是术语。
- 名称与证据强度不匹配：`collects-beyond-service` 是「包括但不限于」触发的；`indefinite-retention` 会被 PIPL 标准表述「实现目的所必需的最短时间」触发（`taxonomy.py:153`），把合规的标准写法判成坏标签有争议。
- `final-interpretation` 的 explain 含法律定性（S5 / §7）。

### 6. 前端 —— 通过

- **真实进度**：`stream.js:12-41` 只监听 stage/document/tag/result/error 五种事件；`useAnalysis.js` 的 reducer 只根据事件更新，轨道只进不退；`pace()` 只保证最小显示间隔，不凭空造事件（`stream.js:94-125`）。扫描线和文案轮播是装饰，但它们的开关跟随真实阶段（`Waiting.jsx:68`）。「已省下 N 分钟」由 document 事件累加。
- **prefers-reduced-motion**：`<MotionConfig reducedMotion="user">`（`App.jsx:55`）；纸张、飞行标签、文档卡、勾选描边、胶囊都有 `reduce` 分支只做淡入；CSS 停掉扫描线、行高亮、呼吸点、闪烁，并把过渡压到 1ms（`styles.css:1872-1891`）；CountUp 直接显示终值；跳转滚动在 reduce 下用 `auto`（`Reader.jsx:58`）。`--reduce` 审计下结果态渲染正常。
- **移动端**：`shot.mjs ?q=zhihu.com --w 390 --audit`：W=390，**无横向溢出、无截断、无低对比、无 <11px 文字**；overlap 都是印章和雷达 SVG 内部的元素（预期内）。桌面 1440 `?q=bilibili.com` 的审计结果相同。
- **无障碍**：除颜色外还有 `PolarityIcon` 区分（胶囊、托盘、分组标题都有）；托盘计数配有文字「处要留神 / 处不错」；`aria-live="polite"` 播报阶段（`Waiting.jsx:140`）和输入模式（`Home.jsx:74`）；错误态有 `role="alert"`；抽屉有 `aria-expanded/aria-controls`；投票按钮有 `aria-pressed`；印章和雷达有 `role="img"` + aria-label。
- 小问题见一般 11。我没能人眼看截图（读图返回 `[image omitted]`）。

### 7. 合规表述 —— 基本通过，1 处需改

- `grep -rn "违法|诈骗|非法|无效|欺诈|illegal|unlawful|fraud" backend/clauselens frontend/src`（排除样例 json）只有以下几处：
  - `jurisdiction.py:3` 是注释；`jurisdiction.py:44` 是法规名称《App违法违规收集使用个人信息行为认定方法》，属于专有名词，可以接受。
  - `Compliance.jsx:74`「……不代表网站违法」是否定式说明，可以接受。
  - **`taxonomy.py:202` / `frontend/src/data/taxonomy.json:261`「在中国这类表述通常属于无效格式条款」是法律定性，需要改**，例如改成「这类表述在中国法下的效力常有争议」，或者删掉。
- 合规检查只有 `found/missing` 两种状态（`jurisdiction.py:150`），没有违法判定。
- 免责声明：页脚 `App.jsx:90`「结果由程序自动分析，仅供参考，不构成法律意见。」，每个视图都会显示；README 里也有。

### 8. 额外：Bug 与性能

- Bug：S2 中未捕获的 `ChunkedEncodingError`；一般 1 的混合语言处理；一般 4 的证据不去重；一般 11 的来源显示错误。
- 性能：单次分析 3–12s（6 站实测）；detect 100 万字约 1.7s、300 万字约 5.1s；首次请求要加载模型，约 +10s。每份文档读取上限 5MB、最多 4 份；结果里 `texts` 每份截到 30 万字（github 的 SSE 结果 191KB）。大文档本身不是瓶颈，瓶颈在 S2 和每个请求一个线程且不受控（一般 6）。

## 附：本次运行的命令（bash）

```
cd backend && python -m uvicorn clauselens.api:app --port 8799          # 后台运行，结束时已停止
curl -sN "http://127.0.0.1:8799/api/analyze?q=<site>&nocache=1"         # 6 站并行
python scripts/train_model_zh.py && python scripts/eval_zh.py test && python scripts/train_model.py
node frontend/scripts/shot.mjs "http://127.0.0.1:8799/?q=zhihu.com" out.png --w 390 --h 844 --wait 16000 --full --audit
```
分析脚本（抽样、泄漏、正则比对、慢速服务器、性能）放在临时目录，没有写进项目。
