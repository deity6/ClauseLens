import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App.jsx";

// ───────── 字体 ─────────
// 中文 webfont 全是 unicode-range 分片：浏览器只拉页面里真正出现的字所在的那几片。
// 展示 · 霞鹜文楷（楷书，有笔锋）｜大数字 · Instrument Serif｜标签 · Space Mono（三者都是特色）
// 正文不挂 webfont：思源黑体分片是首屏最大的一笔开销（实测结果页 1.29 MB 里大头是它），
// 而正文用系统黑体（Windows 微软雅黑 / macOS 苹方）观感差别很小，不值得为此多下几百 KB。
import "lxgw-wenkai-webfont/lxgwwenkai-regular.css";
import "lxgw-wenkai-webfont/lxgwwenkai-bold.css";
import "@fontsource/instrument-serif/latin-400.css";
import "@fontsource/space-mono/latin-400.css";
import "@fontsource/space-mono/latin-700.css";
// 主题 B 的正文/标题字体用 grotesque（Inter），
// 中文交回系统黑体（PingFang / 雅黑），不额外拉中文字体包。
import "@fontsource-variable/inter/wght.css";

import "./patterns.css";
import "./styles.css";
import "./tldr-means.css";
import "./theme-transition.css";
// 主题 B（点阵）的两层：基础层 + 组件皮肤层。全部规则挂在 [data-theme="geek"] 下，
// 浅色主题不受影响；因为体积不大且切换要即时，直接静态引入（不做按需加载）。
import "./theme-geek.css";
import "./theme-geek-components.css";

import { applyTheme, getTheme, startSystemThemeSync } from "./lib/theme.js";

// 主题：index.html 的内联首帧脚本已经在首帧前写过一次 data-theme（防闪白；CSP hash 见 scripts/csp-hash.mjs），
// 这里再走一遍统一入口，把 color-scheme 与 <meta theme-color> 一并对齐。
applyTheme(getTheme(), { persist: false });
// 手机 / 平板：没手动选过主题时跟随系统深浅色（桌面不动）
startSystemThemeSync();

// 底纹随时可切：?pattern=iris（见 patterns.css 顶部清单）
const _pat = new URLSearchParams(location.search).get("pattern");
if (_pat) document.documentElement.dataset.pattern = _pat;

const _font = new URLSearchParams(location.search).get("font");
if (_font) document.documentElement.dataset.font = _font;

// 光晕与视差：CSS 只读变量，JS 负责算。
// --scroll → 背景/花环按不同速度移动，形成纵深。
// --mx1..3/--my1..3 → 三层光晕用不同阻尼系数追同一个鼠标点：快的当「头部」、慢的当「尾巴」，
//   于是光晕不是死死黏在指针上，而是拖着一条尾巴滑过去，松手后还会慢慢收拢。
{
  const root = document.documentElement;
  const layers = [
    { k: 0.2, x: 0, y: 0, vx: "--mx1", vy: "--my1", init: false },
    { k: 0.095, x: 0, y: 0, vx: "--mx2", vy: "--my2", init: false },
    { k: 0.042, x: 0, y: 0, vx: "--mx3", vy: "--my3", init: false },
  ];
  let tx = window.innerWidth * 0.5;
  let ty = window.innerHeight * 0.38;
  let running = false;
  const tick = () => {
    let alive = false;
    for (const L of layers) {
      if (!L.init) {
        L.x = tx;
        L.y = ty;
        L.init = true; // 第一帧不要从 0,0 飞过来
      }
      const dx = tx - L.x;
      const dy = ty - L.y;
      L.x += dx * L.k;
      L.y += dy * L.k;
      root.style.setProperty(L.vx, `${L.x.toFixed(1)}px`);
      root.style.setProperty(L.vy, `${L.y.toFixed(1)}px`);
      if (Math.abs(dx) > 0.5 || Math.abs(dy) > 0.5) alive = true;
    }
    if (alive) requestAnimationFrame(tick);
    else running = false;
  };
  window.addEventListener(
    "pointermove",
    (e) => {
      tx = e.clientX;
      ty = e.clientY;
      if (!running) {
        running = true;
        requestAnimationFrame(tick);
      }
    },
    { passive: true }
  );
  window.addEventListener(
    "scroll",
    () => root.style.setProperty("--scroll", String(window.scrollY)),
    { passive: true }
  );
  requestAnimationFrame(tick); // 先把初始位置写进去
}

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <App />
  </StrictMode>
);