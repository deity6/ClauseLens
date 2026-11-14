// 主题转场：像素方块「落幕」。
//
// 算法不是我们编的 —— 直接照 Ikaleio/lm-detector 的像素风片元着色器改写：
//   web/src/lib/pixel-effects.ts 里的 bayer4() 有序抖动 + blocks()「逐块显现 / 逐块擦除」，
//   web/src/lib/pixel-renderer.ts 里 canvas 每格 = 一个设备像素、再用 CSS 放大（image-rendering: pixelated）。
// 搬过来的三条语法：
//   ① 网格是 4px 一格的真像素（不是模糊的粒子）；画布分辨率 = ceil(宽/4) × ceil(高/4)；
//   ② 边界用 4×4 Bayer 有序抖动：前沿不是一条线，而是一片逐渐加密的方格；
//   ③ 时间按 steps(fps) 量化（他们用 10/12/24fps）——一格一格跳，不做平滑插值。
//
// 为什么这样能藏住换主题的那一帧：新底色的像素铺满屏幕时，底下换没换谁也看不见；
// 等 data-theme 换完，再按同样的抖动规则从左边把格子擦掉 —— 擦掉的格子露出的是
// **新主题的正文**（底色同色，看不出接缝，只有文字透出来），于是读起来就是
// 「旧页面被像素吃掉，新页面的字一格一格长出来」。
import { applyTheme, getTheme, otherTheme, prefersReducedMotion } from "./theme.js";

const CELL = 4; // 每格 CSS 像素（对齐 lm-detector 的默认 cell=4）
const FPS = 15; // 时间量化，15 帧/秒
// v3：整体放慢（原来 560+60+520 ≈ 1.14s，用户嫌快）。这套是**没有 View Transitions
// 的浏览器**才走的兜底：仍然要「铺满 → 换主题 → 擦开」两段，只能把第一段压短、第二段拉长。
const D_FILL = 380; // 像素铺满（比原来短：它只是藏住换主题那一帧）
const D_HOLD = 40; // 铺满后停一拍
const T_COMMIT = D_FILL + D_HOLD;
const D_REVEAL = 980; // 从左边擦掉（= 新内容长出来）
const T_END = T_COMMIT + D_REVEAL;
const EDGE = 0.075; // 前沿抖动带宽度（占屏宽比例）
const P_FULL = 1.12; // 让最右侧、带噪声的格子也过线（order 最大 ≈1.02）
const WIPE_MS = 2200; // View Transitions 版总时长（ms），写进 --cl-wipe-ms

let canvas = null;
let ctx = null;
let img = null;
let buf = null;
let raf = 0;
let busy = false;
let startedAt = 0;
let cfg = null;
let lastTick = -1;
let order = null;

const fract = (v) => v - Math.floor(v);
const rand = (a, b) => a + Math.random() * (b - a);

// ── lm-detector pixel-effects.ts 原样搬过来的三个函数 ──────────────────
function bayer2(x, y) {
  return fract(Math.floor(x) / 2 + Math.floor(y) * Math.floor(y) * 0.75);
}
function bayer4(x, y) {
  return bayer2(x * 0.5, y * 0.5) * 0.25 + bayer2(x, y);
}
function hash(x, y, seed) {
  const p3 = [fract((x + seed) * 0.1031), fract((y + seed) * 0.1031), fract((x + seed) * 0.1031)];
  const d = p3[0] * (p3[1] + 33.33) + p3[1] * (p3[2] + 33.33) + p3[2] * (p3[0] + 33.33);
  p3[0] += d;
  p3[1] += d;
  p3[2] += d;
  return fract((p3[0] + p3[1]) * p3[2]);
}

function readTokens(el) {
  const s = getComputedStyle(el);
  const v = (n, fb) => (s.getPropertyValue(n) || "").trim() || fb;
  return { paper: v("--paper", "#ffffff"), ink: v("--ink", "#171614"), beam: v("--beam", "#c98b4b") };
}

/** 读「假如主题是 t」的 token：把 <html> 的属性临时改一下读计算值（同步，不渲染）。 */
function tokensOf(theme) {
  const root = document.documentElement;
  const prev = root.dataset.theme;
  if (prev !== theme) root.dataset.theme = theme;
  const out = readTokens(root);
  if (prev !== theme) root.dataset.theme = prev;
  return out;
}

/** 任意 CSS 颜色 → [r,g,b]（借它的办法：用 2D 画布把 color-mix/oklch 都转成 sRGB）。 */
let probeCtx = null;
function rgbOf(color) {
  if (!probeCtx) {
    const c = document.createElement("canvas");
    c.width = c.height = 1;
    probeCtx = c.getContext("2d", { willReadFrequently: true });
  }
  probeCtx.clearRect(0, 0, 1, 1);
  probeCtx.fillStyle = color;
  probeCtx.fillRect(0, 0, 1, 1);
  const [r, g, b] = probeCtx.getImageData(0, 0, 1, 1).data;
  return [r, g, b];
}
const mixRGB = (a, b, k) => a.map((v, i) => Math.round(v + (b[i] - v) * k));
const pack = ([r, g, b]) => ((255 << 24) | (b << 16) | (g << 8) | r) >>> 0;

