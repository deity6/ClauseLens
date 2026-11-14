import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useReducedMotion } from "motion/react";
import "./GlassLens.css";

/* ── 玻璃透镜 v3 ─────────────────────────────────────────────────────────────
   观感还是那颗玻璃球（高光、棱镜边、软影、能拖），但三件事换了实现：

   ① 位置：层的坐标是**视口坐标**（position: fixed）。默认坐在「05 · SOURCE」标题
      右侧的 .lensdock 里；dock 不在视口里，整颗球收起来 —— 不再被「夹」到视口
      右下角（v2 的 place() 把 y clamp 进 innerHeight，于是结果页一进来就贴在
      右下角）。用户拖走之后它变成屏幕上的放大镜，位置写 localStorage，Home /
      点 dock 回位。
   ② 光学：圆心是一块**真透明的洞** —— 底下就是活的页面（含原位翻译层），不缩放、
      不模糊、不叠克隆；只有 66%–100% 半径那一圈用两层克隆做「边缘折射」。
      v2 的球心是 1.7× 克隆铺白底 + backdrop-filter，整颗糊成毛玻璃，翻译根本
      看不见；这版中心清清楚楚，「只有小边缘发散」。
   ③ 跟随：页面滚动 / 正文框内部滚动 / 展开收起 / 换文档 / 改尺寸，都先重量几何
      再重画，所以条款一条条往下翻时，球里的内容就是此刻压着的那一段。
      中心是活 DOM，天然不会停在上一段。

   命中 mark.hl 时：边缘色散升起来；正文那条的原字变透明，同一位置由 canvas 在原位
   画成大白话译文（不参与排版、不动行高）。译文画布见下方 effect —— 颜色从可读中性
   色渐变到语义色（v2 从纯白起步，纸底上等于看不见），字号先做适配、必要时往下多占
   一两行，不再被原句 bbox 裁掉。

   性能契约：拖动只写 transform；克隆每种内容只做一次（内容变了才重建）；命中检测
   60ms 节流；球收起时停掉监听。 */

const D = 112; // 球径：正好卡进「05 · SOURCE」上下两条发丝线之间
const CORE = 0.66; // 中心透明区的半径占比；再往外才是折射环（见 CSS 的 mask）
// 边缘两层克隆：越靠边折得越狠。中心 66% 以内不参与，直接看穿。
const RINGS = [{ mag: 1.16 }, { mag: 1.42 }];
const KEY_STEP = 10; // 方向键步长
const PROBE_MS = 60; // 命中检测节流（每帧 getClientRects 会拖慢滚动）
const EDGE_PAD = 10; // 不贴死视口边
const HOLD_MS = 2400; // 透镜移开后，译文再停留 2.4 秒才消散（动画保护）
const STORE_KEY = "cl:lens.v3"; // 只存用户拖过之后的视口坐标；没拖过就跟着 dock

// 极性的一句话：bad → 对你不利
const VERDICT = {
  bad: "对你不利：这段多半让你吃亏",
  good: "对你有利：这段偏向保护你",
  warn: "需要留意：这段有条件或例外",
  neutral: "一般说明：这段只是把规则讲清楚",
  focus: "你刚从标签跳到这里",
};

// 语义色只在这个效果里出现（透镜边缘、原位译文），不进页面其它地方
const PALETTE = {
  light: { bad: "#c2412d", good: "#2f7d5b", warn: "#b7791f", neutral: "#5f5c55", focus: "#43423d" },
  geek: { bad: "#ff6b6b", good: "#5ef08a", warn: "#ffc857", neutral: "#d0d0d0", focus: "#ffffff" },
};
// 译文起点色：可读的中性灰（浅色纸底 / 深色点阵底各一套）。v2 从 #ffffff 起步，
// 纸底上前面几个字直接消失 —— 这就是「浅色渲染有问题」的来源。
const MUTED = { light: "#57544c", geek: "#dcdcdc" };
const isGeek = () => document.documentElement.dataset.theme === "geek";
const palette = () => PALETTE[isGeek() ? "geek" : "light"];
const muted = () => MUTED[isGeek() ? "geek" : "light"];

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
const union = (rects) =>
  rects.reduce(
    (b, r) => ({
      left: Math.min(b.left, r.left),
      top: Math.min(b.top, r.top),
      right: Math.max(b.right, r.left + r.width),
      bottom: Math.max(b.bottom, r.top + r.height),
    }),
    { left: Infinity, top: Infinity, right: -Infinity, bottom: -Infinity }
  );

