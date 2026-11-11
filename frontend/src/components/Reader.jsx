import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { DUR, EASE } from "../lib/motion.js";
import { POLARITY } from "../lib/taxonomy.js";
import { fmtChars } from "../lib/format.js";
import { IconChevron } from "./Icons.jsx";

// 展开/收起的动画时长（只属于开合）。滑动是另一套：页面平滑滚动自己的时长，两件事不共用一个 duration。
const OPEN_MS = 640; // 面板高度动画时长（毫秒）。比原来 320 慢一倍，展开像「卷轴慢慢摊开」

// 自己写缓动滚动：浏览器原生 behavior:"smooth" 固定 300–400ms，控制不了，
// 长距离跳转看起来像「瞬间闪过去」。cubic 的 in-out 让起步和收尾都有缓冲。
// smootherstep（Perlin 的六次多项式）：两端速度为 0、中段几乎匀速。
// 比原来的 cubic in-out 起步柔和得多，长距离滚动不会「窜出去」。
const easeInOut = (t) => t * t * t * (t * (t * 6 - 15) + 10);
// 每个滚动目标各记各的 rAF：一次跳转里要同时滚「内层正文框」和「页面」，
// 共用一个全局 id 的话，第二次会把第一次取消掉（表现为原文框永远停在 0）。
const scrollRafMap = new WeakMap();
function slowScroll(target, top, duration = 900) {
  const prev = scrollRafMap.get(target);
  if (prev) cancelAnimationFrame(prev);
  const isWin = target === window;
  const from = isWin ? window.scrollY : target.scrollTop;
  const to = Math.max(0, top);
  if (Math.abs(to - from) < 1) return;
  const t0 = performance.now();
  const step = (t) => {
    const k = Math.min(1, (t - t0) / duration);
    const y = from + (to - from) * easeInOut(k);
    if (isWin) window.scrollTo(0, y);
    else target.scrollTop = y;
    if (k < 1) scrollRafMap.set(target, requestAnimationFrame(step));
    else scrollRafMap.delete(target);
  };
  scrollRafMap.set(target, requestAnimationFrame(step));
}

// 滚动落点要避开固顶栏。顶栏现在是随页面滚的，以后改成 sticky/fixed 这里会自动算进去。
function topGap() {
  const bar = document.querySelector(".topbar");
  const cs = bar && getComputedStyle(bar);
  const pinned = cs && (cs.position === "fixed" || cs.position === "sticky");
  return (pinned ? bar.getBoundingClientRect().height : 0) + 24;
}

// 把一份原文切成「普通 / 证据」片段。重叠的证据合并，保留第一个命中标签的极性作配色。
function segment(text, spans) {
  const sorted = [...spans].sort((a, b) => a.start - b.start);
  const merged = [];
  for (const s of sorted) {
    const last = merged.at(-1);
    if (last && s.start <= last.end) {
      last.end = Math.max(last.end, s.end);
      last.tags.push(...s.tags);
    } else merged.push({ ...s, tags: [...s.tags] });
  }
  const out = [];
  let at = 0;
  for (const m of merged) {
    if (m.start > at) out.push({ text: text.slice(at, m.start) });
    out.push({ text: text.slice(m.start, m.end), mark: m });
    at = m.end;
  }
  if (at < text.length) out.push({ text: text.slice(at) });
  return out;
}

