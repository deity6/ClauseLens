# 主题 B「点阵 · SPECTRAL SCAN」外部参考

> 调研日期 2026-11-12。只做调研、不改代码。配合 `docs/design/theme-geek.md` 读：那边定目标与 token，这边只回答「别人怎么做的、数字是多少」。
> 本文件不引入任何依赖结论；所有可直接照抄的数字集中在 §6。

**可信度标记**：**[S]** 读到实现源码/GLSL；**[C]** 抓到对方 CSS 并 grep 出具体值；**[P]** 只拿到页面文案/构建产物特征，属推断；**[I]** 找不到源，按视觉与同类实现反推。
环境说明：raw.githubusercontent.com 在本机不可达，全部走 `gh api repos/{o}/{r}/contents/{path}` 与直连 web 抓取。

---

## 1. lm-detector 的动态点阵背景（[S]）

**先纠一个前提：它不是 three.js，也没有全屏点阵 canvas。** 全站只有**一枚单例离屏 WebGL1 上下文** + GLSL ES 1.0 片元着色器；每个装饰宿主 `.fp-pixel`（`position:relative; overflow:hidden; pointer-events:none`）挂一块 2D canvas 当显示面，着色器按**格**渲染，再 `drawImage` 到 2D 画布，CSS `image-rendering: pixelated` 放大。也就是说它做的是「4px 像素风装饰」，不是「24px 点阵场」。
来源：<https://github.com/Ikaleio/lm-detector/blob/main/web/src/lib/pixel-renderer.ts>、<https://github.com/Ikaleio/lm-detector/blob/main/web/src/shell.css>

参数级结论（全部来自 `pixel-renderer.ts`）：

| 项 | 值 | 备注 |
|---|---|---|
| 帧率 | `FPS = 24` | 手动节流，不是每 rAF 都画；`due = now-lastDraw >= 1000/24-1` |
| 时间轴 | `PLAYBACK_RATE = 0.5`，`% 3600` | 所有效果半速 |
| 网格 | `cell` 默认 **4 CSS px/格**；`PixelSpinner` 用 **2**；logo 固定 **24×24** 格 | 画布 `ceil(w/cell) × ceil(h/cell)`，1 格 = 1 device px |
| 颜色 | `getComputedStyle(host).color` → 1×1 的 2D canvas 探针转 sRGB | 能吃 `oklch()`/`color-mix()`，结果按字符串缓存 |
| 亮度 | `ink(a)`：`clamp(a)*u_color.a`，输出**预乘 alpha** | 单个标量 a 同时决定 rgb 与 a，天然抗溢色 |
| 省电 | `IntersectionObserver{rootMargin:'64px'}`、`document.hidden` 停帧、`contextlost` 后重建 | 离开视口即不画 |
| 上下文 | `alpha:true, premultipliedAlpha:true, antialias:false, depth:false, stencil:false, powerPreference:'low-power'` | 全站共用一个上下文，绕开浏览器上下文数量上限 |
| reduced-motion | `STILL_TIME = 3.7` 秒处的单帧、`STILL_AGE = 60`（入场动画直接终态） | 只画 dirty 帧 |
| 鼠标 | **完全没有**：无磁吸、无拖尾、无涟漪 | 交互另有一套 framer-motion 弹簧：`snappy 500/45`、`smooth 260/34`、`gentle 120/24`，列表 stagger `0.06s` |

最接近「点阵底」的是 `dither` 效果：10fps 步进 + Bayer4 有序抖动。
来源：<https://github.com/Ikaleio/lm-detector/blob/main/web/src/lib/pixel-effects.ts>

```ts
const FPS = 24, PLAYBACK_RATE = 0.5, STILL_TIME = 3.7, STILL_AGE = 60
const time = animate ? ((now - this.start) / 1000 * PLAYBACK_RATE) % 3600 : STILL_TIME
const columns = Math.ceil(width / view.cell), rows = Math.ceil(height / view.cell)
gl.uniform2f(program.res, view.columns, view.rows)   // 着色器以「格」为单位工作
```
```glsl
void ink(float a) { a = clamp(a,0.,1.) * u_color.a; gl_FragColor = vec4(u_color.rgb*a, a); }
float bayer2(vec2 a) { a = floor(a); return fract(a.x/2. + a.y*a.y*.75); }
// dither: v=(.5+.5*sin((p.x+p.y)*.09-t*1.4))*(.5+.5*sin(p.x*.021+t*.5+u_seed)); ink(step(bayer4(p), v*.55));
```

**借什么**：24fps 上限、半速时间轴、单上下文、预乘 alpha、按格建画布（像素对齐无半像素模糊）。**不借什么**：4px 格——对 24px 点阵太细，见 §6 第 1、2 条。

---

## 2. bencho.dev 的「磁点」背景（[P] + [C]）

