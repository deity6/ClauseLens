# 01 同类项目调研（Similar Projects）

> 调研日期：2026-11-07。标记约定：**【实测】** = 本次直接调用 API / 读源码 / 读 GitHub 元数据得到；**【文档】** = 来自对方论文、README、官网的声称，未独立复现。
> 许可证一栏以仓库 LICENSE / 官方数据页为准；“数据许可”与“代码许可”分开写。

---

## 0. 一览表

| 项目 | 类型 | 语言 | 规模 | 代码许可 | 数据许可 | 对我们的价值 |
|---|---|---|---|---|---|---|
| ToS;DR | 众包评级 + API + 插件 | 英为主 | 服务约 1 万条（含未评级） | AGPL-3.0 | 贡献内容 CC BY-SA 3.0+ | **标注来源 + 等级对照 + case 体系** |
| ToS;DR DocBot | LLM 自动标注 | 英 | 123 个 case 二分类模型 | GPL-3.0 | 数据集“计划发布” | 方法参考（每 case 一个二分类器） |
| Open Terms Archive | 条款版本存档 | 多语 | contrib 集合 612 个声明 | EUPL-1.2 | versions 库 ODC-By | **原文语料 + 抓取选择器** |
| PrivacySpy | 专家打分 rubric | 英 | 269 个产品、12 道题 | GPL-3.0 | 同仓库（GPL） | 评分 rubric 结构 |
| Polisis / PriBot | 学术系统 | 英 | 13 万篇政策预训练 | 未见公开仓库 | — | 分层分类器思路 |
| OPP-115 等 (usableprivacy) | 标注语料 | 英（MAPP 含德） | 115 篇 | — | **CC BY-NC 精神，商用需另购** | 隐私实践类别体系 |
| CLAUDETTE / UNFAIR-ToS | 不公平条款检测 | 英（后扩德意波） | 50 份 ToS，句级 8 类 | — | LexGLUE 版 CC BY 4.0 | **霸王条款训练/评测集** |
| CAPP-130 | 中文隐私政策语料 | **中** | 130 篇，52,489 标注 | MIT/Apache（有歧义） | CC BY 4.0 | **唯一大规模中文标注集** |
| 网信办等《认定方法》/ TC260 自评估指南 | 监管规则 | 中 | 6 大类 | — | 公文 / 版权受限 | **中国法域检查项骨架** |

---

## 1. ToS;DR（Terms of Service; Didn't Read）

**做什么**：2012 年起的公益项目，志愿者从条款中摘出“point”（一句可读结论 + 原文引用），每个 point 归属一个“case”（标准化结论，带 good / neutral / bad / blocker 分类），再由 curator 审核，按规则算出 A–E 等级。
来源：https://tosdr.org/en/about ，https://github.com/tosdr/edit.tosdr.org （README：point 是“succinct, easy-to-understand mini-conclusion sourced from the complex text”）

### 1.1 API【实测】
- 搜索：`GET https://api.tosdr.org/search/v5/?query=google` → `{"services":[{id, is_comprehensively_reviewed, urls:[...], ...}]}`。`urls` 是域名数组（Google 一条就挂了几十个国家域名），**可直接用于“域名 → 服务”映射**。
- 服务详情：`GET https://api.tosdr.org/service/v3/?id=182`（Facebook）返回键：`id, is_comprehensively_reviewed, name, updated_at, created_at, slug, rating, urls, image, documents, points`。
  - `documents[]`：`{id, name, url, updated_at, created_at}`（如 "Privacy Policy"、"Terms of Service"、"Cookie Policy"）——**等于现成的“条款 URL 发现”结果**。
  - `points[]`：`{id, title, source, status, analysis, case, document_id, updated_at, created_at}`；`case` 内嵌 `{id, weight, title, description, topic_id, classification}`。Facebook 共 65 个 point：neutral 22 / bad 21 / good 18 / blocker 4，rating = "E"。
