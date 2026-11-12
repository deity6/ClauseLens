# 进度日志

## 2026-11-07
- 建立 AGENTS.md、docs/design/contract.md（接口契约 v1）
- 实测可用数据源：ToS;DR API（api.tosdr.org，service/v3 列表 10301 个服务、point/v1 含 quote_text，限速约 5 req/5s）；Open Terms Archive（GitHub 版本库，经 codeload tarball 下载）
- 后端主干完成：net(解析+SSRF 防护+编码判定) / discover(链接打分+二跳) / detect(规则+模型融合) / score / jurisdiction / pipeline / api(SSE)
- 实测 baidu.com：首页 → /duty → 二跳找到「隐私权保护声明」，CN 法域，D 级；github.com：EU（引用 GDPR），D 级，ToS;DR 对照 D
- 已知：taobao / bilibili 首页为脚本渲染，找不到链接 → 计划用 registry.json（已收录站点的条款直链 + 快照）兜底
- 已派子代理：调研、ToS;DR 采集、OTA+中文语料、前端

### 数据（01:00–02:00）
- ToS;DR：API 逐条抓 point 受限速（≈1 req/s）太慢 → 改用 Zenodo 官方整库导出（record 15012282，GPL-3.0），scripts/dl_ranges.py 分片并发下载 267MB documents.csv
- 产出：tosdr_points 22,497 条；tosdr_site_docs 2,211 站 / 4,960 份全文；OTA 790 服务 / 2,544 份；中文 187 站 / 486 份；CAPP-130；CA4P-483（仅学术，未用于训练）
- 中文人工标注：子代理并行标注 2,800 句（train 2000 / dev 400 / test 400），按站点划分，test 站点从不参与调参

### 模型与评测
- ToS;DR case→标签：先用正则映射，发现大量误映射（如"政府请求"映射成"改条款不通知"）→ 改为人工审定表 tosdr_map.py
- 英文：TF-IDF(词+字符)+LR，阈值在 train 内部按站点切出的验证集上按 F0.5 选（精确率优先）。test F1 0.74（P 0.77）
- 中文：先只看 dev 集修规则（F1 0.49→0.77 dev），再用 2000 句训练字符 n-gram 模型；test（去泄漏后 27 站 330 句）融合 F1 0.59
- 规则/模型融合抽成 detect.fuse()，线上与评测共用同一函数
- 评分：最初维度平均分把所有站压到 C/D → 改为在 train 站点上用岭回归学标签惩罚（方向受先验约束）+ 分段映射。test 443 站：完全一致 50%（基线 43%）、±1 级 94%

### 后端修复
- 编码：requests 对无 charset 头的页面按 ISO-8859-1 解码导致乱码 → decode_body：头声明→严格 UTF-8→meta→GB18030
- 发现：法律声明汇总页二跳；跳过"点击此处"类泛锚文本；registry.json（184 个中文站快照 + ToS;DR 2,819 站直链）兜底脚本渲染站点
- 超时：requests 超时是"单次读取"，慢速滴流会卡住 → 单页总时长 20s + 整次分析 40s 预算
- 不可达站点（google.com 等在本机网络 DNS 失败）给出"连不上"而不是"没找到条款"
- 契约 v1.1：结构化 tldr、合规证据按文档偏移、spans 精确高亮、限流走 SSE error

### 前端
- React 19 + Vite 7 + motion；三态（首页/等待/结果），等待态完全由 SSE 事件驱动；演示模式 ?demo=baidu|github
- 已知：Claude 浏览器面板隐藏时 rAF=0，motion 退场动画不结束 → 在面板里看似"卡在首页"；无头 Edge 下正常（已验证 bilibili 实跑到结果页）
- 截图：本环境图片被过滤，子代理与主代理都无法肉眼看图，形态验收用 DOM 审计（溢出/截断/重叠/对比度/字号）代替 → **需要用户人眼过一遍**

## 2026-11-07 晚 · 接手（DSH）

项目从 `E:\claude\project\ClauseLens-条款透镜` 复制到 `E:\deepseek harness\ClauseLens-条款透镜` 继续做，
原目录未改动。CC 会话在 02:17 因上游 API 400/502 中断，停在修 S2 的中间（详见 `.cc-import/README.md`）。