function ensure() {
  if (canvas) return;
  canvas = document.createElement("canvas");
  canvas.className = "theme-wipe";
  canvas.setAttribute("aria-hidden", "true");
  document.body.appendChild(canvas);
  ctx = canvas.getContext("2d");
  resize();
  addEventListener("resize", resize, { passive: true });
}

function buildOrder(cols, rows, seed) {
  // 每格的先后次序：从左到右 + 稳定噪声 + **每行自己的快慢** → 前沿是毛的、斜的，
  // 不是一条直线（用户：y 轴上不一定全对齐，可以有快有慢）。
  const arr = new Float32Array(cols * rows);
  const rowsBias = new Float32Array(rows);
  for (let y = 0; y < rows; y++) {
    // 0–0.07 的行偏置：几条大波长（≈400px）叠一点点逐行噪声 —— 有的行领先、有的落后，
    // 但不要变成「百叶窗」。之前 0.11 + 17 行周期太碎，前沿像撕纸。
    rowsBias[y] = (Math.sin(y * 0.055 + seed * 0.13) * 0.5 + 0.5) * 0.055 + (hash(0.5, y * 0.21, seed) - 0.5) * 0.022;
  }
  for (let y = 0; y < rows; y++) {
    for (let x = 0; x < cols; x++) {
      arr[y * cols + x] = Math.min(1.02, (x / cols) * 0.88 + rowsBias[y] + hash(x * 0.5, y * 0.5, seed) * 0.05);
    }
  }
  return arr;
}

function resize() {
  if (!canvas) return;
  const cols = Math.ceil(window.innerWidth / CELL);
  const rows = Math.ceil(window.innerHeight / CELL);
  canvas.width = cols;
  canvas.height = rows;
  canvas.style.width = cols * CELL + "px";
  canvas.style.height = rows * CELL + "px";
  img = ctx.createImageData(cols, rows);
  buf = new Uint32Array(img.data.buffer);
  // 尺寸变了要重算次序——但如果此刻正在转场，必须当场补上，
  // 否则绘制循环会读到 null 直接抛错，画布就停在最后一帧（第一次踩的就是这个坑）。
  order = busy && cfg ? buildOrder(cols, rows, cfg.seed) : null;
}

function teardown() {
  busy = false;
  cancelAnimationFrame(raf);
  raf = 0;
  removeEventListener("resize", resize);
  canvas?.remove();
  canvas = null;
  ctx = null;
  img = null;
  buf = null;
  order = null;
  cfg = null;
}

// ── 像素擦除之后的内容浮现：按 x 错峰，扫到哪亮到哪 ─────────────────────
const SWEEP_SEL = [
  ".topbar",
  ".stage h1",
  ".stage h2",
  ".stage h3",
  ".stage p",
  ".stage li",
  ".stage .meta",
  ".stage button",
  ".stage .doccard",
  ".stage .ttag",
  ".stage .tag",
  ".stage .paper",
  ".stage .radar",
  ".stage .dimbar",
  ".stage .stamp",
  ".disclaimer",
].join(",");

export function sweepContent(max = 140) {
  const els = [...document.querySelectorAll(SWEEP_SEL)]
    .filter((el) => {
      const r = el.getBoundingClientRect();
      return r.width > 6 && r.height > 6 && r.bottom > -80 && r.top < innerHeight + 80;
    })
    .slice(0, max)
    .map((el) => ({ el, r: el.getBoundingClientRect() }))
    .sort((a, b) => a.r.left + a.r.top * 0.35 - (b.r.left + b.r.top * 0.35));
  const n = Math.max(1, els.length);
  els.forEach(({ el }, i) => {
    el.style.setProperty("--sweep-d", String(Math.round((i / n) * 260)));
    el.classList.add("cl-sweep");
    const clean = () => {
      el.classList.remove("cl-sweep");
      el.style.removeProperty("--sweep-d");
    };
    el.addEventListener("animationend", () => clean(), { once: true });
    setTimeout(clean, 1500);
  });
}

