# 轻量 SPA 渲染方案实测：只要最终 HTML，在 908 MB 机器上跑得动

> 调研 + 实测日期：2026-11-12
> 机器：新加坡 AWS `<主机别名>`（t3.micro，2 vCPU / 908 MB / 4 GB swap / Ubuntu 26.04）
> 被测服务：ClauseLens（`systemctl status clauselens`，常驻 ~174 MB）
> 结论一句话：**用 Lightpanda 1.0.0 的 CLI 子进程方式，实测 48–184 MB / 1 个进程 / 1.9–4.8 s，
> 三个靶站全过；原 Playwright 是 537–685 MB / 7 个进程。** Notion 这类站它渲染不出来，
> 用 Playwright `--single-process` 兜底（314–510 MB，仅失败时启动）。

---

## 0. 速览

| | 进程树 RSS 峰值 | 进程数 | 单页耗时 | 三站 | 泛化六站 |
|---|---|---|---|---|---|
| **Lightpanda CLI（推荐）** | **48.2 / 118.2 / 81.6 MB** | **1** | **1.9 / 2.6 / 4.8 s** | 3/3 | 5/6 |
| Playwright 现状（chromium 143 headless） | 537.4 / 684.7 / 617.9 MB | 7 | 5.9 / 5.7 / 5.3 s | 3/3 | 6/6 |
| Playwright `--single-process`（兜底配置） | 313.7–359.5 MB（notion 509 MB） | 2 | 3.1–4.9 s | 3/3 | 6/6 |
| Obscura 0.2.6（Rust，2026） | 141.7 / 202.1 / 183.1 MB | 4 | 8.8 / 8.9 / 14.1 s | 3/3 | 6/6 |
| jsdom 31 / happy-dom 21 | 147–191 MB | 1 | 10–12 s | 2/3 | — |
| Splash（docker） | 328 MB（cgroup） | — | 7.4–9.6 s | 2/3 | — |
| wkhtmltopdf 0.12（docker） | 13–70 MB | — | ~9 s | 0/3 | — |

三站 = `cloud.doulor.cn/privacy`（Vue）、`lobehub.com/privacy`（Next.js + CF）、`ow.blizzard.cn`（网易 Vue，找条款链接）。
泛化六站另加 `taobao.com`、`zhihu.com/term/privacy`、`notion.com/privacy`。
Playwright 那两行的「6/6」是合并结果（三站用 `pw-shell`，另三站用 `pw-single`）；
Lightpanda 的 5/6 只在 `notion.com` 上失败。

**相对现状的账**（908 MB 机器，基线已用 ~366 MB：clauselens 174 MB + Caddy + docker 空转）：

- 现状 Playwright 峰值 537–685 MB → 总占用 903–1051 MB，**必然吃 swap**（实测峰值 swap 72 MB，可用内存一度掉到 184 MB）。
- 换 Lightpanda 后峰值 48–184 MB → 总占用 414–550 MB，**留 350 MB 以上余量**。
- 换 Obscura 峰值 142–349 MB → 也够，但慢 2–3 倍，且每页固定等 8 s。
- 换 jsdom/happy-dom：省不了多少内存（100–190 MB），还得在 Python 里管一个 Node 子进程，**且 doulor 这种站拿不到**。

> ⚠️ **口径提醒（本报告动手期间仓库变过一次）**：我测到一半时，另一路已经把
> `backend/clauselens/render.py` 改成 `--single-process`（commit `814c688`，"480→280MB，失败自动回退多进程"）。
> 所以「现状」有两个口径：
> **(a) 任务开头给的全量配置**：537–685 MB（我复现出来的数，见下表的 `pw-shell` 行）；
> **(b) 仓库当前（commit 814c688）**：单进程 280–340 MB，我实测同配置 doulor 313.7–337.6 MB（3–4 个进程，
> 比那一路报的 280 MB 略高，因为我的采样把 `--js-flags` 之外的其它进程也算进去了）。
>
> **对 (b) 而言 Lightpanda 仍然是明显更好的一档**：48–118 MB（省 2.4–5.8 倍）+ 没有单进程崩溃风险 +
> 少一次「崩了再重试」的 3 秒，而且 doulor 那页还快 1 s 左右。**结论不变，只是收益从「省 5–11 倍」变成「省 2.4–5.8 倍」。**

---

## 1. 怎么测的（方法与判据）

### 1.1 判据：不只看「有没有输出」，看项目自己的判据

每个方案拿到的 HTML 都喂给项目里的同一套函数（`PYTHONDONTWRITEBYTECODE=1`，只 import 不改代码）：

```python
sys.path.insert(0, "backend")
from clauselens import discover
title, text = discover.extract_text(html)
discover.looks_like_policy(text)
```

**三站的通过判据**（`scripts/bench/bench.py` 每行输出 `text_len` / `is_policy` / `policy_links`，
通过与否按下面这条线判，不是看「有没有输出」）：

| 站 | 判据 | 依据 |
|---|---|---|
| `cloud.doulor.cn/privacy` | 正文 ≥ 400 字且 `looks_like_policy` | 静态只有 12 字，渲染后 Chromium 得 1271 字 |
| `lobehub.com/privacy` | 正文 ≥ 10000 字且 `looks_like_policy` | 渲染后 17631 字；静态被 402 挡 |
| `ow.blizzard.cn` | 首页渲染结果里能捞到 ≥1 条条款/隐私链接 | 首页本身不是条款（656 字），价值在链接 |

另外把「渲染出来的链接」也记下来了（`<a href>` 里命中 `隐私|条款|协议|policy|terms|legal`），
因为 ClauseLens 的 SPA 兜底第一步就是**从渲染后的首页找条款入口**，光有正文不够。

### 1.2 内存：进程树 RSS 峰值，不是主进程

上一轮的教训就是「只测主进程会低估 3–5 倍」。采样器 `scripts/bench/proc_rss.py`：

- 每 80 ms 扫一次 `/proc/*/stat`，按 `ppid` 做闭包，从 root pid 往下把**整棵树**的 `/proc/<pid>/statm` RSS 累加；
- 再按 `cmdline` 子串兜底（父进程先死时子树会被 reparent 到 1，只跟 ppid 会跟丢）；
- 同时记 PSS（`/proc/<pid>/smaps_rollup`，共享库只算一次）、`VmSwap`、以及系统 `MemAvailable` 最低值；
- 峰值那一刻顺手记下**每个进程各占多少**，所以能说出「谁在吃内存」。

实测这条很重要，Playwright 的账是这样的：

```
pw-single  doulor  313.7 MB  2 procs = ['chrome-headless:207MB', 'MainThread:106MB']
pw-shell   doulor  537.4 MB  7 procs（chrome + gpu + zygote + 3×renderer + node driver）
```

**Node driver（`MainThread`，Playwright 的 driver 进程）自己就吃 100–130 MB**——
上一轮量的 482.7 MB 里有一大块不是 Chromium，是那个 driver。所以「换 Playwright 生态里的别的客户端」
（pyppeteer / selenium）省不下这个钱，它们只是换了个 driver（见 §3.8）。

### 1.3 操作上的两个坑（先说，免得别人踩）

1. **这台机的 `/tmp` 是 tmpfs（455 MB，占内存）**。一开始把 180 MB 的 lightpanda 二进制放在 `/tmp`，
   等于白吃 180 MB 物理内存。所有测试物料都挪到了 `~/bench/`（走磁盘）。
2. 每个候选都是**串行**跑的（中间 sleep 2 s），跑完 `killpg` 整个进程组，并复查 `free -m`。
   并行跑两个 Chromium 会互相把对方挤进 swap，测出来的数没意义。

---

## 2. 逐方案结论

### 2.1 Lightpanda 1.0.0（重点）

**能不能用**：能。三站全过，泛化抽检 5/6。

**它是什么**：Zig 写的、从零实现的无头浏览器，V8 15.5.35.13 当 JS 引擎，**没有图形渲染管线**
（这是它省内存的根本原因：没有布局/绘制/合成，只有 DOM + JS + 网络）。

