// 四套语义图标：同一 24×24 网格、同一套语义槽位（警告 / 好 / 中性 / 待确认），只换手感。
//   A 线性（现有基准）· B 实心填充 · C 手绘抖动 · D 印刷双线
// 颜色一律走 currentColor，形状负责语义、颜色负责极性，和 Icons.jsx 的分工一致。
//
// 用法：
//   <PolarityIcon polarity="bad" width={15} height={15} />       风格跟随 <html data-icon-style="a|b|c|d">
//   <PolarityIcon polarity="bad" style="B" width={15} height={15} />  显式指定（style 传 A–D 时当风格 id）
//   <IconWarning style="C" /> / <IconGood style="D" />           单拿某一个
//
// 这里同时导出面板用的极简全局设置仓库（写 <html> 的 data-* + 订阅通知），
// Stamp.jsx 也从这里取印章风格，避免多一个文件。
import { useSyncExternalStore } from "react";

const VIEW = "0 0 24 24";

// 丢掉值为 undefined 的键：调用方写 width={undefined} 时不会把默认尺寸顶掉
function clean(o) {
  const out = {};
  for (const k in o) if (o[k] !== undefined) out[k] = o[k];
  return out;
}

const BASE = { width: 18, height: 18, viewBox: VIEW, "aria-hidden": true, focusable: "false" };

/* ─────────────────────────── A · 线性（现有基准） ─────────────────────────── */
const lineA = (p) => clean({ ...BASE, fill: "none", stroke: "currentColor", strokeWidth: 1.6, strokeLinecap: "round", strokeLinejoin: "round", ...p });

export const AlertLine = (p) => (
  <svg {...lineA(p)}>
    <path d="M12 3.5 21.5 20h-19z" />
    <path d="M12 10v4.5M12 17.2v.3" />
  </svg>
);
export const CheckLine = (p) => (
  <svg {...lineA(p)}>
    <path d="M5 12.5 10 17 19 7.5" />
  </svg>
);
export const DotLine = (p) => (
  <svg {...lineA(p)}>
    <circle cx="12" cy="12" r="4" />
  </svg>
);
export const QuestionLine = (p) => (
  <svg {...lineA(p)}>
    <circle cx="12" cy="12" r="8.5" />
    <path d="M9.6 9.6a2.5 2.5 0 1 1 3.4 2.3c-.6.3-1 .8-1 1.5v.4M12 16.8v.2" />
  </svg>
);

/* ─────────────────────────── B · 实心填充 ───────────────────────────
   剪影实心，内部记号挖成纸色（--paper）：深色主题下挖空变深，不靠白色硬撑。
   轮廓比 A 略小一圈，好让实心面积不至于比线性重一档。 */
const solid = (p) => clean({ ...BASE, fill: "currentColor", stroke: "none", ...p });
const CUT = { fill: "none", strokeLinecap: "round", strokeLinejoin: "round", style: { stroke: "var(--paper, #fff)" } };

export const AlertSolid = (p) => (
  <svg {...solid(p)}>
    <path d="M12 3.7 20.9 19.5H3.1z" stroke="currentColor" strokeWidth="1.2" strokeLinejoin="round" />
    <path d="M12 9.3v4.1" strokeWidth="2.3" {...CUT} />
    <path d="M12 16.6v.2" strokeWidth="2.8" {...CUT} />
  </svg>
);
export const CheckSolid = (p) => (
  <svg {...solid(p)}>
    <circle cx="12" cy="12" r="8.5" />
    <path d="M7.7 12.2 10.7 15.1 16.4 9.1" strokeWidth="2.2" {...CUT} />
  </svg>
);
export const DotSolid = (p) => (
  <svg {...solid(p)}>
    <circle cx="12" cy="12" r="4.5" />
  </svg>
);
export const QuestionSolid = (p) => (
  <svg {...solid(p)}>
    <circle cx="12" cy="12" r="8.5" />
    <path d="M9.5 9.4a2.7 2.7 0 1 1 3.7 2.5c-.7.35-1.1.9-1.1 1.6v.35" strokeWidth="2.1" {...CUT} />
    <path d="M12 17.3v.2" strokeWidth="2.4" {...CUT} />
  </svg>
);

/* ─────────────────────────── C · 手绘 / 不规则 ───────────────────────────
   不画完整几何形：三角形是三笔（两腰粗细不同、顶点没接上、底线两头出头），
   勾是一笔画歪的、还叠了一道更细的复描（墨没盖住），中性是一个按下去的墨点。
   整体再转 -2°~-4°，像有人顺手在纸上标了一下。 */
const hand = (p) => clean({ ...BASE, fill: "none", stroke: "currentColor", strokeWidth: 1.75, strokeLinecap: "round", strokeLinejoin: "round", ...p });