- **URL 对不上**：`/blocks/glass-bubble` 的标题是 "Liquid Glass Refraction Effect"，文案 "Drag a ball of glass over a photo and watch it bend the picture beneath"，是玻璃折射球。磁点是另一个 block：**`/blocks/magnetic-dots`**，文案 "A field of dots that leans toward your cursor and springs back after"。
  来源：<https://bencho.dev/blocks/glass-bubble>、<https://bencho.dev/blocks/magnetic-dots>
- **介质**：主 bundle `/assets/index-Cg2ZONiB.js`（568KB）中 `webgl`、`fragmentShader` 命中 **0**，`canvas` 命中 6 → 不是 WebGL 着色器路径（2D canvas 或 CSS/SVG 滤镜）。磁点 block 的源码被 Pro 锁：bundle 里只有尺寸表 `"magnetic-dots":{w:250,h:250}`，**参数取不到**。
- **能读到的（CSS，[C]）**：board 底 `radial-gradient(rgba(var(--ink-rgb),.13) 1px, transparent 1px)` + `background-size:22px 22px`（**22px 网格 / 1px 点 / 13% 亮度**）；卡片 `border-radius:28px`；`ease: cubic-bezier(.22,1,.36,1)`，pop `cubic-bezier(.24,1.34,.38,1)`；press `scale:.96`；弹簧 `settle{380,34}`、`lively{500,18}`；微交互时长 `.16s/.18s/.2s`；字体 `Inter, Maison Neue, Instrument Sans, Helvetica Neue`；官方示例代码里磁吸用 `useSpring(value,{stiffness:320,damping:28})`，拖拽另一处 `{stiffness:340,damping:30,mass:.8}`。
  来源：<https://bencho.dev/assets/index-DlgYVlsG.css>、<https://bencho.dev/assets/index-Cg2ZONiB.js>
- **替代参数（[I]，与 `theme-geek.md` §5 对齐）**：磁吸半径 **120px**、最大位移 **16px**（= 2/3 格）、力 `(1-(d/r)²)` 立方衰减、回位 `stiffness 320 / damping 28`（≈550ms 收敛）、点击涟漪初速 **700px/s**、同时最多 3 个。

---

## 3. Rice-dog 的「光谱点阵帷幕」（**未找到**，[I]）

检索过程：`gh search repos --owner Rice-dog` 只有 **1 个公开仓库** `Rice-dog/code-codex`（Rust/Tauri，给 Codex Desktop 加本地文件树的插件，1576★），无 web 前端、无点阵/着色器代码；`21st.dev/@ricedog` 返回 `User not found`；`gh search code` 与 `web_search` 均无命中。
来源：<https://github.com/Rice-dog/code-codex>、<https://21st.dev/@ricedog>

**结论：未找到，以下为视觉反推（3 平面波 + 1 径向项，逐点位移，非流体模拟）：**

```js
// i = 0..2；方向 θ = [0°, 60°, 120°]；p 为点阵格点，t 为秒
const A = [14, 9, 6], L = [900, 520, 300], W = [0.25, 0.4, 0.6], PH = [0, 2.1, 4.2]
const s = Math.sin(TAU * (x*cos(TH[i]) + y*sin(TH[i])) / L[i] + t*W[i] + PH[i])
dx += A[i]*cos(TH[i])*s;  dy += A[i]*sin(TH[i])*s          // 位移沿波传播方向
// 鼠标：局部相位偏移，避免整场平移
phase += 1.6 * Math.exp(-(d*d)/(2*180*180));  light += 0.35 * Math.exp(-(d*d)/(2*90*90))
```
要点：振幅随波数递减（14/9/6），三个方向互成 60° 才能出现「光谱斜纹」而不形成棋盘；相位速度 0.25–0.6 rad/s（周期 10–25s），比 lm-detector 的 0.5 倍速观感更慢。

---

## 4. 极客黑白终端风的排版与交互语法（[C]）