### 修完审查报告的 S2–S5

- **S2 单页总超时（上一轮没修成）**：根因是 urllib3 的 `read(amt)` 内部循环 recv 直到攒够 amt 字节，
  socket 超时只管单次 recv——对端每秒滴 1 字节就能一直占着线程。改成 `_DeadlineKiller`：
  到点直接 `shutdown()` 正在读的 socket。现测：慢滴 20.0s 退出、零数据 10.0s 退出，都抛 `FetchError(timeout)`。
- **S1 补齐**：连接后校验对端真实 IP 的 `_GuardedConnMixin` 保留；`_is_timeout()` 把 urllib3 的
  `ReadTimeoutError` 归到「网站响应太慢」，不再落到「打不开这个网站」。
- **S3 查百度拿到别的产品**：registry 文档按 host 分主域/子域，**主站首页永远先翻一遍**，
  只有首页一无所获（SPA）时才用子域条目兜底；主域已收录隐私政策正文时跳过首页省一次往返。
  现在 baidu.com → `www.baidu.com/duty/` → 「隐私权保护声明」11074 字，站名「百度」（原为「百度一下」）。
  `documents[]` 新增 `host` 字段，结果页可显示条款来自哪个子域。
- **S4 模型单独命中就贴负面标签**：① 加 `_model_worthy()` 门槛（长度、导航/标题形态、异语言字符），
  只作用于「纯模型命中」的句子；② 纯模型命中的 bad/blocker 打 `provisional`，不进 TL;DR、评分按半权。
  bilibili「改条款不通知」那句发推送通知的句子现在是「待确认」，不再主导评分。
- **S5 `sole discretion` 被判成解释权**：英文正则收紧为真正的 `final/conclusive interpretation` 表述；
  `explain_zh` 删掉「在中国这类表述通常属于无效格式条款」——那是法律定性，违反 §7 用词红线。

### 回归

- `net.py` 自测 6/6：正常页 / 302 / 5MB 截断 / 慢滴 20s / 零数据 10s / 重定向死循环。
- 英文句子级 F1 **0.736**（P 0.773 / R 0.702，仅规则 0.29），与审查前一致。
- 中文句子级 F1 **0.592**（P 0.646 / R 0.546，仅规则 0.433），一致。
- 实站复验：baidu.com 4s / bilibili.com 2.6s / zhihu.com 3.3s / taobao.com 3.6s / github.com 32s（4 份文档）。
- 训练脚本在本机需要限制线程才能跑通（`OMP_NUM_THREADS=1 LOKY_MAX_CPU_COUNT=1 JOBLIB_MULTIPROCESSING=0`），
  否则 joblib 并行会抛 `numpy ArrayMemoryError`（31.8GB 内存、16GB 空闲也不够）。

### 顺手修的一般问题

- **§5 反馈接口没有防护**：加每 IP 60 次/分钟限流、`domain` 用域名正则校验（带端口/路径/`../` 一律 400）、
  同一 IP 对同一站点的同一标签只能投一次（存 `ip_hash` 而不是明文 IP，重复投 409）；
  `feedback.jsonl` 超过 8 MB 滚动成 `.1`；`summary()` 改为内存索引，启动读一次、写入时同步，不再每次扫全文件。
  `_hits` / `_fb_hits` 限流表超过 5000 条时清理过期项。
- **§11 前端来源显示**：`rule+model` 不再显示成"规则匹配"，改为"规则 + 模型"；`provisional` 的标签在详情里标「程序推测，待确认」。
- **§8 依赖未锁版本**：新增 `requirements.txt`（本机实测版本）；`.gitignore` 补 `data/processed/*`（只留 `split.json`、
  `CORPUS.md`、`zh_label_guide.json`）与 `data/models/`，避免 365 MB 进仓库。

### 还没做

- 审查报告 §一般问题 6（取消请求后 worker 线程仍跑完）、
  8 的其余部分（站点级评测缓存不随模型哈希失效、`eval_sites.py` 文件头与行为不一致）、
  12（首个请求冷启动 11.7s）。