export default function Reader({ docs, texts, tags, taxonomy, focus, open, setOpen }) {
  const reduce = useReducedMotion();
  const [active, setActive] = useState(docs[0]?.id);
  // 面板高度动画是否已经走完。量位置必须等它结束，否则展开动画会把落点一路带偏。
  const [expanded, setExpanded] = useState(false);
  // 等着落地的那次「在原文中查看」。滚动只认它，不认 open。
  const [pending, setPending] = useState(null);
  const rootRef = useRef(null);
  const bodyRef = useRef(null);
  const readAt = useRef(null); // 收起前读到哪：{doc, top}
  const restoreTo = useRef(null); // 本次展开要放回的 scrollTop
  const landed = useRef(0);
  const innerTimer = useRef(0); // 已经处理过的请求序号

  const spans = useMemo(() => {
    const by = {};
    for (const t of tags) {
      const pol = taxonomy.byId[t.id]?.polarity || "neutral";
      for (const e of t.evidence || []) (by[e.doc] ||= []).push({ start: e.start, end: e.end, cls: POLARITY[pol]?.cls, tags: [taxonomy.byId[t.id]?.name_zh || t.id] });
    }
    if (focus) (by[focus.doc] ||= []).push({ start: focus.start, end: focus.end, cls: "focus", tags: [] });
    return by;
  }, [tags, taxonomy, focus]);

  const text = texts?.[active] ?? "";
  const segs = useMemo(() => segment(text, spans[active] || []), [text, spans, active]);

  // 真正动的那一下：内层正文框先把证据放到上三分之一，页面再滑过去把它居中。
  const land = useCallback(
    (req) => {
      const box = bodyRef.current;
      const el = box?.querySelector(`[data-s="${req.start}"]`) || box?.querySelector("mark.is-target");
      if (!box || !el) {
        // 没有可定位的高亮区间（偏移缺失）：至少把原文区带到眼前
        const r = rootRef.current?.getBoundingClientRect();
        if (r) {
          const top = window.scrollY + r.top - (window.innerHeight - r.height) / 2;
          if (reduce) window.scrollTo(0, top);
          else slowScroll(window, top, 700);
        }
        return;
      }

      // 用 offsetTop：.reader__body 是 offsetParent，这个值在它内部恒等于「内容中的位置」，
      // 不受当前 scrollTop 影响。（改用 getBoundingClientRect 反而量出 0——元素在渲染完成前
      // 拿不到真实位置。）落点从原来的「上 1/3」改成**垂直居中**。
      const boxRect0 = box.getBoundingClientRect();
      const maxTop = Math.max(0, box.scrollHeight - box.clientHeight);
      const elH = el.offsetHeight || 0;
      const target = Math.min(Math.max(0, el.offsetTop - (box.clientHeight - elH) / 2), maxTop);
      // 第二段刻意延后：第一段（页面滚到「05 · SOURCE」）刚停下就立刻滚内层的话，
      // 两层滚动会糊在一起，用户看不到「原文里的文本在滚」。先让他看见区块，再滚里面。
      clearTimeout(innerTimer.current);
      if (reduce) box.scrollTop = target;
      else innerTimer.current = setTimeout(() => slowScroll(box, target, 1900), 1500);
      // 跳转本身就是一次「用户操作」：把阅读进度认到这条上，之后收起再展开回到这里
      readAt.current = { doc: req.doc, top: target };
      restoreTo.current = null;

      // 页面落点：内层滚动**不会**改变证据在页面里的位置（框没动，动的只是框里的内容），
      // 所以这里不能减去内层的位移——之前那一版减了 shift，算出负数再被 clamp 到 0，
      // 于是页面一路滚回顶部（就是你看到「往上跑」的原因）。
      const boxPageTop = window.scrollY + boxRect0.top;        // 原文框在页面中的顶部
      const evPageY = boxPageTop + el.offsetTop + elH / 2;     // 证据中心在页面中的位置
      const gap = topGap();
      const want = gap + (window.innerHeight - gap) / 2;       // 视口可见区的中心（扣掉固顶栏）
      const maxY = document.documentElement.scrollHeight - window.innerHeight;
      const pageTop = Math.min(Math.max(evPageY - want, 0), Math.max(maxY, 0));
      if (reduce) window.scrollTo(0, pageTop);
      else slowScroll(window, pageTop, 1400);

      // 闪烁交给 CSS：眼睛跟过去之后，告诉你就是这一句
      el.classList.remove("is-flash");
      void el.offsetWidth;
      el.classList.add("is-flash");
    },
    [reduce]
  );

  // ① 新请求到达：记下来，切到它所在的文档。
  //    先把「05 · SOURCE 原文」这一块整体带到视野里（让用户看见它展开），
  //    具体滚到某一条等展开完成之后（见 ④ land）。
  useEffect(() => {
    if (!focus) return;
    setPending(focus);
    setActive(focus.doc);
    const r = rootRef.current?.getBoundingClientRect();
    if (r) {
      const top = Math.max(0, window.scrollY + r.top - topGap() - 12);
      if (reduce) window.scrollTo(0, top);
      else slowScroll(window, top, 1100);
    }
  }, [focus]);

  // ② 开合只决定「展开完成没有」：关了就清零，开了等高度动画走完。
  //    减少动态效果时没有动画可等，直接算完成。
  useEffect(() => {
    if (!open) {
      setExpanded(false);
      return;
    }
    if (reduce) {
      setExpanded(true);
      return;
    }
    const t = setTimeout(() => setExpanded(true), OPEN_MS + 80);
    return () => clearTimeout(t);
  }, [open, reduce]);

  // ③ 收起再展开：回到上次读到的地方（有跳转请求时以请求为准）。
  //    只认切回「展开」时记下的那个位置，之后用户切 tab 不会被拽回来。
  useEffect(() => {
    if (!open) return;
    const top = restoreTo.current;
    if (top == null) return;
    const memo = readAt.current;
    if (memo && memo.doc !== active) {
      setActive(memo.doc); // 先切回上次那份文档，下一轮再放位置
      return;
    }
    restoreTo.current = null;
    if (bodyRef.current) bodyRef.current.scrollTop = top;
  }, [open, active]);

  // ④ 执行器：请求 + 面板展开完成 + 正文已切到目标文档，三件齐了才动，一次只动一次。
  useEffect(() => {
    if (!pending || !open || !expanded || active !== pending.doc) return;
    if (landed.current === pending.seq) return;
    landed.current = pending.seq;
    land(pending);
  }, [pending, open, expanded, active, land]);

  // ⑤ 阅读进度：谁最后动了正文框，进度就归谁 —— 用户手动滚动也会实时记下来
  //    （原来只在收起时记一次，于是「点了跳转、再收起」会记成跳转后的位置，而手动滚过的又会被覆盖）
  useEffect(() => {
    const box = bodyRef.current;
    if (!box || !open) return;
    const onScroll = () => {
      readAt.current = { doc: active, top: box.scrollTop };
    };
    box.addEventListener("scroll", onScroll, { passive: true });
    return () => box.removeEventListener("scroll", onScroll);
  }, [open, active]);

  // ⑥ 手动展开后，正文框要是在屏幕外（收起时页面被浏览器夹过），把它框回视野中间。
  //    已经完整看得见就一动不动 —— 展开本身不该顺带推页面。
  useEffect(() => {
    if (!open || !expanded || pending) return;
    const box = bodyRef.current;
    if (!box) return;
    const r = box.getBoundingClientRect();
    if (r.top >= topGap() && r.bottom <= window.innerHeight) return;
    const boxTop = window.scrollY + r.top - (window.innerHeight - r.height) / 2;
    if (reduce) window.scrollTo(0, boxTop);
    else slowScroll(window, boxTop, 760);
  }, [open, expanded, pending, reduce]);

  if (!texts) return null;
  const doc = docs.find((d) => d.id === active);
  const isTarget = (m) => focus && active === focus.doc && m.start <= focus.start && m.end >= focus.end;

  // 收起：记下读到哪一段，并把这次跳转收尾，免得下次展开又被它带着滚一次
  const toggle = () => {
    if (open) {
      readAt.current = { doc: active, top: bodyRef.current?.scrollTop ?? 0 };
      restoreTo.current = null;
      setPending(null);
      setOpen(false);
      return;
    }
    const memo = readAt.current;
    restoreTo.current = memo ? memo.top : null;
    setOpen(true);
  };

  return (
    <div className={`reader ${open ? "is-open" : ""}`} ref={rootRef}>
      <button type="button" className="reader__toggle" aria-expanded={open} onClick={toggle}>
        <span>{open ? "收起原文" : "展开原文"}</span>
        <span className="meta">{docs.length} DOCS · 标签证据已在原文中高亮</span>
        <IconChevron className="reader__chev" />
      </button>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            className="reader__panel"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: reduce ? 0 : OPEN_MS / 1000, ease: [0.22, 0.61, 0.36, 1] }}
          >
            {/* 内容比容器晚一点淡入：容器先把高度摊开，文字再浮现，像卷轴展开后墨迹显出来 */}
            <motion.div
              className="reader__inner"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 6, transition: { duration: reduce ? 0 : 0.18 } }}
              transition={{ duration: reduce ? 0 : 0.52, delay: reduce ? 0 : 0.18, ease: [0.22, 0.61, 0.36, 1] }}
            >
            <div className="reader__tabs" role="tablist">
              {docs.map((d) => (
                <button key={d.id} role="tab" type="button" aria-selected={d.id === active} className={`rtab ${d.id === active ? "is-on" : ""}`} onClick={() => setActive(d.id)}>
                  {d.title}
                  <span className="meta">{(spans[d.id] || []).length}</span>
                </button>
              ))}
            </div>
            <div className="reader__src meta">
              {fmtChars(doc?.chars)} ·{" "}
              <a href={doc?.url} target="_blank" rel="noreferrer noopener">
                {doc?.url}
              </a>
            </div>
            <div className="reader__body" ref={bodyRef} tabIndex={0} role="tabpanel" aria-label={doc?.title}>
              {segs.map((s, i) =>
                s.mark ? (
                  <mark key={i} data-s={s.mark.start} className={`hl hl--${s.mark.cls} ${isTarget(s.mark) ? "is-target" : ""}`} title={s.mark.tags.join("、")}>
                    {s.text}
                  </mark>
                ) : (
                  <span key={i}>{s.text}</span>
                )
              )}
            </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
