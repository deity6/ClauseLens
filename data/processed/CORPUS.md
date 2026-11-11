# CORPUS — 条款全文语料清单

> 数字来自 `python scripts/corpus_stats.py`（写入 `corpus_stats.json`），不是手填的。获取时间：2026-11-07（北京时间 00:30–01:45）。
> 原始数据在 `data/raw/`（不入库），这里只放处理后的 jsonl。

| 来源 | 文件 | 站点/服务 | 文档 | 总字符 | 许可 |
|---|---|---|---|---|---|
| Open Terms Archive（19 个 `*-versions` 仓库） | `ota_docs.jsonl` | 790 个服务 | 2,544 | 128.6M | ODC-BY 1.0 |
| 自抓中文站点 | `cn_docs.jsonl` | 187 / 200 个站点 | 486 | 5.98M | 原站版权；仅供研究分析，不再分发全文 |
| CAPP-130（NeurIPS 2023） | `capp130_docs.jsonl` + `capp130_sentences.jsonl` | 130 个 App | 130 篇 / 38,889 句（25,089 句有标签） | 1.95M | 数据 CC BY 4.0，代码 Apache-2.0 |
| CA4P-483（EMNLP 2022） | `ca4p483_docs.jsonl` | 483 个 App | 483 | 3.90M | **仅限学术研究**，商用须原作者书面许可 |

## 1. Open Terms Archive — `ota_docs.jsonl`

- 字段：`service, doc_type, lang, text, source_repo, chars`
- 获取方式：`codeload.github.com/OpenTermsArchive/<repo>/tar.gz/refs/heads/main` → `scripts/build_ota.py`（只以文本方式读取 tar 里的 `.md`，不解压、不执行）。
- 仓库（19 个）：contrib、dating、france、france-elections、pga、p2b-compliance、cote-d-ivoire、genai-contrib、kenya、india、vlopses-gb/ie/ca/au/us、sante-numerique-france、dsa-reports、genai-eu、user-rights。没要 demo / sandbox / france-elections-experiment（测试用的仓库）。
- main 分支里每个 `<服务>/<文档类型>.md` 就是该文档的**当前版本**，所以不用翻历史。
- 语言（启发式判断）：en 1,940、fr 473、pt 60、de 25、es 18、zh 5、其他/unknown 23。
- 文档类型前几名：Terms of Service 690、Privacy Policy 618、Trackers Policy 124、Community Guidelines 99。
- 许可：ODC-BY 1.0，使用时须署名 Open Terms Archive；部分仓库要求连同贡献方一起署名，比如 france 要署 UFC-Que Choisir，dating 要署 Dating Privacy collective。各仓库 README 写有具体署名要求。

已知问题：
- 跨仓库去重键是「服务名 + 文档类型 + 前 2000 字」，共去掉 683 条重复。同一服务在不同地区仓库（如 vlopses-gb 和 vlopses-us）里文本略有不同的，会作为不同记录保留。
- 有些文档很长：DSA 系统性风险报告、多语言合集等，最长的约 96 万字符。字符数中位数是 28k。训练前建议按长度截断或分段。
- `service` 是 OTA 的服务名（如 "Facebook"），不是域名。要和 ToS;DR / `sites.jsonl` 对齐，还得做一层映射。
- 语言判断只靠停用词，混合语言的文档可能判错。

## 2. 中文站点自抓 — `cn_docs.jsonl`（差异化重点）

- 字段：`domain, name, doc_type(privacy/terms/other), url, title, anchor, text, chars, sha1, fetched_at, render`
- 站点清单：`scripts/cn_sites.py`，200 个中国主流站点/App，覆盖电商、社交、视频、出行、招聘、银行、运营商、AI 等。每个站点带一份「可信主机后缀」白名单，例如阿里系条款统一放在 `terms.alicdn.com`。
- 流程（`scripts/harvest_cn.py`）：
  1. 抓首页，从锚文本里找隐私政策、用户协议、服务条款等链接；
  2. 找不到时，用 anysearch 搜「站名 + 隐私政策 site:域名」等，只接受白名单内的 URL；
  3. 还找不到，就试常见路径（`/privacy`、`/agreement`、`/terms` 等）；
  4. 抓取后提取正文，再按长度、中文占比、条款用语密度做校验；
  5. 静态抓取失败的站点，用 `--render`（无头 Chromium）再跑一轮。
