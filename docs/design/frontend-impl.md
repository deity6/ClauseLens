# 前端实现说明 v1

> 对应规格 `frontend.md`。本文记录实际实现：组件结构、动效清单、验收方式与已知不足。

## 1. 结构

```
frontend/
  index.html                 lang=zh-CN，color-scheme: light dark
  vite.config.js             dev(5173) / preview(4173) 都把 /api 代理到 127.0.0.1:8787
  scripts/shot.mjs           截图验收：自起无头 Edge（临时 profile，用完即删）+ CDP；--audit 输出溢出/截断/重叠/低对比
  src/
    main.jsx
    App.jsx                  三态路由（home / waiting / result），URL ?q= 与 ?demo= 同步，popstate 可回退
    styles.css               唯一样式文件；token：paper / sheet / ink / line / X-tint / X-ink / g-A..E
    lib/
      motion.js              缓动四件套 EASE + 时长 DUR + 整页过渡 pageVariants（全站唯一来源）
      stream.js              openSSE（真实）/ openDemo（样例回放）/ pace（显示节拍器）
      useAnalysis.js         事件 reducer；七阶段 → 四段轨道 RAIL
      taxonomy.js            GET /api/taxonomy，失败或演示模式退回随包 taxonomy.json
      feedback.js            投票 POST + summary GET + localStorage 记住已投
      format.js              字数/分钟格式化、输入模式识别（整站 / 单页 / 无效）
    components/
      Home.jsx               标题、输入框 + 实时模式提示、示例 chips、三步说明
      Waiting.jsx            阶段轨道、纸张扫描、标签托盘、文案轮播、文档卡、已省下 N 分钟、错误态
      Result.jsx             报告头（印章 + CountUp）、TL;DR、各分区、再查一个 / 复制链接
      Stamp.jsx              SVG 双环印章（环形文字 + 等级字母 + 粗糙滤镜 + 磨损遮罩）
      TagWall.jsx            三组胶囊、手风琴抽屉（解释 / 证据 / 置信度 / 投票）；导出 Highlight
      Radar.jsx              手写 SVG 六维雷达 + 维度横条 + 悬停提示该维命中标签
      Compliance.jsx         法域清单；全文偏移 → {doc,start,end} 换算后可跳原文
      Reader.jsx             原文阅读器：文档 tab、证据高亮、跳转滚动 + 闪烁
      CountUp.jsx            全站唯一数字滚动组件
      Icons.jsx              线性图标；好 ✓ / 坏 ! / 中性 · —— 颜色之外的第二通道
```

### 数据流

`EventSource` / 演示计时器 → `pace()` → `useReducer`。等待态**只读 reducer 状态**：轨道位置来自 `stage`，
文档卡来自 `document`，托盘来自 `tag`，结果切换来自 `result`。没有任何自增的假进度。

`pace()` 只给"显示"设最小间隔（stage 420ms / document 520ms / tag 150ms / result 900ms），
不改变事件顺序与内容。原因：后端命中缓存时几十毫秒吐完全部事件，不节流的话等待态一闪而过、读不出过程。

### 演示模式

`?demo=baidu` / `?demo=github`：不连后端（taxonomy 用随包 json，不拉 feedback summary，投票只写 localStorage）。
`demoEvents()` 按真实 pipeline 的事件顺序合成：resolve → discover(found) → 每份文档 fetch+document →
extract → analyze(0.3, clauses) → 逐个 tag → analyze(1.0) → score → result，总时长约 9–11s。
样例 json 动态 import，不进主包。

## 2. 动效清单

曲线只用 `lib/motion.js` / CSS 变量里的四条：默认 `out (.22,1,.36,1)`、进入 `enter (.2,.7,.3,1)`、
回弹 `spring (.34,1.56,.64,1)`（只给缩放/弹入）、长尾 `tail (.22,.61,.12,1)`（只给填充/进度/数字）。

