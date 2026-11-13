// 点阵背景 —— **抄录**自 bencho.dev 的 `hero-dots`（其前端 bundle：`function A({ink,gap,className,drift})`）。
//
// 这里做的是「逐行还原 + 去掉用不到的分支」，不是自己另发明一套：
//   · 网格 gap 20px、点半径 0.75px，点位置按 (w%gap)/2 对齐（让边缘留半格，看起来才匀）；
//   · 底色亮度来自 10 个「引力池」(Cs)：每点取所有池的高斯衰减最大值，所以画面自带明暗团块，
//     不是均匀铺点；
//   · 鼠标 130px 内是磁铁：力 ∝ (1-d/130)²，最近 24px 内归零（保证指针正下方不堆点），
//     用 2.4Hz 弹簧 + 0.55 阻尼做位移，所以点是被「拉过去又弹回」而不是硬贴；
//   · 点击放一颗涟漪：半径 90px 在 0.9s 内按 (1-(1-t)³) 扩散，波带 20px，亮度与推力都跟着走；
//   · 亮度是「慢衰减」：悬停用 0.28s 时间常数、离开后按 C 的指数衰减收掉，不做逐帧线性淡出；
//   · 主题切换由 MutationObserver 监 data-theme，重新读 `--ink-rgb`（它原本就是为明暗两套写的）。
// 我们对原版只动了两处：① 加了 BASE 常量让点静止时也隐约可见（原版靠 CSS 底纹补这一层）；
// ② 去掉 drift 漫游（我们不需要它自己动，鼠标动就够了）。参数都在下面这张表里。
import { useEffect, useRef } from "react";

const GAP = 20; // 网格间距
const DOT_R = 0.75; // 点半径
const BASE = 0.17; // 原版是 0（静息不亮，靠 CSS 点纹补）；我们删掉了那层 CSS，所以这里给一点底色亮度，单层就够
const MOUSE_R = 130; // 磁吸半径
const MOUSE_FORCE = 9; // 磁吸力度
const SPRING_HZ = 2.4; // 弹簧频率
const DAMPING = 0.55; // 阻尼比
const RIPPLE_LIFE = 0.9; // 涟漪寿命（秒）
const RIPPLE_R = 90; // 涟漪最大半径
const DECAY_HOVER = 0.85; // 悬停时亮度衰减时间常数
const DECAY_IDLE = 0.28; // 离开后衰减时间常数
const CLICK_GAIN = 0.51; // 交互对亮度的贡献系数
const TAU = Math.PI * 2;

// 10 个高斯引力池：[x%, y%, 权重] —— 原版数值，直接照抄，画面才有它那种「一边亮一边暗」
const POOLS = [
  [0.1, 0.28, 0.22],
  [0.9, 0.2, 0.2],
  [0.8, 0.88, 0.17],
  [0.2, 0.92, 0.13],
  [0.33, 0.06, 0.09],
  [0.66, 0.02, 0.1],
  [0.98, 0.62, 0.12],
  [0.02, 0.66, 0.1],
  [0.58, 0.99, 0.09],
  [0.4, 0.97, 0.07],
];

