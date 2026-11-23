// ASCII 点阵场：把文本光栅化成圆点掩膜，悬停时点会变成字符梯度，松手按 trail 冷却。
// 三处适配：
//   ① 尺寸不再写死 360×240，改成跟随容器（ResizeObserver），并能传 own mask；
//   ② 第 4 节「你要判断的部分」：--fill-on / --ink 直接映射到本项目的 --ink（见 theme-geek.css），
//      不再定义新全局；
//   ③ mask 从「立方体」抽象成可注入的采样函数，这样同一套算法能同时画：评分徽章（字母）、页脚山脊。
//
// 原理没变：一格一个数（热度），指针沿着移动轨迹往里加温、每帧整体按同一比例冷却，
// 数字决定这一格取字符梯度上的第几个；冷的地方是圆点（半调），热的地方才出字符。
import { useEffect, useRef } from "react";

const clamp = (v, a, b) => Math.min(b, Math.max(a, v));
const MONO = `ui-monospace, "SF Mono", SFMono-Regular, Menlo, Consolas, monospace`;

/* lightest to densest; the first is always a blank */
export const RAMPS = {
  Classic: [" ", ".", ":", "-", "=", "+", "*", "#", "%", "@"],
  Blocks: [" ", "·", "░", "▒", "▓", "█"],
  Dots: [" ", "·", "•", "●"],
  Binary: [" ", ".", ":", "0", "1"],
};

/* below this much heat a cell is the field: a dot */
const COLD = 0.04;
/* how long a press's ring takes to spread and fade, s */
const RING_S = 2.2;

/* ── Bencho 页脚那条山脊的密度场（原样搬的 `to(e,t,n)`） ─────────────
   三条正弦叠出天际线，线下越深越密，再乘一层高频细纹；r^1.4 让山脚更实。 */
export function ridgeMask(xs, ys, W, H) {
  const out = new Float32Array(xs.length);
  for (let i = 0; i < xs.length; i++) {
    const x = xs[i];
    const y = ys[i];
    const r = clamp(
      0.5 + (y - H * (0.5 + 0.2 * Math.sin(x * 0.0058 + 0.4) + 0.12 * Math.sin(x * 0.0141 + 1.3) + 0.06 * Math.sin(x * 0.033 + 0.7))) / (H * 0.5),
      0,
      1
    );
    const grain = 0.8 + 0.2 * Math.sin(x * 0.045 + y * 0.06);
    out[i] = Math.pow(r, 1.4) * grain;
  }
  return out;
}

/* ── 立方体（原组件自带的形状，留作通用形状用） ───────────────────── */
const CUBE = 112;
export function cubeMask(xs, ys, W, H) {
  const out = new Float32Array(xs.length);
  const lit = (v, dark) => 0.35 + 0.65 * clamp(dark ? v : 1.09 - v, 0, 1);
  const dark = true; // 深色主题：点是亮的，受光面最密
  const R = CUBE;
  const c = Math.cos(Math.PI / 6) * R;
  const h = R / 2;
  const T = [0, -R];
  const UR = [c, -h];
  const B = [0, R];
  const LL = [-c, h];
  const UL = [-c, -h];
  const along = (o, p, q, x, y) => {
    const ax = p[0] - o[0], ay = p[1] - o[1], bx = q[0] - o[0], by = q[1] - o[1];
    const dx = x - o[0], dy = y - o[1];
    const det = ax * by - ay * bx;
    return [(dx * by - dy * bx) / det, (ax * dy - ay * dx) / det];
  };
  const inside = ([s, t]) => s >= 0 && s <= 1 && t >= 0 && t <= 1;
  const seam = (v) => (v < 0.045 ? 1 : 0);
  for (let i = 0; i < xs.length; i++) {
    const x = xs[i] - W / 2;
    const y = ys[i] - H / 2;
    const top = along(T, UR, UL, x, y);
    if (inside(top)) {
      const [s, t] = top;
      out[i] = seam(1 - s) || seam(1 - t) ? 1 : lit(0.96 - 0.1 * ((s + t) / 2), dark);
      continue;
    }
    const left = along(UL, [0, 0], LL, x, y);
    if (inside(left)) {
      const [s, t] = left;
      out[i] = seam(s) ? 1 : lit(0.56 - 0.12 * t, dark);
      continue;
    }
    const right = along([0, 0], UR, B, x, y);
    if (inside(right)) {
      const [s, t] = right;
      out[i] = seam(s) || seam(t) ? 1 : lit(0.13 - 0.05 * s, dark);
    }
  }
  return out;
}