| 动效 | 触发 | 时长 | 曲线 |
|---|---|---|---|
| 整页三态切换（出） | view 变化 | 320ms | out，上移 24px 淡出 |
| 整页三态切换（入） | 同上 | 640ms 位移 / 520ms 透明度 | out，32px → -4px → 0（尾韵 overshoot），透明度 enter |
| 首页三步说明进场 | 首页挂载 | 520ms，错峰 80ms | enter |
| 输入模式提示切换 | 输入变化导致模式变化 | 160ms | out |
| 按钮 / chip / 胶囊 hover | hover | 160ms | out；同时动 transform + 阴影 + 颜色/描边 |
| 输入框聚焦 | focus | 160ms 描边 / 320ms 阴影与抬起 | out |
| 轨道当前阶段呼吸点 + 光环 | 当前阶段 | 1.6s 循环 | out |
| 轨道勾选描边 | 阶段完成 | 320ms | out（pathLength 0→1） |
| 轨道连接线填充 | 阶段完成 | 600ms | tail |
| 纸张滑入 | 进入等待态 | 720ms | enter，y 120→0，旋转 2°→-1.2° |
| 扫描光带 + 行高亮 | stage ∈ discover/fetch/extract/analyze | 2.4s 循环；行按序错开 0.11s | 光带 out，行高亮 linear 关键帧 |
| 纸上印章虚影 | stage = score | 700ms | spring，scale 1.4→1 |
| 标签飞入托盘 | 每个 `tag` 事件 | 520ms 位移缩放 / 320ms 透明度 | spring（从纸张方向 x -180~-240） |
| 文档卡出现 | 每个 `document` 事件 | 520ms | enter |
| 已省下 N 分钟 | 文档累计分钟变化 | 900ms，从当前值续滚 | tail |
| 文案轮播 | 每 2.6s / 阶段切换 | 320ms | enter，淡入上移 10px，淡出上移 8px |
| 印章盖下 | 结果态挂载 +250ms | 700ms | spring，scale 1.3→1，rotate -22°→-8° |
| 墨迹扩散 | 印章落下中段 | 1000ms | out，径向晕 scale 0.6→1.4 淡出 |
| 报告头震动 | 印章动画结束 | 320ms | out，y 0→3→-1→0（一次下沉，不来回抖） |
| 分数 CountUp | 结果态挂载 +200ms | 1300ms | tail |
| 分区进场 | 滚入视口（once） | 520ms | enter，y 24→0 |
| TL;DR 条目 | 滚入视口 | 520ms，错峰 60ms | enter |
| 标签胶囊弹入 | 滚入视口 | 520ms，错峰 40ms | spring（scale .85→1） |
| 标签抽屉 / 合规抽屉 / 阅读器展开 | 点击 | 320ms | out（height auto） |
| 置信度条 | 抽屉展开 | 800ms | tail |
| 投票反馈 | 点击投票 | 320ms | spring，按钮 scale 1→1.18→1，计数自上落入 |
| 雷达多边形生长 | 滚入视口 | 820ms | spring（scale 0→1，绕中心） |
| 维度横条填充 | 滚入视口 | 900ms，错峰 60ms | tail |
| 雷达悬停提示 | hover/focus 轴标签 | 160ms | out |
| 阅读器 tab 下划线 | 切换 tab | 320ms | out |
| 原文跳转闪烁 | 点击“在原文中查看” | 滚动 smooth + 1.2s×2 闪烁 | out |

**prefers-reduced-motion**：`MotionConfig reducedMotion="user"` 关闭 motion 的位移/缩放；组件里对纸张、
飞行标签、文档卡显式降级为纯淡入；CSS 停掉扫描线、行高亮、呼吸点、闪烁，过渡压到 1ms；
CountUp 直接显示终值；**文案轮播保留**（规格要求）。

## 3. 视觉要点