- 抓取约束：每个主机至少间隔 1 秒；单次读取超时 20 秒，整页下载上限 60 秒；单页不超过 5MB；只允许 http(s)，每一跳重定向都检查是否指向内网地址（防 SSRF）；不登录、不处理验证码。
- 结果：**187 / 200 个站点成功**，486 篇（privacy 258、terms 206、other 22），其中 86 篇来自渲染模式。
- 失败记录：`data/raw/cn/failures.jsonl`（逐 URL 记阶段和原因）。原始 HTML 在 `data/raw/cn/html/<domain>/`。被剔除的新闻/博客页记在 `data/raw/cn/rejected.jsonl`。

仍失败的 13 个站点及主要原因：

| 原因 | 站点 |
|---|---|
| 渲染后正文仍过短（条款在 App 内或要登录才能看） | 微云、番茄小说、同程旅行、迅雷、招商银行、曹操出行、阅文集团、36氪 |
| 反爬（HTTP 432）/ 首页无链接 | Trip.com |
| 候选全是登录页或帮助页 | 喜马拉雅、赶集网、BOSS直聘 |
| DNS 失败 / 链接失效 | 圆通 |

已知问题：
- **子产品文档混入**：搜索补链只要求域名在集团白名单内，所以会抓到同集团其他产品的条款。例如 `baidu.com` 下收进了「百度关怀版」「百度手机卫士」的隐私政策，`taobao.com` 下收进了 SDK 隐私政策。`title` 字段能看出是哪个产品。做「站点级」评分前，需要按标题筛出主产品的文档。
- 有 11 篇文本被多个站点共用（同集团同一份政策，如百度地图和百度百科），`sha1` 字段相同。按站点划分 train/test 时，要把共享 sha1 的站点放进同一侧，否则会泄漏。
- 正文提取靠启发式，可能残留少量导航文字或页脚。`doc_type` 按锚文本/标题判断，「个人信息共享清单」「SDK 目录」这类附属文档也可能被归为 terms 或 privacy。
- 一次性快照，没有版本历史。条款会更新，`fetched_at` 是唯一的时间锚点。
- 版权归各站点所有。本语料只用于研究分析和模型训练，不对外再分发全文。

## 3. 公开中文隐私政策数据集

搜索关键词：「CAPP-130」「中文隐私政策 数据集 github」「Chinese app privacy policy corpus」等。找到两个可用的数据集：

### CAPP-130 — `capp130_docs.jsonl`、`capp130_sentences.jsonl`
- 来源：github.com/EnlightenedAI/CAPP-130（NeurIPS 2023 Datasets & Benchmarks）。下载到 `data/raw/datasets/CAPP-130/repo.tgz`，用 `scripts/build_cn_datasets.py` 转换。
- 内容：130 篇中文 App 隐私政策原文（`Original_policies`），以及逐句标注（`Annotation`）。标注有 13 类数据实践，包括信息收集、权限获取、共享披露、存储、安全、特殊人群、风险等，另有法律专家写的改写句。
- 许可：README 写明数据为 **CC BY 4.0**、代码为 Apache-2.0，允许研究使用（须署名）。
- 注意：句子级标签可以直接拿来训练或评测中文识别器，但它的标签体系和我们的 taxonomy 不同，需要做映射。部分 App（如 12306、58同城）和自抓语料重叠，划分时要按站点合并。

### CA4P-483 — `ca4p483_docs.jsonl`
- 来源：github.com/zacharykzhao/CA4P-483（EMNLP 2022，Fine-grained Chinese Software Privacy Policy Dataset）。下载到 `data/raw/datasets/CA4P-483/repo.tgz`。
- 内容：483 篇 Android App 隐私政策 HTML，已转成纯文本；`app` 字段取 Apkid，即包名。逐段的序列标注（`annotation_data/*.json`）保留在 raw 里，还没转换。
- 许可：**仅限学术研究**，任何商用都须先取得第一作者书面许可，再分发时要保留许可并注明来源。如果 ClauseLens 以后要商用或公开发布模型，不能用这份数据，或者需要先取得授权。
- 注意：以长尾小 App 为主（如「美V聊天」），和主流站点清单基本不重叠，更适合做预训练或扩充负例。

其他候选：ylqianbj/CPP-130-Chinese-privacy-policy-dataset 没有许可证，未下载。

## 4. 复现

```
# bash，逐行执行（下载和抓取都很耗时，建议放后台）
python scripts/build_ota.py                 # 需先把各 OTA tarball 放到 data/raw/ota/<repo>/repo.tgz
python scripts/harvest_cn.py --workers 12   # 断点续跑：data/raw/cn/done.txt
python scripts/harvest_cn.py --retry-failed --render --chrome <chromium 路径> --workers 6
python scripts/build_cn_datasets.py
python scripts/corpus_stats.py --dedupe
```