/** 把一行字做成密度场：字号吃满容器，取 alpha 当掩膜（0 在外，1 在笔画里）。 */
export function textMask(text, { weight = 700, family = "Inter Variable, Inter, sans-serif", fill = 0.82 } = {}) {
  return (xs, ys, W, H) => {
    const c = document.createElement("canvas");
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    c.width = Math.round(W * dpr);
    c.height = Math.round(H * dpr);
    const g = c.getContext("2d", { willReadFrequently: true });
    const px = Math.min(W / Math.max(1, text.length * 0.66), H * fill);
    g.scale(dpr, dpr);
    g.font = `${weight} ${px}px ${family}`;
    g.textAlign = "center";
    g.textBaseline = "middle";
    g.fillStyle = "#fff";
    g.fillText(text, W / 2, H / 2 + px * 0.02);
    const img = g.getImageData(0, 0, c.width, c.height).data;
    const out = new Float32Array(xs.length);
    for (let i = 0; i < xs.length; i++) {
      const px2 = Math.min(c.width - 1, Math.max(0, Math.round(xs[i] * dpr)));
      const py2 = Math.min(c.height - 1, Math.max(0, Math.round(ys[i] * dpr)));
      out[i] = img[(py2 * c.width + px2) * 4 + 3] / 255;
    }
    return out;
  };
}