- 服务列表：`GET https://api.tosdr.org/service/v3/`（不带 id）返回 `{"services":[...], "page":{"total":10301,"current":1,"start":1,"end":21}}`，列表项含大量 `rating:"N/A"`（未评级）。
- 文档：`GET https://api.tosdr.org/document/v1/?id=239` 返回 200。
- 官方文档列出 `GET /case/v2/`（https://github.com/tosdr/docs/blob/main/dev/tos-dr-developers/restful-api/case-api/get-case-v2.md ），但本次实测 `/case/v2/?id=122` 返回 404 —— **case 字典建议从 service/v3 的内嵌 case 汇总**，或参考 https://edit.tosdr.org/cases 。
- **限速**：连续请求后收到 `{"error_msg":"You are doing this too much"}`【实测】。与 AGENTS.md 中 1 req/s 的约定一致，采集脚本必须退避。
- API 官方文档入口：https://developers.tosdr.org/dev/restful-api （本机连接超时，内容以 GitHub 上的 tosdr/docs 仓库为准：https://github.com/tosdr/docs ）

### 1.2 A–E 评级规则【实测：读源码】
`app/models/service.rb`（https://github.com/tosdr/edit.tosdr.org/blob/master/app/models/service.rb ）：
- 只统计 `status='approved'` 且有 case 的 point；
- `balance = good − bad − 3 × blocker`；
- 无 good/bad/blocker → `N/A`；`balance ≤ −10` 或 `blocker > good` → **E**；`blocker ≥ 3` 或 `bad > good` → **D**；`balance < 5` → **C**；仍有 bad → **B**；否则 **A**。
- 官方说明与此一致（“as of Sept 2025, a blocker counts as 3 bad points”）：https://github.com/tosdr/docs/blob/main/phoenix/how-are-classifications-calculated.md
- 注意：case 有 `weight` 字段（Facebook 的 case 193 weight=50），但**评级算法不使用 weight**，只计数。neutral 不参与。

### 1.3 开源仓库【实测：GitHub API】
| 仓库 | 说明 | 许可 | 最近推送 |
|---|---|---|---|
| tosdr/edit.tosdr.org（Phoenix） | Rails 标注/审核平台 | AGPL-3.0 | 2026-11-04 |
| tosdr/browser-extensions | 浏览器插件（WXT/TS），511★ | AGPL-3.0 | 2026-10 |
| tosdr/DocBot | ML 自动标注 | GPL-3.0 | 2026-11-02 |
| tosdr/tosdr-android / tosdr-safari / apple | 移动端 | MIT / – / AGPL | 2025–2026 |
| tosdr/ota-engine、tosdr-declarations、tosdr-versions | 基于 OTA 的抓取与版本库 | EUPL-1.2 / AGPL | 2024–2025 |
| tosdr/terms-types | 条款类型字典 | EUPL-1.2 | 2024-11 |

来源：https://github.com/tosdr

**数据许可**：贡献者条款写明贡献以 **CC BY-SA 3.0（或后续版本）** 发布，并允许以 AGPL-3.0 纳入“更大程序”。来源：https://github.com/tosdr/docs/blob/main/site/tosdr-terms/tosdr.org-terms-of-contribution.md
→ 我们用 ToS;DR 的 point/case 训练和展示，**需署名并对衍生数据集采用相同许可（SA）**；前端若直接复用插件代码则需 AGPL。

### 1.4 浏览器插件
Firefox / Chrome / Safari 均有上架，工具栏图标显示等级，点开看摘要。来源：https://github.com/tosdr/browser-extensions （README）

### 1.5 我们能借用什么
1. `search/v5` 的 `urls` 做域名匹配；`service/v3` 的 `documents` 做条款 URL 种子（发现阶段的强先验）。
2. `points` 的 `source`（原文）+ `case` 作为**带人工标注的段落级训练数据**，`rating` 作为等级一致率的对照标签（契约 §2 `tosdr` 字段）。
3. case 体系可直接映射到我们 `taxonomy.py` 的 `tosdr_cases`。
4. “blocker 计 3 个 bad”的计数式规则可作为 baseline 评分器。

### 1.6 不足（= 我们的差异化）
- **覆盖**：大量服务 `N/A`（列表首页即可见），且依赖志愿者；中文站点几乎没有人工评审。
- **语言**：case 与 point 基本是英文，`localized_title` 为空（Facebook 样本中为 null）。
- **无法域检查**：只给“好/坏”，不对照任何国家的法定必备项。
- **评分粗糙**：不用 weight，只计数；不分维度。
- **交互门槛**：网站与插件需要先知道“服务名”；贡献需注册登录才能投票/标注。

---

