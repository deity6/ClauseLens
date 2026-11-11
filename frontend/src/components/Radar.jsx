import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { DIM_ORDER, gradeOf } from "../lib/taxonomy.js";
import { DUR, EASE } from "../lib/motion.js";

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
    <div className="radar">
      <div className="radar__chart">
        <svg ref={svgRef} viewBox={`${-PAD} 0 ${VW} 300`} role="img" aria-label="六个维度的得分雷达图">
          {[0.25, 0.5, 0.75, 1].map((k) => (
            <polygon key={k} className="radar__grid" points={DIM_ORDER.map((_, i) => pt(i, k).join(",")).join(" ")} />
          ))}
          {DIM_ORDER.map((d, i) => {
            const [x, y] = pt(i, 1);
            return <line key={d} className="radar__axis" x1={C} y1={C} x2={x} y2={y} />;
          })}
          <motion.g
            style={{ transformOrigin: `${C}px ${C}px` }}
            initial={reduce ? { opacity: 0 } : { scale: 0, opacity: 0 }}
            whileInView={{ scale: 1, opacity: 1 }}
            viewport={{ once: true, amount: 0.5 }}
            transition={{ duration: DUR.enter + 0.3, ease: EASE.spring, opacity: { duration: DUR.state } }}
          >
            <polygon className="radar__area" points={poly} />
            {DIM_ORDER.map((d, i) => {
              const [x, y] = pts[i];
              const hot = hover === d || dragDim === d;
              return (
                <g key={d}>
                  <circle className={`radar__pt g-${gradeOf(dims[d], grades)}`} cx={x} cy={y} r={hot ? 5 : 3.5} />
                  {/* 透明抓手：比可见的点大一圈，好点好拖 */}
                  <circle className="radar__grab" cx={x} cy={y} r={15} fill="transparent" onPointerDown={(e) => onDown(d, e)} />
                </g>
              );
            })}
          </motion.g>
        </svg>
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
          return (
            <li key={d} className={`dimbar ${hover === d ? "is-on" : ""}`} onMouseEnter={() => showTip(d)} onMouseLeave={hideTip}>
              <span className="dimbar__name">{dimMeta[d]?.name_zh}</span>
              <span className="dimbar__track">
                <motion.span
                  className={`dimbar__fill bg-${g}`}
                  initial={{ scaleX: reduce ? 1 : 0 }}
                  whileInView={{ scaleX: (dims[d] ?? 0) / 100 }}
                  viewport={{ once: true }}
                  transition={{ duration: 0.9, delay: 0.1 + i * 0.06, ease: EASE.tail }}
                />
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