export const AlertHand = (p) => (
  <svg {...hand(p)}>
    <g transform="rotate(-4 12 12)">
      {/* 两腰各是一笔、笔尖没接上（顶点留个缺口），粗细也不同（1.95 vs 1.3）；
          底线单独一笔、两端都出头，中间还微微塌下去——手画就是凑不齐。 */}
      <path d="M4.1 19.6c1.7-3.9 5.3-11 7.3-14.1" strokeWidth="1.95" />
      <path d="M12.4 5.2c2.2 4.4 5.2 10.5 7.4 14.3" strokeWidth="1.3" />
      <path d="M3.1 19.9c5.9-.9 11.3-.7 17.8-.2" strokeWidth="1.6" />
      <path d="M12.2 10c.1 1.5 0 2.8-.1 4.2" strokeWidth="2.05" />
      <ellipse cx="12.1" cy="17.1" rx="0.85" ry="0.75" fill="currentColor" stroke="none" />
    </g>
  </svg>
);
export const CheckHand = (p) => (
  <svg {...hand(p)}>
    <g transform="rotate(-2 12 12)">
      <path d="M5.2 12.6c1.2.9 2.5 2.3 3.6 4.1 2.8-4.6 5.5-7.7 8.6-10.3" strokeWidth="1.8" />
      <path d="M6.4 13c.9.7 1.8 1.7 2.6 2.8" strokeWidth="0.7" opacity="0.45" />
    </g>
  </svg>
);
export const DotHand = (p) => (
  <svg {...hand(p)}>
    {/* 笔尖顿下去的一坨墨，不是几何圆 */}
    <path d="M12.9 8c2.1.25 3.5 2 3.3 4.1-.2 2.1-2 3.6-4.1 3.4-2.1-.2-3.5-1.9-3.3-4 .15-2 1.9-3.7 4.1-3.5z" fill="currentColor" stroke="none" />
  </svg>
);
export const QuestionHand = (p) => (
  <svg {...hand(p)}>
    <g transform="rotate(-1.5 12 12)">
      {/* 圆没画满：起笔和收笔在一点钟方向差着 1.5 个单位 */}
      <path d="M13.4 3.9c4.3.5 7.6 4.3 7.3 8.6-.3 4.4-4 7.7-8.3 7.5-4.3-.2-7.5-3.9-7.4-8.1.1-4 3.1-7.2 6.9-7.9" />
      <path d="M9.4 9.7c-.2-1.4 1-2.6 2.5-2.6 1.5 0 2.7 1 2.6 2.4-.1 1.3-1.1 1.8-1.9 2.3-.6.4-.9.9-.9 1.6v.3" />
      <path d="M12 16.9v.3" strokeWidth="1.9" />
    </g>
  </svg>
);

/* ─────────────────────────── D · 印刷 / 印章 ───────────────────────────
   双线边框（外粗内细）来自钢印与印刷版：轮廓硬、内线细；勾是对位不准的手写。
   方框负责「盖章」，勾负责「通过」。 */
const print = (p) => clean({ ...BASE, fill: "none", stroke: "currentColor", strokeWidth: 1.7, strokeLinecap: "round", strokeLinejoin: "round", ...p });
const INNER = { strokeWidth: 0.7, opacity: 0.8 };

export const AlertPrint = (p) => (
  <svg {...print(p)}>
    {/* 外圈粗线 + 一圈淡墨（印油洇开），内圈细线离得远一点：小尺寸下才看得出是双线 */}
    <path d="M12 3.4 21.1 19.8H2.9z" strokeWidth="4.6" opacity="0.16" />
    <path d="M12 3.4 21.1 19.8H2.9z" strokeWidth="2.2" strokeLinejoin="miter" />
    <path d="M12 7.9 17.8 17.4H6.2z" strokeWidth="0.9" />
    <path d="M12 10.4v3.3" strokeWidth="1.15" />
    <path d="M12 15.9v.25" strokeWidth="1.45" />
  </svg>
);
export const CheckPrint = (p) => (
  <svg {...print(p)}>
    <rect x="4.8" y="4.8" width="14.4" height="14.4" rx="1" strokeWidth="3.8" opacity="0.14" />
    <rect x="4.8" y="4.8" width="14.4" height="14.4" rx="1" strokeWidth="1.9" />
    <path d="M8 12.3c1.2.8 2.3 2 3.3 3.4 1.7-3 3.4-5.2 5.2-7" strokeWidth="1.55" />
  </svg>
);
export const DotPrint = (p) => (
  <svg {...print(p)}>
    <rect x="4.5" y="4.5" width="15" height="15" rx="2" strokeWidth="1.2" opacity="0.55" />
    <rect x="8.9" y="8.9" width="6.2" height="6.2" rx="0.8" fill="currentColor" stroke="none" />
  </svg>
);
export const QuestionPrint = (p) => (
  <svg {...print(p)}>
    <rect x="3.9" y="3.9" width="16.2" height="16.2" rx="2.2" strokeWidth="1.6" />
    <rect x="6.8" y="6.8" width="10.4" height="10.4" rx="1.2" {...INNER} />
    <path d="M9.6 9.8a2.4 2.4 0 1 1 3.3 2.3c-.6.3-1 .8-1 1.4v.35" strokeWidth="1.15" />
    <path d="M12 16.1v.25" strokeWidth="1.35" />
  </svg>
);