export function startThemeWipe(nextTheme, { onDone } = {}) {
  if (busy) return false;
  const next = nextTheme || otherTheme(getTheme());
  const from = getTheme();

  if (prefersReducedMotion()) {
    applyTheme(next);
    sweepContent();
    onDone?.();
    return true;
  }

  // ① 首选 View Transitions（Chromium 111+）：浏览器替我们拍一张**旧页快照**，
  //    换主题后的活页面是另一层。两层同时存在，所以能做到「一次铺」——
  //    旧的那层从开关那里向外化掉，新的那层同时在底下露出来，不再有「先全黑再上色」。
  //    波形/时长/原点都在 theme-transition.css 里（原点用 --cl-ox/--cl-oy 传开关位置）。
  if (typeof document.startViewTransition === "function") {
    busy = true;
    const root = document.documentElement;
    const sw = document.querySelector(".liq-sw");
    if (sw) {
      const r = sw.getBoundingClientRect();
      // 开关在屏幕外（页面滚下去了 / 键盘触发的）时夹进视口：否则圆从视口上方很远的
      // 地方开始长，前 1 秒屏幕里什么都不会发生 —— 看起来像「转场坏了」。
      const ox = Math.min(98, Math.max(2, ((r.left + r.width / 2) / innerWidth) * 100));
      const oy = Math.min(98, Math.max(2, ((r.top + r.height / 2) / innerHeight) * 100));
      root.style.setProperty("--cl-ox", `${ox.toFixed(1)}%`);
      root.style.setProperty("--cl-oy", `${oy.toFixed(1)}%`);
    }
    root.style.setProperty("--cl-wipe-ms", `${WIPE_MS}ms`);
    const done = () => {
      busy = false;
      root.style.removeProperty("--cl-wipe-ms");
      root.style.removeProperty("--cl-ox");
      root.style.removeProperty("--cl-oy");
      onDone?.();
    };
    try {
      const vt = document.startViewTransition(() => applyTheme(next));
      vt.finished.then(done, done);
      return true;
    } catch {
      done();
      // 掉到下面的画布落幕（老浏览器 / 被策略禁用的情况）
    }
  }

  ensure();
  busy = true;
  startedAt = performance.now();
  lastTick = -1;

  const newT = tokensOf(next);
  const cols = canvas.width;
  const rows = canvas.height;
  const paperRGB = rgbOf(newT.paper);
  const FILL = pack(paperRGB);
  const EDGE_C = pack(mixRGB(paperRGB, rgbOf(newT.beam), 0.42));
const FILL_DIM = pack(mixRGB(paperRGB, rgbOf(newT.beam), 0.07)); // 抬起那层的一点点扫描纹，让「还没擦到」的地方看得出是一块屏

  const seed = rand(0, 100);
  order = buildOrder(cols, rows, seed);
  cfg = { next, onDone, committed: false, seed };

  const quantize = (t) => Math.floor(t / (1000 / FPS)) * (1000 / FPS);

  /** p: 0 → P_FULL。铺：probe>0 的格子实心，处于抖动带的格子按 bayer4 决定。 */
  const drawFill = (p) => {
    for (let y = 0; y < rows; y++) {
      const row = y * cols;
      const by = y & 3;
      for (let x = 0; x < cols; x++) {
        const i = row + x;
        const probe = (p - order[i]) / EDGE;
        let v = 0;
        if (probe >= 1) v = FILL;
        else if (probe > -1 && bayer4(x & 3, by) < (probe + 1) * 0.5) v = probe < 1 ? EDGE_C : FILL;
        buf[i] = v;
      }
    }
  };

  /** 擦：和铺完全同一套抖动，只是方向反过来——从左边开始把格子擦掉。 */
  const drawReveal = (p) => {
    for (let y = 0; y < rows; y++) {
      const row = y * cols;
      const by = y & 3;
      // 还没擦到的格子留一层极淡的横向扫描纹（每 4 行一条），这样「抬起的那层」看得出是一块屏，
      // 而不是和页面底色完全一样（否则擦的时候只有文字能透出来，过程看不见）。
      const still = by === 0 ? FILL_DIM : FILL;
      for (let x = 0; x < cols; x++) {
        const i = row + x;
        const probe = (p * P_FULL - order[i]) / EDGE;
        let v = still;
        if (probe >= 1) v = 0;
        else if (probe > -1) {
          // 前沿的擦除头：擦到一半的格子用提亮色，读起来是「橡皮擦在发光」
          v = bayer4(x & 3, by) < (probe + 1) * 0.5 ? 0 : EDGE_C;
        }
        buf[i] = v;
      }
    }
  };

  const frame = (now) => {
    try {
      const t = now - startedAt;
      const q = quantize(t);
      if (q === lastTick) {
        raf = requestAnimationFrame(frame);
        return;
      }
      lastTick = q;

      if (t <= T_COMMIT) {
        drawFill(Math.min(P_FULL, (q / D_FILL) * P_FULL));
        if (!cfg.committed && q >= D_FILL) {
          cfg.committed = true;
          applyTheme(cfg.next);
          sweepContent();
        }
      } else if (t <= T_END) {
        drawReveal(Math.min(1, (q - T_COMMIT) / D_REVEAL));
      } else {
        const done = cfg?.onDone;
        teardown();
        done?.();
        return;
      }
      ctx.putImageData(img, 0, 0);
      raf = requestAnimationFrame(frame);
    } catch (err) {
      // 兜底：画布不能把切换卡在半路（宁可少一段动画，也不能让页面停在黑屏上）
      console.error("[theme-wipe]", err);
      const next = cfg?.next;
      teardown();
      if (next) applyTheme(next);
      sweepContent();
    }
  };

  raf = requestAnimationFrame(frame);
  return true;
}

export function isWiping() {
  return busy;
}