import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useReducedMotion } from "motion/react";
import "./GlassLens.css";

/* ── 玻璃透镜 ──────────────────────────────────────────────────────────────
   观感来自 Bencho 的 GlassBubble（MIT，glass lens.txt）：中间轻微放大、边缘更硬、
   上缘吃光、最边缘裂开一条彩色、底下压一片软影。

   那边把整页拍成纹理走 WebGL SDF（「边缘像素沿法线往外取样」）。这里底下是**活的
   DOM 文本**——要跟着滚动、跟着换文档、还能认出 .hl，所以换个稳的做法：

     · 球是一个 absolute 的圆，挂在一层 body 级的 overflow:visible 定位层上（portal），
       坐标是**页面坐标**：它既能在阅读器面板里，也能被拖到面板外的空白处；页面滚动时
       球跟着文档走，不用任何滚动补偿；
     · 放大不是 shader：圆心压在 .reader__body 上时，把正文深拷贝进裁剪圆，按圆心对齐
       后 scale 到 1.7，拖动中只改克隆层的 translate；
     · 边缘弯折：中心 1.7、往外 1.42 / 1.16 三层克隆，各露在自己那一环上。贴边处的字被
       「压回去」，看上去就是沿法线向内收——那边靠 SDF 法线，这里靠三层倍率差；
     · 色散 / 棱镜：错位的红、青细环 + 一层 conic 光谱，mix-blend-mode: screen，
       全部裁在球里；
     · 球跨过面板边缘时按最近的那条边轻微压扁、垂直方向拉长（弹簧跟随），像一颗玻璃球
       挤进／挤出画框。

   命中高亮（mark.hl）时，除了含义卡，还会在该句的**行盒**上盖一层 canvas：原句的字符
   先被打散成噪声，再逐字重排成语义色的一句话（explain_zh），最后淡出。canvas 只覆盖
   那几行高亮，绝对定位、pointer-events:none，**不动任何正文排版**；透镜移开后整段效果
   再停留 HOLD_MS 才消散（动画保护）。

   性能契约：拖动中只写 transform；克隆每种内容只做一次；命中检测节流到 60ms；
   阅读器收起时它还在（位置照旧），组件卸载时克隆与监听一起消失。 */

const D = 112; // 球径：正好卡在「05 · SOURCE」上下两条发丝线之间
// 一枚球面透镜的放大率从心到边是连续衰减的。三层克隆逼近这条曲线：
// 中心 1.7（看得清字），往外 1.42、1.16 —— 每层只露在自己的环上（见 CSS 的 .glens__band）。
const LAYERS = [{ mag: 1.7 }, { mag: 1.52 }, { mag: 1.36 }];
const KEY_STEP = 10; // 方向键步长
const PROBE_MS = 60; // 命中检测节流（每帧 elementFromPoint 会让拖动掉帧）
const EDGE_PAD = 10; // 不贴死视口边
const HOLD_MS = 2500; // 透镜移开后，译文与 ASCII 过渡再停 2.5 秒（用户说这个时长够了）
const STORE_KEY = "cl:lens"; // 透镜落点（页面坐标），刷新/切主题/开合面板都不重置
const CARD_W = 300; // 含义卡宽度（与 CSS 对齐）
const CARD_GAP = 12;

// 极性的一句话：bad → 对你不利
const VERDICT = {
  bad: "对你不利：这段多半让你吃亏",
  good: "对你有利：这段偏向保护你",
  warn: "需要留意：这段有条件或例外",
  neutral: "一般说明：这段只是把规则写清楚",
  focus: "你刚从标签跳到这里",
};

// 语义色只在这个效果里出现（透镜内部与译文卡），不进页面其它地方
const PALETTE = {
  light: { bad: "#c2412d", good: "#2f7d5b", warn: "#b7791f", neutral: "#6b6a64", focus: "#43423d" },
  geek: { bad: "#ff6b6b", good: "#5ef08a", warn: "#ffc857", neutral: "#c9c9c9", focus: "#ffffff" },
};
const isGeek = () => document.documentElement.dataset.theme === "geek";
const palette = () => PALETTE[isGeek() ? "geek" : "light"];

const clamp = (v, a, b) => (b < a ? a : Math.min(b, Math.max(a, v)));
const hex = (s) => {
  const h = String(s).replace("#", "").trim();
  return h.length === 3 ? h.split("").map((c) => parseInt(c + c, 16)) : [0, 2, 4].map((i) => parseInt(h.slice(i, i + 2), 16));
};
const mix = (a, b, t) => {
  const x = hex(a);
  const y = hex(b);
  return `rgb(${Math.round(x[0] + (y[0] - x[0]) * t)},${Math.round(x[1] + (y[1] - x[1]) * t)},${Math.round(x[2] + (y[2] - x[2]) * t)})`;
};