/* ─────────────────────────── 索引 ─────────────────────────── */
export const ICON_STYLES = ["A", "B", "C", "D"];

export const SETS = {
  A: { warning: AlertLine, good: CheckLine, neutral: DotLine, question: QuestionLine },
  B: { warning: AlertSolid, good: CheckSolid, neutral: DotSolid, question: QuestionSolid },
  C: { warning: AlertHand, good: CheckHand, neutral: DotHand, question: QuestionHand },
  D: { warning: AlertPrint, good: CheckPrint, neutral: DotPrint, question: QuestionPrint },
};

export const KIND_LABEL = { warning: "警告", good: "好", neutral: "中性", question: "待确认" };
export const STYLE_LABEL = { A: "线性", B: "实心", C: "手绘", D: "印刷" };

/* ─────────────────────────── 面板设置仓库 ───────────────────────────
   单一真相放在 <html> 的 data-* 上（CSS 与 React 都能读），订阅器只负责叫醒 React。 */
const FALLBACK = { iconStyle: "a", font: "a", stamp: "1" };
const ALLOWED = {
  iconStyle: ["a", "b", "c", "d"],
  font: ["a", "b", "c"],
  stamp: ["1", "2", "3"],
};
const listeners = new Set();

function normalize(key, value) {
  if (value == null) return null;
  const v = String(value).trim().toLowerCase();
  return ALLOWED[key]?.includes(v) ? v : null;
}

export function getDevSetting(key) {
  if (!ALLOWED[key]) return null;
  return normalize(key, document.documentElement.dataset[key]) ?? FALLBACK[key];
}

export function setDevSetting(key, value) {
  const v = normalize(key, value);
  if (!v || !ALLOWED[key]) return v;
  if (document.documentElement.dataset[key] !== v) {
    document.documentElement.dataset[key] = v;
    listeners.forEach((fn) => fn());
  }
  return v;
}

function subscribe(fn) {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

// 也监听 <html> 上的 data-* 被外部直接改（截图脚本 --eval、控制台手改）：
// 直接写 dataset 不会经过 setDevSetting，没有这一层就不会通知 React。
if (typeof MutationObserver !== "undefined" && !globalThis.__clDevObserved) {
  globalThis.__clDevObserved = true;
  new MutationObserver((records) => {
    if (records.some((r) => ["data-icon-style", "data-stamp", "data-font"].includes(r.attributeName))) listeners.forEach((fn) => fn());
  }).observe(document.documentElement, { attributes: true, attributeFilter: ["data-icon-style", "data-stamp", "data-font"] });
}

// 读 <html data-icon-style> / data-stamp；面板一改，用到它的组件立刻重绘
export function useDevSetting(key) {
  return useSyncExternalStore(
    subscribe,
    () => getDevSetting(key),
    () => FALLBACK[key] ?? null,
  );
}

/* ─────────────────────────── 对外语义组件 ─────────────────────────── */
export function kindOfPolarity(polarity) {
  if (polarity === "good") return "good";
  if (polarity === "bad" || polarity === "blocker") return "warning";
  if (polarity === "question" || polarity === "unknown" || polarity === "unclear") return "question";
  return "neutral";
}

export function resolveStyleId(style) {
  if (typeof style === "string" && /^[abcd]$/i.test(style.trim())) return style.trim().toUpperCase();
  return null;
}

function pick(setId, kind, width, height, rest) {
  const Comp = SETS[setId]?.[kind] || SETS.A.neutral;
  const size = {};
  if (width !== undefined) size.width = width;
  if (height !== undefined) size.height = height;
  return <Comp {...size} {...rest} />;
}

export function IconWarning({ style, width, height, ...rest }) {
  const live = useDevSetting("iconStyle");
  return pick(resolveStyleId(style) || live.toUpperCase(), "warning", width, height, rest);
}
export function IconGood({ style, width, height, ...rest }) {
  const live = useDevSetting("iconStyle");
  return pick(resolveStyleId(style) || live.toUpperCase(), "good", width, height, rest);
}
export function IconNeutral({ style, width, height, ...rest }) {
  const live = useDevSetting("iconStyle");
  return pick(resolveStyleId(style) || live.toUpperCase(), "neutral", width, height, rest);
}
export function IconQuestion({ style, width, height, ...rest }) {
  const live = useDevSetting("iconStyle");
  return pick(resolveStyleId(style) || live.toUpperCase(), "question", width, height, rest);
}

// 标签 chip / 分组标题用的就是它：polarity 走语义映射，风格默认跟面板走。
// style 传 A–D 时当风格 id；传对象时当普通 CSS style 往下透传（保持原组件的用法不受影响）。
export function PolarityIcon({ polarity, kind, style, width, height, ...rest }) {
  const live = useDevSetting("iconStyle");
  const forced = resolveStyleId(style);
  const css = !forced && style && typeof style === "object" ? style : undefined;
  return pick(forced || live.toUpperCase(), kind || kindOfPolarity(polarity), width, height, { ...rest, style: css });
}

export default SETS;