export default function AsciiField({
  glyphs = "Classic",
  size = 10,
  reach = 50,
  trail = 1.2,
  pull = 40,
  mask = cubeMask,
  interactive = true,
  reveal = 0, // >0 时开局按「从上往下」逐点点亮（ms），用于评分徽章的出现
  ambient = false, // 页脚山脊：慢波动 + 随机冒泡（小云上浮、可被指针提前触散）
  className = "",
  ariaLabel = "点阵图形",
}) {
  const box = useRef(null);
  const cv = useRef(null);
  const knobs = useRef({ glyphs, reach, trail, pull, mask, interactive, reveal, ambient });
  knobs.current = { glyphs, reach, trail, pull, mask, interactive, reveal, ambient };
  const st = useRef({
    W: 0,
    H: 0,
    cols: 0,
    rows: 0,
    cw: 0,
    ch: 0,
    ox: 0,
    oy: 0,
    font: "",
    heat: new Float32Array(0),
    mask: new Float32Array(0),
    hx: -999,
    hy: -999,
    lx: NaN,
    ly: NaN,
    near: 0,
    inside: false,
    rings: [],
    deal: 0,
    tick: 0,
    thresh: new Float32Array(0),
    revealT0: 0,
    ambientT: 0,
    bubbles: [],
    lastSpawn: 0,
    raf: 0,
    ratio: 1,
  });

  const build = () => {
    const s = st.current;
    const el = box.current;
    const c = cv.current;
    if (!el || !c) return;
    const W = Math.max(1, el.clientWidth);
    const H = Math.max(1, el.clientHeight);
    const r = Math.min(2, window.devicePixelRatio || 1);
    s.W = W;
    s.H = H;
    s.ratio = r;
    c.width = Math.round(W * r);
    c.height = Math.round(H * r);
    s.ch = size * 0.82;
    s.cw = size * 0.62;
    s.cols = Math.max(1, Math.floor(W / s.cw - 0.5));
    s.rows = Math.max(1, Math.floor(H / s.ch));
    s.font = `500 ${size}px ${MONO}`;
    s.heat = new Float32Array(s.cols * s.rows);
    const ox = (s.ox = (W - s.cols * s.cw) / 2);
    const oy = (s.oy = (H - s.rows * s.ch) / 2);
    const xs = new Float32Array(s.cols * s.rows);
    const ys = new Float32Array(s.cols * s.rows);
    for (let j = 0; j < s.rows; j++) {
      for (let i = 0; i < s.cols; i++) {
        const k = j * s.cols + i;
        xs[k] = ox + (i + 0.5 + (j & 1) * 0.5) * s.cw;
        ys[k] = oy + (j + 0.5) * s.ch;
      }
    }
    s.mask = knobs.current.mask(xs, ys, W, H);
    // 逐点点亮的次序：上多下少，再掺一点噪声，像打印头从上往下扫
    s.thresh = new Float32Array(s.cols * s.rows);
    for (let j = 0; j < s.rows; j++) {
      for (let i = 0; i < s.cols; i++) {
        const k = j * s.cols + i;
        s.thresh[k] = (j / Math.max(1, s.rows - 1)) * 0.76 + hash(k, 7) * 0.24;
      }
    }
  };

  const stamp = (x, y, rad, amt) => {
    const s = st.current;
    x -= s.ox;
    y -= s.oy;
    const c0 = Math.max(0, Math.floor((x - rad) / s.cw));
    const c1 = Math.min(s.cols - 1, Math.ceil((x + rad) / s.cw));
    const r0 = Math.max(0, Math.floor((y - rad) / s.ch));
    const r1 = Math.min(s.rows - 1, Math.ceil((y + rad) / s.ch));
    const R2 = rad * rad;
    for (let j = r0; j <= r1; j++) {
      const dy = (j + 0.5) * s.ch - y;
      for (let i = c0; i <= c1; i++) {
        const dx = (i + 0.5) * s.cw - x;
        const q = (dx * dx + dy * dy) / R2;
        if (q >= 1) continue;
        const t = 1 - q;
        const k = j * s.cols + i;
        s.heat[k] = Math.min(1, s.heat[k] + amt * t * t);
      }
    }
  };

  const radius = () => 12 + (clamp(knobs.current.reach, 0, 100) / 100) * 58;

  const paint = () => {
    const s = st.current;
    const c = cv.current;
    if (!c || !s.cols) return;
    const g = c.getContext("2d");
    g.setTransform(s.ratio, 0, 0, s.ratio, 0, 0);
    g.clearRect(0, 0, s.W, s.H);
    /* one ink for everything, the theme's own —— 本项目里就是 --ink（白） */
    g.fillStyle = getComputedStyle(c).color;
    const dot = Math.min(s.cw, s.ch) * 0.44;
    g.font = s.font;
    g.textAlign = "center";
    g.textBaseline = "middle";
    /* 出现动画：还没到点亮次序的格子先不画 */
    const rp = s.revealT0 ? Math.min(1, (performance.now() - s.revealT0) / Math.max(1, knobs.current.reveal)) : 1;
    const ramp = RAMPS[knobs.current.glyphs] ?? RAMPS.Classic;
    const top = ramp.length - 1;
    const lean = (clamp(knobs.current.pull, 0, 100) / 100) * s.near;
    const rad = radius();
    const far = rad * 2;
    const far2 = far * far;
    const R2 = rad * rad;
    const rings = s.rings.map((r) => {
      const p = r.t / RING_S;
      const e = 1 - Math.pow(1 - p, 3);
      return { x: r.x, y: r.y, R: 8 + e * 260, amp: 0.6 * (1 - p) * (1 - p) * Math.min(1, p * 6) };
    });
    for (let j = 0; j < s.rows; j++) {
      const y = s.oy + (j + 0.5) * s.ch;
      for (let i = 0; i < s.cols; i++) {
        const k = j * s.cols + i;
        const cx = s.ox + (i + 0.5 + (j & 1) * 0.5) * s.cw;
        /* ambient：整片山脊慢慢起伏（横向一道缓慢的密度波），像呼吸 */
        let m = s.mask[k];
        if (knobs.current.ambient) m *= 0.8 + 0.2 * Math.sin(cx * 0.011 + s.ambientT * 0.75);
        if (m <= 0) continue;
        if (rp < 1 && s.thresh[k] > rp) continue;
        let h = s.heat[k];
        if (s.near > 0.002) {
          const q = ((cx - s.hx) ** 2 + (y - s.hy) ** 2) / R2;
          if (q < 1) h = Math.max(h, 0.95 * s.near * (1 - q) * (1 - q));
        }
        for (const r of rings) {
          const d = (Math.hypot(cx - r.x, y - r.y) - r.R) / 24;
          if (d > -2.5 && d < 2.5) h += r.amp * Math.exp(-d * d);
        }
        h *= 0.55 + 0.45 * m;
        const v = Math.min(1, h);
        let u = v * top + 0.5;
        if (h > COLD) u += (hash(k, s.deal) - 0.5) * 1.6 * Math.min(1, h * 2);
        const idx = clamp(Math.floor(u), 1, top);
        let x = cx;
        let yy = y;
        if (lean > 0.002) {
          const dx = s.hx - x;
          const dy = s.hy - yy;
          const d2 = dx * dx + dy * dy;
          if (d2 < far2) {
            const f = 1 - d2 / far2;
            const d = Math.sqrt(d2) || 1;
            const mm = Math.min(d * 0.6, 14 * lean * f * f);
            x += (dx / d) * mm;
            yy += (dy / d) * mm;
          }
        }
        if (h <= COLD || idx === 1) {
          g.globalAlpha = 1;
          g.beginPath();
          g.arc(x, yy, Math.max(0.45, dot * Math.sqrt(m)), 0, Math.PI * 2);
          g.fill();
          continue;
        }
        g.globalAlpha = 1;
        g.fillText(ramp[idx], x, yy);
      }
    }
    g.globalAlpha = 1;
  };

  const run = () => {
    const s = st.current;
    if (s.raf) return;
    let prev = performance.now();
    const step = (t) => {
      const dt = Math.min(0.05, (t - prev) / 1000);
      prev = t;
      const keep = Math.exp((-dt * 3) / Math.max(0.1, knobs.current.trail));
      let warm = 0;
      for (let k = 0; k < s.heat.length; k++) {
        const h = s.heat[k] * keep;
        s.heat[k] = h < 0.003 ? 0 : h;
        if (h > warm) warm = h;
      }
      s.rings = s.rings.filter((r) => (r.t += dt) < RING_S);
      s.near += ((s.inside ? 1 : 0) - s.near) * (1 - Math.pow(0.004, dt));
      s.tick += dt;
      if (s.tick > 0.07) {
        s.tick = 0;
        s.deal++;
      }
      paint();
      const still = warm === 0 && !s.rings.length && Math.abs((s.inside ? 1 : 0) - s.near) < 0.004;
      s.raf = still ? 0 : requestAnimationFrame(step);
    };
    s.raf = requestAnimationFrame(step);
  };

  useEffect(() => {
    build();
    paint();
    const ro = new ResizeObserver(() => {
      build();
      paint();
    });
    if (box.current) ro.observe(box.current);
    // 主题翻转 / 字体加载完，密度场要重算
    const mo = new MutationObserver(() => {
      build();
      paint();
    });
    mo.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
    const onFonts = () => {
      build();
      paint();
    };
    document.fonts?.ready.then(onFonts);
    return () => {
      ro.disconnect();
      mo.disconnect();
      cancelAnimationFrame(st.current.raf);
      st.current.raf = 0;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [size]);

  useEffect(() => {
    build();
    paint();
  }, [mask, glyphs]);

  /* 出现动画：按 thresh 从上往下逐格点亮（评分徽章用；0 = 不做动画） */
  useEffect(() => {
    if (!reveal) return;
    const s = st.current;
    s.revealT0 = performance.now();
    let raf = 0;
    const tick = () => {
      paint();
      if (performance.now() - s.revealT0 < reveal + 40) raf = requestAnimationFrame(tick);
      else {
        s.revealT0 = 0;
        paint();
      }
    };
    raf = requestAnimationFrame(tick);
    return () => {
      cancelAnimationFrame(raf);
      s.revealT0 = 0;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reveal, mask, size]);

  /* ambient：页脚山脊整片慢慢呼吸 + 随机冒小云（往上飘、慢慢散，指针靠近提前触散） */
  useEffect(() => {
    if (!ambient) return;
    const s = st.current;
    let raf = 0;
    let last = performance.now();
    const tick = (now) => {
      /* dt 必须量「上一次真正画过的那一帧」，不能量「上一次 rAF 回调」——
         无头浏览器里 rAF 会跑到 200Hz+，用回调间隔当 dt 会让时间流速只剩 1/5。 */
      if (now - last < 41) {
        raf = requestAnimationFrame(tick);
        return;
      }
      const dt = Math.min(0.1, (now - last) / 1000);
      last = now;
      s.ambientT += dt;

      const t = s.ambientT;
      // 只保留大云的自然起伏（用户要求删掉析出小云）
      paint();
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ambient, mask, size]);

  const where = (e) => {
    const r = e.currentTarget.getBoundingClientRect();
    return { x: e.clientX - r.left, y: e.clientY - r.top };
  };
  const move = (e) => {
    if (!knobs.current.interactive) return;
    const s = st.current;
    const { x, y } = where(e);
    const rad = radius();
    if (Number.isNaN(s.lx)) {
      s.lx = x;
      s.ly = y;
    }
    const d = Math.hypot(x - s.lx, y - s.ly);
    const n = Math.max(1, Math.ceil(d / (rad / 3)));
    for (let k = 1; k <= n; k++) {
      const f = k / n;
      stamp(s.lx + (x - s.lx) * f, s.ly + (y - s.ly) * f, rad, 0.5);
    }
    s.lx = x;
    s.ly = y;
    s.hx = x;
    s.hy = y;
    s.inside = true;
    run();
  };

  return (
    <div
      ref={box}
      className={`asc ${className}`}
      onPointerEnter={(e) => {
        if (!knobs.current.interactive) return;
        const s = st.current;
        s.lx = NaN;
        move(e);
      }}
      onPointerMove={move}
      onPointerLeave={() => {
        if (!knobs.current.interactive) return;
        const s = st.current;
        s.inside = false;
        s.lx = NaN;
        run();
      }}
      onPointerDown={(e) => {
        if (!knobs.current.interactive) return;
        const { x, y } = where(e);
        st.current.rings.push({ x, y, t: 0 });
        run();
      }}
      role="img"
      aria-label={ariaLabel}
    >
      <canvas ref={cv} className="asc-canvas" aria-hidden="true" />
    </div>
  );
}

/* a stable 0..1 per cell per deal, so the shimmer is noise that
   holds for a few frames rather than flicker every frame */
function hash(k, n) {
  let h = (k * 374761393 + n * 668265263) | 0;
  h = Math.imul(h ^ (h >>> 13), 1274126177);
  return ((h ^ (h >>> 16)) >>> 0) / 4294967296;
}