- 结果页还没把 `documents[].host` 显示出来（字段已下发，前端未接）。

## 2026-11-07 晚 · 第二轮（读图验收 + 多语言）

这一轮 DSH 侧能读图了，截图不再靠 DOM 审计代替。

### §1 中英文文档混在一个结果里

- `detect()` 改为**按句判语言**：中文句走中文规则 + 中文模型，英文句走英文规则 + 英文模型，
  结果按标签合并。原来只拿前 200 句判一次，整批按一种语言处理。
- 文档去重做了两层：请求 URL（`_url_dup_key` 去掉 `/zh/`、`/en/` 这类语言路径段）和
  **跟随重定向后的最终 URL**。github 的两份同款中英文文档就是这么进来的——ToS;DR 给的旧链接
  `help.github.com/articles/github-terms-of-service/` 带着 `Accept-Language: zh-CN` 重定向到了
  `docs.github.com/zh/...`，跟另一个候选的 `/en/...` 撞成两份。
- `dominant_zh()` 按字符量判整站主语言，不再只看开头 3000 字。

### 规则层两处极性反转（§4 同类问题）

- `terms-change-no-notice`：中文正则「随时 + 修改 + 协议」把「虽然我们可能会随时修改本协议，
  但对任何重大变更，我们都会通知用户」判成了"改条款不通知"。加 `neg_zh` 排除承诺通知的句式。
- `forced-arbitration`：英文正则把「An individual has the possibility, under certain conditions,
  to invoke binding arbitration」（DPF 框架下用户**主动**发起仲裁的**权利**）判成强制仲裁。
  加 `neg_en` 排除 opt-out 和"可以主动发起仲裁"的句式。

### 前端（看过图之后改的）

- **合规检查的红色叉号**改成中性空心圆 + 灰色字。原来 12 项里有 7 项是红 ✗，整页像判了罪，
  和页脚「未在条款中找到不代表网站违法」自相矛盾。
- 等待态文档卡的「正常人要读 28 分钟」不再被拆成「28 分 / 钟」。
- 新增截图 `10-result-compliance.png`（结果页全页）、`11-result-cn.png`（真实后端 bilibili.com 亮色）。

### 回归

- 英文句子级 fused F1 **0.736**（rule 0.289 / model 0.733），中文 **0.592**（rule 0.435）——两处 neg 改动都没影响指标。
- `shot.mjs --audit`：1440 与 390 宽都 `trunc: []`、`lowContrast: []`、`small: []`，
  剩下的 overlap 全是雷达图的 SVG 图元。

### 还没做

- bilibili 的 `terms-change-no-notice` 证据仍然是那句「我们可能使用您的信息…发送推送通知」，
  现在降级成「待确认」（不进 TL;DR、评分半权），但没有被彻底排除——通用规则判不了这种语义误判。
- §1 之后的 `site.lang` 与法域检查仍按整站一种语言；github 这类中英混排站点，法域检查只看主语言。

## 2026-11-07 晚 · 第三轮（泛用性 / 字体 / 境外出口）

### 泛用性：40 站实测 24 → 29（60% → 72%），`unreachable` 清零

改动都在「发现」环节：

- **补探不再只看"有没有候选"**。原来的逻辑是「一个候选都没有才试常见路径的前 6 条」，
  于是首页只要捞到一条「版权声明」就再也不往下试了（coolapk 就是这么漏掉隐私政策的）。
  现在按**覆盖率**补探：缺 privacy 或 terms 就继续找。
- **兄弟路径推断**：从一个已知声明页推同目录其他的（`/about/copyright.html` → `/about/privacy.html`），
  这是救回 coolapk 的那一下。中文站很吃这个——首页常只挂一条「版权声明」。
- **常见路径 11 → 34 条**，加了 `/about/*`、`/policies/*`、`.php` 变体和中文习惯写法；并发 6 路探测。
- **`probe_paths` 用原始 HTML 判「像不像条款」的 bug**：SPA 页面前两万字全是脚本，
  关键词一个都扫不到，一律判 false。必须先 `extract_text` 再判——小宇宙（xiaoyuzhoufm）就是栽在这。
