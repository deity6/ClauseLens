import { useEffect, useMemo, useRef, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { DIM_ORDER, gradeOf } from "../lib/taxonomy.js";
import { DUR, EASE } from "../lib/motion.js";
import "./Radar.css";

// 六维雷达：分数越高越友好。多边形从中心生长（缩放用回弹），网格与轴线静止不动，
// 只让“数据”在动——读者的视线会被唯一运动的东西带走。
//
// 顶点可小幅拖动：拖的时候**整个六边形跟着变形**（不只是那个小圆点），松手弹回。
// 可拖范围以顶点自身为圆心、半径 MAX_DRAG（远小于 R，只是“手感”级别的小扰动）。
const R = 108;
const C = 150;
const MAX_DRAG = 18;
// 左右各留 PAD 给轴标签：标签按“含留白的画布”定位，窄屏上也不会贴边
const PAD = 44;
const VW = 300 + PAD * 2;
const pt = (i, v) => {
  const a = -Math.PI / 2 + (i * Math.PI * 2) / 6;
  return [C + Math.cos(a) * R * v, C + Math.sin(a) * R * v];
};

// ─── 主题 B（点阵）的几何 ─────────────────────────────────────────────────
// 只做“数据准备”，画不画由 Radar.css 决定：这些层在 A 主题下是 display:none，
// 于是暖纸主题的 DOM 与像素都不变（B 的规则一律挂在 [data-theme="geek"] 下）。

// 网格：四级同心六边形 → 沿每条边按固定步长排小点（外环最亮、内环最暗）。
const RING_STEP = 12;
const RING_KS = [0.25, 0.5, 0.75, 1];
const RING_DOTS = RING_KS.map((k) => {
  const hex = DIM_ORDER.map((_, i) => pt(i, k));
  const out = [];
  for (let e = 0; e < 6; e++) {
    const [x1, y1] = hex[e];
    const [x2, y2] = hex[(e + 1) % 6];
    // 每条边分 n 段、只在每段起点放点（不重复画顶点，读完一圈正好闭合）
    const n = Math.max(2, Math.round(Math.hypot(x2 - x1, y2 - y1) / RING_STEP));
    for (let s = 0; s < n; s++) {
      const t = s / n;
      out.push([x1 + (x2 - x1) * t, y1 + (y2 - y1) * t]);
    }
  }
  return out;
});

// 数据面：方形点阵铺满外接圆；点**不随拖动移动**（点阵是“屏幕”），
// 只有“哪些点亮着、多亮”随多边形变——这就是点云变形的观感。
const CLOUD_STEP = 6; // 点阵间距（viewBox 单位；≈ 7.4 屏幕像素）
const CLOUD_SQUARE = 2; // 2px 方块
const CLOUD_LEVELS = 5; // 亮度档
const CLOUD_REACH = R + MAX_DRAG + 6; // 顶点拖出去也在点阵范围内
const CLOUD_DOTS = (() => {
  const out = [];
  for (let dy = -CLOUD_REACH; dy <= CLOUD_REACH; dy += CLOUD_STEP) {
    for (let dx = -CLOUD_REACH; dx <= CLOUD_REACH; dx += CLOUD_STEP) {
      if (Math.hypot(dx, dy) > CLOUD_REACH) continue;
      out.push([C + dx, C + dy]);
    }
  }
  return out;
})();

// 点云的每一档是一张 <path>：把几百个 2px 方块并进一条 d，几十次/秒重算也不掉帧。
// 亮度 = f(到中心距离 / 该方向上的边界距离)：
//   射线与（可拖动的）多边形求交 → 得到该方向的边界半径，再按比值分档。
function cloudLayers(vertices, hotIdx) {
  const v = vertices.map(([x, y]) => [x - C, y - C]);
  const buf = Array.from({ length: CLOUD_LEVELS }, () => []);
  for (const [x, y] of CLOUD_DOTS) {
    const ux = x - C;
    const uy = y - C;
    let hit = 0;
    let edge = -1;
    for (let e = 0; e < 6; e++) {
      const [ax, ay] = v[e];
      const [bx, by] = v[(e + 1) % 6];
      const dx = bx - ax;
      const dy = by - ay;
      const den = ux * dy - uy * dx; // cross(u, d)
      if (!den) continue;
      const t = (ax * dy - ay * dx) / den; // 交点 = t·u
      if (t <= 1e-6) continue;
      const s = (ax * uy - ay * ux) / den; // 交点在边上的位置
      if (s < 0 || s > 1.000001) continue;
      if (t > hit) {
        hit = t;
        edge = e;
      }
    }
    if (edge < 0) continue;
    // hit 是“交点相对这个点自身”的倍数：>1 才在面内（=1 正好压在折线上）
    if (hit <= 1.000001) continue;
    const q = Math.min(1, 1 / hit); // 0 = 中心，1 = 边界（线性分档：越靠边越亮）
    let lv = Math.min(CLOUD_LEVELS - 1, Math.floor(q * CLOUD_LEVELS));
    if (edge === hotIdx) lv = Math.min(CLOUD_LEVELS - 1, lv + 1); // hover 的那一维整片提亮
    buf[lv].push(`M${x.toFixed(1)} ${y.toFixed(1)}h${CLOUD_SQUARE}v${CLOUD_SQUARE}h-${CLOUD_SQUARE}z`);
  }
  return buf.map((d) => d.join(""));
}

// 右侧维度条：B 主题是 20 段小方块
const SEGS = 20;

export default function Radar({ dims, dimMeta, tagsByDim, grades }) {
  const reduce = useReducedMotion();
  const [hover, setHover] = useState(null); // 立即生效：只负责高亮
  const [tipDim, setTipDim] = useState(null); // 延迟生效：负责浮层，避免快速划过时闪
  const [offsets, setOffsets] = useState({}); // {dim: [dx, dy]}
  const [dragDim, setDragDim] = useState(null);
  const svgRef = useRef(null);
  const dragStart = useRef(null);
  const rafRef = useRef(0);
  const tipTimer = useRef(0);

  // 每个顶点的最终坐标（含拖动偏移）——多边形和小圆点共用这一份，才能一起动
  const pts = DIM_ORDER.map((d, i) => {
    const v = Math.max(0.04, (dims[d] ?? 0) / 100);
    const [x, y] = pt(i, v);
    const o = offsets[d] || [0, 0];
    return [x + o[0], y + o[1]];
  });
  const poly = pts.map(([x, y]) => `${x},${y}`).join(" ");
  // 当前被 hover / 拖动的维度下标：点云据此把那一维整片提亮
  const hotIdx = DIM_ORDER.indexOf(dragDim || hover || "");
  // poly 变 = 顶点动了；点云只在这时重算（静止时零开销）
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const cloud = useMemo(() => cloudLayers(pts, hotIdx), [poly, hotIdx]);

  // 指针位置 → viewBox 坐标（viewBox 的 x 从 -PAD 开始，y 从 0）
  const toView = (clientX, clientY) => {
    const rect = svgRef.current?.getBoundingClientRect();
    if (!rect) return null;
    return [
      ((clientX - rect.left) / rect.width) * VW - PAD,
      ((clientY - rect.top) / rect.height) * 300,
    ];
  };

  const onDown = (d, e) => {
    e.preventDefault();
    const v = toView(e.clientX, e.clientY);
    if (!v) return;
    cancelAnimationFrame(rafRef.current);
    dragStart.current = { at: v, off: offsets[d] || [0, 0] };
    setDragDim(d);
  };

  // 松手：阻尼振荡回到 0（polygon 和点一起被 offsets 驱动，所以一起弹回去）
  const springBack = (dim, from) => {
    cancelAnimationFrame(rafRef.current);
    const t0 = performance.now();
    const dur = reduce ? 1 : 640;
    const tick = (t) => {
      const k = Math.min(1, (t - t0) / dur);
      const damp = Math.exp(-4.2 * k) * Math.cos(7.4 * k);
      setOffsets((o) => ({ ...o, [dim]: [from[0] * damp, from[1] * damp] }));
      if (k < 1) rafRef.current = requestAnimationFrame(tick);
      else setOffsets((o) => ({ ...o, [dim]: [0, 0] }));
    };
    rafRef.current = requestAnimationFrame(tick);
  };

  useEffect(() => {
    if (!dragDim) return;
    const move = (e) => {
      const v = toView(e.clientX, e.clientY);
      const s = dragStart.current;
      if (!v || !s) return;
      let dx = s.off[0] + (v[0] - s.at[0]);
      let dy = s.off[1] + (v[1] - s.at[1]);
      const len = Math.hypot(dx, dy);
      if (len > MAX_DRAG) {
        dx = (dx / len) * MAX_DRAG;
        dy = (dy / len) * MAX_DRAG;
      }
      setOffsets((o) => ({ ...o, [dragDim]: [dx, dy] }));
    };
    const up = () => {
      const d = dragDim;
      const from = offsets[d] || [0, 0];
      dragStart.current = null;
      setDragDim(null);
      springBack(d, from);
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
    window.addEventListener("pointercancel", up);
    return () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
      window.removeEventListener("pointercancel", up);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dragDim]);

  useEffect(() => () => {
    cancelAnimationFrame(rafRef.current);
    clearTimeout(tipTimer.current);
  }, []);

  // 浮层的冷却：划过 140ms 才出现，移开 90ms 才消失，快速扫过不会一串闪
  const showTip = (d) => {
    setHover(d);
    clearTimeout(tipTimer.current);
    tipTimer.current = setTimeout(() => setTipDim(d), 140);
  };
  const hideTip = () => {
    setHover(null);
    clearTimeout(tipTimer.current);
    tipTimer.current = setTimeout(() => setTipDim(null), 90);
  };

  return (
    <div className={`radar${hover || dragDim ? " is-hot" : ""}`}>
      <div className="radar__chart">
        <svg ref={svgRef} viewBox={`${-PAD} 0 ${VW} 300`} role="img" aria-label="六个维度的得分雷达图">
          {/* A 主题：四级实线六边形（B 主题里由下面的点阵环取代） */}
          {RING_KS.map((k) => (
            <polygon key={k} className="radar__grid" points={DIM_ORDER.map((_, i) => pt(i, k).join(",")).join(" ")} />
          ))}
          {/* B 主题：点阵环 */}
          <g className="radar__rings" aria-hidden="true">
            {RING_DOTS.map((dots, r) =>
              dots.map(([x, y], j) => (
                <circle key={`${r}-${j}`} className={`radar__dot is-r${r + 1}`} cx={x} cy={y} r={0.85} />
              ))
            )}
          </g>
          {/* 轴：A 实线 / B 虚线（stroke-dasharray 在 Radar.css 里） */}
          {DIM_ORDER.map((d, i) => {
            const [x, y] = pt(i, 1);
            return <line key={d} className="radar__axis" x1={C} y1={C} x2={x} y2={y} />;
          })}
          <motion.g
            style={{ transformOrigin: `${C}px ${C}px` }}
            initial={reduce ? { opacity: 0 } : { scale: 0, opacity: 0 }}
            whileInView={{ scale: 1, opacity: 1 }}
            viewport={{ once: true, amount: 0.05 }}   // 0.5 太严：手机上雷达图只露出一角时永远不触发
            transition={{ duration: DUR.enter + 0.3, ease: EASE.spring, opacity: { duration: DUR.state } }}
          >
            {/* A 主题：半透明数据面 */}
            <polygon className="radar__area" points={poly} />
            {/* B 主题：点云（每档一条 path，几百个 2px 方块） */}
            <g className="radar__cloud" aria-hidden="true">
              {cloud.map((d, i) =>
                d ? <path key={i} className={`radar__cloud-lv lv-${i + 1}`} d={d} /> : null
              )}
            </g>
            {/* B 主题：1px 折线勾边 */}
            <polygon className="radar__edge" points={poly} />
            {DIM_ORDER.map((d, i) => {
              const [x, y] = pts[i];
              const hot = hover === d || dragDim === d;
              const g = gradeOf(dims[d], grades);
              const side = hot ? 6 : 4; // B 主题的顶点小方块（4px，hover 6px）
              return (
                <g key={d}>
                  {/* A 主题：小圆点 */}
                  <circle className={`radar__pt g-${g}`} cx={x} cy={y} r={hot ? 5 : 3.5} />
                  {/* B 主题：语义色小方块 */}
                  <rect className={`radar__node g-${g}`} x={x - side / 2} y={y - side / 2} width={side} height={side} />
                  {/* 透明抓手：比可见的点大一圈，好点好拖 */}
                  <circle className="radar__grab" cx={x} cy={y} r={15} fill="transparent" onPointerDown={(e) => onDown(d, e)} />
                </g>
              );
            })}
          </motion.g>
        </svg>
        {/* B 主题：扇形扫描头（screen 混合，扫过的点云会被提亮；reduced-motion 下不出现） */}
        <div className="radar__beam" aria-hidden="true" />
        {DIM_ORDER.map((d, i) => {
          const [x, y] = pt(i, 1.24);
          return (
            <button
              key={d}
              type="button"
              className={`radar__label ${hover === d ? "is-on" : ""}`}
              style={{ left: `${((x + PAD) / VW) * 100}%`, top: `${(y / 300) * 100}%` }}
              onMouseEnter={() => showTip(d)}
              onMouseLeave={hideTip}
              onFocus={() => showTip(d)}
              onBlur={hideTip}
            >
              {dimMeta[d]?.name_zh || d}
              <b>{dims[d]}</b>
            </button>
          );
        })}
        {/* mode="wait" + key 变化：从「隐私收集」划到「数据共享」时，旧浮层先淡出、新的再淡入，
            能看出是「换了一条」而不是同一块内容突变 */}
        <AnimatePresence mode="wait">
          {tipDim && (
            <div className="radar__tip-anchor" key={tipDim}>
              <motion.div
                className="radar__tip"
                role="tooltip"
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -4, transition: { duration: reduce ? 0 : 0.12 } }}
                transition={{ duration: reduce ? 0 : 0.18, ease: EASE.out }}
              >
                <div className="meta">{dimMeta[tipDim]?.name_en}</div>
                {(tagsByDim[tipDim] || []).length ? (
                  <ul>
                    {tagsByDim[tipDim].map((t) => (
                      <li key={t.id} className={`c-${t.cls}`}>
                        {t.name}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p>这一维没有命中标签</p>
                )}
              </motion.div>
            </div>
          )}
        </AnimatePresence>
      </div>

      <ul className="dimbars">
        {DIM_ORDER.map((d, i) => {
          const g = gradeOf(dims[d], grades);
          const lit = Math.max(0, Math.min(SEGS, Math.round((dims[d] ?? 0) / (100 / SEGS))));
          return (
            <li key={d} className={`dimbar ${hover === d ? "is-on" : ""}`} onMouseEnter={() => showTip(d)} onMouseLeave={hideTip}>
              <span className="dimbar__name">{dimMeta[d]?.name_zh}</span>
              <span className="dimbar__track">
                {/* 用 animate 而不是 whileInView：手机上这几条在首屏下方，
                    永远不进视口 → whileInView 不触发 → scaleX 一直 0，条是空的。 */}
                <motion.span
                  className={`dimbar__fill bg-${g}`}
                  initial={{ scaleX: reduce ? 1 : 0 }}
                  animate={{ scaleX: (dims[d] ?? 0) / 100 }}
                  transition={{ duration: 0.9, delay: 0.1 + i * 0.06, ease: EASE.tail }}
                />
                {/* B 主题：20 段小方块，按得分亮起 lit/20 段（A 主题隐藏） */}
                <span className="dimbar__segs" data-grade={g} aria-hidden="true">
                  {Array.from({ length: SEGS }, (_, k) => (
                    <i key={k} className={k < lit ? "is-on" : undefined} style={{ "--k": k }} />
                  ))}
                </span>
              </span>
              <span className="dimbar__val">
                <b>{dims[d]}</b>
                <i className={`gradechip c-g-${g}`}>{g}</i>
              </span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}