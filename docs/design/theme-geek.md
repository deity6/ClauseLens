# 主题 B「Quiet Dark」契约 v2

> 两套主题：A = 现有「验光单」暖纸（`data-theme="light"`，不动）；B = 近黑极简（`data-theme="geek"`）。
> **v2 与 v1 的区别**：v1 是自制的「终端/扫描风」（角标、括号、刻度尺、扫描线），被否了；
> v2 全部从三家现成站点**搬**过来，只保留参数调节，不自己发明视觉语言。

## 0. 来源（照抄对象）

| 搬什么 | 从哪搬 | 拿到的是 |
|---|---|---|
| 色板 / 字体层级 / 圆角 / 缓动 / 卡片 hover | **SOFT LAB** <https://doit.loc.cc>（开源：`github.com/deity6/softlab`，`src/styles/index.css`） | 源码级 token |
| 点阵背景 / 分段控件 / 胶囊按钮 / 面板 | **bencho.dev**（`hero-dots` canvas + `.canvas-root` 静态点纹 + `glass-bubble` 面板） | 源码级（bundle 逐行还原） |
| 像素落幕转场 | **lm-detector** <https://github.com/Ikaleio/lm-detector>（`web/src/lib/pixel-effects.ts` 的 `bayer4` / `blocks`） | 源码级 |
| 组件库参考 / 是否有源码的判定 | uipicks.top 的 `ai/catalog.json`（`code:true` 才去下游取源码） | 索引 |

调研笔记：`docs/design/theme-geek-refs.md`、`out/ref/refs-2.md`。

## 1. Token（`theme-geek.css` 的 `[data-theme="geek"]` 块，全部是 SOFT LAB 原文值）

```
--paper:#0b0e14  --paper-2:#070910  --sheet:#171c28  --paper-3:#10141d
--ink:#e8ecf4    --ink-2:#a3adc0    --ink-3:#7d8899   --ink-rgb:232,236,244
--line:rgb(255 255 255/.1)          --line-2:rgb(255 255 255/.22)
--accent:#7aa9ff --accent-soft:#a3c4ff --accent-wash:#16233f
```

- 强调色**必须** `#7aa9ff`：`#3b82f6` 在 `#0b0e14` 上只有 3.4:1，小字读不出来。
- 语义色只出现在「点 / 等级字母 / 小标签」上：`--good #58c48f`、`--warn #e6b45c`、`--bad #f07575`，
  等级 A–E 同一色系。
- 圆角二选一，我们取**圆角派**：卡片 10–12px、大面板 18px、按钮/标签 999px、浮层 10–16px。
- 字体：`"Inter Variable","Inter","Helvetica Neue","PingFang SC","Microsoft YaHei"`（SOFT LAB 的栈；
  它没打包 Inter，我们自托管了 `@fontsource-variable/inter`）；等宽只留给机器读数。
- 只给标题 `-0.035em ~ -0.045em`、正文 `-0.006em`；**不用** `-webkit-font-smoothing: antialiased`（原文也没有）。

## 2. 背景：两层点阵（都是 bencho 的写法）

```css
/* ① 常驻：纯 CSS，零 JS */
.dotsstatic{background-image:radial-gradient(rgba(var(--ink-rgb),.13) 1px,transparent 1px);background-size:22px 22px}
/* ② 交互：canvas，静息 alpha=0，只有光标/点击会点亮 */
.hero-dots{left:-20px;width:calc(100% + 40px);mask-image:linear-gradient(#0000,#000 24% 70%,#0000)}
```

`DotsBackdrop.jsx` 是 bencho `hero-dots` 的**逐行还原**：gap 20、点半径 .75、10 个高斯池、
磁吸 130px / 力度 9、最近 24px 归零、2.4Hz 弹簧 + 0.55 阻尼、点击涟漪 90px / 0.9s / 波带 20px、
亮度按 0.28s（悬停）/ 0.85s（离开）时间常数衰减；`MutationObserver` 盯 `data-theme` 重新读 `--ink-rgb`；
`IntersectionObserver` 离开视口停帧；`prefers-reduced-motion` 不挂指针。对原版唯一的改动：去掉 drift 漫游。

另有一层顶部冷光（`html::before`：`radial-gradient(1200px 640px at 50% -18%, rgba(122,162,255,.17), transparent)`），
这是全站唯一的“氛围层”，没有噪点、没有扫描纹、没有水印、没有四角角标。

## 3. 组件语法（`theme-geek-components.css`）

- **卡片**：`1px var(--line)` + `background: color-mix(sheet 55%, transparent)`，无投影；
  hover：`translateY(-3px)` + 底色抬到 92% + `0 16px 34px rgba(0,0,0,.45)`，450ms `cubic-bezier(.22,1,.36,1)`（SOFT LAB 原值）。