- **URL 语言变体去重**（`/zh/...` 与 `/en/...` 视为同一份文档）+ **按句判语言**，
  github 不再把同一份条款的中英两版各算一遍。
- **结论站不住时主动说**：`result.warnings` 在条款太短（<2500 字）、一个标签都没认出来、
  有效标签少于 2 个时给提示，前端渲染成黄色提示条。v2ex 就是典型案例——只找到 954/1128 字的
  两个页面，0 标签，现在会明说「等级和标签都不可靠」。

剩下 11 个 `not_found` 里，`overreacted.io` / `danluu.com` / `jvns.ca` / `ruanyifeng.com`
是个人博客，本来就没有条款页——报「没找到」是正确结果；`52pojie.cn` / `hostloc.com` 把协议放在
注册页或论坛帖里；`mastodon.social` / `archive.org` / `medium.com` / `linode.com` 的条款在
子域（`policy.medium.com`）或 `.php` 路径下，仍然没覆盖到。

### 境外出口（解决被墙站点）

本机 DNS 被污染（`signal.org` → 31.13.90.33 是 Facebook 的 IP、`duckduckgo.com` → 108.160.169.175
是 Dropbox 的），`v2ex.com` 解析正常但 SNI 被阻断。这类问题换出口才有解。

- 新增 `CLAUSELENS_EGRESS`，直连失败（`fetch_failed`/`timeout`/`unreachable`）时自动改走出口重试。
  两种形态：`instabox:<machine-id>`（借 InstaBox 容器的 `exec` 跑一次 curl）和 `socks5h://host:port`。
- **选了 exec 而不是常驻代理**：不发布端口、不起 systemd 进程，就没有「开放代理被扫到滥用」的面，
  也符合 InstaBox 平台「不在机器里做批量探测」的红线。代价是每次多 1–2 秒 API 往返，所以只在直连失败时触发。
- **gzip 压缩后传输**：duckduckgo 的 349 KB 页面从 51.6s 降到 8.8s（回执 95 KB）。
- **失败记忆**：某个域名直连失败过一次，同一次分析里后续请求直接走出口，不再每次白等 6 秒连接超时
  （signal.org 从 71s 降到 48s）。
- **总预算 `ANALYZE_BUDGET=60s`**：首页 + 补探 + 抓取三段共享，防止慢站点把一次分析拖到 90 秒。
- 出口模式下跳过「连接建立后校验对端 IP」这一步（对端是代理），域名层校验保留。
  这是有意的降级，写在 `egress_session()` 的 docstring 里。

### 字体

用户明确不要宋体。原来的 `--serif` 是 `"Noto Serif SC","Source Han Serif SC","Songti SC","STSong"`，
而且没加载任何 Web 字体，没装思源宋体的机器直接掉到系统宋体。

- 展示（标题 / 站名 / 章节标题 / 印章）：**霞鹜文楷 LXGW WenKai**（楷书，有笔锋）
- 大数字（分数）：**Instrument Serif**
- 元数据（REPORT · 01 · TL;DR · FOUND）：**Space Mono**
- 正文：系统黑体（苹方 / 微软雅黑）——**特意不挂 Noto Sans SC 的 webfont**：它是首屏最大的一笔开销
  （实测结果页 1.29 MB 字体里大头是它），而正文黑体换成系统字体观感差别很小。

体积账：CSS 29 KB → 214 KB（全是 unicode-range 声明），后端加了 `StaticGZip` 后 gzip 74 KB；
实际首屏字体从 578 KB 降到 297 KB、结果页从 1.29 MB 降到 554 KB。SSE 走 `/api/` 被排除在压缩之外，
否则等待态的进度事件会被缓冲住。

### 前端

- 合规检查的「未在条款中找到」从红叉改成中性空心圆 + 灰字（原来 12 项里 7 项红叉，整页像判了罪，
  和页脚「不代表网站违法」自相矛盾）。