export default function DotsBackdrop() {
  const ref = useRef(null);

  useEffect(() => {
    const cv = ref.current;
    if (!cv) return;
    const ctx = cv.getContext("2d");
    if (!ctx) return;

    const fine = matchMedia("(hover: hover) and (pointer: fine)").matches;
    const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
    const interactive = fine && !reduce;

    let W = 0;
    let H = 0;
    let dots = [];
    let raf = 0;
    let last = 0;
    let energy = 0; // 指针活跃度（进入后 0→1，离开后指数衰减）
    let inView = true;
    let hovering = false;
    let px = -9999;
    let py = -9999;
    let lastMove = 0;
    let ink = "238, 240, 243";
    let gain = 1;
    const ripples = [];
    /* 滚轮呼吸：滚动时在这条点阵带上随机点亮几团，1.7s 内淡出（局部、连续、随机） */
    let pulses = [];
    let lastScrollAt = 0;

    const readInk = () => {
      const raw = getComputedStyle(document.documentElement).getPropertyValue("--ink-rgb").trim();
      ink = raw || "238, 240, 243";
      gain = document.documentElement.dataset.theme === "geek" ? 1 : 1.2;
    };

    const build = () => {
      const rect = cv.getBoundingClientRect();
      W = rect.width;
      H = rect.height;
      const dpr = Math.min(2, window.devicePixelRatio || 1);
      cv.width = Math.round(W * dpr);
      cv.height = Math.round(H * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      readInk();
      dots = [];
      const startX = (W % GAP) / 2;
      const startY = (H % GAP) / 2;
      for (let y = startY; y < H; y += GAP) {
        for (let x = startX; x < W; x += GAP) {
          let a = 0;
          for (const [ox, oy, w] of POOLS) {
            const radius = w * Math.max(W, H * 2);
            const dist = Math.hypot(x - ox * W, (y - oy * H) * 1.4) / radius;
            a = Math.max(a, Math.exp(-dist * dist * 2.2));
          }
          dots.push({ x, y, a, ox: 0, oy: 0, vx: 0, vy: 0, lit: 0 });
        }
      }
      draw(0);
    };

    const draw = (dt) => {
      const grabbed = interactive && hovering && performance.now() - lastMove < 1200;
      const mx = grabbed ? px : -9999;
      const my = grabbed ? py : -9999;

      energy = performance.now() - lastMove < 350 ? Math.min(1, energy + dt / 0.15) : energy * Math.exp((-dt / 0.6) * 3);

      ctx.clearRect(0, 0, W, H);
      const now = performance.now();
      while (ripples.length && (now - ripples[0].at) / 1000 > RIPPLE_LIFE) ripples.shift();
      for (const p of pulses) p.life -= dt / 1.7;
      pulses = pulses.filter((p) => p.life > 0);

      let alive = (dt > 0 && energy > 0.01) || ripples.length > 0 || grabbed || pulses.length > 0;
      const k = (TAU * SPRING_HZ) ** 2;
      const damp = 2 * Math.sqrt(k) * DAMPING;

      for (const dot of dots) {
        const dx0 = mx - dot.x;
        const dy0 = my - dot.y;
        const dist = Math.hypot(dx0, dy0);
        const pull = grabbed && dist < MOUSE_R ? 1 - dist / MOUSE_R : 0;
        const force = pull * pull * MOUSE_FORCE * Math.min(1, dist / 24);
        let tx = dist > 0.01 ? (dx0 / dist) * force : 0;
        let ty = dist > 0.01 ? (dy0 / dist) * force : 0;

        let rippleGlow = 0;
        for (const pulse of pulses) {
          const ddx = dot.x - pulse.x;
          const ddy = dot.y - pulse.y;
          const dd2 = ddx * ddx + ddy * ddy;
          const rr2 = pulse.r * pulse.r;
          if (dd2 < rr2) {
            const f = 1 - dd2 / rr2;
            rippleGlow = Math.max(rippleGlow, 0.5 * f * f * pulse.life);
          }
        }
        for (const rp of ripples) {
          const age = (now - rp.at) / 1000;
          const ddx = dot.x - rp.x;
          const ddy = dot.y - rp.y;
          const dd = Math.hypot(ddx, ddy);
          const prog = age / RIPPLE_LIFE;
          const ring = RIPPLE_R * (1 - (1 - prog) ** 3);
          const band = Math.max(0, dd - ring) / 20;
          const g = Math.exp(-band * band) * (1 - prog) ** 1.5;
          if (g < 0.01) continue;
          rippleGlow = Math.max(rippleGlow, g);
          const push = Math.exp(-(((dd - ring) / 20) ** 2));
          if (dd > 0.01) {
            tx += (ddx / dd) * push * rippleGlow * 3;
            ty += (ddy / dd) * push * rippleGlow * 3;
          }
        }

        if (dt > 0) {
          dot.vx += (k * (tx - dot.ox) - damp * dot.vx) * dt;
          dot.vy += (k * (ty - dot.oy) - damp * dot.vy) * dt;
          dot.ox += dot.vx * dt;
          dot.oy += dot.vy * dt;
          if (
            Math.abs(dot.ox - tx) > 0.02 ||
            Math.abs(dot.oy - ty) > 0.02 ||
            Math.abs(dot.vx) > 0.5 ||
            Math.abs(dot.vy) > 0.5
          ) {
            alive = true;
          }
        }

        const target = Math.max(pull * pull * (grabbed ? 1 : energy), rippleGlow);
        if (dt > 0) {
          dot.lit = Math.max(target, dot.lit * Math.exp(-dt / (grabbed ? DECAY_HOVER : DECAY_IDLE)));
          if (dot.lit > 0.01) alive = true;
        } else {
          dot.lit = Math.max(dot.lit, target);
        }

        const alpha = (dot.a * BASE + dot.lit * CLICK_GAIN) * gain;
        if (alpha < 0.012) continue;
        ctx.fillStyle = `rgba(${ink}, ${alpha.toFixed(3)})`;
        ctx.beginPath();
        ctx.arc(dot.x + dot.ox, dot.y + dot.oy, DOT_R * (1 + pull * 0.25 + rippleGlow * 0.6), 0, TAU);
        ctx.fill();
      }
      return alive;
    };

    const loop = () => {
      if (raf) return;
      const t0 = performance.now();
      const tick = (now) => {
        const dt = Math.min(0.033, (now - t0) / 1000);
        last = now;
        if (!draw(dt) && !hovering) {
          raf = 0;
          return;
        }
        raf = requestAnimationFrame(tick);
      };
      raf = requestAnimationFrame(tick);
    };
    void last;

    const onMove = (e) => {
      if (e.pointerType !== "mouse") return;
      const rect = cv.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;
      const inside = x >= 0 && y >= 0 && x <= rect.width && y <= rect.height;
      if (!inside && !hovering) return;
      hovering = inside;
      px = x;
      py = y;
      lastMove = performance.now();
      loop();
    };
    const onDown = (e) => {
      if (e.pointerType !== "mouse" || e.button !== 0) return;
      const rect = cv.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;
      if (x < 0 || y < 0 || x > rect.width || y > rect.height) return;
      ripples.push({ x, y, at: performance.now() });
      loop();
    };
    const onLeave = () => {
      if (!hovering) return;
      hovering = false;
      loop();
    };
    /* 滚轮呼吸：每 90ms 最多放一团，位置随机、半径 120–240，1.7s 淡出；
       连续滚会有好几团叠在一起，读起来像这片点阵在「吸气」 */
    const onScroll = () => {
      if (reduce) return;
      const now = performance.now();
      if (now - lastScrollAt < 90) return;
      lastScrollAt = now;
      const n = Math.random() < 0.45 ? 2 : 1;
      for (let i = 0; i < n; i++) {
        W = cv.clientWidth || W;
        H = cv.clientHeight || H;
        pulses.push({
          x: (0.12 + Math.random() * 0.76) * W,
          y: (0.12 + Math.random() * 0.8) * H,
          r: 120 + Math.random() * 120,
          life: 1,
        });
      }
      if (pulses.length > 8) pulses.splice(0, pulses.length - 8);
      loop();
    };

    build();
    // 主题切换时重新读 --ink-rgb（原版也是这么写的：MutationObserver 盯 data-theme）
    const mo = new MutationObserver(() => {
      readInk();
      if (!raf) draw(0);
    });
    mo.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });

    const ro = new ResizeObserver(() => build());
    ro.observe(cv);
    const io = new IntersectionObserver(([entry]) => {
      inView = entry.isIntersecting;
      if (inView && !reduce) loop();
      else if (!inView && raf) {
        cancelAnimationFrame(raf);
        raf = 0;
      }
    });
    io.observe(cv);

    if (interactive) {
      addEventListener("pointermove", onMove, { passive: true });
      addEventListener("pointerdown", onDown, { passive: true });
      document.documentElement.addEventListener("pointerleave", onLeave);
    }
    addEventListener("scroll", onScroll, { passive: true });
    void inView;

    return () => {
      if (raf) cancelAnimationFrame(raf);
      raf = 0;
      ro.disconnect();
      io.disconnect();
      mo.disconnect();
      removeEventListener("pointermove", onMove);
      removeEventListener("pointerdown", onDown);
      document.documentElement.removeEventListener("pointerleave", onLeave);
      removeEventListener("scroll", onScroll);
    };
  }, []);

  return (
    <>
      <canvas ref={ref} className="dotsbackdrop" aria-hidden="true" />
    </>
  );
}