## 2. ToS;DR DocBot（ToS;DR 的 LLM 自动标注）

**做什么**【文档】：对新爬到的文档，每周运行 **123 个 case 模型**（把大模型微调成二分类器），输出 point 建议 + 置信度，交 curator 审核。README 称“plan to release our datasets used for training/evaluation”。
来源：https://github.com/tosdr/DocBot （GPL-3.0）

**借用**：每个标签一个二分类器 + 置信度 + 人审的架构，与我们“宁可未发现、不乱贴负面标签”的 precision 优先原则一致。
**不足**：模型不对外提供推理服务（README 要求把文档加到平台等待处理）；训练集尚未公开；英文。

---

## 3. Open Terms Archive（OTA）

**做什么**：公开记录数字服务条款的每一个版本，便于追踪变更。获 UNDP 等认定为 Digital Public Good。按“集合（collection）= 语言 × 法域 × 行业”组织。
来源：https://opentermsarchive.org/en/ ，https://github.com/OpenTermsArchive/engine （EUPL-1.2）

【实测：GitHub API】
- `contrib-declarations`：612 个声明文件（EUPL-1.2），其中含 `Alibaba.com`、`Tencent`、`WeChat`、`WeChat Open Platform`、`TikTok` 等。声明文件描述“哪个 URL、用什么 CSS 选择器提取条款正文”。https://github.com/OpenTermsArchive/contrib-declarations
- `contrib-versions`：版本库，LICENSE 为 **ODC-By（Open Data Commons Attribution）**；Releases 提供打包数据集，最新 `contrib-collection-dataset-2026-11-02.zip` 约 **541 MB**。https://github.com/OpenTermsArchive/contrib-versions/releases
- 还有按地区/主题的集合：france、pga（社交平台，Bremen 大学）、genai-contrib（48 个生成式 AI 服务，官网数字）、dsa-reports、india、kenya、vlopses-{gb,ie,ca,au,us} 等。https://github.com/OpenTermsArchive

**借用**：
1. versions 数据集 = 干净的条款正文（已去菜单广告），直接作为多语种语料（需署名 ODC-By）。
2. declarations 里的选择器 = 现成的“正文提取规则”，可为 `extract.py` 做站点特例；也能为 `discover.py` 提供“服务 → 条款 URL”种子。
3. 版本历史可做“条款近期改过什么”功能（未来）。
**不足**：只存档不评价；中文站点很少；面向研究者/监管者，普通用户难用。

---

## 4. PrivacySpy

**做什么**：用一套固定 rubric 给隐私政策打 0–10 分。代码 GPL-3.0，Politiwatch 维护。
来源：https://github.com/Politiwatch/privacyspy ，https://privacyspy.org

【实测】
- rubric 共 **12 题**：behavioral-marketing、data-breaches、data-collection-reasoning、data-deletion、history、law-enforcement、list-collected、noncritical-purposes、revision-notify、security、third-party-access、third-party-collection（`rubric/*.toml`）。每题有 `points` 与若干选项的 `percent`，例如“是否允许行为定向营销”：Yes=0%、可 opt-out=35%、须 opt-in=70%、No=100%。
- `products/` 下 **269** 个产品；公开 JSON：`https://privacyspy.org/api/v2/index.json`（含 name、hostnames、score、last_updated）。
- 仓库最后推送 2025-03-08，活跃度低；Zenodo 有 2025-08-01 的评分快照：https://doi.org/10.5281/zenodo.16424690

**借用**：“题目 × 选项百分比”的 rubric 是**可解释评分**的好模板——我们的维度分可按“每个维度若干检查题”实现，用户能看到每题得分。
**不足**：人工打分、规模小、更新停滞、只看隐私政策不看服务条款、英文。

---

## 5. Polisis / PriBot

**做什么**【文档】：USENIX Security 2018。用 **13 万篇**隐私政策训练隐私领域语言模型，配合分层神经网络分类器（高层类别 + 细粒度属性）；应用一是自动生成“隐私图标”（准确率 88.4%），应用二 PriBot 是对隐私政策的自由问答。
来源：https://arxiv.org/abs/1802.02561 ，https://www.usenix.org/conference/usenixsecurity18/presentation/harkous