- 等待态文档卡的「正常人要读 28 分钟」不再被拆成「28 分 / 钟」。
- 新增黄色提示条渲染 `warnings`。
- **空区块隐藏**：0 标签时「一句话总结」「条款里写了什么」两节整段不渲染——原来只剩两个光秃秃的标题，
  比不显示更糟。
- 截图：`12-font-home.png`、`13-font-result.png`、`14-warning-thin.png`（v2ex，条款太短 + 0 标签的提示条）。

### 还没做

- 站点把条款放在子域（`policy.medium.com`）时仍然找不到；medium.com 首页本身 403。
- 论坛类站点（Discuz）的协议在注册页，没有专门的发现路径。
- 走出口的页面单次 2–9 秒，被墙站点整次分析仍在 30–60 秒；没有做「同一 host 批量抓取」的合并。

## 2026-11-07 夜 · 第四轮（两类"抓到了却读不出来"）

这两轮都是「页面明明抓到了，却报没找到」，但根因完全不同，都不是加路径能解决的。

### A. 正文躲在 `<noscript>` 里（nodeloc.com）

NodeLoc 是 Discourse 论坛：服务端 HTML 1,170,900 字符，其中 `<script>` 占 1,069,562（91%），
而**25,963 字的正文全在 `<noscript>` 里**——那是给爬虫看的降级版本。

`NOISE_TAGS` 里把 `noscript` 当噪音删掉了，于是正文归零 → 判成「不像条款」→ 报没找到。
修法：`extract_text` 先收集 noscript 里的文本，若正常提取结果 < 600 字、而 noscript 内容多得多，
就用 noscript 那份。Discourse 类社区（很多技术论坛）都是这个结构。

### B. 正文要跑 JS 才有（cloud.doulor.cn）

这个站更极端：`/`、`/terms`、`/privacy` **三个地址返回同一份 13,644 字节的 HTML**，
提取出来只有 12 个字的 "Doulor Cloud"。纯前端路由（Vue/React 后台面板），
条款只在浏览器执行 JS 后才出现——静态抓取拿到的永远是空壳，换路径、改正则都没用。

新增 `backend/clauselens/render.py`：

- playwright + **系统已装的 Edge**（`channel="msedge"`，不下载 chromium）
- 触发条件：静态提取的正文 < 400 字（明显是空壳），且本次分析渲染次数没用完、剩余预算 > 18 秒
- **复用浏览器实例**：一次分析最多渲染 3 页，但只启动一次浏览器。
  每次重开的话，三次渲染光启动就多花近 10 秒，直接把预算吃光，最后一份文档永远抓不到
- 图片/媒体/字体一律 abort，只拉文本和脚本
- playwright 不可用时静默降级，行为回退到纯静态抓取

`cloud.doulor.cn` 现在两页都拿全了：隐私政策 1,271 字 + 服务条款 5,024 字。
注意它的隐私政策**本身就只有 1,271 字**，所以会带「条款太短」的提示——这是对的，不是 bug。

### 顺带

- 错误提示不再固定举例「试试 https://www.baidu.com/duty/」，改成说明「粘整条带 /privacy 的地址会只分析那一页」。
- 单站命令行入口：`python scripts/query.py <域名>`（或 `backend/` 下 `python -m clauselens <域名>`），
  支持 `--json` / `-v` / `--no-cache`，失败退出码 2。
- 批量探针移到 `scripts/probe_sites.py`，支持 `--file`。

## 2026-11-07 深夜 · 第五轮：600 字硬门槛系统性误杀小站

### 现象

`dnsneko.com` 模糊和精确两种模式都报「没找到」，而 `https://www.dnsneko.com/privacy`
在浏览器里明明能打开。

### 链路

1. 服务端返回 **2,609 字节的空壳**（纯前端路由），提取正文 0 字
2. 触发渲染 → 拿到 **492 字的完整隐私政策**（"本页内容 1. 信息收集 2. 信息使用…"）
3. 交给 `looks_like_policy()` 判断 —— 它的第一行是：

   ```python
   if len(text) < 600:
       return False
   ```

4. 492 < 600，**判成「这不是条款」直接丢掉**，于是报「没找到」。

精确模式失败的原因不是「没抓」，而是「抓到了、渲染出来了，又被判据毙了」。