- **按钮**：胶囊；主按钮白底深字（bencho 的 “Add to bench”）；次按钮 1px 边框，hover 只加 6% 白底；`active` 不下移（保持在原位）。
- **标签**：`.ttag` / `.pill` 统一胶囊 + 发丝线，语义色只染边框与图标，不铺整块底色。
- **标题层级**：h2 600–700 / -0.03em；正文 15px；`.meta` 11px / .08em / 500（**不再**全站大写等宽 + 括号）。
- **印章**：圆形双环 + 墨晕全部隐藏，改成一个 18px 圆角面板里的一枚大字母（颜色=等级色）。
- **进度轨**：圆点、完成=强调色实心、活动=4px 光晕；没有方块、没有虚线轨道。
- **雷达**：细网格 + 1.5px 强调色折线 + 12% 面积填充 + 顶点圆点；维度条回到 4px 圆角细条。
- **等待页文档纸**：18px 圆角面板 + 细骨架条 + 一条 1px 扫描线（不再点阵行/读数墙）。

## 4. 切换转场：一次铺的「化开」（View Transitions，2026-11-14 起）

**旧的像素落幕是两段**（先全铺新底色 → 再擦开）。用户反馈「一次切换要铺两次」，而且两段都往同一个方向扫，
看起来就是两遍。根因没法绕：DOM 只有一个主题，必须等铺满那一帧才敢换 `data-theme`。

现在主路径改成浏览器自带的 View Transitions：

1. `document.startViewTransition(() => applyTheme(next))` —— 浏览器替我们留一张**旧页快照**
   （`::view-transition-old(root)`），换主题后的活页面是 `::view-transition-new(root)`；
2. 两层同时存在，于是只需要**一次** mask 动画：旧页从右上角（开关所在）向外被一个圆化掉，
   新的那层在底下同时露出来 —— 不再有「先黑屏再上色」；
3. mask 是 `radial-gradient(circle at 开关) + @property --cl-r`，2.2s、`cubic-bezier(.33,.05,.35,1)`；
   圆的波前天然满足「y 轴不对齐、有快有慢」：中间那行先过、越远越晚，同一行里中间快两头慢；
   边是一条 4.5% 半径宽的溶解带，所以是「化开」不是「切过去」；
4. **降级**：没有 `startViewTransition` 的浏览器仍走 `theme-wipe.js` 的画布版（已放慢到
   `380 + 40 + 980ms`，`order` 里给每行加了 0–7% 的偏置，前沿不再是一条竖线）。

实现：`src/theme-transition.css`（伪元素 + `@property --cl-r`）、`src/lib/theme-wipe.js`（选择走哪条路）。
`prefers-reduced-motion` 下两边都不播动画，直接换主题。

## 5. 文件

| 文件 | 内容 |
|---|---|
| `src/lib/theme.js` | 主题状态（localStorage `cl:theme`、首帧前落地） |
| `src/lib/theme-wipe.js` | 像素转场 |
| `src/components/ThemeSwitch.jsx` | 右上角分段开关 |
| `src/components/DotsBackdrop.jsx` | 点阵背景（bencho hero-dots 移植） |
| `src/components/{ScanDoc,Radar}.{jsx,css}` | 等待页文档纸 / 六维雷达 |
| `src/theme-geek.css` / `theme-geek-components.css` | token+基础层 / 组件皮肤 |
## 3.5 纯黑白（2026-11-13 第三轮）

用户要求：**纯黑 + 白**，参照 bencho.dev；评分徽章用 `ascii.txt` 里那套 ASCII 点阵；页脚搬 bencho 的
点阵山脊；点阵背景不要再全铺满、也不要有两层。

- **色板**：`--paper:#000`、`--paper-2:#0a0a0a`、`--paper-3:#121212`、`--sheet:#161616`、
  `--ink:#fff`、`--ink-2:#b4b4b4`、`--ink-3:#7c7c7c`、`--line:rgba(255,255,255,.1)`；
  `--accent` = 纯白；语义色与 A–E 全部落成灰阶（好坏靠图标 + 边框粗细，不再靠色相）。
- **点阵**：只剩一层（canvas），高度 640px 贴顶、底部渐隐；`BASE=0.17` 让静息可见
  （原版靠另一层 CSS 点纹补，我们删掉了那层）。布局上只在首屏出现，页面下方是纯黑。
- **评分徽章**：`ScoreBadge.jsx` → `AsciiField.jsx`（ascii.txt 的 ASCIIWake 原算法）把等级字母
  光栅化成掩膜，掩膜里的格子是圆点；悬停会把点变成字符梯度（@ # + …）再冷却。纸主题仍是原来的圆形钢印。
- **页脚**：`RidgeFoot.jsx` 用 bencho 页脚那块 `.foot-field` 的密度场（原文 `to(x,y,H)` 三条正弦天际线 +
  `r^1.4`），贴页面底部一条 188px 的带，墨色压到 26%，鼠标扫过会冒出字符。
