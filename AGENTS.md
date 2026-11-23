# AGENTS.md — ClauseLens 条款透镜

> 给所有参与本项目的 agent（主代理 / 子代理 / 审查代理）读的总纲。先读这个，再动手。

## 1. 项目一句话

用户输入一个网站（`baidu.com` 模糊 / `https://www.baidu.com/duty/` 精准），ClauseLens 找到它的
服务条款、隐私政策等文档，抽取关键条款，给出**等级（A–E）+ 分数 + 标签 + 原文证据 + 所在法域合规检查**，
并允许用户对每个标签投票「认可 / 不认可」，回流成数据。

目标用户：不读条款的普通人。**界面写用户正在做的事，不写实现原理；每个结论都能点开看原文。**

> **文档双语**：README 有中英两版（README.md 默认展示，顶部互相有切换链接）。改中文版必须同步改 README.en.md，别只改一边。

## 2. 目录约定

```
AGENTS.md            ← 本文件（总纲、分工、流程、红线）
docs/
  research/          ← 调研产出：同类项目、条款模板、各国法规要点
  design/            ← 标签体系、评分模型、前端设计说明
  reviews/           ← 审查代理的报告（每轮一份，带日期）
  PROGRESS.md        ← 进度日志：做了什么、还差什么、已知问题
data/
  raw/               ← 抓取原始数据（不入库，.gitignore）
  processed/         ← 清洗后的数据集（jsonl），train/test 划分在这里
scripts/             ← 数据采集、清洗、训练、评测脚本（可单独运行）
backend/clauselens/  ← Python 后端：发现 → 抓取 → 抽取 → 分段 → 识别 → 评分 → 法域检查
eval/                ← 评测脚本与报告（指标必须由脚本算出，不手填）
frontend/            ← React + Vite + motion 前端
```

## 3. 流水线（后端）

**详细流程图与逐段代码对照见 `docs/design/pipeline.md`**（含每个节点的 `文件:行号`、阈值表和五种典型输入的走法）。这里只列骨架：

| 阶段 | 代码 | 输入 → 输出 |
|---|---|---|
| ① 解析输入 | `net.parse_query()` | 用户字符串 → `Query{mode: fuzzy/precise, domain, url}`；有 path 即 precise |
| ② 编排 | `pipeline.analyze()` | 缓存 → registry → 三条岔路（precise / 有主域快照 / 翻首页+补探）→ 抓取循环 |
| ③ 发现文档 | `discover.*` | 首页 `<a>` 打分（`find_candidates`）、兄弟路径（`sibling_paths`）、并发探 34 条常见路径（`probe_paths`） |
| ④ 抓取 | `net.fetch()` | 安全抓取：5MB / 20s 上限、SSRF 校验、DNS 重绑定防护、`CLAUSELENS_EGRESS` 出口回退 |
| ⑤ 提取 | `discover.extract_text()` | HTML → 正文；`<noscript>` 兜底、大页面先剥 script |
| ⑥ 渲染兜底 | `render.Renderer` | 正文 < 400 字（纯前端路由站）时用无头 Edge 执行 JS，一次分析最多 3 页、复用浏览器 |
| ⑦ 判据 | `discover.looks_like_policy()` | ≥150 字 + 关键词密度（短页面要求更密），不是字数硬门槛 |
| ⑧ 分句 | `detect.split_sentences()` | 正文 → 句子（8–1200 字） |
| ⑨ 识别 | `detect.detect()` + `taxonomy.py` | **按句判语言**→中英分组→规则+模型融合→`provisional` 标记 |
| ⑩ 评分 | `score.score()` | 标签 → 0–100 + A–E + 六维；`provisional` 置信度 ×0.5 |
| ⑪ 法域 | `jurisdiction.py` | 域名/文本 → CN/EU/US… + 必备项检查（只报找到/未找到） |
| ⑫ 对外 | `api.py` / `__main__.py` | SSE（`/api/analyze`）＋命令行（`python scripts/query.py <域名>`） |

当前代码里**没有** `query.py` / `fetch.py` / `extract.py` / `segment.py`（那是早期设计稿）；
抓取在 `net.py`、提取与发现在 `discover.py`、分句在 `detect.py`。