### 为什么这是系统性问题

小站和个人站的条款本来就写得短——几句话把话说清楚；大厂才写几千字。**拿字数当判据，
等于系统性地惩罚小站、奖励大厂**，这正是「大厂能搜到、小站搜不到」的一个真实原因。

同一个毛病在代码里出现过三次，都是「字数 < N 就算不是」：

| 位置 | 原阈值 | 现在的做法 |
|---|---|---|
| `looks_like_policy` | 600 字 | 150 字起判，短页面改看**关键词密度**（每 150 字至少 1 个） |
| `extract_text` 的 noscript 回退 | 600 字 | 保留，但阈值只参与「和 noscript 谁更长」的比较 |
| 渲染触发条件 | 400 字 | 保留（空壳判定，与条款判定无关） |

新判据的正负样本验证：

```
492字隐私政策   -> True     404 页面    -> False
正常长条款      -> True     登录提示    -> False
                            空壳12字    -> False
```

### 结果

`dnsneko.com` 两种模式都通了：精确 492 字 / C 63；模糊 2 份文档（隐私政策 492 + 用户协议 1,215）/ C 60。
9 站回归 9/9，没有引入噪音页面（404、登录页仍被挡在外面）。

副作用：`v2ex.com` 从「2 份文档 0 标签」变成「4 份文档 4 标签」——旧判据砍掉的短页面现在收进来了。



## 2026-11-12 凌晨 · 上线 + 安全审计 + 内存优化

### 部署（B 方案，全部在境外）

- **仓库**：github.com/deity6/ClauseLens（私有）。HTTPS 推送被重置，改走 SSH（443）。
- **前端**：Cloudflare Pages（clauselens 项目），lens.dohub.tech 自定义域。
- **后端**：AWS 新加坡 t3.micro，venv + systemd（clauselens.service），Caddy 443 反代。
  一开始误放在腾讯小机，后来按用户要求全部迁到境外（国内机未备案）。