**借用**：分层标签（先判段落属于哪个大类，再判细属性）可降低误报；“问答式”交互可作为后续功能。
**不足**：pribot.org 本次访问无响应【实测】，服务已基本停摆；英文；基于 OPP-115 体系，与中国法规的告知项不对齐。

---

## 6. OPP-115 及 Usable Privacy 系列数据集

【文档】https://usableprivacy.org/data
- **OPP-115**（ACL 2016）：115 个网站隐私政策，每篇由 3 名法学研究生标注数据实践。下载：`OPP-115_v1_0.zip`（94.5 MB）。论文：https://usableprivacy.org/static/files/swilson_acl_2016.pdf ，https://aclanthology.org/P16-1126/
  - **许可**：仅限研究/教学，“in the spirit of CC BY-NC”；**annotations/consolidation 子目录商用需购买商业许可**（CMU flintbox）。
- **MAPP**（LREC 2022）：64 篇英文 + 91 篇德文 App 隐私政策，双语；同为 NC 精神。
- **APP-350**（PETS 2019）、**OptOutChoice 2017/2020**、**MAPS Policies**、**Privacy Q&A**（EMNLP 2019）、**OPP-115 ↔ GDPR 对应关系**（JURIX 2020，83 KB）、**Privacy Law Corpus**（CC BY-NC-SA 2.0）、**FSDK**（CC BY 4.0）。

**借用**：OPP-115 的 10 类数据实践（类别名见 ACL 2016 论文，【文档】）（first-party collection、third-party sharing、user choice、access/edit/deletion、data retention、data security、policy change、do-not-track、international/specific audiences、other）是隐私维度标签的成熟起点；JURIX 2020 的 GDPR 映射可直接帮我们把标签对到 GDPR 条文。
**风险**：**NC 许可**——若 ClauseLens 有任何商业化可能，不能把 OPP-115 标注混进主训练集；建议只用于离线对照评测，并在 `eval/` 报告中单列。

---

## 7. CLAUDETTE（欧洲不公平条款检测）

**做什么**【文档】：EUI / 博洛尼亚大学等，用机器学习自动检测在线服务条款中“潜在不公平”的条款（依据欧盟消费者法）。
来源：https://arxiv.org/abs/1805.01217 （Artificial Intelligence and Law, 2019, https://doi.org/10.1007/s10506-019-09243-2 ），项目站 http://claudette.eui.eu/

- **数据**：50 份平台 ToS（YouTube、eBay、Facebook 等），**句级标注 8 类**不公平条款：Limitation of liability（责任限制）、Unilateral termination（单方终止）、Unilateral change（单方修改）、Content removal（删除内容）、Contract by using（使用即同意）、Choice of law（适用法律）、Jurisdiction（管辖）、Arbitration（仲裁）。
- **可下载**：LexGLUE 基准收录为 `unfair_tos`，Hugging Face `coastalcph/lex_glue`，**CC BY 4.0**【实测：HF API 返回 license:cc-by-4.0】，切分 5,532 / 2,275 / 1,607，约 9.41k 行。https://huggingface.co/datasets/coastalcph/lex_glue ，https://github.com/coastalcph/lex-glue
- LexGLUE 报告 RoBERTa 在 UNFAIR-ToS 上 μ-F1 95.8 / m-F1 81.6（README 表格）。
- **多语扩展**：2024 年论文把系统扩到德、意、波兰语，新语料 + 多种迁移策略；文中提到 150 份 ToS 中至少 68 份的德/意/波版本是英文原版的翻译。https://link.springer.com/article/10.1007/s10506-024-09398-7 （Open Access）
- 8 类名称【实测：读源码】取自 LexGLUE 预处理脚本的 label 列表（A/CH/CR/J/LAW/LTD/TER/USE）：https://github.com/coastalcph/lex-glue/blob/main/utils/preprocess_unfair_tos.py
- **解释能力**：后续工作用 memory network 给出“为什么不公平”的法律理由：https://iris.unimore.it/bitstream/11380/1215122/1/NLLP2020.pdf

**借用**：8 类直接对应我们 `control` / `liability` / `content` 维度的标签；UNFAIR-ToS 可作英文“霸王条款”分类器的训练与评测集（许可友好）。
**不足**：规模小（50 份）、只有英文和欧洲语言、无中文、只判句子不出整体评级。

---

## 8. 近年用 LLM 做条款分析/摘要的项目