/**
 * 挂在 Reader 里（DOM 上是一层 portal 到 body 的定位层）。
 * @param anchorRef  阅读器根节点：判断「原文区还在不在视口里」
 * @param bodyRef    .reader__body：边缘折射要克隆的那份原文
 * @param dockRef    「05 · SOURCE」标题右边的凹槽：默认落点就是它的中心
 * @param contentKey 当前文档 id：换文档时克隆要重建
 */
export default function GlassLens({ anchorRef, bodyRef, dockRef, contentKey }) {
  const reduce = useReducedMotion();
  const layerRef = useRef(null);
  const ballRef = useRef(null);
  const mags = useRef([]); // 边缘折射的两层克隆

  const pos = useRef({ x: 0, y: 0 }); // 视口坐标（球左上角）
  const geo = useRef(null); // {bodyLeft, bodyTop, scrollTop, width} —— 全是视口坐标
  const moved = useRef(false); // 用户拿走过：之后按屏幕坐标待着，不再跟 dock
  const drag = useRef(null);
  const raf = useRef(0);
  const cloneKey = useRef("");
  const dirty = useRef(true); // 正文 DOM 变了（MutationObserver 置位）
  const lastProbe = useRef(0);
  const hitKey = useRef("");
  const holdTimer = useRef(0);

  const [hit, setHit] = useState(null); // {pol, labels, explain, quote, key, el, idx}
  const [dragging, setDragging] = useState(false);
  const [over, setOver] = useState(false);
  const [shown, setShown] = useState(false);

  /* ── 量几何：正文框此刻在视口里的位置（fixed 坐标，滚动时 rect.top 会变 → 每次都重量） ── */
  const measure = useCallback(() => {
    const body = bodyRef?.current;
    if (!body) {
      geo.current = null;
      return null;
    }
    const r = body.getBoundingClientRect();
    geo.current = {
      bodyLeft: r.left,
      bodyTop: r.top,
      scrollTop: body.scrollTop,
      width: body.clientWidth,
    };
    return geo.current;
  }, [bodyRef]);

  /* ── 一帧：球到位；两层克隆把「圆心压着的那一点内容」钉回圆心 ─────────────────
     中心那 66% 不画任何克隆（CSS mask 挡住），所以底下永远是活的页面本身。 */
  const paint = useCallback(() => {
    const ball = ballRef.current;
    if (!ball) return;
    const p = pos.current;
    ball.style.transform = `translate3d(${p.x.toFixed(1)}px, ${p.y.toFixed(1)}px, 0)`;

    const g = geo.current;
    if (!g) return;
    const half = D / 2;
    const cx = p.x + half - g.bodyLeft;
    const cy = p.y + half - g.bodyTop + g.scrollTop;
    for (let i = 0; i < RINGS.length; i++) {
      const el = mags.current[i];
      if (!el) continue;
      const m = RINGS[i].mag;
      el.style.transform = `translate3d(${(half - m * cx).toFixed(1)}px, ${(half - m * cy).toFixed(1)}px, 0) scale(${m})`;
    }
  }, []);

  /* ── 克隆（只给边缘环用）：key 里带文档 / 宽度 / 高度 / 字数，变了才重建 ──────── */
  const buildClone = useCallback(() => {
    const body = bodyRef?.current;
    const host = mags.current[0];
    if (!body || !host || reduce) return;
    const key = `${contentKey}|${body.clientWidth}|${body.scrollHeight}|${body.childElementCount}|${body.textContent.length}`;
    if (cloneKey.current === key && host.firstElementChild) {
      dirty.current = false;
      return;
    }

    const w = body.clientWidth;
    const mk = () => {
      const c = body.cloneNode(true);
      c.removeAttribute("tabindex");
      c.removeAttribute("role");
      c.removeAttribute("aria-label");
      c.setAttribute("aria-hidden", "true");
      c.querySelectorAll(".is-flash").forEach((el) => el.classList.remove("is-flash"));
      // 命中时那条原字是透明的；克隆里要还原成原文 —— 边缘环该透着「原来的字」，
      // 中心那圈才是译文（否则环上会缺一段看起来像漏字）
      c.querySelectorAll(".is-glens-hidden").forEach((el) => el.classList.remove("is-glens-hidden"));
      // 原位译文画布也在正文里，克隆时剔掉一份，不然边缘环里会多出一块重复的译文
      c.querySelectorAll(".glens__fx").forEach((el) => el.remove());
      // 克隆不是滚动容器：铺到底，靠 translate 对准（字体/行高/内边距照旧生效）
      c.style.width = `${w}px`;
      c.style.height = "auto";
      c.style.maxHeight = "none";
      c.style.overflow = "hidden";
      c.style.margin = "0";
      return c;
    };
    for (let i = 0; i < RINGS.length; i++) if (mags.current[i]) mags.current[i].replaceChildren(mk());
    cloneKey.current = key;
    dirty.current = false;
  }, [bodyRef, contentKey, reduce]);

  /* ── 命中检测：透镜圆和 mark.hl 的行盒求交，取离圆心最近的那条 ──────────────
     <mark> 是 inline，bbox 一半是行间空隙，所以不用 elementFromPoint。 */
  const probe = useCallback(() => {
    const body = bodyRef?.current;
    const ballEl = ballRef.current;
    if (!body || !ballEl) return;
    const br = ballEl.getBoundingClientRect();
    const cx = br.left + br.width / 2;
    const cy = br.top + br.height / 2;
    // 球在视口外：什么都别判
    if (cx < 0 || cy < 0 || cx > innerWidth || cy > innerHeight) return;

    let mark = null;
    let onBody = false;
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
      const r = body.getBoundingClientRect();
      const nx = clamp(cx, r.left, r.right);
      const ny = clamp(cy, r.top, r.bottom);
      onBody = Math.hypot(cx - nx, cy - ny) <= R;
    } else onBody = true;

    setOver((v) => (v === onBody ? v : onBody));
    if (ballEl) ballEl.dataset.hit = mark ? "1" : "0";

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
      const idx = [...body.querySelectorAll("mark.hl")].indexOf(mark);
      // key 不含位置：同一条原文里挪动透镜不该重建画布（滚动时也不会一直闪）
      const key = `${pol}|${explain}|${quote}|${idx}`;
      if (key !== hitKey.current) {
        hitKey.current = key;
        setHit({ pol, labels, explain, quote, key, el: mark, idx });
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

  /* ── 落点：默认坐在 dock 里；用户拖过就固定在屏幕上 ─────────────────────────
     出现条件：没被拿走时，dock 必须在视口里（结果页顶部时它在屏幕外，球收起来；
     v2 会把球 clamp 进视口，于是「一分析完就贴在右下角」——这轮的头号问题）。
     被拿走之后它是一枚屏幕上的放大镜：只要原文这一节还在视口里就留着，往下读也在。 */
  const relayout = useCallback(() => {
    const dock = dockRef?.current;
    const anchor = anchorRef?.current;
    if (dock) {
      // 空槽里那句「点我回位」只在球被拿走时出现
      const take = moved.current ? "1" : "0";
      if (dock.dataset.taken !== take) dock.dataset.taken = take;
    }
    let show = false;

    if (!moved.current) {
      const dr = dock?.getBoundingClientRect();
      show = !!dr && dr.width > 0 && dr.bottom > 48 && dr.top < innerHeight - 24;
      if (show) {
        pos.current = {
          x: clamp(dr.left + dr.width / 2 - D / 2, EDGE_PAD, innerWidth - D - EDGE_PAD),
          // 槽被滚到边上时球跟着贴边，但绝不允许半颗挂在视口外
          y: clamp(dr.top + dr.height / 2 - D / 2, EDGE_PAD, innerHeight - D - EDGE_PAD),
        };
      }
    } else {
      const sr = (dock?.closest(".rsec") || anchor)?.getBoundingClientRect();
      show = !!sr && sr.bottom > 120 && sr.top < innerHeight - 100;
      pos.current = {
        x: clamp(pos.current.x, EDGE_PAD, innerWidth - D - EDGE_PAD),
        y: clamp(pos.current.y, EDGE_PAD, innerHeight - D - EDGE_PAD),
      };
    }

    setShown((prev) => (prev === show ? prev : show));
    if (!show && hitKey.current) {
      hitKey.current = "";
      setHit(null);
    }
    return show;
  }, [anchorRef, dockRef]);

  /* ── 一次同步：量 → 摆 → 重建（需要时）→ 画 → 命中 ─────────────────────── */
  const sync = useCallback(
    (now = false) => {
      const run = () => {
        raf.current = 0;
        measure();
        const show = relayout();
        if (!show) return;
        if (dirty.current) buildClone();
        paint();
        const t = performance.now();
        if (now || t - lastProbe.current >= PROBE_MS) {
          lastProbe.current = t;
          probe();
        }
      };
      if (now) {
        if (raf.current) cancelAnimationFrame(raf.current);
        raf.current = 0;
        run();
        return;
      }
      if (!raf.current) raf.current = requestAnimationFrame(run);
    },
    [measure, relayout, buildClone, paint, probe]
  );

  /* ── 初次落位：有存档（用户拖过）就用存档，否则跟 dock ─────────────────── */
  useLayoutEffect(() => {
    let stored = null;
    try {
      stored = JSON.parse(localStorage.getItem(STORE_KEY) || "null");
    } catch {
      stored = null;
    }
    const ok =
      stored &&
      Number.isFinite(stored.x) &&
      Number.isFinite(stored.y) &&
      stored.x > -D * 0.5 &&
      stored.x < innerWidth &&
      stored.y > -D * 0.5 &&
      stored.y < innerHeight;
    if (ok) {
      moved.current = true;
      pos.current = { x: stored.x, y: stored.y };
    }
    measure();
    relayout();
    buildClone();
    paint();
    probe();
  }, [measure, relayout, buildClone, paint, probe]);

  /* ── 滚动 / 改尺寸 / 面板高度动画：都先重量再画 ─────────────────────────────
     scroll 不冒泡，但捕获阶段能看到任何滚动容器（页面、.reader__body）；v2 只在
     页面滚动时 paint 不 measure，所以球里的内容会停在上一段。 */
  useEffect(() => {
    const onScroll = () => sync();
    addEventListener("scroll", onScroll, { capture: true, passive: true });
    addEventListener("resize", onScroll);
    const ro = typeof ResizeObserver === "function" ? new ResizeObserver(onScroll) : null;
    if (bodyRef?.current) ro?.observe(bodyRef.current);
    if (anchorRef?.current) ro?.observe(anchorRef.current);
    if (dockRef?.current) ro?.observe(dockRef.current);

    // 正文 DOM 变了（换文档、跳转后新增高亮、主题相关的 class 变化）→ 下一次同步重建克隆
    const mo =
      typeof MutationObserver === "function"
        ? new MutationObserver(() => {
            dirty.current = true;
            sync();
          })
        : null;
    if (bodyRef?.current) mo?.observe(bodyRef.current, { childList: true, characterData: true, subtree: true, attributes: true, attributeFilter: ["class", "style"] });

    return () => {
      removeEventListener("scroll", onScroll, { capture: true });
      removeEventListener("resize", onScroll);
      ro?.disconnect();
      mo?.disconnect();
      if (raf.current) cancelAnimationFrame(raf.current);
    };
  }, [sync, bodyRef, anchorRef, dockRef]);

  // 换文档：正文换了，边缘克隆跟着换，命中也要重判
  useEffect(() => {
    dirty.current = true;
    sync(true);
  }, [contentKey, sync]);

  // 收起时清定时器
  useEffect(
    () => () => {
      cancelAnimationFrame(raf.current);
      if (holdTimer.current) clearTimeout(holdTimer.current);
    },
    []
  );

  /* ── 回位：Home 键 / 点 dock（Result 里那个凹槽派发事件） ──────────────────── */
  const recall = useCallback(() => {
    moved.current = false;
    try {
      localStorage.removeItem(STORE_KEY);
    } catch {
      /* 隐身模式：记不住就算了 */
    }
    sync(true);
  }, [sync]);

  useEffect(() => {
    const onHome = () => recall();
    addEventListener("cl:lens:home", onHome);
    return () => removeEventListener("cl:lens:home", onHome);
  }, [recall]);

  const save = useCallback(() => {
    if (!moved.current) return;
    try {
      localStorage.setItem(STORE_KEY, JSON.stringify({ x: Math.round(pos.current.x), y: Math.round(pos.current.y) }));
    } catch {
      /* 隐身模式：记不住就算了 */
    }
  }, []);

  /* ── 原位译文：把命中的那条 mark 的字变透明（占位/行高不变），同一块位置用 canvas
        逐字重排成大白话。译文比原句长是常态 —— 先缩字号，仍放不下就往下多占 1–2 行，
        并把底衬铺出来（v2 被原句 bbox 裁掉，后半句直接没了）。 */
  useEffect(() => {
    if (!hit) return undefined;
    const body = bodyRef?.current;
    const el = hit?.el;
    if (!body || !el || !el.isConnected) return undefined;

    const rects = [...el.getClientRects()].filter((r) => r.width > 4 && r.height > 4);
    if (!rects.length) return undefined;
    const bbox = union(rects);
    const br = body.getBoundingClientRect();
    const cs = getComputedStyle(body);
    const fontPx = parseFloat(cs.fontSize) || 15;
    const lineH = parseFloat(cs.lineHeight) || fontPx * 1.9;
    const padR = parseFloat(cs.paddingRight) || 0;
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    const text = hit.explain || VERDICT[hit.pol] || "";
    if (!text) return undefined;

    // 内容坐标（挂在 .reader__body 里，跟正文一起滚）
    const left = bbox.left - br.left + body.scrollLeft;
    const top = bbox.top - br.top + body.scrollTop;
    const bboxW = bbox.right - bbox.left;
    const bboxH = bbox.bottom - bbox.top;
    const availW = Math.max(160, body.clientWidth - left - padR);
    const w = Math.min(availW, Math.max(bboxW, 320));
    const maxH = Math.max(bboxH, lineH * 1.15) + lineH * 2; // 最多往下多占两行

    // 字号适配：先在一块离屏 context 上试（真画布的高度要等排好版才知道）。
    // 从原字号往下试，能整段塞进 maxH 就停；最小 58%，再放不下才截。
    const probe = document.createElement("canvas").getContext("2d");
    probe.textBaseline = "middle";
    probe.textAlign = "left";
    const fontOf = (k) => `${cs.fontWeight} ${fontPx * k}px ${cs.fontFamily}`;
    let fitK = 0.58;
    let lines = [];
    for (const k of [1, 0.94, 0.88, 0.83, 0.78, 0.73, 0.68, 0.63, 0.58]) {
      probe.font = fontOf(k);
      const lh = lineH * k;
      const rows = [];
      let x = 0;
      let row = "";
      let clipped = false;
      for (const ch of text) {
        const cw = probe.measureText(ch).width;
        if (x + cw > w) {
          rows.push(row);
          row = "";
          x = 0;
        }
        if ((rows.length + 1) * lh > maxH) {
          clipped = true;
          break;
        }
        row += ch;
        x += cw;
      }
      if (row) rows.push(row);
      fitK = k;
      lines = rows;
      if (!clipped) break;
    }
    if (!lines.length) return undefined;
    const fitLineH = lineH * fitK;
    const textH = lines.length * fitLineH;
    // 底衬至少盖住原句那一块（原字已经透明，留空会像丢字）；译文比原句短就居中
    const plateH = Math.max(bboxH, textH + 4);
    const y0 = (plateH - textH) / 2;

    const cv = document.createElement("canvas");
    cv.className = "glens__fx";
    cv.width = Math.round(w * dpr);
    cv.height = Math.round(plateH * dpr);
    cv.style.cssText = `position:absolute;left:${Math.round(left)}px;top:${Math.round(top)}px;width:${Math.round(w)}px;height:${Math.round(plateH)}px;pointer-events:none;z-index:2`;
    body.appendChild(cv);

    const ctx = cv.getContext("2d");
    ctx.scale(dpr, dpr);
    ctx.textBaseline = "middle";
    ctx.textAlign = "left";

    // 底衬：纸色 + 左侧语义色条，让译文压在后面的行上也读得清
    const pal = palette();
    const target = pal[hit.pol] || pal.neutral;
    const geek = isGeek();
    const sheet = geek ? "rgba(16,16,16,0.95)" : "rgba(255,255,255,0.96)";
    const rule = target;

    // 每个字一个槽位：先按字排好位置，再按时间逐个「电离 → 定形」
    ctx.font = fontOf(fitK);
    const index = [];
    for (let li = 0; li < lines.length; li++) {
      let x = 14;
      const y = y0 + li * fitLineH + fitLineH / 2 + 1;
      for (const ch of lines[li]) {
        const cw = ctx.measureText(ch).width;
        index.push({ ch, w: cw, x, y });
        x += cw;
      }
    }
    const total = index.length;

    const r = 9;
    const drawPlate = () => {
      ctx.clearRect(0, 0, w, plateH);
      ctx.beginPath();
      ctx.roundRect ? ctx.roundRect(0, 0, w, plateH, r) : ctx.rect(0, 0, w, plateH);
      ctx.fillStyle = sheet;
      ctx.fill();
      ctx.strokeStyle = geek ? "rgba(255,255,255,0.18)" : "rgba(23,22,20,0.10)";
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.roundRect ? ctx.roundRect(0.5, 0.5, w - 1, plateH - 1, r) : ctx.rect(0.5, 0.5, w - 1, plateH - 1);
      ctx.stroke();
      // 左缘那条语义色
      ctx.fillStyle = rule;
      ctx.beginPath();
      ctx.roundRect ? ctx.roundRect(0, 0, 3, plateH, [r, 0, 0, r]) : ctx.rect(0, 0, 3, plateH);
      ctx.fill();
    };
    const startedAt = performance.now();
    const NOISE = "アカサタナハマ0110#%&/\\<>[]{}";
    const noiseSrc = `${hit.quote || text}${text}`.replace(/\s+/g, "");
    let raf2 = 0;
    let dead = false;

    const draw = (now) => {
      const t = now - startedAt;
      const appear = clamp(t / 160, 0, 1);
      const resolve = clamp((t - 200) / 900, 0, 1);
      const done = resolve * total;
      const flick = Math.floor(t / 70);

      ctx.save();
      ctx.globalAlpha = appear;
      drawPlate();
      ctx.restore();

      ctx.font = fontOf(fitK);
      for (let i = 0; i < index.length; i++) {
        const s = index[i];
        const p = clamp(done - i, 0, 1);
        if (p >= 1) {
          ctx.globalAlpha = appear;
          ctx.fillStyle = mix(muted(), target, clamp(i / Math.max(6, total - 1), 0, 1));
          if (geek) {
            ctx.shadowColor = target;
            ctx.shadowBlur = 8;
          }
          ctx.fillText(s.ch, s.x, s.y);
          ctx.shadowBlur = 0;
        } else {
          const k = flick + i * 7;
          const ch = k % 4 === 0 ? NOISE[k % NOISE.length] : noiseSrc[(k * 31) % Math.max(1, noiseSrc.length)];
          ctx.globalAlpha = 0.4 + 0.28 * (1 - p);
          ctx.fillStyle = geek ? "#a8a8a8" : "#7c7873";
          ctx.fillText(ch, s.x, s.y);
        }
      }
      ctx.globalAlpha = 1;
      if (!dead) raf2 = requestAnimationFrame(draw);
    };
    // 减少动态效果时不跑逐字动画，但仍要给出译文（画一帧静止的就停）
    if (reduce) {
      dead = true;
      draw(performance.now() + 8000);
    } else raf2 = requestAnimationFrame(draw);

    // 原字让位（占位与行高都不变）
    el.classList.add("is-glens-hidden");

    return () => {
      dead = true;
      cancelAnimationFrame(raf2);
      cv.style.transition = "opacity 420ms ease";
      cv.style.opacity = "0";
      setTimeout(() => cv.remove(), 460);
      el.classList.remove("is-glens-hidden");
    };
  }, [hit, reduce, bodyRef]);

  /* ── 指针：原生监听（球 portal 到 body，#root 之外，React 合成事件收不到） ── */
  const onPointerDown = (e) => {
    if (e.pointerType === "mouse" && e.button !== 0) return;
    e.preventDefault();
    moved.current = true;
    drag.current = { id: e.pointerId, dx: e.clientX - pos.current.x, dy: e.clientY - pos.current.y };
    try {
      e.currentTarget.setPointerCapture(e.pointerId);
    } catch {}
    setDragging(true);
    sync(true);
  };

  const onPointerMove = (e) => {
    const d = drag.current;
    if (!d || e.pointerId !== d.id) return;
    pos.current = {
      x: clamp(e.clientX - d.dx, EDGE_PAD, innerWidth - D - EDGE_PAD),
      y: clamp(e.clientY - d.dy, EDGE_PAD, innerHeight - D - EDGE_PAD),
    };
    sync();
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
    sync(true);
  };

  /* ── 键盘：方向键微调（Shift 加速），Home 回 dock ─────────────────────────── */
  const onKeyDown = (e) => {
    const step = KEY_STEP * (e.shiftKey ? 4 : 1);
    let dx = 0;
    let dy = 0;
    if (e.key === "ArrowLeft") dx = -step;
    else if (e.key === "ArrowRight") dx = step;
    else if (e.key === "ArrowUp") dy = -step;
    else if (e.key === "ArrowDown") dy = step;
    else if (e.key === "Home") {
      e.preventDefault();
      recall();
      return;
    } else return;
    e.preventDefault();
    moved.current = true;
    pos.current = {
      x: clamp(pos.current.x + dx, EDGE_PAD, innerWidth - D - EDGE_PAD),
      y: clamp(pos.current.y + dy, EDGE_PAD, innerHeight - D - EDGE_PAD),
    };
    sync(true);
    setTimeout(save, 700);
  };

  const onFocus = () => sync(true);

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
    ? "玻璃透镜：正压在一句高亮条款上，原句已经就地换成了它的大白话解释。方向键微调，Home 回原位。"
    : "玻璃透镜：拖到条款上会放大并透出边缘折射；压在高亮条款上时，那句话会就地换成解释。方向键微调，Home 回原位。";
  const verdict = hit ? VERDICT[hit.pol] || VERDICT.neutral : "";

  const tree = (
    <div className="glens-layer" ref={layerRef} data-show={shown ? "1" : "0"} style={{ "--glens-d": `${D}px`, "--glens-core": `${CORE}` }}>
      <div
        ref={ballRef}
        className={`glens__ball${dragging ? " is-dragging" : ""}${over ? " is-over" : ""}`}
        role="button"
        tabIndex={0}
        aria-label={label}
        aria-keyshortcuts="ArrowUp ArrowDown ArrowLeft ArrowRight Home"
        onKeyDown={onKeyDown}
        onFocus={onFocus}
      >
        {/* 只有边缘两环是克隆（折射）；中心是透的，直接看穿到页面 */}
        <div className="glens__lens" aria-hidden="true">
          <div className="glens__band glens__band--mid">
            <div
              className="glens__mag"
              ref={(el) => {
                mags.current[0] = el;
              }}
            />
          </div>
          <div className="glens__band glens__band--rim">
            <div
              className="glens__mag"
              ref={(el) => {
                mags.current[1] = el;
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