- **跨域**：Pages Function unctions/api/[[path]].js 把 /api/* 同源代理到 pi.dohub.tech，
  前端代码不用改，SSE 原样透传。
- 踩坑：Docker Hub 在国内拉不动基础镜像（改 venv）；pkill -f 会自杀（改 systemctl）；
  Pages 自定义域的 DNS 记录删了没重建导致解析失败。

### 安全审计（docs/reviews/2026-11-12-security.md，结论：打回）

三条必修，已全部修完并实测：

- **S1（严重，我自己引入的）**：为提速加的 
e.sub(r"<script[^>]*>.*?</script>") 在页面含
  **未闭合 <script>** 时退化成 O(n²)——0.48MB 畸形页面要 86.8 秒，期间 GIL 占满、整个 API 失联，
  一个请求就能打瘫。改成两指针线性扫描 _strip_scripts()，并加 2MB 解析上限。
  顺带把「逐节点 insert_before/insert_after」换成一次 get_text("\n")。
  **实测：86.8s → 0.00s**，正常页面提取质量不变。
- **H1（高）**：投票去重与限流用 
equest.client.host，但生产链路是 CF Pages Function 代理，
  后端看到的是 Cloudflare 边缘 IP（同一客户端三次落在三个不同 IP），去重完全失效。
  改成优先读 CF-Connecting-IP。实测：连投 3 次现在是 200/409/409。
- **H2（高）**：没有请求体上限、没有并发上限。Caddy 加 
equest_body max_size 256KB
  （实测 30 万字符 POST → 413），后端加 _analyze_slots = BoundedSemaphore(3)
  （实测 5 路并发 → 3 成功 + 2 立即 busy）。

SSRF 那一层审计确认**全部守住了**（DNS 重绑定、慢滴、chunked、逐跳重定向、端口白名单、
XFF 伪造、快照路径穿越，含 tcpdump 验证）。

### 内存优化

实测四种 Chromium 启动配置（进程树 RSS 合计，AWS 上测）：

| 配置 | 耗时 | RSS | 进程 |
|---|---|---|---|
| 默认多进程 | 5.9s | 462.9 MB | 6 |
| + 常规瘦身 flags | 3.0s | 490.2 MB | 6 |
| **--single-process** | **2.8s** | **280.4 MB** | **3** |
| single + no-zygote + 更多 | 4.1s | 496.0 MB | 2 |

结论：--single-process 省 180MB 且更快。风险是单进程模式有崩溃概率，所以做成
「先试省内存的，渲染失败自动关闭实例、退回多进程重试一次」。

三个 SPA 站实测（nocache）：cloud.doulor.cn 10.3s / lobehub.com 16.0s / ow.blizzard.cn 17.8s，
全部成功；服务内存 571 → 484 MB（可用从 337 升到 424）。


## 2026-11-12 深夜 · 按覆盖报告修四项

`docs/reviews/2026-11-12-coverage.md` 把真实覆盖率拆穿成 42.5%（模糊）/ 56.8%（精确）——
表面 80% 里近一半是靠预存快照撑的。按报告建议逐项修：

### 1. 三类「假成功」

- **错误页被当条款**：`error.taobao.com` 的错误页 976 字给了 C 级。新增
  `discover.looks_like_error_page()`：前 600 字命中「页面不存在 / 404 / Just a moment /
  checking your browser / 访问被拒绝」且总长 < 2500 就判否。构造样本实测：错误页 712 字 → False，
  真条款 750 字 → True。
- **跨站 WAF 页**：ezg.com 被 Cloudflare 拦住，页面里那条 Cloudflare 自己的隐私政策被算成它的条款
  （还缓存 24h）。根因是 `find_candidates` 对跨域只扣 3 分。改成**主域不同直接不采信**
  （新增 `base_domain()`，`ow.blizzard.cn` 与 `wow.blizzard.cn` 都归到 `blizzard.cn`，仍算同家）。
- **首页短内容**：alipay 精确模式命中首页 185 字，判成 C 级。加规则：根路径 + 正文 < 800 字直接跳过。

### 2. 裸域 vs www

`pipeline.py` 首页抓取失败时自动换 `www.` 变体（反之亦然）。实测救回：

| 站点 | 修前 | 修后 |
|---|---|---|
| cosmoplat-aiot.com | not_found | D51 · 2 份 · 24,487 字 |
| appinn.net | not_found | C61 · 1 份 |

### 3. 中文路径

`COMMON_PATHS` 38 → 69 条，补了 11 条中文语义路径（`/隐私政策` `/用户协议` `/服务协议`
`/法律声明` …）和国内常见的协议中心结构（`/info/privacy` `/site/terms` `/company/privacy`）。
同时把「首页已发现候选时的探测预算」从 14 提到 22——原来 14 条正好把排在后面的中文路径挤掉。

### 4. 渲染空壳 + SSE 终结

- 渲染跑过、正文仍 < 400 字时记 `render_empty`，最终错误消息改成「渲染过了但拿到的仍然不是条款」，
  不再笼统说「可能没有公开条款」。
- `api.py` 的 SSE 流加 `ANALYZE_HARD_LIMIT = 100` 秒硬上限：超时一定发 `error` 事件。
  之前 notion.so 渲染卡死后 128 秒静默断开，前端只能一直转圈。

### 踩坑

`ANALYZE_HARD_LIMIT` 第一次没定义成功（替换锚点被前一次改动改掉了），服务起来后 SSE 直接抛
`NameError`、整条流返回空——这类「改了但没生效」只能靠起完服务立刻打一次接口才发现。


## 2026-11-12 上午 · 一个自己引入的严重 bug（已修）

用户反馈「dnsneko / cloud.doulor.cn 明明有隐私条款，为什么查不到」。查下来是**上一轮改
pipeline.py 时把整段发现逻辑误缩进进了 except net.FetchError 块**：

```
try:
    home = net.fetch(...)
except net.FetchError as _e:
    ... (裸域/www 重试)
    homepage_html = home.text                    ← 正常路径走不到
    home_cands = discover.find_candidates(...)   ← 同上
    ...
except net.FetchError as e:                      ← 第二个 except，永远轮不到
```

后果：**只有首页抓取失败时才做发现**。抓取成功时直接跳过「找链接 → 探路径 → 渲染首页」，
found=0，只剩 registry 快照能用。所以之前很多「成功」其实是预存快照撑着，清缓存后全露馅。

判定方法：analyze() 的 stage 流只有 `resolve > discover` 且耗时 1.9 秒——正常站点发现阶段
至少要有 find_candidates 的调用。

修完（含三个连带问题）：

| 站点 | 修前 | 修后 |
|---|---|---|
| dnsneko.com | not_found | C63 · 492 字（渲染首页找到 www.dnsneko.com/privacy） |
| cloud.doulor.cn | not_found | C60 · 1,271 + 5,398 字（隐私 + 条款） |
| ow.blizzard.cn | not_found | C61 · 8,084 + 2,270 字 |

连带修的三处：

1. **首页渲染阈值**：len(htext) < 400 → < 3000。ow.blizzard.cn 首页静态 545 字，
   刚好超过门槛不渲染，而条款链接全在 JS 里。
2. **补探遇到空壳**：probe_paths 探到 /privacy 但静态只回 12 字空壳时被判否丢弃，
   而抓取阶段本来有渲染兜底。现在路径像条款 + 返回 200 就保留候选（正文可短至 5 字）。
3. **同品牌跨 TLD**：paperpal.cn 的条款在 paperpal.com，被跨站过滤误杀。
   加 brand_name() 按品牌名放行（ezg.com → Cloudflare 仍被拦）。

### 覆盖率（清空缓存后真实抓取，77 次调用）

| 口径 | 本轮前 | 本轮后 | 最初（含缓存） |
|---|---|---|---|
| 模糊 | 75.0% | 87.5%（35/40） | 80.0% |
| 精确 | 86.5% | 86.5%（32/37） | 83.8% |

### 教训

改 pipeline / discover 之后，**必须立刻在服务器上跑一次 analyze() 并打印 stage 事件流**，
而不是只看 systemctl is-active。这次如果早看一眼「1.9 秒 + found=0」就能当时发现。


## 2026-11-12 中午 · 评分系统重做 + 移动端进度条

用户反馈：六维封顶 72、总分没见过 70 以上、ToS;DR 评 A 的站也被判 C 级并警告「内容太少不可靠」。

**根因有两层**：

1. `score.py` 的 `DEFAULT` 是 `base=72, k_bad=3.2, k_good=1.6`——负面权重是正面的两倍，
   而且「零标签」直接落到 72 分。
2. 总分走 `mode: learned`（ToS;DR 学到的惩罚模型），`raw=0` 经 anchors 插值恰好是 **64.7 分**。
   于是「没发现明显问题」被系统性地判成「中等偏下」，我们自己的六维只用来画图，不参与总分。

**改法**（`git tag v1-before-scoring-rework` 是回退点）：

| 项 | 旧 | 新 |
|---|---|---|
| base（中性起点） | 72 | **82** |
| k_bad（坏标签系数） | 3.2 | **2.0** |
| k_good（好标签系数） | 1.6 | **2.8** |
| 总分构成 | 100% learned | **70% 六维 + 30% learned** |

**效果**：

| 站点 | 改前 | 改后 |
|---|---|---|
| nextdns.io（零标签、626 字） | C 65 | **B 77**（六维全 82） |
| apple.com（26 标签，14 坏 9 好） | D 52 | **C 66**（六维 67/77/100/60/48/75） |
| mozilla.org | 抓不到 | **B 72** |

**警告语气**：`thin_docs` 从「内容太少，等级和标签都不可靠——可能放在 App 里」改成
「这次读到 N 字的条款。条款本身可能就是这么短，也可能还有一份没被我们发现——结论按读到的内容算」，
并统一加 `severity: "info"`。`no_tags` / `few_tags` 同步改写。

**移动端进度条空白的根因**：`Radar.jsx` 的维度条用 `whileInView` + `viewport={{once:true}}`，
手机上这几条在首屏下方，永远不进视口 → `scaleX` 一直是 0 → 条是空的。改成 `animate`。
雷达图本体的 `amount: 0.5` 也放宽到 0.05。