| 名称 | 内容 | 来源 |
|---|---|---|
| PolicyGPT（2023） | 用 ChatGPT/GPT-4 零样本对隐私政策分段分类，在 OPP-115 等两套数据上测试 | https://arxiv.org/abs/2309.10238 |
| Text to Trust（2025） | 在 CLAUDETTE-ToS 上对比全量微调 BERT、LoRA（LLaMA/SaulLM）与 GPT-4o 零样本；结论：**全量微调的 precision/recall 平衡最好**，LoRA 内存省 3 倍 | https://arxiv.org/abs/2510.22531 |
| Is It Worth Using LLMs for Unfair Clause Detection in ToS?（2025） | LLM 与传统模型在不公平条款检测上的比较 | https://doi.org/10.1145/3769126.3769218 |
| ToS;DR DocBot | 生产环境 LLM 二分类器 + 人审 | https://github.com/tosdr/DocBot |
| APPSI-139（2026） | 139 篇英文 App 隐私政策、15,692 对改写平行句、36,351 细粒度标签，CAPP-130 同团队 | https://arxiv.org/abs/2604.27550 |
| 各类小型“ToS summarizer” | 多为 Flask/插件 demo，0–4★，如 kerisai/shorterms-client（MIT） | https://github.com/kerisai/shorterms-client |
| tosdr-ml（2020） | 早期 ToS;DR 机器学习实验，5★，已不活跃 | https://github.com/deep-learning-for-humans/tosdr-ml |

**启示**：(1) 纯零样本 LLM 在细粒度法律标签上不如微调小模型稳定（Text to Trust），我们的“规则 + 微调分类器融合”路线合理；LLM 更适合生成 `tldr_zh` 和“这对你意味着什么”的解释。(2) 社区里的 LLM 摘要工具大量存在但都是 demo 级、无证据定位、无评测——**“每个结论可点开看原文 + 有公开评测指标”本身就是差异化**。

---

## 9. 中国相关

### 9.1 监管侧“检测标准”
- **《App违法违规收集使用个人信息行为认定方法》**（国信办秘字〔2019〕191号，网信办/工信部/公安部/市场监管总局）：六类行为——未公开收集使用规则；未明示目的方式范围；未经同意收集使用；违反必要原则；未经同意向他人提供；未提供删除更正功能或未公布投诉举报方式。其中多条可在文本层面判断（如“隐私政策中没有收集使用规则”“未提供简体中文版”“以默认选择同意”“未逐一列出第三方 SDK”“未提供注销账号功能”）。
  来源：https://www.cac.gov.cn/2019-12/27/c_1578986455686625.htm
- **TC260-PG-20202A《App收集使用个人信息自评估指南》**（2020-07）：把上述六类拆成 6 个评估点、约 28 个检查子项（如 1.5“公开的收集使用规则是否完整”、2.1“是否逐一列出目的方式范围”、6.1“是否提供有效的注销用户账号功能”）。
  来源（转载）：https://web.tlawyer.cn/article/a55ba55be50dc595.html ；原发布方 https://www.tc260.org.cn/ 。**注意**：该指南声明版权属信安标委秘书处、禁止抄袭翻译，我们只引用检查点名称并注明来源，不复制全文。
- **《常见类型移动互联网应用程序必要个人信息范围规定》**（2021）：39 类 App 的“基本功能 + 必要个人信息”清单（如地图导航类：位置、出发地、到达地），并规定“不得因用户不同意提供非必要个人信息而拒绝基本功能”（第四条）。可用于“过度收集”判断。
  来源：http://www.gov.cn/zhengce/zhengceku/2021-03/23/content_5595088.htm
- 工信部 / 各地通信管理局会分批通报“侵害用户权益行为的 App”。本次未能抓到具体批次页面（检索结果为裁判文书等噪声），**未实测**；后续中文语料代理可从 https://www.miit.gov.cn/ 的通报栏目采集作为“负例站点”线索（只记录 App 名与问题类型）。