| 站点 | 字体栈 | 字距 | 边框/圆角 | hover / 光标 | 转场 |
|---|---|---|---|---|---|
| [rauno.me](https://rauno.me) | `JetBrains Mono` + `Georgia, serif` | 标题靠 optical sizing，正文无显式 tracking | `border-radius:12px`、`9999px`、`50%` | **`cursor:none` + 自定光标 `.cross`**：`--cross-size:16px`、`--guide-width:1.5px`、`--cross-color:gray12`、`pointer-events:none`；`focus-ring:2px` | `transition: opacity/transform var(--transition-duration) ease`；网格 `--gap:8px` |
| [pacocoursey.com](https://pacocoursey.com) | `ui-monospace, SFMono-Regular, Consolas, Menlo` | **`letter-spacing:-.05em`**（标题级） | `--radius` 变量；单侧圆角 `0 var(--radius) var(--radius) 0` | `transition: color/border-color var(--transition)` | 另有 `--transition-xx` 用于大位移 |
| [bencho.dev](https://bencho.dev) | `Inter, Maison Neue, Instrument Sans` | 无显式 tracking | 22px 点阵底 + `28px` 圆角 | 弹簧 (380/34, 500/18)、`scale:.96` | `.16–.2s`，ease `(.22,1,.36,1)` |
| [ghostty.org](https://ghostty.org) | 等宽主导（终端模拟器官网） | — | `border-radius:10px`，`--control-size` 统一控件尺寸 | 无阴影、纯边框 | — |
| [terminal.shop](https://terminal.shop) | 站内无 CSS 字体声明，靠等宽默认 | — | — | 整站是浏览器里的 TUI（Astro 静态页 + 键盘交互） | — |

三条可复用的语法（[C]/[I] 综合）：
1. **字距两极**：大标题负 `-.03 ~ -.05em`，12px 小标签正 `+.14 ~ +.18em`；中间字号不加 tracking。
2. **边框是唯一分隔手段**：1px（甚至 0.5px 发丝线），圆角只在 `0` 与 `10–28px` 两极，阴影一律归零——和本契约 §2 `--sh-*: none` 一致。
3. **自定光标比 hover 阴影更「极客」**：rauno 的 16px 十字 + 1.5px 导引线，本质是「把鼠标变成测量工具」，正好接本契约的 `cursor:crosshair`。

---

## 5. 左→右 hero 转场 / 粒子 dissolve / scan wipe 的现成实现（[S]）

**① gl-transitions `Disintegrate.glsl` —— 与本项目「旧文字碎成点飞走」几乎一一对应**
`particleSize 0.008`（帧高比例，1080p ≈ 8.6px 颗粒）、`direction (1,-0.15)`（向右略上扬，即「风」）、`spread 0.75`、颗粒寿命 `LIFE = 0.45`（转场进度的 45%）、最远飞 `reach ≤ 60` 格；释放前沿是**毛边**：`front += 0.14*noise + 0.08*(hash-0.5)`，且**逆风侧先释放**（`1-(x+half)/2half`）；颗粒体积 `0.5 → 0.3` 收缩 + `smoothstep(0.15,1,t)` 淡出。每像素最多回看 35 个候选颗粒（近 17 个逐格，之后 1/2、1/4 抽样）。
来源：<https://github.com/gl-transitions/gl-transitions/blob/master/transitions/Disintegrate.glsl>

```glsl
float release(vec2 c, float h, float half, float s) {
  float front = 1.0 - (c.x + half) / (2.0*half) + 0.14*noise(c*s*6.0) + 0.08*(h-0.5);
  return clamp((front + 0.12) / 1.24, 0.0, 1.0) * (1.0 - LIFE);
}
float travel = reach * (0.4 + 0.6*fract(h*13.7)) * t * (0.2 + 0.8*t);   // 先慢后快的加速
float size = mix(0.5, 0.3*(1.0 - 0.5*t)*(0.6 + 0.4*h), smoothstep(0.0,0.25,t));
```

**② `PolkaDotsCurtain.glsl` —— 「点阵帷幕」的数学原型**
`dots = 20`（横跨画面的点数），判据 `distance(fract(uv*dots), .5) < progress / distance(uv, center)`：每个点按 `progress/dist` 长大，等价于「从中心辐射的点阵擦除」。把 `center` 挪到画面左侧很远（如 `vec2(-3.0, 0.5)`），`1/dist` 项退化成近似线性 → **左→右点阵帷幕**。
来源：<https://github.com/gl-transitions/gl-transitions/blob/master/transitions/PolkaDotsCurtain.glsl>

**③ `DirectionalWipe.glsl` —— 斜向软边扫描头**
`direction (1,-1)`（45°）、`smoothness 0.5`，边缘 `smoothstep(-smoothness, 0, ...)`；`smoothness = 0` 得硬边。总时长由外层 progress 映射决定，gl-transitions 惯例 0.6–1.2s。
来源：<https://github.com/gl-transitions/gl-transitions/blob/master/transitions/DirectionalWipe.glsl>

**④ View Transitions API —— 不做粒子时的标准做法（[文档]，未跑 demo）**
`::view-transition-new(root)` 上跑 `clip-path: inset(0 0 0 p%)` + `animation-duration: 520ms` + `mix-blend-mode: normal`，`document.startViewTransition(() => commitTheme())` 一句话接管。Chromium 111+ / Safari 18+ 可用，Firefox 仍需 flag；且它只能做「形状揭示」，做不了碎点。本项目面向普通用户、跨浏览器一致性优先，**结论：只作为降级备选，主路径仍走契约 §6 的 canvas**。
来源：<https://developer.mozilla.org/en-US/docs/Web/API/View_Transition_API>

---

## 6. 给本项目的 12 条可执行参数

1. **点阵间距 24px**（桌面）/ 22px（≤390px 移动端可缩到 20px）；间距取 4 的倍数，避免与 3px 扫描纹产生摩尔纹。
2. **点尺寸**：`DPR = min(devicePixelRatio, 1.5)`；基础点半径 **1.4px**（`arc()` 直径 2.8 逻辑 px），**每 7 格**（`i%7===0 && j%7===0`）换成一个 **2×2px 方块**（`fillRect`），方块不参与磁吸也不参与亮度波。
3. **亮度场**：`L = 0.16 + 0.06*sin(x*.006+t*.5) + 0.05*sin(y*.011-t*.35) + 0.05*sin((x+y)*.0032+t*.22)`，`clamp(L, 0.10, 0.34)`，直接写进 `globalAlpha`（对应 `--dot: rgba(238,240,243,.20)`）。三层波周期分别 ≈ 17s / 18s / 19s，不共振。
4. **磁吸**：半径 **130px**（≈5.4 格）、最大位移 **4px**（≤1/6 格）、力 `(1-(d/r)²)`；松开后每帧 `pos += (target-pos)*0.12`（60fps 下 ~480ms 收敛，比 spring 便宜）。
5. **点击涟漪**：初速 **700px/s**、波前 `amp = d < 24 ? 10 : 6*exp(-(d-24)/90)`、寿命 **1.1s**、并发上限 **3** 个；涟漪只推开（不改点半径），亮度另算。
6. **鼠标提亮**：`+0.32*(1-d/90)²`（90px 内）+ 涟漪 `+0.45*decay`，两者相加后 `clamp ≤ 0.85`（= `--dot-hi` 的 `.80`）。
7. **帧率**：上限 **30fps**（lm-detector 的 24 是纯装饰下限；我们要跟手，取 30）；静止 **2s** 后降到 **8fps**；`visibilitychange` 直接停帧；`prefers-reduced-motion` 只画一帧（取 `t = 3.7` 这类固定时刻）。
8. **预算**：1920×1080 → 80×45 = **3600 点**，单帧 canvas 预算 **≤3ms**；只在 `resize` 与 DPR 变更时重建画布，`ceil(w/24)*ceil(h/24)`，不建 mipmap、不读像素。
9. **帷幕**：斜角 **9°**（每次随机 ±9°，`skewX` 或 canvas 内切线 `dx/dy = tan9°`），扫头 x 从 **-4% → 106%**，**520ms**，缓动 `cubic-bezier(.2,.9,.2,1)`；头部亮带 2px（`--beam`）+ 24px 渐隐拖尾。
10. **碎点**：上限 **900**（移动端 **400**），寿命 **420–700ms** 随机，初速 **120–260px/s**、方向 `(1, -0.3)`（复制 Disintegrate 的 `direction (1,-0.15)` 但更陡），阻力 `v *= 0.96/frame`，尺寸 **1–2.5px**、`alpha *= (1-t)`；数量按「每 1200 逻辑 px² 一个」反推，不按 DOM 节点数（避免长文页爆量）。
11. **时间轴**：`0–520ms` 帷幕推进 → **`540ms` commit `data-theme`** → `620ms` 起碎点消失、新内容按 x 错峰 **0–220ms** 浮现（`blur(6px)→0`、`translateY(6px)→0`）→ 总时长 **1150ms**；转场期间开关只换图标，`pointer-events:none` 的全屏遮罩 `z-index` 低于开关。
12. **降级**：`prefers-reduced-motion: reduce` → 不建 canvas、不建 WebGL、不做碎点，直接 commit + **180ms** 交叉淡入；`visibilitychange`/`contextlost`/`IntersectionObserver` 三种暂停都要有，且**离开视口立即释放**绘制回调。

---

## 来源清单

- lm-detector：<https://github.com/Ikaleio/lm-detector>（`web/src/lib/pixel-renderer.ts`、`pixel-effects.ts`、`components/pixel-shader.tsx`、`shell.css`、`tokens.css`、`lib/motion.ts`）
- bencho：<https://bencho.dev/blocks/glass-bubble>、<https://bencho.dev/blocks/magnetic-dots>、`/assets/index-Cg2ZONiB.js`、`/assets/index-DlgYVlsG.css`
- Rice-dog：<https://github.com/Rice-dog/code-codex>、<https://21st.dev/@ricedog>
- 站点语法：<https://rauno.me>、<https://pacocoursey.com>、<https://ghostty.org>、<https://terminal.shop>
- 转场实现：<https://github.com/gl-transitions/gl-transitions>（`Disintegrate` / `PolkaDotsCurtain` / `DirectionalWipe`）、<https://developer.mozilla.org/en-US/docs/Web/API/View_Transition_API>