## 4. 分工与并行（子代理）

主代理负责：拆任务、写接口契约、合并、最终验收。**大块的读写交给子代理，主代理只收结论**（省上下文）。

| 角色 | 何时派 | 产出 | 约束 |
|---|---|---|---|
| 调研代理 Researcher | 开工时 | `docs/research/*.md` | 每条结论带来源 URL；区分「实测/文档声称」 |
| 数据代理 Harvester | 开工时，长跑 | `scripts/harvest_*.py` + `data/raw/` | 遵守对方限速（ToS;DR 1 req/s）；可断点续跑；只抓公开页面 |
| 中文语料代理 | 开工时 | 中文站点条款语料 + 人工标注小集 | 不登录、不绕反爬；抓不到就记录失败原因 |
| 后端/模型代理 | 契约定好后 | `backend/` + `scripts/train_*.py` | 模块单测可跑；训练/测试按**站点**划分，禁止同站泄漏 |
| 前端代理 | 契约定好后 | `frontend/` | 遵守 `docs/design/frontend.md`；交付前自己截图看形态 |
| **审查代理 Reviewer** | 每个里程碑后 | `docs/reviews/YYYY-MM-DD-<主题>.md` | 只读不改；按 §6 清单逐条给结论 + 证据；严重问题打回 |

并行规则：
- 互不依赖的任务**同一条消息里一起派**；有依赖的等上游产出契约再派。
- 子代理之间通过**文件**交接（契约写在 `docs/design/`），不靠对话记忆。
- 子代理回报只给：改了哪些文件、怎么验证的、还剩什么问题。不贴大段代码。

## 5. 数据与评测纪律

- 语料来源：ToS;DR 公共 API（带人工标注的 case/point）、Open Terms Archive 公开版本库、自行抓取的中文站点。
- **≥1000 个站点**的条款文本或标注；每条记录保留来源 URL 与抓取时间。
- 划分：按站点（domain）做 train/test，固定随机种子，划分文件入库。
- 指标：每个标签的 precision / recall / F1，以及等级一致率（与 ToS;DR 人工等级对比）。报告由 `eval/` 脚本生成。
- 模型不确定时宁可「未发现」也不乱贴负面标签——**误伤一个友好网站比漏判更伤信任**；评分看 precision。

## 5.5 改完立刻验证（血的教训）

动过 pipeline.py / discover.py / net.py 之后，**不能只看 systemctl is-active**。至少跑一次：

    ssh <主机别名> 'cd ~/clauselens && .venv/bin/python /tmp/trace_srv.py'

**判据**：正常站点必须出现 fetch 阶段（通常还有 render）；只有 `resolve > discover` 且耗时
不到 2 秒 = 发现逻辑没跑（2026-11-12 就是缩进错误导致全站 found=0，半天才发现）。

前端同理：改完 build + 截图，别只信 npm run build 的退出码。

## 6. 审查清单（Reviewer 必查）

1. **正确性**：随机抽 10 个结果，标签与原文证据是否真的对应？有没有断章取义？
2. **泄漏**：test 集站点是否出现在 train 集？规则词表是否是看着 test 集调出来的？
3. **可复现**：从空目录按 README 能否跑出同样的指标？
4. **安全**：抓取是否有 SSRF 风险（内网地址、file://）？是否限制体积与超时？
5. **用户可读**：标签名普通人看得懂吗？每个负面标签有没有解释「这对你意味着什么」？
6. **前端**：等待动画是否反映真实进度？`prefers-reduced-motion` 是否尊重？移动端是否可用？
7. **合规表述**：法域检查只能说「未在文本中找到 X」，不得断言「违法」。

## 7. 红线

- 不提交凭据；`data/raw/` 不入库；git 作者邮箱用 GitHub noreply。
- 不主动 `git push`；部署前先给用户本地看。
- 抓取只碰公开页面，不登录、不绕验证码、不打对方限速。
- 结论用词：「条款写明」「未找到」，不写「违法」「诈骗」。本工具不是法律意见，页面要有免责声明。
- 改文件先读，定点修改；写文件 UTF-8 无 BOM + LF。