### 9.2 数据集与开源
- **CAPP-130**（NeurIPS 2023 Datasets & Benchmarks）：130 篇热门中文 App 隐私政策，法律专家标注，**52,489 条标注、20,555 条改写句**；提出 TCSI-pp 框架（RoBERTa 抽句 + mT5 改写），称优于 GPT-4。
  来源：https://papers.nips.cc/paper_files/paper/2023/hash/92225ec7e87b97a9e007ca6ab7944b14-Abstract-Datasets_and_Benchmarks.html ，https://github.com/EnlightenedAI/CAPP-130
  - 【实测：README】数据实践 11 类 + 2 个属性：信息收集 6,967、权限获取 1,852、共享与披露 4,740、使用 3,589、存储 1,360、安全措施 3,000、特殊人群 1,416、管理（用户权利）5,324、联系方式 712、授权与修订 1,049、停止运营 110；Important 20,555、Risks 1,815。已预切分 important / risk / topic 识别与改写子集（如 risk_identification 14,338/3,083/3,084）。
  - **许可**：README 徽章写 **Data CC BY 4.0、Code MIT**；GitHub API 识别仓库 LICENSE 为 Apache-2.0【实测】。数据许可明确为 CC BY 4.0，代码许可二者都宽松，使用时以 LICENSE 文件为准并署名。
  - **对我们最有用**：“Risks”句子标注可直接训练中文负面标签检测；11 个类别与 PIPL 第17条告知项高度对齐，可用于法域检查的“found/missing”判断。
- WxxW2002/APP_Privacy_Policy_analyze（MIT，大创项目，App 违规收集检测中的隐私政策分析部分，2★）：https://github.com/WxxW2002/APP_Privacy_Policy_analyze
- 学术：《基于〈个人信息保护法〉的App隐私政策合规性检测》（计算机工程）：https://www.ecice06.com/CN/10.19678/j.issn.1000-3428.0069804

**中国侧不足**：监管检测面向 App 运营者与执法，结果不以“给普通人看的评级”形式开放；CAPP-130 是研究语料而非产品；**没有面向网站、可输入域名即出结果、带用户投票的中文工具**。

---

## 10. 结论

### 10.1 需求是否存在
- **存在且长期未被满足**：ToS;DR 自 2012 年运营至今，插件 511★、三端上架、2026 年仍在活跃开发（https://github.com/tosdr ），说明“不读条款也想知道风险”的需求稳定；OTA 获联合国开发计划署等认定为数字公共品（https://opentermsarchive.org/en/ ），说明监管/公共侧也需要。
- 中国监管自 2019 年起持续治理 App 隐私政策（《认定方法》、TC260 指南、必要信息范围规定），说明**中文条款问题普遍、有明确的判断标准可依**，但面向用户的透明工具空缺。
- LLM 摘要类 demo 在 GitHub 大量出现但都停在玩具阶段（§8），需求热但没有可信产品。

### 10.2 我们的差异化
1. **中文优先**：唯一同时覆盖中文 ToS + 隐私政策的用户产品；语料用 CAPP-130（CC BY 4.0）+ 自抓中文站点，英文用 ToS;DR + UNFAIR-ToS + OTA。
2. **法域检查**：在“好/坏标签”之外，给出“按所在法域，文本中 找到 / 未找到 某必备告知项”（PIPL 第17条、GDPR 第13条、CCPA §7011 等，见 03 文档）。ToS;DR、PrivacySpy、CLAUDETTE 都没有这一层。
3. **低门槛交互**：输入 `baidu.com` 或任意 URL 即可，自动发现条款文档；SSE 真实进度；每个结论可点开原文证据。ToS;DR 需服务已被人工收录，否则 N/A。
4. **用户投票回流**：免登录对每个标签“认可/不认可”，形成数据闭环；ToS;DR 的投票/标注需注册且要 curator 审。
5. **可复现评测**：按站点划分、公开 per-tag P/R/F1 与 ToS;DR 等级一致率——同类 LLM demo 均无。

### 10.3 许可证注意
| 资源 | 许可 | 能否进主训练集 |
|---|---|---|
| ToS;DR points/cases | CC BY-SA 3.0+ | 可，需署名，衍生数据集 SA |
| UNFAIR-ToS（LexGLUE） | CC BY 4.0 | 可 |
| CAPP-130 数据 | CC BY 4.0 | 可 |
| OTA versions | ODC-By | 可（作原文语料） |
| OPP-115 / MAPP / APP-350 | NC 精神，商用需购买 | **仅离线评测，不进主训练集** |
| PrivacySpy | GPL-3.0 | 可参考 rubric；复用数据需遵守 GPL |
