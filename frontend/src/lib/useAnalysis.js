import { useEffect, useReducer, useRef } from "react";
import { openDemo, openSSE, pace } from "./stream.js";

// 四段轨道 ← 后端七个阶段
export const RAIL = [
  { key: "find", label: "找到网站", stages: ["resolve"] },
  { key: "dig", label: "翻找条款", stages: ["discover", "fetch", "extract"] },
  { key: "read", label: "逐条阅读", stages: ["analyze"] },
  { key: "stamp", label: "打分盖章", stages: ["score", "done"] },
];
export const railIndex = (stage) => Math.max(0, RAIL.findIndex((r) => r.stages.includes(stage)));

const init = { stage: null, message: "", found: null, clauses: null, progress: 0, docs: [], tags: [], result: null, error: null };

function reducer(s, [ev, d]) {
  switch (ev) {
    case "reset":
      return init;
    case "stage":
      return {
        ...s,
        // 后端在缓存命中时也会回到 analyze，轨道只前进不后退
        stage: s.stage && railIndex(d.stage) < railIndex(s.stage) ? s.stage : d.stage,
        message: d.message || s.message,
        found: d.found ?? s.found,
        clauses: d.clauses ?? s.clauses,
        progress: d.progress ?? s.progress,
      };
    case "document":
      return { ...s, docs: [...s.docs, d] };
    case "tag":
      return s.tags.some((t) => t.id === d.id) ? s : { ...s, tags: [...s.tags, d] };
    case "result":
      return { ...s, stage: "done", result: d };
    case "error":
      return { ...s, error: d };
    default:
      return s;
  }
}

// source: {kind:"sse", q} | {kind:"demo", name} | null
export function useAnalysis(source, taxonomy) {
  const [state, dispatch] = useReducer(reducer, init);
  const stopRef = useRef(() => {});
  const id = source ? `${source.kind}:${source.q || source.name}:${source.nonce || 0}` : null;

  useEffect(() => {
    dispatch(["reset"]);
    if (!source || !taxonomy) return;
    const pacer = pace((ev, data) => dispatch([ev, data]));
    const close =
      source.kind === "demo"
        ? openDemo(source.name, (ev, data) => pacer.push(ev, data), taxonomy)
        : openSSE(source.q, (ev, data) => pacer.push(ev, data));
    stopRef.current = () => {
      close();
      pacer.close();
    };
    return () => stopRef.current();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id, !!taxonomy]);

  return { state, cancel: () => stopRef.current() };
}
