import { useEffect, useRef, useState } from "react";
import { useReducedMotion } from "motion/react";
import { DUR } from "../lib/motion.js";

// 全站唯一的数字滚动。长尾曲线（只给填充/进度语义）。
// 目标值变化时从当前显示值继续滚，不从 0 重来——等待态累计分钟数会多次变化。
const tail = (t) => {
  // cubic-bezier(.22,.61,.12,1) 的近似：用 1-(1-t)^3.4 拟合，尾段更长
  return 1 - Math.pow(1 - t, 3.4);
};

export default function CountUp({ value, duration = 1.1, delay = 0, format = (n) => n, className }) {
  const reduce = useReducedMotion();
  const [shown, setShown] = useState(reduce ? value : 0);
  const fromRef = useRef(reduce ? value : 0);
  const shownRef = useRef(shown);
  shownRef.current = shown;

  useEffect(() => {
    if (reduce) {
      setShown(value);
      return;
    }
    const from = shownRef.current;
    fromRef.current = from;
    let raf;
    let start;
    const tick = (now) => {
      if (start == null) start = now + delay * 1000;
      const t = Math.min(1, Math.max(0, (now - start) / (duration * 1000)));
      setShown(Math.round(from + (value - from) * tail(t)));
      if (t < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [value, reduce, duration, delay]);

  return (
    <span className={className} aria-label={String(format(value))}>
      <span aria-hidden="true">{format(shown)}</span>
    </span>
  );
}

CountUp.DUR = DUR;