- 分层靠发丝线 + 字号跳跃 + 留白，没有区块背景色；唯一的"浮起"是等待态那张纸（三层柔和阴影）。
- 语义色只出现在：标签胶囊、TL;DR 圆点、合规勾叉、等级色（分数/印章/维度条）。标题里"同意了什么"用一次朱砂。
- 深色单独调色：tint 用主色 + 低 alpha，语义色各提亮一档，阴影换成纯黑低 alpha，纸纹透明度单独调。
- ≤640px：单列；首页隐藏输入框图标与"查看"文字只留箭头；轨道改为四列竖排；
  报告头改为网格（站名左、印章 104px 右）；合规行法条换到第二行；所有可点目标 ≥44px（阅读器 tab 46px）。

## 4. 验收方式

```
cd frontend && npm run build && npx vite preview --port 4173
node scripts/shot.mjs "http://127.0.0.1:4173/?demo=baidu" out.png --wait 16000 --full --light --audit
```
`--light/--dark/--reduce` 只在这个无头实例里模拟媒体特性，不碰系统设置。`--audit` 报告横向溢出、
文字截断、兄弟元素重叠、对比度 <3.2 的文字、<11px 的字。截图在 `docs/design/screens/`：

| 文件 | 内容 |
|---|---|
| 01-home.png | 首页 1440 |
| 02-waiting.png | 等待态（demo 第 8s，逐条阅读阶段） |
| 03-result.png | 结果态全页（baidu，浅色） |
| 04-mobile-result.png | 移动端 390 结果态全页（github） |
| 05-result-expanded.png | 展开标签 + 投票 + 跳转原文后 |
| 06-mobile-waiting.png | 移动端等待态 |
| 07-result-dark.png | 深色模式结果态（github） |
| 08-mobile-home.png | 移动端首页 |
| 09-error.png | 错误态（真实后端，输入 localhost → bad_input） |

已验证：真实后端 SSE（经 preview 代理）`?q=baidu.com` 能走完到结果态；展开抽屉、投票写入 localStorage、
"在原文中查看"后目标高亮位于阅读器可视区并闪烁；reduced-motion 下结果正常显示；各态 audit 无横向溢出、无低对比文字。

## 5. 契约 v1.1 适配（2026-11-07）

- TL;DR 用结构化 `tldr[{tag,polarity,text}]`，坏的在前；只有旧 `tldr_zh` 时按中性显示，不反查。
- 证据高亮只用 `evidence.spans`（quote 内区间）；spans 为空（模型独立命中）整句淡底 `.ev-whole`。通用词表已删除。
- 合规证据直接用 `{doc,start,end}` 跳原文，命中词用 `match_start/end - start` 高亮；删掉了全文偏移换算。
- 错误态按 `code` 给标题与建议（rate_limited / network / bad_input / not_found / blocked / fetch_failed / timeout）；
  EventSource onerror 文案：「连不上服务器，请确认服务已启动。」
- 雷达画布左右各加 44 单位留白给轴标签（viewBox 388×300），移动端不再限 300px 宽，标签离屏幕边 ≥35px。

## 6. 已知不足

1. **截图的人眼复核没有做成**：本环境的 Read 工具只返回 `[image omitted]`，看不到图像内容（子代理也一样）。
   形态验收改用了 DOM 几何审计、像素采样和 ASCII 降采样，能发现溢出、截断、重叠、对比度问题，
   但发现不了"难看"。**需要人看一遍 `docs/design/screens/`**。
2. `EventSource` 的 onerror 拿不到 HTTP 状态码，onerror 一律按「连不上服务器」处理（限流已改走 error 事件，不受影响）。
3. 主包 400KB（gzip 130KB），大头是 motion。可以改用 `motion/react-m` + `LazyMotion` 再减约 30KB，当前没做。
4. 没有引入 Web 字体：标题依赖本机的 Noto Serif SC / 思源宋体 / 宋体，没装这些字体的机器会退到系统 serif，观感会差一档。