**成熟度**（实测核过，不是抄宣传）：

| 项 | 值 |
|---|---|
| 版本 | 1.0.0（2026-10-02 出 beta，见 [1.0 公告](https://lightpanda.io/blog/posts/lightpanda-1-0)） |
| 仓库 | [lightpanda-io/browser](https://github.com/lightpanda-io/browser)，41,899 star，90 open issue，**最后 push 2026-11-11**（昨天） |
| 一致性 | 过 1,739,845 个 Web Platform Tests 子测试，约 Chrome 的 80%；差距主要在 CSS/editing/SVG（它本来就不画） |
| 二进制 | **有 Linux x86_64**（也有 aarch64 / macOS），glibc 链接，单文件 188 MB，**零运行时依赖** |
| 安装 | `curl -fsSL https://pkg.lightpanda.io/install.sh \| bash -s 1.0.0`；或 `pip install lightpanda`（1.0.3，75 MB wheel，**内含二进制**）；或 docker |
| 接口 | CLI `fetch --dump html/markdown/…`、CDP server（`serve`，Playwright/Puppeteer/Selenium 都能连）、WebDriver BiDi、MCP、Python SDK |
| 安全 | 1.0 起默认强制 CORS；`--block-private-networks` / `--block-cidrs` / `--block-urls` / `--obey-robots` |

**JS 支持度：够跑 Vue/React 的 hydration 吗？** 实测答案是「大多数够」：

| 站 | 技术栈 | Lightpanda 结果 | Chromium 对照 |
|---|---|---|---|
| cloud.doulor.cn/privacy | Vue 3 + Vite（ESM） | ✅ 1271 字，**与 Chromium 逐字一致** | 1271 字 |
| lobehub.com/privacy | Next.js（React Router 流式） | ✅ 17631 字（完全一致） | 17631 字 |
| ow.blizzard.cn | 网易 Vue 站 | ✅ 656 字 + 16 链接（含 3 条隐私链接） | 656 字 + 16 链接 |
| taobao.com | 重 React/rax | ✅ 8018 字 + **1874 链接**（与 Chromium 一致到条数） | 8020 字 + 1874 链接 |
| zhihu.com/term/privacy | React | ✅ 18331 字（完全一致） | 18331 字 |
| notion.com/privacy | Next.js（重客户端） | ❌ 88 字，0 链接 | ✅ 214 字 + 6 链接（含 2 条隐私链接） |

**它到底卡在哪（具体，不是"支持不全"）**：

1. **`notion.com` 渲染不出来**——8.15 s 后拿到的还是空壳（88 字）。同类重客户端框架的站会有零星失败，
   这是无布局引擎路线的固有代价；**必须留 Chromium 兜底**，否则会退化成「某些站永远抓不到」。
2. **iframe / worker / 样式表默认不加载**（0.4.0 起 opt-in，`--load-resources iframe|worker|stylesheet|image`）。
   靠 iframe 承载正文、或 hydration 依赖 Worker 的站会拿到空壳。实测 `--load-resources stylesheet`
   是必开的（见下一条），iframe 只在个别站需要。
3. **不载样式表时，`display:none` 的菜单/横幅会混进正文**。实测：默认配置下 doulor 的正文 4411 字（英文版），
   加上 `--load-resources stylesheet` 后变成 1271 字——和 Chromium 的 `extract_text()` 输出**逐字相同**。
   所以 `--load-resources stylesheet` 不是可选项。
4. **不能伪装成 Mozilla**：`--user-agent "Mozilla/5.0 …"` 直接 `fatal: invalid user-agent (err=Reserved,
   hint=must be printable ASCII and can't contain Mozilla)`。默认 UA 是 `Lightpanda/1.0`，可用
   `--user-agent-suffix` 追加。**项目的 `net.UA` 传给它会让进程起不来**——这是接入时最容易踩的一脚。
   反过来说：拿 `Lightpanda/1.0` 去打 Cloudflare（lobehub）居然没被挡，三站都 200。
5. **语言标签要显式给**：`--locale` 默认 `en-US`，同时决定 `navigator.language` / `Accept-Language` / `Intl`。
   不给的话 doulor 返回**英文版**（4411 字），给 `--locale zh-CN` 才是中文 1271 字。
   注意 `--http-header "Accept-Language: …"` 单独改不动它（站点读的是 `navigator.language`）。
6. **`--wait-until` 必须显式给 `networkidle`**，默认是 `load`：Vue 站在 `load` 之后就返回，hydration 还没跑完
   → 实测 doulor 只有 12 字（就是静态空壳）。加 `--wait-until networkidle --wait-ms 8000` 后 1.99 s 拿到 4411 字。
   `--wait-ms` 单独给没用（它只是 wait-until 的封顶）。
7. **`--strip-mode shell/clutter` 会连链接一起剥掉**：实测 doulor 加 `--strip-mode shell` 后正文还在，
   但 `policy_links` 从 `['/terms','/privacy']` 变成空——**找条款入口的站别用 strip**。
8. issue 里已知的坑（都已关闭，但说明历史）：[#2402](https://github.com/lightpanda-io/browser/issues/2402)
   CDP 命令在持续 JS 活动的页面上卡 15–20 s；[#3359](https://github.com/lightpanda-io/browser/issues/3359)
   `performance.getEntriesByType('resource')` 返回空导致 CDP 侧 networkidle 检测失效；
   [#2460](https://github.com/lightpanda-io/browser/issues/2460) 长跑页面的节点泄漏。
   **还开着的**是 [#4179](https://github.com/lightpanda-io/browser/issues/4179)：iframe 在 CDP 下拿不到子上下文
   （2026-10-26）——用 iframe 的站要注意。
   [#1798](https://github.com/lightpanda-io/browser/issues/1798)（"React/Vue SPA 是不是根本没法跑"）2026-09-15 已关闭。

**三种用法实测对比**（同一台机，同一批站）：

| 用法 | 启动 | 三页（doulor privacy + terms + blizzard） | 峰值 | 说明 |
|---|---|---|---|---|
| CLI 每页一个子进程 | ~0.1 s | 逐页 1.9 / 1.7 / 4.8 s，合计 8.6 s | 单页 48–82 MB | **推荐**：进程退出即还内存，无状态、无泄漏 |
| `serve` + Playwright CDP 复用 | ~0.4 s | 逐页 2.0 / 1.7 / 4.9 s，合计 10.0 s | 222.9 MB（含 driver） | 需要 `wait_for_selector` 之类交互时才用；多带一个 Playwright driver |
| `pip install lightpanda` SDK | 0.19 s | 1.24 / 4.01 / **15.95** s | 125.9 MB（三页共用一个进程） | API 最顺手，但 `wait_until="networkidle"` 没有封顶，blizzard 等了 16 s |

> CLI 的时间是 `--wait-ms 8000` 封顶的；SDK 那次 `goto(wait_until="networkidle", timeout=25000)`
> 在 blizzard 上一直等到 15.95 s。**接入时把 wait 封顶**，否则 60 s 的分析预算会被一页吃掉。

### 2.2 `chromium --single-process`（Playwright 内部压内存）

**能不能用**：能，六站全过（包括 Lightpanda 失败的 notion）。但它是「把 7 个进程塞进 1 个」，不是变轻。

> 这套组合**已经进仓库了**：commit `814c688` 把 `render.py` 改成默认 `--single-process`、失败自动回退多进程。
> 下面是我独立复现的数据，结论与该 commit 一致（单进程确实是唯一有效的开关），只是我的采样把
> Playwright 的 node driver 也算进树里，所以数字比它报的 280 MB 略高。

| 配置 | doulor | lobehub | blizzard | notion | 进程数 |
|---|---|---|---|---|---|
| 现状（`--disable-gpu --no-sandbox`，chromium 143 headless） | 537.4 MB | 684.7 MB | 617.9 MB | — | 7 |
| 加一组压内存 flags（不合并进程） | 548.4 MB | 652.0 MB | 554.7 MB | — | 5 |
| ＋`--single-process` | **337.6** | **450.6** | **336.8** | 509.5 | **2** |
| ＋更狠的 V8 堆上限（64 MB）+ single-process | 425.9 ✗ | — | 436.3 ✗ | 650.5 ✗ | 4 |
| ＋`--in-process-gpu`（不合并 renderer） | 480.4 ✗ | — | 434.2 ✗ | 676.2 ✗ | 4 |

结论：**`--single-process` 是唯一真正把 Chromium 压下来的开关（-30~40%），再叠别的 flag 反而变差**
（V8 堆上限掐太死会让它退化/多起进程；`--in-process-gpu` 也不划算）。
坑：`--single-process` 是 Chromium 不承诺支持的配置，社区里新 headless 下崩的案例不少
（[puppeteer-sharp#2512](https://github.com/hardkoded/puppeteer-sharp/issues/2512)、[pptr 排障页](https://pptr.dev/troubleshooting)），
本机 6 站没崩，但**只能当兜底，不能当主路径**。

### 2.3 Obscura 0.2.6（2025–2026 的 Rust 新方案）

**能不能用**：能，**泛化六站 6/6**（唯一一个连 notion 都拿到的轻量方案），CDP 兼容，单文件 43 MB（no-render 版 60 MB 二进制）。
但**慢**：每页固定 `--wait 8`，实测 8.8 / 8.9 / 14.1 / 9.8 s；内存 141.7 / 202.1 / 183.1 / 349.4 MB，4 个进程。

- 安装：`obscura-x86_64-linux-no-render.tar.gz`（43 MB）解包即用，零依赖；有 `serve`(CDP) / `fetch` / `scrape` / `mcp`。
- 支持度：doulor 拿到 4411 字（英文版，没找到 locale 开关）、notion 870 字（比 Lightpanda 强）、
  blizzard 718 字 + 3 条隐私链接。
- 坑：出的是英文版（无 `--locale`）；默认 `--wait` 是「5 s 自适应」，我显式给 8 s 才稳定；
  4 个进程、峰值 349 MB 已经接近 Chromium `--single-process` 的水平，"轻"的优势没那么大。
- 判断：**可以作为第二备选（比 Chromium 稳定省内存），但作为主路径不如 Lightpanda**（快 3–5 倍、省一半内存）。

### 2.4 jsdom / happy-dom（只跑 JS 引擎，不跑浏览器）

**能不能用**：部分。**doulor 拿不到（12 字），lobehub 和 blizzard 能拿到。**

| 方案 | doulor | lobehub | blizzard | 内存 | 耗时 |
|---|---|---|---|---|---|
| jsdom 31.0.0 | ❌ 12 字 / 0 链接 | ✅ 17631 字 | ✅ 545 字 + 3 条隐私链接 | 147.2–191.0 MB | 10.4–11.7 s |
| jsdom + IntersectionObserver/ResizeObserver/matchMedia 垫片 | ❌ 12 字 | ✅ 17631 | ✅ 545 字 + 3 链接 | 142.7–191.0 MB | 10.3–11.7 s |
| happy-dom 21.0.4 | ❌ 12 字 / 0 链接 | ✅ 17631 | ✅ 540 字 + 3 链接 | 107.8–115.7 MB | 9.9–10.5 s |

- **为什么 doulor 失败**：Vite 生产构建是 `<script type="module">`，jsdom 不执行 module script（happy-dom 同理）。
  这是硬伤，不是加垫片能解决的。lobehub 能拿到 17631 字是因为它**服务端就渲染好了**（SSR），跟 JS 无关。
- 内存没优势：100–190 MB，跟 Lightpanda 一个量级（甚至更高），而 Lightpanda 是完整引擎。
- 架构代价：为了它要在 Python 服务里常驻一个 Node 子进程 + 一套跨语言协议；项目里 `net.UA`/`Page` 那套接口要重写。
- **判断：不值得走。** 如果非要"只跑 JS 引擎"，Lightpanda 就是这条路的最优解（它是 V8 + DOM，不是"浏览器"）。

### 2.5 Splash（scrapy 生态的渲染服务）

**能不能用**：部分。`render.html` 能直接返回渲染后 HTML（这点比 wkhtmltopdf 强），
但 doulor 拿不到（12 字），lobehub ✅ 17631 字，blizzard ✅ 562 字 + 3 条隐私链接。

- 内存：容器 cgroup 峰值 **328 MB**；耗时 8.8 / 7.4 / 9.6 s；启动 4.1 s。
- 安装：docker 镜像（`scrapinghub/splash`），要常驻一个 HTTP 服务 + 端口。
- 坑：内核是老 QtWebKit（跟 wkhtmltopdf 同源），ESM/现代语法跑不动；仓库**最后提交 2024-08-02**，两年没动。
- 判断：**比现状省一半内存，但慢、依赖容器、且照样吃不下现代 SPA**——不如 Lightpanda。

### 2.6 wkhtmltopdf / wkhtmltoimage

**能不能用**：**不能用**，两个层面都不行：

1. **它根本不能输出 HTML**（只能 PDF / PNG）。ClauseLens 的 `render()` 契约是返回 HTML 给
   `discover.extract_text()`；走它就变成「PDF → 抽文字」，判据、去噪、`<noscript>` 兜底全部作废。
2. **JS 支持跟不上**：实测 doulor 出 1209 字节的空白 PDF（抽文字 1 字节），blizzard 出 181 KB 但抽文字 1 字节；
   只有 lobehub 抽到 17805 字（那是 SSR 页面，不需要 JS）。
   QtWebKit 2015 年废弃、2016 年移除，ES6 支持一直没补齐（[wkhtmltopdf 状态页](https://wkhtmltopdf.org/status.html)、
   [ES6 issue #4010](https://github.com/wkhtmltopdf/wkhtmltopdf/issues/4010)）。
- 内存倒是真省：容器 cgroup 峰值 70 / 13 / 45 MB，~9 s/页。省内存但拿不到东西，等于 0 分。

### 2.7 pyppeteer / selenium（换个客户端，不换引擎）

**本质还是 Chromium，省不下来**。实测 pyppeteer 2.0.0 驱动同一个 Chromium 143：

```
pyppeteer + chromium 143, doulor: peak_rss 488.0 MB, 5 procs
  ['chrome:344MB', 'chrome:68MB', 'chrome:68MB', 'chrome_crashpad:3MB', 'chrome_crashpad:3MB']
```

比 Playwright 现状（537 MB）略低，比 Playwright `--single-process`（314–338 MB）**更差**；
而且 pyppeteer 自带的那份 Chromium 是 2021 年的（仓库最后提交 2024-06-29），selenium 只是把 driver 换成 chromedriver
（driver 也要 15–130 MB，跟 Playwright 的 node driver 同一量级）。
**能省的只有 flags，不是客户端**——flags 的最优组合见 §2.2 / §4。

### 2.8 其它 2024–2026 的轻量方案（扫过，没进实测）

- **Lightpanda Cloud**：托管的同类服务，按页计费；本地能跑就不必。
- **Camoufox / Patchright / nodriver**：都是「另一个 Chromium/Firefox 的变体」，内存跟 Chromium 同级别。
- **browserless / playwright-server（docker）**：把 Chromium 挪进容器，总内存不变，还多一层网络。
- **Reader/LM 型抽取服务（Jina Reader、Firecrawl）**：本质是把渲染外包出去，隐私和成本都不合适自建服务。

---

## 3. 对比表（三站 × 内存 × 耗时）

| 方案 | doulor（Vue） | lobehub（Next+CF） | blizzard（找链接） | 进程树 RSS 峰值 | 进程数 | 单页耗时 | 安装 |
|---|---|---|---|---|---|---|---|
| **Lightpanda CLI（推荐配置）** | ✅ 1271 字 | ✅ 17631 字 | ✅ 16 链接 / 3 条条款 | **48.2 / 118.2 / 81.6 MB** | **1** | **1.9 / 2.6 / 4.8 s** | 单文件 188 MB，或 pip 75 MB |
| Lightpanda（默认参数，不给 wait-until） | ❌ 12 字 | ✅ 17631 | ✅ 14 链接 | 47.2 / 79.1 / 73.5 MB | 1 | 0.9 / 1.1 / 4.3 s | 同上 |
| Lightpanda `serve`+CDP | ✅ 4411 字* | ✅ 17631 | ✅ 16 链接 | 52.2 / 116.8 / 88.7 MB | 1（+driver） | 3.3 / 3.8 / 4.4 s | 同上 |
| Lightpanda Python SDK | ✅ 1271 | ✅ 17631 | ✅（15.9 s） | 125.9 MB（三页） | 1 | 1.2 / 4.0 / 16.0 s | `pip install lightpanda` |
| Obscura 0.2.6 | ✅ 4411* | ✅ 17631 | ✅ 3 条条款 | 141.7 / 202.1 / 183.1 MB | 4 | 8.8 / 8.9 / 14.1 s | 43 MB tar |
| Splash（docker） | ❌ 12 字 | ✅ 17631 | ✅ 3 条条款 | 328 MB（cgroup） | — | 8.8 / 7.4 / 9.6 s | 镜像 + 常驻服务 |
| jsdom 31 | ❌ 12 字 | ✅ 17631 | ✅ 3 条条款 | 147–191 MB | 1 | 10.4–11.7 s | node + npm 46 MB |
| happy-dom 21 | ❌ 12 字 | ✅ 17631 | ✅ 3 条条款 | 108–116 MB | 1 | 9.9–10.5 s | node + npm |
| wkhtmltopdf 0.12 | ❌ 空白 PDF | ⚠️ 只能出 PDF | ❌ 空白 PDF | 70 / 13 / 45 MB | — | ~9 s | 158 MB 镜像 |
| pyppeteer 2.0（+chromium143） | ✅ | 未测 | 未测 | 488 MB | 5 | — | pip + 自带旧 Chromium |
| **Playwright 现状** | ✅ 1271 | ✅ 17631 | ✅ 3 条条款 | 537.4 / 684.7 / 617.9 MB | 7 | 5.9 / 5.7 / 5.3 s | 已装 |
| Playwright 全量 chromium（channel=chromium） | ✅ | ✅ | ✅ | 966.8 / 1031.1 / 1014.8 MB | 9 | 6.1 / 7.4 / 5.1 s | 已装 |
| Playwright + 压内存 flags | ✅ | ✅ | ✅ | 548.4 / 652.0 / 554.7 MB | 5 | 4.4 / 5.5 / 3.6 s | 已装 |
| **Playwright `--single-process`（兜底）** | ✅ | ✅ | ✅ | **337.6 / 450.6 / 336.8 MB** | **2** | 3.1 / 6.0 / 4.9 s | 已装 |

\* 4411 字是**英文版**的同一份条款（站点按 `navigator.language` 切语言；Lightpanda 需 `--locale zh-CN` 才是中文 1271 字）。

泛化抽检（不在三站里，用来看覆盖率）：

| 站 | Lightpanda（推荐配置） | Chromium `--single-process` | Obscura |
|---|---|---|---|
| taobao.com | ✅ 8018 字 + 1874 链接（184.4 MB / 4.3 s） | ✅ 8020 字 + 1874 链接（472.4 MB / 11.0 s） | — |
| zhihu.com/term/privacy | ✅ 18331 字（161.6 MB / 3.4 s） | ✅ 18331 字（447.4 MB / 5.7 s） | — |
| notion.com/privacy | ❌ 88 字（53.6 MB / 8.2 s） | ✅ 214 字 + 2 条隐私链接（581.7 MB / 7.9 s） | ✅ 870 字（349.4 MB / 9.8 s） |

---

## 4. 推荐：908 MB 上就这么接

### 4.1 结论

1. **主路径**：Lightpanda 1.0.0，CLI 子进程，每页一个进程，参数固定成下面这一串。
   三站全过，实测 48–184 MB / 1 进程 / 1.9–4.8 s。
   对比**任务开头的全量 Chromium 口径**（537–685 MB）省 5.8–11 倍内存、快 1.1–3.1 倍；
   对比**仓库当前的单进程口径**（commit 814c688，280–340 MB）仍省 2.4–5.8 倍，且不承担单进程崩溃风险。
2. **兜底**：Lightpanda 返回的正文仍 < 400 字（即"还是空壳"）时，才用 Playwright `--single-process`
   补一次，且**每次分析最多 1 次**、启动前检查 `MemAvailable ≥ 420 MB`。notion 这类站靠它。
3. **别做的**：把 `net.UA` 传给 Lightpanda（会 fatal）；用 `--strip-mode`（会丢链接）；
   给 Lightpanda 配 iframe/worker（除非目标站明确需要）。

### 4.2 安装（服务器上，二选一）

```bash
# A. 单文件（推荐：不碰项目 venv，不引入 Python 依赖）
curl -fsSL https://pkg.lightpanda.io/install.sh | bash -s 1.0.0     # → ~/.local/bin/lightpanda
# 想放别处：LIGHTPANDA_DIR=/opt/lightpanda bash -c 'curl -fsSL … | bash -s 1.0.0'

# B. 装进项目 venv（多 75 MB，但省掉 PATH 管理）
~/clauselens/.venv/bin/pip install lightpanda==1.0.3
```

实测体积：二进制 188 MB（`du -sh` 显示 180 MiB），`pip` wheel 75 MB（内含二进制），**无其它依赖**。
`/tmp` 是 tmpfs，**别装在 `/tmp`**。

### 4.3 参数（实测过的那一串）

```bash
lightpanda fetch --json --dump html "$URL" \
  --locale zh-CN \
  --wait-until networkidle --wait-ms 8000 \
  --load-resources stylesheet \
  --block-private-networks \
  --terminate-ms 25000
```

每一条的理由：

| 参数 | 为什么 | 不给的后果（实测） |
|---|---|---|
| `--json` | 拿 `http_status` + `content`，不用自己解析 HTML | 只有裸 HTML，状态码丢失 |
| `--dump html` | 要的就是 DOM 序列化 | — |
| `--locale zh-CN` | 决定 `navigator.language`/`Accept-Language` | doulor 返回英文版（4411 字 vs 1271 字） |
| `--wait-until networkidle` | 等 hydration 跑完 | doulor 只有 12 字（空壳），0 链接 |
| `--wait-ms 8000` | 给 networkidle 封顶，别让常驻活动的页面吃满预算 | blizzard 类站可能等到 15 s+ |
| `--load-resources stylesheet` | 让 `display:none` 的元素真的不可见 | 隐藏菜单混进正文（4411 vs 1271 字） |
| `--block-private-networks` | 浏览器这条路径本来绕过 `net.py` 的 SSRF 校验（见 `docs/reviews/2026-11-12-security.md` L7） | 内网/元数据地址可被页面请求 |
| `--terminate-ms 25000` | 硬截止，防死循环脚本 | 只能靠外面 `subprocess` 超时 |

### 4.4 替换 `render.py`：完整代码

保留原来的公开接口（`available()` / `unavailable_reason()` / `render()` / `Renderer` / `Budget`），
`pipeline.py` 一行都不用改。`Renderer` 现在自带两套后端：

```python
"""无头渲染：Lightpanda 为主、Chromium 单进程兜底。

实测（2026-11-12，t3.micro 908 MB）：
  Lightpanda 1.0.0  48.2 / 118.2 / 81.6 MB，1 进程，1.9 / 2.6 / 4.8 s（doulor / lobehub / blizzard）
  原 Playwright      537.4 / 684.7 / 617.9 MB，7 进程（其中 100–130 MB 是 node driver）
所以主路径换成 Lightpanda；它渲染不出来的站（notion.com 这类重客户端 Next.js）回落到
Chromium --single-process（313.7–359.5 MB，2 进程）。

为什么需要：很多站点对任何路径都返回同一份 index.html 空壳，正文只在浏览器执行 JS 后才出现。
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import threading

from .net import Page

MAX_RENDERS = int(os.environ.get("CLAUSELENS_MAX_RENDERS", "3"))
RENDER_TIMEOUT_MS = int(os.environ.get("CLAUSELENS_RENDER_TIMEOUT_MS", "25000"))
RENDER_IDLE_MS = int(os.environ.get("CLAUSELENS_RENDER_IDLE_MS", "1200"))

# ---- Lightpanda ----------------------------------------------------------
LP_BIN = os.environ.get("CLAUSELENS_LIGHTPANDA") or shutil.which("lightpanda") or ""
# 不能传 net.UA：Lightpanda 拒绝任何含 "Mozilla" 的 UA（启动即 fatal: invalid user-agent），
# 默认 UA 是 Lightpanda/1.0，这里只加后缀。
LP_UA_SUFFIX = os.environ.get("CLAUSELENS_UA_SUFFIX", " ClauseLens/0.1")
LP_LOCALE = os.environ.get("CLAUSELENS_LOCALE", "zh-CN")
LP_WAIT_MS = int(os.environ.get("CLAUSELENS_LP_WAIT_MS", "8000"))

# ---- Chromium 兜底 ------------------------------------------------------
PW_ARGS = [
    "--disable-gpu", "--no-sandbox", "--single-process", "--disable-dev-shm-usage",
    "--no-zygote", "--renderer-process-limit=1",
    "--blink-settings=imagesEnabled=false",
    "--js-flags=--max-old-space-size=96 --max-semi-space-size=2",
    "--disable-features=site-per-process,IsolateOrigins,Translate,BackForwardCache",
    "--disable-background-networking", "--disable-component-update", "--disable-breakpad",
]
MAX_PW_FALLBACK = int(os.environ.get("CLAUSELENS_PW_FALLBACK", "1"))   # 每次分析最多几次兜底
MIN_FREE_MB = int(os.environ.get("CLAUSELENS_MIN_FREE_MB", "420"))    # 不够就不冒险起 Chromium

# 全局只允许一个渲染任务在跑：908 MB 上两个 180 MB 还行，但两个 Chromium 一定互相挤死
_RENDER_LOCK = threading.Lock()
_disabled = False
_unavailable_reason = ""


def _lp_available() -> bool:
    return bool(LP_BIN) and os.access(LP_BIN, os.X_OK)


def available() -> bool:
    global _disabled, _unavailable_reason
    if _disabled:
        return False
    if _lp_available():
        return True
    try:
        import playwright.sync_api  # noqa: F401
    except Exception as e:
        _disabled = True
        _unavailable_reason = f"lightpanda 与 playwright 都不可用: {type(e).__name__}"
        return False
    return True


def unavailable_reason() -> str:
    return _unavailable_reason


def _mem_available_mb() -> float:
    try:
        for line in open("/proc/meminfo"):
            if line.startswith("MemAvailable:"):
                return int(line.split()[1]) / 1024
    except OSError:
        pass
    return 9999.0


_TAG = re.compile(r"<(script|style)\b.*?</\1>|<[^>]+>", re.I | re.S)


def _visible_text_len(html: str) -> int:
    """粗算正文长度，只用来判断「是不是还是空壳」，不参与判据。"""
    txt = _TAG.sub(" ", html)
    return len(" ".join(txt.split()))


class Renderer:
    """一次分析复用一个实例；Lightpanda 侧没有常驻状态，Chromium 侧按需启动。"""

    def __init__(self):
        self._pw = None
        self._browser = None
        self._ctx = None
        self._fallbacks = 0

    # ---------- 对外 ----------
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False

    def close(self) -> None:
        for obj, meth in ((self._ctx, "close"), (self._browser, "close"), (self._pw, "stop")):
            if obj is None:
                continue
            try:
                getattr(obj, meth)()
            except Exception:
                pass
        self._pw = self._browser = self._ctx = None

    def render(self, url: str, timeout_ms: int | None = None) -> Page | None:
        if not available():
            return None
        tmo = RENDER_TIMEOUT_MS if timeout_ms is None else max(4000, min(RENDER_TIMEOUT_MS, timeout_ms))
        with _RENDER_LOCK:
            page = self._render_lightpanda(url, tmo)
            if page is not None and _visible_text_len(page.text) >= 400:
                return page
            # 还是空壳（或 Lightpanda 不在）→ 用 Chromium 补一次，但要先确认内存够
            if not _lp_available():
                return self._render_chromium(url, tmo) or page
            if self._fallbacks >= MAX_PW_FALLBACK or _mem_available_mb() < MIN_FREE_MB:
                return page
            self._fallbacks += 1
            return self._render_chromium(url, tmo) or page

    # ---------- Lightpanda ----------
    def _render_lightpanda(self, url: str, tmo_ms: int) -> Page | None:
        cmd = [
            LP_BIN, "fetch", "--json", "--dump", "html", url,
            "--locale", LP_LOCALE,
            "--wait-until", "networkidle", "--wait-ms", str(LP_WAIT_MS),
            "--load-resources", "stylesheet",
            "--block-private-networks",
            "--user-agent-suffix", LP_UA_SUFFIX,
            "--terminate-ms", str(tmo_ms),
        ]
        try:
            p = subprocess.run(cmd, capture_output=True, timeout=tmo_ms / 1000 + 5)
        except (OSError, subprocess.TimeoutExpired):
            return None
        if p.returncode != 0:
            # 导航/等待失败（若加 --fail-on-http-error，HTTP 4xx/5xx 也会是 22）
            return None
        try:
            obj = json.loads(p.stdout.decode("utf-8", "replace"))
        except ValueError:
            return None
        html = obj.get("content") or ""
        if len(html) < 200:
            return None
        return Page(url, int(obj.get("http_status") or 200), "text/html; charset=utf-8", html)

    # ---------- Chromium 兜底 ----------
    def _start_chromium(self) -> None:
        from playwright.sync_api import sync_playwright
        self._pw = sync_playwright().start()
        for kw in ({"channel": "chromium"}, {}):      # channel="chromium" 才是完整 chromium
            try:
                self._browser = self._pw.chromium.launch(headless=True, args=PW_ARGS, **kw)
                break
            except Exception:
                continue
        if self._browser is None:
            raise RuntimeError("Chromium 起不来")
        self._ctx = self._browser.new_context(
            locale=LP_LOCALE, viewport={"width": 1440, "height": 1000})

    def _render_chromium(self, url: str, tmo_ms: int) -> Page | None:
        try:
            if self._ctx is None:
                self._start_chromium()
            page = self._ctx.new_page()
            try:
                page.route("**/*", lambda r: r.abort()
                           if r.request.resource_type in ("image", "media", "font") else r.continue_())
                resp = page.goto(url, wait_until="domcontentloaded", timeout=tmo_ms)
                try:
                    page.wait_for_load_state("networkidle", timeout=min(RENDER_IDLE_MS, tmo_ms // 3))
                except Exception:
                    pass
                page.wait_for_timeout(300)
                html = page.content()
                return Page(url, int(getattr(resp, "status", 200) or 200),
                            "text/html; charset=utf-8", html)
            finally:
                try:
                    page.close()
                except Exception:
                    pass
        except Exception:
            self.close()
            return None


class Budget:
    """一次分析里的渲染次数配额。"""

    def __init__(self, limit: int | None = None):
        self.limit = MAX_RENDERS if limit is None else limit
        self.used = 0

    def take(self) -> bool:
        if self.used >= self.limit:
            return False
        self.used += 1
        return True


def render(url: str) -> Page | None:
    """单页一次性渲染（会新起一个进程）。多次渲染请用 Renderer 复用。"""
    with Renderer() as r:
        return r.render(url)
```

行为对照（实测）：

| 场景 | 走的路径 | 实测 |
|---|---|---|
| doulor / lobehub / blizzard / taobao / zhihu | Lightpanda | 48–184 MB，1.9–4.8 s，正文与 Chromium 一致 |
| notion.com | Lightpanda 拿到 88 字 → Chromium 兜底 | 额外 314–510 MB、约 8 s，仅此一次 |
| Lightpanda 没装 | 直接 Chromium | 与现状等价 |
| 机器已经很紧张（可用 < 420 MB） | 不启动 Chromium，返回 Lightpanda 的结果 | 宁可少一个站，不把机器拖垮 |

**这段代码是照抄就能用的，不是伪代码**：`py_compile` 通过；并且在服务器上**原样**验证过一遍
（把项目包复制到 `/tmp/lptest` 再把这文件盖到 `render.py` 的位置，项目代码零改动）：

```
available= True
https://cloud.doulor.cn/privacy  4.6s  status=200  html=40282B  text=1271   # Lightpanda 路径
https://ow.blizzard.cn/          7.6s  status=200  html=288221B text=656    # Lightpanda 路径
https://www.notion.com/privacy   9.5s  status=401  html=76176B  text=214    # 走了 Chromium 兜底
```

（notion 那行 status=401 是 Notion 对无 cookie 请求本身的响应，Chromium 也是 401，但页面渲染出来了，
214 字里能捞到 2 条隐私链接——所以「兜底」这一步是有效的，不是白跑。）

### 4.5 用 SDK 的写法（如果不想管 PATH / 子进程路径）

```python
from lightpanda import Browser

browser = Browser(args=["--locale", "zh-CN", "--load-resources", "stylesheet"])
try:
    s = browser.new_session()
    r = s.goto(url=url, wait_until="load", timeout=25000)   # 别用 networkidle，没有封顶
    html = s.html()                                          # 或 s.links() 直接拿链接
    s.close()
finally:
    browser.close()
```

实测：启动 0.19 s，三页共用一个进程峰值 125.9 MB。
坑：`goto(wait_until="networkidle")` 在 blizzard 上一直等到 15.9 s（没有 `--wait-ms` 那种封顶），
**要么用 `load` + `wait_for_selector`，要么把 timeout 压到 10 s**。
另外 SDK 是在 Python 进程里 `Popen` 一个 `lightpanda` 子进程，所以 systemd 的 cgroup 记账是准的（会算进 `clauselens.service` 的内存）。

---

## 5. 如果必须留在 Playwright：实测过的压内存组合

（本机 6 站全过，是 Lightpanda 之外的兜底；**不是**主路径。）

```python
args = [
    "--disable-gpu",
    "--no-sandbox",
    "--single-process",              # 唯一真正有效的一条：7 进程 → 2 进程，-30~40%
    "--disable-dev-shm-usage",       # /dev/shm 在这台机只有 64 MB
    "--no-zygote",                   # 少一个 zygote
    "--renderer-process-limit=1",
    "--blink-settings=imagesEnabled=false",
    "--js-flags=--max-old-space-size=96 --max-semi-space-size=2",
    "--disable-features=site-per-process,IsolateOrigins,Translate,BackForwardCache",
    "--disable-background-networking", "--disable-component-update", "--disable-breakpad",
]
page.route("**/*", lambda r: r.abort()
           if r.request.resource_type in ("image", "media", "font") else r.continue_())
```

实测账（三站）：

| 组合 | doulor | lobehub | blizzard | 进程数 |
|---|---|---|---|---|
| 现状 `--disable-gpu --no-sandbox` | 537.4 | 684.7 | 617.9 | 7 |
| 上面这串 flags 但**去掉** `--single-process` | 548.4 | 652.0 | 554.7 | 5 |
| 上面这串 flags（含 `--single-process`） | **337.6** | **450.6** | **336.8** | **2** |
| 再加 `--js-flags=--max-old-space-size=64` | 425.9 ✗ | — | 436.3 ✗ | 4 |
| 改 `--in-process-gpu`（不合并 renderer） | 480.4 ✗ | — | 434.2 ✗ | 4 |
| `channel="chromium"`（完整 chromium 新 headless） | 966.8 | 1031.1 | 1014.8 | 9 |

要点：**`--disable-gpu --no-sandbox` 之外的 flags 单独看基本没用**（548 vs 537，噪声级别）；
真正省的是 `--single-process`。再叠更狠的堆上限会适得其反（Chromium 会退化/多起进程）。
`channel="chromium"` 千万别用——**比默认重一倍**（967–1031 MB）。

风险：`--single-process` 不是 Chromium 支持的配置，遇到崩溃就整个渲染失败（本项目已经 `try/except` + `close()` 丢弃，
下次重开，所以要保证 `Renderer` 用完即 `close()`，`pipeline.analyze()` 现在的 `finally: rr.close()` 正好对）。

---

## 6. 接入时容易踩的坑（都实测过）

1. **UA**：`net.UA` 含 `Mozilla`，Lightpanda 直接拒绝启动（`err=Reserved`）。用默认 `Lightpanda/1.0` 或 `--user-agent-suffix`。
   实测三站 + taobao/zhihu 用 `Lightpanda/1.0` 都 200（lobehub 的 Cloudflare 也没挡）。
2. **locale**：不给 `--locale zh-CN`，i18n 站返回英文版（doulor 4411 字英文 vs 1271 字中文）。正文长度会对不上，中文判据也会失灵。
3. **wait**：`--wait-until networkidle` 是必须的；`--wait-ms` 只是封顶。给得太小（如 1500）会在 hydration 中途截断。
4. **strip**：`--strip-mode shell` 会把导航/页脚连链接一起剥掉（doulor 的 `policy_links` 变空）。找条款入口时别用。
5. **iframes/workers**：默认不加载。遇到"渲染出来还是空壳"的站，先试 `--load-resources iframe`（worker 同理）。
6. **PDF/PNG**：Lightpanda 的 `--dump pdf/png` 是「把 markdown 排版成图」，不是真渲染——别拿它当截图用。
7. **`/tmp` 是 tmpfs**：180 MB 二进制放 `/tmp` 等于吃 180 MB 内存。装到 `~/.local/bin` 或 `/opt`。
8. **并发**：Lightpanda 单页 48–184 MB，两个并发还行；但兜底的 Chromium 一次只允许一个（代码里有 `_RENDER_LOCK`）。
9. **HTTP 4xx 的退出码**：`fetch` 默认即使 404 也以 **0** 退出并 dump 错误页（实测 `https://httpbin.org/status/404` → rc=0；
   加 `--fail-on-http-error` 才是 rc=22）。上面的代码按「非 0 退出 = 失败」处理，4xx 错误页原样返回、由
   `looks_like_policy` 判死——和现在 Chromium 返回 402 页面给判据的行为一致。
10. **并发**：Lightpanda 单页 48–184 MB，两页并发按峰值估算 ~368 MB，够用（未实测）；
    但兜底的 Chromium **一次只能一个**（代码里有 `_RENDER_LOCK`），并发起两个 500 MB 的 Chromium 会直接进 swap。

---

## 7. 复现：脚本在哪、怎么跑

本地产物在 `scripts/bench/`（已同步到服务器 `~/bench/bench/`）：

| 文件 | 干什么 |
|---|---|
| `proc_rss.py` | 进程树 RSS/PSS/swap 采样器（`/proc/*/statm` 累加 + cmdline 兜底 + 峰值时逐进程拆分） |
| `bench.py` | 主测框架：`run <scheme> <target>` 单跑；`matrix --schemes … --targets …` 跑矩阵，写 jsonl |
| `report.py` | 把 jsonl 汇总成上面的 markdown 表 |
| `compare_text.py` | 同一 URL 用 Lightpanda / Chromium 各渲一次，对比 `extract_text()` 的正文（本次靠它发现"英文版 4411 vs 中文版 1271"） |
| `lp_multi.py` | 「一次分析渲染 3 页」的两种接法对比（CLI 子进程 vs serve+CDP 复用） |
| `lp_sdk_test.py` | `pip install lightpanda` SDK 的端到端测试（需 `venv-lp`：`pip install lightpanda beautifulsoup4 lxml requests`） |
| `node_render.mjs` | jsdom / jsdom+垫片 / happy-dom 的渲染测试（node 22） |
| `pyppeteer_test.py` | pyppeteer 驱动同一份 Chromium 的内存/进程实测 |
| `splash_test.py` | Splash 容器：`render.html` + cgroup `memory.peak` |
| `docker_measure.sh` | 通用：跑一个 docker 容器并读它 cgroup 的 `memory.peak` |

服务器上的复现步骤：

```bash
ssh <主机别名>
cd ~/bench
# 1) 主结果（约 3 分钟，含 npm install）
bash run_all.sh      # pw-shell / pw-chromium / pw-flags / pw-single / lp-* / node-*
bash run2.sh         # lp-cli-full / lp-cli-strip / taobao+zhihu+notion / lp_multi
bash run3.sh         # lp-rec（推荐配置，六站） / obscura
bash run4.sh         # pw-single2 / pw-inproc
python3 bench/report.py ~/bench/all.jsonl
```

Python 用 `~/clauselens/.venv/bin/python`（只 import `clauselens`，不改项目；`PYTHONDONTWRITEBYTECODE=1` 避免写 `__pycache__`）。

**测完的现场（已核对）**：`pgrep -a lightpanda` / `obscura` / `node_render` 全空；
`docker ps -a` 里没有 bench 容器（`splash-bench` 已删）；`systemctl is-active clauselens caddy` 都是 active；
2.69 GB 的 `scrapinghub/splash` 镜像已删掉，磁盘回到 15 GB 可用。
`~/bench` 留 461 MB 物料（lightpanda 180 MB + obscura 113 MB + 两个测试 venv + node_modules），
`~/.cache/ms-playwright/` 和 `~/clauselens/.venv` 一个字节没动。
> 备注：采样时看到 PID 549221/549301（node driver 89 MB + chrome-headless 425 MB）是 **clauselens 服务自己**
> 正在响应用户请求（PPID 546938 = uvicorn），不是遗留进程——正好现场演示了现状的内存开销。

---

## 附录 A：全部实测原始行

（`进程树 RSS` = 该方案整棵进程树 `/proc/*/statm` 累加峰值；`PSS` 把共享库只算一次；`当时可用内存` 是采样期间的 `MemAvailable` 最低值，越小说明机器越紧。）

| 方案 | 站 | 渲染后正文 | 像条款 | 进程树 RSS 峰值 | PSS | 峰值 swap | 当时可用内存 | 进程数 | 单页耗时 | 备注 |
|---|---|---|---|---|---|---|---|---|---|---|
| `lp-rec` | doulor | 1271 字 | 是 | 48.2 MB | 46.0 MB | 0.0 MB | 416.9 MB | 1 | 1.92 s | 与 Chromium 逐字一致 |
| `lp-rec` | lobehub | 17631 字 | 是 | 118.2 MB | 115.9 MB | 0.0 MB | 361.9 MB | 1 | 2.64 s | iframe 未加载（warn） |
| `lp-rec` | blizzard | 656 字 | 否 | 81.6 MB | 79.3 MB | 0.0 MB | 393.6 MB | 1 | 4.79 s | 16 链接 / 3 条条款 |
| `lp-rec` | taobao | 8018 字 | 否 | 184.4 MB | 181.2 MB | 0.0 MB | 302.0 MB | 1 | 4.29 s | 1874 链接 |
| `lp-rec` | zhihu | 18331 字 | 是 | 161.6 MB | 158.0 MB | 0.0 MB | 323.0 MB | 1 | 3.44 s | worker 未加载（warn） |
| `lp-rec` | notion | 88 字 | 否 | 53.6 MB | 51.2 MB | 0.0 MB | 402.7 MB | 1 | 8.15 s | ❌ 还是空壳 |
| `lp-cli`（默认） | doulor | 12 字 | 否 | 47.2 MB | 30.7 MB | 0.0 MB | 430.7 MB | 1 | 0.94 s | ❌ wait-until 太早 |
| `lp-cli`（默认） | lobehub | 17631 字 | 是 | 79.1 MB | 45.8 MB | 0.0 MB | 332.6 MB | 1 | 1.05 s | |
| `lp-cli`（默认） | blizzard | 595 字 | 否 | 73.5 MB | 70.6 MB | 3.4 MB | 244.2 MB | 1 | 4.29 s | 14 链接 / 3 条款 |
| `lp-cli-wait` | doulor | 4411 字 | 是 | 50.6 MB | 48.4 MB | 0.0 MB | 319.6 MB | 1 | 1.99 s | 英文版 |
| `lp-cli-wait` | lobehub | 17631 字 | 是 | 113.4 MB | 111.0 MB | 0.0 MB | 273.9 MB | 1 | 2.61 s | |
| `lp-cli-wait` | blizzard | 653 字 | 否 | 75.8 MB | 73.4 MB | 0.0 MB | 276.2 MB | 1 | 4.74 s | |
| `lp-cli-res` | doulor | 12 字 | 否 | 45.1 MB | 44.8 MB | 0.0 MB | 224.4 MB | 1 | 1.00 s | ❌ 光给资源没用 |
| `lp-cli-res` | lobehub | 17631 字 | 是 | 80.2 MB | 67.7 MB | 0.0 MB | 296.2 MB | 1 | 1.38 s | |
| `lp-cli-res` | blizzard | 595 字 | 否 | 75.4 MB | 73.2 MB | 0.0 MB | 351.3 MB | 1 | 7.19 s | |
| `lp-cli-full` | doulor | 4411 字 | 是 | 48.6 MB | 46.5 MB | 0.0 MB | 365.3 MB | 1 | 1.88 s | 英文版 |
| `lp-cli-full` | lobehub | 17631 字 | 是 | 106.7 MB | 104.3 MB | 0.0 MB | 310.4 MB | 1 | 4.11 s | |
| `lp-cli-full` | blizzard | 653 字 | 否 | 82.4 MB | 80.1 MB | 0.0 MB | 338.7 MB | 1 | 3.61 s | |
| `lp-cli-strip` | doulor | 4411 字 | 是 | 51.5 MB | 49.4 MB | 0.0 MB | 356.2 MB | 1 | 1.41 s | ⚠️ 链接被剥光（0 条） |
| `lp-cli-strip` | lobehub | 17631 字 | 是 | 107.1 MB | 104.9 MB | 0.0 MB | 305.0 MB | 1 | 2.13 s | 67 链接 |
| `lp-cli-strip` | blizzard | 653 字 | 否 | 78.4 MB | 76.0 MB | 0.0 MB | 343.6 MB | 1 | 2.81 s | 16 链接 |
| `lp-cdp` | doulor | 4411 字 | 是 | 52.2 MB | 50.1 MB | 0.0 MB | 292.6 MB | 1 | 3.27 s | 英文版（未设 locale） |
| `lp-cdp` | lobehub | 17631 字 | 是 | 116.8 MB | 114.5 MB | 0.0 MB | 232.9 MB | 1 | 3.77 s | |
| `lp-cdp` | blizzard | 653 字 | 否 | 88.7 MB | 84.1 MB | 0.0 MB | 268.0 MB | 1 | 4.43 s | |
| `obscura-cli` | doulor | 4411 字 | 是 | 141.7 MB | 114.3 MB | 0.0 MB | 299.7 MB | 4 | 8.82 s | 英文版 |
| `obscura-cli` | lobehub | 17631 字 | 是 | 202.1 MB | 174.7 MB | 0.0 MB | 254.3 MB | 4 | 8.91 s | |
| `obscura-cli` | blizzard | 718 字 | 否 | 183.1 MB | 155.3 MB | 0.0 MB | 256.2 MB | 4 | 14.05 s | 3 条条款链接 |
| `obscura-cli` | notion | 870 字 | 否 | 349.4 MB | 316.5 MB | 0.2 MB | 156.2 MB | 4 | 9.83 s | ✅ 唯一拿到 notion 的轻量方案 |
| `node-jsdom` | doulor | 12 字 | 否 | 147.2 MB | 140.7 MB | 0.0 MB | 286.8 MB | 1 | 11.73 s | ❌ ESM 不执行 |
| `node-jsdom` | lobehub | 17631 字 | 是 | 155.7 MB | 148.0 MB | 0.0 MB | 301.1 MB | 1 | 11.28 s | SSR 内容 |
| `node-jsdom` | blizzard | 545 字 | 否 | 176.4 MB | 170.2 MB | 0.0 MB | 289.7 MB | 1 | 10.92 s | 3 条条款链接 |
| `node-jsdom-poly` | doulor | 12 字 | 否 | 142.7 MB | 136.5 MB | 0.0 MB | 311.4 MB | 1 | 10.36 s | 垫片也没用 |
| `node-jsdom-poly` | lobehub | 17631 字 | 是 | 156.6 MB | 149.9 MB | 0.0 MB | 300.9 MB | 1 | 10.45 s | |
| `node-jsdom-poly` | blizzard | 545 字 | 否 | 191.0 MB | 185.0 MB | 0.0 MB | 279.5 MB | 1 | 10.27 s | |
| `node-happy-dom` | doulor | 12 字 | 否 | 107.8 MB | 101.6 MB | 0.0 MB | 357.1 MB | 1 | 10.46 s | ❌ |
| `node-happy-dom` | lobehub | 17631 字 | 是 | 115.7 MB | 109.4 MB | 0.0 MB | 303.4 MB | 1 | 9.94 s | |
| `node-happy-dom` | blizzard | 540 字 | 否 | 112.4 MB | 105.5 MB | 0.0 MB | 318.5 MB | 1 | 9.87 s | |
| `pw-shell`（现状） | doulor | 1271 字 | 是 | 537.4 MB | 296.3 MB | 72.0 MB | 352.1 MB | 7 | 5.89 s | 已在吃 swap |
| `pw-shell`（现状） | lobehub | 17631 字 | 是 | 684.7 MB | 432.2 MB | 0.2 MB | 245.8 MB | 7 | 5.68 s | networkidle 超时 |
| `pw-shell`（现状） | blizzard | 656 字 | 否 | 617.9 MB | 367.6 MB | 0.0 MB | 334.7 MB | 7 | 5.32 s | |
| `pw-chromium` | doulor | 1271 字 | 是 | 966.8 MB | 456.2 MB | 2.1 MB | 296.4 MB | 9 | 6.06 s | 完整 chromium |
| `pw-chromium` | lobehub | 17631 字 | 是 | 1031.1 MB | 525.4 MB | 15.9 MB | 222.8 MB | 9 | 7.40 s | |
| `pw-chromium` | blizzard | 656 字 | 否 | 1014.8 MB | 489.4 MB | 0.0 MB | 303.2 MB | 9 | 5.14 s | |
| `pw-flags` | doulor | 1271 字 | 是 | 548.4 MB | 347.4 MB | 0.0 MB | 404.5 MB | 5 | 4.37 s | 只加 flags 没用 |
| `pw-flags` | lobehub | 17631 字 | 是 | 652.0 MB | 431.2 MB | 0.0 MB | 315.1 MB | 5 | 5.51 s | |
| `pw-flags` | blizzard | 656 字 | 否 | 554.7 MB | 355.2 MB | 0.0 MB | 374.7 MB | 5 | 3.63 s | |
| `pw-single` | doulor | 1271 字 | 是 | 313.7–337.6 MB | 288.6 MB | 37.6 MB | 184.4 MB | 2 | 3.13–10.11 s | ✅ 兜底首选 |
| `pw-single` | lobehub | 17631 字 | 是 | 450.6 MB | 405.7 MB | 0.0 MB | 292.2 MB | 2 | 6.01 s | |
| `pw-single` | blizzard | 656 字 | 否 | 336.8–359.5 MB | 314.7 MB | 14.9 MB | 283.3 MB | 2 | 4.89–9.21 s | |
| `pw-single` | notion | 214 字 | 是 | 509.5–581.7 MB | 440.5 MB | 81.8 MB | 256.4 MB | 2 | 7.87–15.88 s | 唯一能拿到 notion 的兜底 |
| `pw-single2`（更狠堆上限） | doulor | 1271 字 | 是 | 425.9 MB | 337.0 MB | 0.0 MB | 378.1 MB | 4 | 3.68 s | ✗ 反而更差 |
| `pw-single2` | blizzard | 656 字 | 否 | 436.3 MB | 345.3 MB | 0.0 MB | 357.5 MB | 4 | 4.98 s | |
| `pw-single2` | notion | 214 字 | 是 | 650.5 MB | 526.7 MB | 26.3 MB | 183.1 MB | 4 | 8.84 s | |
| `pw-inproc` | doulor | 1271 字 | 是 | 480.4 MB | 332.5 MB | 0.0 MB | 406.2 MB | 4 | 3.96 s | ✗ |
| `pw-inproc` | blizzard | 656 字 | 否 | 434.2 MB | 308.3 MB | 89.7 MB | 350.8 MB | 4 | 6.68 s | |
| `pw-inproc` | notion | 214 字 | 是 | 676.2 MB | 489.1 MB | 27.5 MB | 210.8 MB | 4 | 8.62 s | |
| `pyppeteer` | doulor | 未判（43 KB HTML） | — | 488.0 MB | — | — | — | 5 | — | 客户端换汤不换药 |

容器方案（cgroup `memory.peak`，不是进程树）：

| 方案 | 站 | 结果 | 峰值内存 | 耗时 |
|---|---|---|---|---|
| Splash | doulor | ❌ 12 字 | 328 MB | 8.8 s |
| Splash | lobehub | ✅ 17631 字 | 328 MB | 7.4 s |
| Splash | blizzard | ✅ 562 字 + 3 条条款链接 | 328 MB | 9.6 s |
| wkhtmltopdf | doulor | ❌ 空白 PDF（1209 B，抽文字 1 字节） | 70 MB | 8.9 s |
| wkhtmltopdf | lobehub | ⚠️ PDF 59355 B / 17805 字（SSR 内容） | 13 MB | ~8 s |
| wkhtmltopdf | blizzard | ❌ 空白 PDF（181 KB，抽文字 1 字节） | 45 MB | ~9 s |

---

## 附录 B：参考

- Lightpanda 1.0 公告（WPT 1,739,845、CORS、V8 15.5）：<https://lightpanda.io/blog/posts/lightpanda-1-0>
- 仓库与 issue（含 [#1798](https://github.com/lightpanda-io/browser/issues/1798) SPA 提问、[#2402](https://github.com/lightpanda-io/browser/issues/2402) CDP 卡顿、[#3359](https://github.com/lightpanda-io/browser/issues/3359) networkidle、[#4179](https://github.com/lightpanda-io/browser/issues/4179) iframe 仍开着）：<https://github.com/lightpanda-io/browser>
- 安装（单文件 / docker / 包管理器 / 系统要求）：<https://lightpanda.io/docs/run-locally/installation/one-liner>
- CLI 参考（`fetch` 全部参数、`serve` 的 CDP/WebDriver）：<https://lightpanda.io/docs/reference/cli/fetch>
- Obscura（Rust，2026-10-31 v0.2.6，32.8k star，x86_64 二进制）：<https://github.com/h4ckf0r0day/obscura>
- Splash（最后提交 2024-08-02）：<https://github.com/scrapinghub/splash>
- pyppeteer（最后提交 2024-06-29）：<https://github.com/pyppeteer/pyppeteer>
- wkhtmltopdf 状态（QtWebKit 2015 废弃 / 2016 移除）：<https://wkhtmltopdf.org/status.html>，ES6 问题：<https://github.com/wkhtmltopdf/wkhtmltopdf/issues/4010>
- Chromium `--single-process` 崩溃案例：<https://github.com/hardkoded/puppeteer-sharp/issues/2512>，<https://pptr.dev/troubleshooting>
- 项目内相关：`docs/design/pipeline.md` §C（SPA 走法）、`docs/reviews/2026-11-12-security.md` L7（浏览器绕过 SSRF 校验）