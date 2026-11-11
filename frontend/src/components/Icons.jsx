import { PolarityIcon as IconSetPolarity } from "./IconSet.jsx";

// 线性图标，1.6 描边，跟随 currentColor。好坏除了颜色还靠形状区分（✓ / ! / ·）。
// 这里全部保持原样（= IconSet 的 A 套）；语义图标另有一层可换风格的实现，见 IconSet.jsx。
const S = (p) => ({ width: 18, height: 18, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: 1.6, strokeLinecap: "round", strokeLinejoin: "round", "aria-hidden": true, ...p });

export const IconLens = (p) => (
  <svg {...S(p)}>
    <circle cx="10.5" cy="10.5" r="6.5" />
    <path d="M15.5 15.5 21 21" />
    <path d="M8 9.5h5M8 12h3.5" />
  </svg>
);
export const IconArrow = (p) => (
  <svg {...S(p)}>
    <path d="M5 12h14M13 6l6 6-6 6" />
  </svg>
);
export const IconCheck = (p) => (
  <svg {...S(p)}>
    <path d="M5 12.5 10 17 19 7.5" />
  </svg>
);
export const IconCross = (p) => (
  <svg {...S(p)}>
    <path d="M6.5 6.5l11 11M17.5 6.5l-11 11" />
  </svg>
);
export const IconAlert = (p) => (
  <svg {...S(p)}>
    <path d="M12 3.5 21.5 20h-19z" />
    <path d="M12 10v4.5M12 17.2v.3" />
  </svg>
);
export const IconDot = (p) => (
  <svg {...S(p)}>
    <circle cx="12" cy="12" r="4" />
  </svg>
);
export const IconQuestion = (p) => (
  <svg {...S(p)}>
    <circle cx="12" cy="12" r="8.5" />
    <path d="M9.6 9.6a2.5 2.5 0 1 1 3.4 2.3c-.6.3-1 .8-1 1.5v.4M12 16.8v.2" />
  </svg>
);
export const IconDoc = (p) => (
  <svg {...S(p)}>
    <path d="M6 3h8l4 4v14H6z" />
    <path d="M14 3v4h4M9 12h6M9 15.5h6M9 9h2" />
  </svg>
);
export const IconSearchDoc = (p) => (
  <svg {...S(p)}>
    <path d="M5 3h8l4 4v5" />
    <path d="M5 3v18h6" />
    <circle cx="16" cy="16.5" r="3" />
    <path d="m18.2 18.7 2.3 2.3" />
  </svg>
);
export const IconRead = (p) => (
  <svg {...S(p)}>
    <path d="M3 5.5c3-1 6-1 9 1 3-2 6-2 9-1V19c-3-1-6-1-9 1-3-2-6-2-9-1z" />
    <path d="M12 6.5V20" />
  </svg>
);
export const IconStamp = (p) => (
  <svg {...S(p)}>
    <path d="M9 3.5h6l-1 7h-4z" />
    <path d="M4 14.5h16v3H4zM6 20.5h12" />
  </svg>
);
export const IconThumb = ({ down, ...p }) => (
  <svg {...S(p)} style={down ? { transform: "scaleY(-1)" } : undefined}>
    <path d="M7 10.5v9H4v-9zM7 10.5 11 3c1.6 0 2.5 1 2.2 2.6L12.6 9H19a1.8 1.8 0 0 1 1.8 2.1l-1.2 6.8A2 2 0 0 1 17.6 19.5H7" />
  </svg>
);
export const IconLink = (p) => (
  <svg {...S(p)}>
    <path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1" />
    <path d="M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1" />
  </svg>
);
export const IconChevron = (p) => (
  <svg {...S(p)}>
    <path d="m6 9 6 6 6-6" />
  </svg>
);

// 语义图标转发到 IconSet：默认仍是上面这套线性图标，只是多了一个可选的 style="A|B|C|D"
// 和 <html data-icon-style> 的全局开关（设计调试面板用；正常访问时 dataset 为空，等价于 A）。
export function PolarityIcon({ polarity, style, ...p }) {
  return <IconSetPolarity polarity={polarity} style={style} {...p} />;
}