/**
 * 挂在 Reader 里（DOM 上是一层 portal 到 body 的定位层）。
 * @param anchorRef  阅读器根节点：默认落点、压扁边界都用它量
 * @param bodyRef    .reader__body：被放大的那份原文
 * @param contentKey 当前文档 id：换文档时克隆要重建
 */
export default function GlassLens({ anchorRef, bodyRef, contentKey }) {
  const reduce = useReducedMotion();
  const layerRef = useRef(null);
  const ballRef = useRef(null);
  const mags = useRef([]); // 三张放大层，每张一份同样的克隆

  const pos = useRef({ x: 0, y: 0 }); // 页面坐标（左上角）
  const to = useRef({ x: 0, y: 0 });
  const vel = useRef({ x: 0, y: 0 });
  const scl = useRef({ x: 1, y: 1, tx: 1, ty: 1, vx: 0, vy: 0 });
  const geo = useRef(null); // {bodyLeft, bodyTop, scrollTop, width} —— 全是页面坐标
  const drag = useRef(null);
  const raf = useRef(0);
  const cloneKey = useRef("");
  const lastProbe = useRef(0);
  const hitKey = useRef("");
  const holdTimer = useRef(0);
  const anchorRect = useRef(null);
  const placed = useRef(false);
  const moved = useRef(false); // 用户自己拖过/移过之后，就不再自动摆位 // 落点只算一次（要么用存档，要么用面板上方的默认位）

  const [hit, setHit] = useState(null); // {pol, labels, explain, quote, rects, key}
  const [dragging, setDragging] = useState(false);
  const [over, setOver] = useState(false);

  /* ── 量几何：正文在**页面坐标**里的位置（滚动不影响它，所以只在布局变时量） ── */
  const measure = useCallback(() => {
    const body = bodyRef?.current;
    const a = anchorRef?.current;
    if (a) {
      const r = a.getBoundingClientRect();
      anchorRect.current = { left: r.left + scrollX, top: r.top + scrollY, right: r.right + scrollX, bottom: r.bottom + scrollY };
    }
    if (!body) {
      geo.current = null;
      return null;
    }
    const r = body.getBoundingClientRect();
    geo.current = {
      bodyLeft: r.left + scrollX,
      bodyTop: r.top + scrollY,
      scrollTop: body.scrollTop,
      width: body.clientWidth,
    };
    return geo.current;
  }, [bodyRef, anchorRef]);

  /* ── 一帧：球到位（平移 + 挤压），克隆层把「圆心那一块内容」钉回圆心 ─────── */
  const paint = useCallback(() => {
    const ball = ballRef.current;
    if (!ball) return;
    const p = pos.current;
    const s = scl.current;
    ball.style.transform = `translate3d(${p.x.toFixed(2)}px, ${p.y.toFixed(2)}px, 0)`;

    const g = geo.current;
    const layer = mags.current[0];
    if (!g || !layer) return;
    const cx = p.x + D / 2 - g.bodyLeft;
    const cy = p.y + D / 2 - g.bodyTop + g.scrollTop;
    const half = D / 2;
    for (let i = 0; i < LAYERS.length; i++) {
      const el = mags.current[i];
      if (!el) continue;
      const m = LAYERS[i].mag;
      el.style.transform = `translate3d(${(half - m * cx).toFixed(2)}px, ${(half - m * cy).toFixed(2)}px, 0) scale(${m})`;
    }
  }, []);

  /* ── 克隆：只做一次。key 里带上「哪份文档 / 正文多宽 / 多少字」，变了才重建 ── */
  const buildClone = useCallback(() => {
    const body = bodyRef?.current;
    const host = mags.current[0];
    if (!body || !host || reduce) return;
    const key = `${contentKey}|${body.clientWidth}|${body.childElementCount}|${body.textContent.length}`;
    if (cloneKey.current === key && host.firstElementChild) return;

    const w = body.clientWidth;
    const mk = () => {
      const c = body.cloneNode(true);
      c.removeAttribute("tabindex");
      c.removeAttribute("role");
      c.removeAttribute("aria-label");
      c.setAttribute("aria-hidden", "true");
      c.querySelectorAll(".is-flash").forEach((el) => el.classList.remove("is-flash"));
      // 克隆不是滚动容器：铺到底，靠 translate 对准（.reader__body 的字体/行高/内边距照旧生效）
      c.style.width = `${w}px`;
      c.style.height = "auto";
      c.style.maxHeight = "none";
      c.style.overflow = "hidden";
      c.style.margin = "0";
      return c;
    };
    for (let i = 0; i < LAYERS.length; i++) if (mags.current[i]) mags.current[i].replaceChildren(mk());
    cloneKey.current = key;
    // 有了克隆，球里就是「一块被折射过的画面」，底子要挡住背后的原文字——
    // 否则放大后的字会和背后没放大的字叠成双影（用 data 属性而不是 className：
    // React 管着 className，重渲染会把 class 覆盖掉，data-* 不会被碰）。
    if (ballRef.current) ballRef.current.dataset.mag = "1";
  }, [bodyRef, contentKey, reduce]);

  /* ── 命中检测：圆心底下是不是 mark.hl / 是不是正文 ─────────────────────── */
  const probe = useCallback(() => {
    const body = bodyRef?.current;
    /* 圆心直接用球的实际屏幕位置算 —— 不信 pos 与页面坐标的换算，
       portal + fixed 的层里那套换算踩过太多次坑。 */
    const ballEl = ballRef.current;
    const br = ballEl ? ballEl.getBoundingClientRect() : null;
    const cx = br ? br.left + br.width / 2 : pos.current.x + D / 2;
    const cy = br ? br.top + br.height / 2 : pos.current.y + D / 2;
    // 球滚出视口了：什么都别判
    if (cx < 0 || cy < 0 || cx > innerWidth || cy > innerHeight) return;

    let mark = null;
    let onBody = false;
    /* 用几何判定，不用 elementsFromPoint：<mark> 是 inline，bbox 里有一半是行间空隙，
       点上去经常命中父元素（实测圆心落在 mark 的 bbox 内却返回 .reader__body）。
       这里直接遍历每条高亮的每个行盒，看圆心落不落在里面。 */
    if (body) {
      /* 「照到」而不是「圆心压住」：只要透镜的圆和某个行盒相交就算命中，
         取离圆心最近的那条。112px 的球压在字上，圆心常常落在行间空隙里。 */
      const R = D / 2 - 6;
      let best = Infinity;
      for (const m of body.querySelectorAll("mark.hl")) {
        for (const r of m.getClientRects()) {
          if (r.width < 2 || r.height < 2) continue;
          const nx = clamp(cx, r.left, r.right);
          const ny = clamp(cy, r.top, r.bottom);
          const dist = Math.hypot(cx - nx, cy - ny);
          if (dist <= R && dist < best) {
            best = dist;
            mark = m;
          }
        }
      }
      if (!mark) {
        const br = body.getBoundingClientRect();
        const nx = clamp(cx, br.left, br.right);
        const ny = clamp(cy, br.top, br.bottom);
        onBody = Math.hypot(cx - nx, cy - ny) <= R;
      } else onBody = true;
    }
    setOver((v) => (v === onBody ? v : onBody));
    if (ballRef.current) ballRef.current.dataset.hit = mark ? "1" : "0";

    if (mark) {
      if (holdTimer.current) {
        clearTimeout(holdTimer.current);
        holdTimer.current = 0;
      }
      const pol = ["bad", "good", "warn", "neutral", "focus"].find((k) => mark.classList.contains(`hl--${k}`)) || "neutral";
      const labels = (mark.getAttribute("title") || "")
        .split("、")
        .map((s) => s.trim())
        .filter(Boolean);
      const explain = (mark.dataset.explain || "").trim();
      const raw = (mark.textContent || "").replace(/\s+/g, " ").trim();
      const quote = raw.length > 60 ? `${raw.slice(0, 60)}…` : raw;
      const rects = [...mark.getClientRects()]
        .filter((r) => r.width > 2 && r.height > 2)
        .map((r) => ({ left: r.left + scrollX, top: r.top + scrollY, width: r.width, height: r.height }));
      if (!rects.length) return;
      const bbox = rects.reduce(
        (b, r) => ({ left: Math.min(b.left, r.left), top: Math.min(b.top, r.top), right: Math.max(b.right, r.left + r.width), bottom: Math.max(b.bottom, r.top + r.height) }),
        { left: Infinity, top: Infinity, right: -Infinity, bottom: -Infinity }
      );
      const cardX = clamp(bbox.left, scrollX + 12, scrollX + innerWidth - CARD_W - 12);
      const cardY = bbox.bottom + CARD_GAP + 150 > scrollY + innerHeight - 12 ? Math.max(scrollY + 12, bbox.top - 168) : bbox.bottom + CARD_GAP;
      const key = `${pol}|${explain}|${quote}|${Math.round(bbox.left)}|${Math.round(bbox.top)}`;
      if (key !== hitKey.current) {
        hitKey.current = key;
        setHit({ pol, labels, explain, quote, rects, card: { x: cardX, y: cardY }, key, el: mark, idx: [...body.querySelectorAll("mark.hl")].indexOf(mark) });
      }
      return;
    }

    // 离开了高亮：效果先留着，HOLD_MS 之后再收（动画保护）
    if (hitKey.current && !holdTimer.current) {
      holdTimer.current = setTimeout(() => {
        holdTimer.current = 0;
        hitKey.current = "";
        setHit(null);
      }, HOLD_MS);
    }
  }, [bodyRef]);

  /* ── 挤压：球跨过阅读器面板的边时，按最近那条边压扁 / 垂直拉长 ─────────── */
  const deform = useCallback(() => {
    // 用户要求去掉「压扁 / 拉长」的形变：玻璃球永远是一个正圆
    return { tx: 1, ty: 1 };
  }, []);

  /* ── spring：跟手（k 大、阻尼小）→ settle 就停 rAF ──────────────────────
     frames 不是毫秒：dt 是「过了几个 1/60 秒」，阻尼取 dt 次方，掉帧时衰减一致。 */
  const kick = useCallback(() => {
    if (raf.current) return;
    let prev = 0;
    const tick = (t) => {
      const dt = prev ? clamp((t - prev) / 16.67, 0, 2.5) : 1;
      prev = t;
      const p = pos.current;
      const q = to.current;
      const v = vel.current;

      // 用户要求「不要阻尼、不要 Q 弹」：位置直接钉到目标，一帧到位
      p.x = q.x;
      p.y = q.y;
      v.x = v.y = 0;

      // 形变（跨面板边时的压扁/拉长）已按用户要求整套去掉：球始终是正圆
      paint();
      if (t - lastProbe.current >= PROBE_MS) {
        lastProbe.current = t;
        probe();
      }

      const moving = Math.abs(q.x - p.x) > 0.05 || Math.abs(q.y - p.y) > 0.05 || drag.current;
      if (moving) raf.current = requestAnimationFrame(tick);
      else {
        p.x = q.x;
        p.y = q.y;
        paint();
        raf.current = 0;
        probe(); // 落定后再确认一次
      }
    };
    raf.current = requestAnimationFrame(tick);
  }, [paint, probe]);

  /* ── 落点：存的是「相对阅读器面板左上角」的偏移（页面坐标） ──────────────
     面板展开只会往下长，顶边不动，所以相对偏移在折叠/展开、切主题、刷新之间都稳定；
     直接存页面坐标的话，刷新后（面板是收起的）会把球夹到文档末尾去。 */
  const panelBase = useCallback(() => {
    const a = anchorRef?.current;
    if (!a) return null;
    const r = a.getBoundingClientRect();
    if (!r.width || !r.height) return null;
    return { left: r.left + scrollX, top: r.top + scrollY, width: r.width, height: r.height };
  }, [anchorRef]);

  const save = useCallback(() => {
    try {
      localStorage.setItem(STORE_KEY, JSON.stringify({ rx: Math.round(pos.current.x), ry: Math.round(pos.current.y) }));
    } catch {
      /* 隐身模式：记不住就算了 */
    }
  }, [panelBase]);

  const home = useCallback(() => {
    // 落在「05 · SOURCE 原文」那块：面板右上角往里一点，压在面板外的空白上
    const b = panelBase();
    return b
      ? { x: b.left + b.width - D - 32, y: Math.max(0, b.top - D - 40) }
      : { x: scrollX + innerWidth - D - 40, y: scrollY + 120 };
  }, [panelBase]);

  /* 默认落点只在第一次落一次（存档优先） */
  const placeIfNeeded = useCallback(() => {
    if (placed.current) return false;
    let stored = null;
    try {
      stored = JSON.parse(localStorage.getItem(STORE_KEY) || "null");
    } catch {
      stored = null;
    }
    // 面板还没展开时用「05 · SOURCE 原文」这一节本身当锚点，保证默认落点就在那一块
    const b = panelBase();
    let sec = null;
    const secEl = document.getElementById("reader") || document.querySelector(".rsec#reader");
    if (secEl) {
      const r = secEl.getBoundingClientRect();
      sec = { left: r.left + scrollX, top: r.top + scrollY, width: r.width, height: r.height };
    }
    const base = b || sec;
    /* 视口坐标：区块在屏幕上的位置 → 球贴在区块右上、正好卡在两条发丝线之间的空档里 */
    const def = base
      ? { x: base.left + base.width - D - 32, y: Math.max(0, base.top - D - 10) }
      : { x: scrollX + innerWidth - D - 40, y: scrollY + 140 };
    const x = stored && Number.isFinite(stored.rx) && Number.isFinite(stored.ry) ? stored.rx : def.x;
    const y = stored && Number.isFinite(stored.rx) && Number.isFinite(stored.ry) ? stored.ry : def.y;
    const maxX = Math.max(EDGE_PAD, document.documentElement.scrollWidth - D - EDGE_PAD);
    const maxY = Math.max(EDGE_PAD, document.documentElement.scrollHeight - D - EDGE_PAD);
    pos.current = { x: clamp(x, EDGE_PAD, maxX), y: clamp(y, EDGE_PAD, maxY) };
    to.current = { ...pos.current };
    placed.current = true;
    return true;
  }, [panelBase]);

  /* ── 自动落位：原文区展开 / 文档切换导致高度变化时，把球重新摆到区块右侧 ──
     用户自己拖过之后就不再自动动它。 */
  useEffect(() => {
    const sec = document.getElementById("reader");
    if (!sec) return undefined;
    const place = () => {
      if (moved.current) return;
      const r = sec.getBoundingClientRect();
      /* x 贴区块右边、y 放区块上方 —— 但要保证「此刻在屏幕里」：
         区块很高（展开的原文）时，区块顶可能已经在视口外，球就顺势落到视口上沿附近。 */
      const x = clamp(r.right + scrollX - D - 32, scrollX + EDGE_PAD, scrollX + innerWidth - D - EDGE_PAD);
      const y = clamp(r.top + scrollY - D - 10, scrollY + 96, scrollY + innerHeight - D - EDGE_PAD);
      pos.current = { x, y };
      to.current = { ...pos.current };
      placed.current = true;
      paint();
      probe();
    };
    place();
    /* 没被用户拖过时，随页面滚动一直贴着区块 —— 不会出现「球停在结果页顶部」 */
    let ticking = false;
    const onScroll = () => {
      if (ticking) return;
      ticking = true;
      requestAnimationFrame(() => {
        ticking = false;
        place();
      });
    };
    addEventListener("scroll", onScroll, { passive: true });
    const ro = new ResizeObserver(place);
    ro.observe(sec);
    const mo = new MutationObserver(place);
    mo.observe(sec, { attributes: true, attributeFilter: ["class"] });
    return () => {
      removeEventListener("scroll", onScroll);
      ro.disconnect();
      mo.disconnect();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [paint, probe]);

  useLayoutEffect(() => {
    placeIfNeeded(); // 有存档就用存档，没有就放到面板上方的空白处
    if (!placed.current && ballRef.current) ballRef.current.style.visibility = "hidden";
    vel.current = { x: 0, y: 0 };
    measure();
    paint();
    probe();
  }, [measure, paint, placeIfNeeded, probe]);

  // 面板还没量出来（刚挂载 / 结果页进场动画里）时，逐帧再试；放好之后才让它露面
  useEffect(() => {
    if (placed.current) return undefined;
    let n = 0;
    let id = 0;
    const tick = () => {
      if (placeIfNeeded()) {
        if (ballRef.current) ballRef.current.style.visibility = "";
        paint();
        probe();
        return;
      }
      if (++n < 180) id = requestAnimationFrame(tick);
    };
    id = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(id);
  }, [paint, placeIfNeeded, probe]);

  /* ── 布局/正文滚动变化：重量一次（页面滚动不用管，坐标是页面坐标） ─────── */
  useEffect(() => {
    const body = bodyRef?.current;
    let queued = 0;
    const sync = () => {
      if (queued) return;
      queued = requestAnimationFrame(() => {
        queued = 0;
        measure();
        paint();
        const now = performance.now();
        if (now - lastProbe.current >= PROBE_MS) {
          lastProbe.current = now;
          probe();
        }
      });
    };
    body?.addEventListener("scroll", sync, { passive: true });
    /* 页面滚动时透镜留在屏幕上不动（放大镜该有的行为）：页面坐标跟着加回滚动量，
       再重画一次克隆 —— 这样「滚轮一动，透镜里的字就跟着换」。 */
    let lastWinY = window.scrollY;
    const onWinScroll = () => {
      const dy = window.scrollY - lastWinY;
      lastWinY = window.scrollY;
      if (!dy) return;

      paint();
      const now = performance.now();
      if (now - lastProbe.current >= PROBE_MS) {
        lastProbe.current = now;
        probe();
      }
    };
    addEventListener("scroll", onWinScroll, { passive: true });
    addEventListener("resize", sync);
    const ro = typeof ResizeObserver === "function" ? new ResizeObserver(sync) : null;
    if (body) ro?.observe(body);
    if (anchorRef?.current) ro?.observe(anchorRef.current);
    return () => {
      if (queued) cancelAnimationFrame(queued);
      body?.removeEventListener("scroll", sync);
      removeEventListener("scroll", onWinScroll);
      removeEventListener("resize", sync);
      ro?.disconnect();
    };
  }, [anchorRef, bodyRef, measure, paint, probe]);

  // 换文档：正文换了，克隆跟着换，命中也要重判
  useEffect(() => {
    if (cloneKey.current) buildClone();
    measure();
    paint();
    probe();
  }, [contentKey, buildClone, measure, paint, probe]);

  useEffect(
    () => () => {
      cancelAnimationFrame(raf.current);
      if (holdTimer.current) clearTimeout(holdTimer.current);
    },
    []
  );

  /* ── 译文卡逐字浮现 ───────────────────────────────────────────────────── */

  /* ── 高亮句原位替换：canvas 覆盖那几行，把原句「拆成字符 → 重排成译文」 ─────
     纯视觉：canvas 绝对定位、pointer-events:none，正文一个字符都不动、行高不变；
     透镜移开后再停留 HOLD_MS 才淡出，原文自己回来。 */
  useEffect(() => {
    if (!hit || reduce) return undefined;
    const layer = layerRef.current;
    const body = bodyRef?.current;
    if (!layer || !body) return undefined;

    const bbox = hit.rects.reduce(
      (b, r) => ({
        left: Math.min(b.left, r.left),
        top: Math.min(b.top, r.top),
        right: Math.max(b.right, r.left + r.width),
        bottom: Math.max(b.bottom, r.top + r.height),
      }),
      { left: Infinity, top: Infinity, right: -Infinity, bottom: -Infinity }
    );
    const w = Math.ceil(bbox.right - bbox.left);
    const h = Math.ceil(bbox.bottom - bbox.top);
    if (w < 8 || h < 8) return undefined;

    const cs = getComputedStyle(body);
    const fontPx = parseFloat(cs.fontSize) || 15;
    const lineH = parseFloat(cs.lineHeight) || fontPx * 1.9;
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    const cv = document.createElement("canvas");
    cv.className = "glens__fx";
    cv.width = Math.round(w * dpr);
    cv.height = Math.round(h * dpr);
    /* 译文画布挂进正文容器（.reader__body）里，用「内容坐标」——
       这样它和正文是同一套滚动：页面滚 / 面板内部滚，它都跟着字走，滚出视口就被裁掉。 */
    const host = bodyRef?.current || document.body;
    const hostRect = host.getBoundingClientRect();
    const left = bbox.left - (hostRect.left + scrollX) + (host.scrollLeft || 0);
    const top = bbox.top - (hostRect.top + scrollY) + (host.scrollTop || 0);
    cv.style.cssText = `position:absolute;left:${Math.round(left)}px;top:${Math.round(top)}px;width:${w}px;height:${h}px;pointer-events:none;z-index:2`;
    host.appendChild(cv);
    // 原文让位：这条 mark 的字变透明（占位与行高不变），译文直接落在页面上，不铺黑底
    if (hit.el) {
      hit.el.classList.add("is-glens-hidden");
      hit.el.style.color = "transparent";
      hit.el.style.background = "transparent";
    }
    // 透镜里的放大层也换成译文：映射后的文字在棱镜内同样看得到
    const palHit = palette();
    const hitColor = palHit[hit.pol] || palHit.neutral;
    for (let i = 0; i < LAYERS.length; i++) {
      const mag = mags.current[i];
      const m = mag && mag.querySelectorAll("mark.hl")[hit.idx];
      if (m) {
        m.textContent = hit.explain;
        m.style.color = hitColor;
        m.style.background = "transparent";
      }
    }
    const ctx = cv.getContext("2d");
    ctx.scale(dpr, dpr);
    ctx.textBaseline = "middle";
    ctx.textAlign = "left";
    ctx.font = `${cs.fontWeight} ${fontPx}px ${cs.fontFamily}`;

    const geek = isGeek();
    const pal = palette();
    const target = pal[hit.pol] || pal.neutral;
    const sheet = geek ? "#101010" : "#ffffff";
    const noiseSrc = `${hit.quote || hit.explain || "条款透镜"}${hit.explain || ""}`.replace(/\s+/g, "");
    const NOISE = "アカサタナハマ0110#%&/\\<>[]{}";

    // 译文比原句长是常态。不能影响正文排版，所以只能「缩字」：先挑一档能整段塞进
    // 原句 bbox 的字号（最宽到 100%，最小到 62%），再按这档字号排字。
    const fontOf = (k) => `${cs.fontWeight} ${(fontPx * k).toFixed(2)}px ${cs.fontFamily}`;
    let fitK = 0.62;
    let fitLineH = lineH * 0.62;
    for (const k of [1, 0.94, 0.88, 0.83, 0.78, 0.73, 0.68, 0.62]) {
      ctx.font = fontOf(k);
      let xx = 0;
      let yy = (lineH * k) / 2;
      for (const ch of hit.explain) {
        const cw = ctx.measureText(ch).width;
        if (xx + cw > w) {
          xx = 0;
          yy += lineH * k;
        }
        xx += cw;
      }
      if (yy + (lineH * k) / 2 <= h) {
        fitK = k;
        fitLineH = lineH * k;
        break;
      }
    }
    ctx.font = fontOf(fitK);

    const slots = [];
    let x = 0;
    let y = fitLineH / 2;
    let clipped = false;
    for (let i = 0; i < hit.explain.length; i++) {
      const ch = hit.explain[i];
      const cw = Math.max(1, ctx.measureText(ch).width);
      if (x + cw > w) {
        x = 0;
        y += fitLineH;
      }
      if (y + fitLineH / 2 > h) {
        clipped = true;
        break;
      }
      slots.push({ ch, x, y, w: cw });
      x += cw;
    }
    if (clipped && slots.length) {
      const last = slots[slots.length - 1];
      last.ch = "…";
    }
    if (!slots.length) return undefined;

    const startedAt = performance.now();
    let raf2 = 0;
    let dead = false;

    const draw = (now) => {
      const t = now - startedAt;
      const appear = clamp(t / 180, 0, 1);
      const resolve = clamp((t - 240) / 950, 0, 1);
      const done = resolve * slots.length;
      const flick = Math.floor(t / 70);

      ctx.clearRect(0, 0, w, h);
      // 不铺底色：原文由「隐藏那一条 mark」让位，译文直接落在页面上（滚动时不会露馅）
      ctx.globalAlpha = 1;

      for (let i = 0; i < slots.length; i++) {
        const s = slots[i];
        const p = clamp(done - i, 0, 1);
        if (p >= 1) {
          // 已重排：译文的字，颜色从白渐变到语义色
          ctx.globalAlpha = 0.97;
          ctx.fillStyle = mix("#ffffff", target, clamp(i / Math.max(6, slots.length - 1), 0, 1));
          if (geek) {
            ctx.shadowColor = target;
            ctx.shadowBlur = 9;
          }
          ctx.fillText(s.ch, s.x, s.y);
          ctx.shadowBlur = 0;
        } else {
          // 还没到：原句拆散后的字符 / 乱码
          const k = flick + i * 7;
          const ch = k % 4 === 0 ? NOISE[k % NOISE.length] : noiseSrc[(k * 31) % Math.max(1, noiseSrc.length)];
          ctx.globalAlpha = 0.34 + 0.3 * (1 - p);
          ctx.fillStyle = geek ? "#a8a8a8" : "#8a8a8a";
          ctx.fillText(ch, s.x, s.y);
        }
      }
      ctx.globalAlpha = 1;
      if (!dead) raf2 = requestAnimationFrame(draw);
    };
    raf2 = requestAnimationFrame(draw);

    return () => {
      dead = true;
      cancelAnimationFrame(raf2);
      // 消散：淡出再摘掉，原文随即回来
      cv.style.transition = "opacity 460ms ease";
      cv.style.opacity = "0";
      setTimeout(() => cv.remove(), 500);
      // 原文解除隐藏；克隆层里换回的原文由下一次 buildClone 重建
      if (hit.el) {
        hit.el.classList.remove("is-glens-hidden");
        hit.el.style.color = "";
        hit.el.style.background = "";
      }
      cloneKey.current = "";
    };
  }, [hit, reduce, bodyRef]);

  /* ── 指针：capture 起来拖，球只写 transform ─────────────────────────────── */
  const onPointerDown = (e) => {
    if (e.pointerType === "mouse" && e.button !== 0) return;
    e.preventDefault(); // 拖动时别顺手选中文字 / 别让触屏滚页面
    try {
      // 拖拽不再抢焦点：焦点环是「方框」的元凶，键盘用户仍然可以 Tab 进来
    } catch {}
    moved.current = true; // 用户上手了，之后不再自动摆位
    drag.current = {
      id: e.pointerId,
      dx: e.clientX + scrollX - pos.current.x,
      dy: e.clientY + scrollY - pos.current.y,
    };
    try {
      e.currentTarget.setPointerCapture(e.pointerId);
    } catch {}
    measure();
    buildClone();
    setDragging(true);
    paint();
  };

  const onPointerMove = (e) => {
    const d = drag.current;
    if (!d || e.pointerId !== d.id) return;
    const maxX = scrollX + innerWidth - D - EDGE_PAD; // 拖的时候不出视口
    const maxY = scrollY + innerHeight - D - EDGE_PAD;
    to.current = {
      x: clamp(e.clientX + scrollX - d.dx, scrollX + EDGE_PAD, maxX),
      y: clamp(e.clientY + scrollY - d.dy, scrollY + EDGE_PAD, maxY),
    };
    kick();
  };

  const endDrag = (e) => {
    const d = drag.current;
    if (!d) return;
    if (e?.pointerId != null && e.pointerId !== d.id) return;
    drag.current = null;
    try {
      e?.currentTarget?.releasePointerCapture?.(e.pointerId);
    } catch {}
    setDragging(false);
    save();
    kick();
  };

  /* ── 键盘：方向键微调（Shift 加速），Home 回默认位 ─────────────────────── */
  const onKeyDown = (e) => {
    const step = KEY_STEP * (e.shiftKey ? 4 : 1);
    let dx = 0;
    let dy = 0;
    if (e.key === "ArrowLeft") dx = -step;
    else if (e.key === "ArrowRight") dx = step;
    else if (e.key === "ArrowUp") dy = -step;
    else if (e.key === "ArrowDown") dy = step;
    else if (e.key === "Home") {
      const h = home();
      to.current = { x: h.x, y: h.y };
      measure();
      buildClone();
      kick();
      setTimeout(save, 900);
      e.preventDefault();
      return;
    } else return;
    e.preventDefault();
    measure();
    buildClone();
    to.current = {
      x: clamp(to.current.x + dx, EDGE_PAD, innerWidth - D - EDGE_PAD),
      y: clamp(to.current.y + dy, EDGE_PAD, innerHeight - D - EDGE_PAD),
    };
    kick();
    setTimeout(save, 900);
  };

  const onFocus = () => {
    measure();
    buildClone();
    paint();
  };

  /* ── 指针：用**原生监听**绑在球上 ──────────────────────────────────────────
     这颗球是 createPortal 到 document.body 的，在 #root 之外；React 19 的事件委托
     只挂在根容器上，合成事件收不到（实测：原生 pointerdown 能收到，React 的 onPointerDown
     一次都不触发，所以拖拽其实是死的）。这里自己 addEventListener，portal 与否都能拖。 */
  useEffect(() => {
    const el = ballRef.current;
    if (!el) return undefined;
    const down = (e) => onPointerDown(e);
    const move = (e) => onPointerMove(e);
    const up = (e) => endDrag(e);
    el.addEventListener("pointerdown", down);
    el.addEventListener("pointermove", move);
    el.addEventListener("pointerup", up);
    el.addEventListener("pointercancel", up);
    return () => {
      el.removeEventListener("pointerdown", down);
      el.removeEventListener("pointermove", move);
      el.removeEventListener("pointerup", up);
      el.removeEventListener("pointercancel", up);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const label = hit
    ? "玻璃透镜：正压在一句高亮条款上，原句已经就地换成了它的大白话解释。方向键微调，Home 回默认位置。"
    : "玻璃透镜：把它拖到原文上会放大文字；压在高亮条款上时，那句话会就地换成它的解释。方向键微调，Home 回默认位置。";

  const verdict = hit ? VERDICT[hit.pol] || VERDICT.neutral : "";

  const tree = (
    <div className="glens-layer" ref={layerRef} style={{ "--glens-d": `${D}px` }}>
      <div
        ref={ballRef}
        className={`glens__ball is-refracting${dragging ? " is-dragging" : ""}${over ? " is-over" : ""}`}
        role="button"
        tabIndex={0}
        aria-label={label}
        aria-keyshortcuts="ArrowUp ArrowDown ArrowLeft ArrowRight Home"
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={endDrag}
        onPointerCancel={endDrag}
        onLostPointerCapture={endDrag}
        onKeyDown={onKeyDown}
        onFocus={onFocus}
      >
        <div className="glens__lens" aria-hidden="true">
          {/* 三层放大：圆心 1.7，往外 1.52 / 1.36，各露在自己那一环上 → 字在贴边处被折回来。
              主层也裁到 ~90% 半径为止，不然贴边那圈会和「折回来」的那层叠成双影。 */}
          <div className="glens__mainclip">
            <div
              className="glens__mag glens__mag--main"
              ref={(el) => {
                mags.current[0] = el;
              }}
            />
          </div>
          <div className="glens__band glens__band--mid">
            <div
              className="glens__mag glens__mag--mid"
              ref={(el) => {
                mags.current[1] = el;
              }}
            />
          </div>
          <div className="glens__band glens__band--rim">
            <div
              className="glens__mag glens__mag--rim"
              ref={(el) => {
                mags.current[2] = el;
              }}
            />
          </div>
        </div>
        <span className="glens__shade" aria-hidden="true" />
        <span className="glens__sheen" aria-hidden="true" />
        <span className="glens__disp glens__disp--r" aria-hidden="true" />
        <span className="glens__disp glens__disp--c" aria-hidden="true" />
        <span className="glens__prism" aria-hidden="true" />
      </div>


      {/* 读屏用：原文替换是纯视觉的，内容在这里念出来 */}
      <span className="glens__live" role="status" aria-live="polite">
        {hit ? `${verdict}。${hit.explain}${hit.labels.length ? `标签：${hit.labels.join("、")}。` : ""}原文：${hit.quote}` : ""}
      </span>
    </div>
  );

  return createPortal(tree, document.body);
}
