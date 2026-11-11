import { motion, useReducedMotion } from "motion/react";
import { DUR, EASE } from "../lib/motion.js";
import { useDevSetting } from "./IconSet.jsx";

// 印章：结果页唯一的强装饰，用等级色，其余地方不再出现大面积语义色。
// 三套形态（由 DevPanel 的 <html data-stamp> 或 variant 参数选）：
//   1 圆形双环：外圈环形文字 + 中央大字母（原有形态，默认）
//   2 方章：中式方形印章，双线方框 + 中央大字母
//   3 双色叠印：两枚章轻微错位叠加，后层走青墨，像印刷套印没对准
// 共同点：入场都是「盖下」——scale 1.3→1 + 旋转回落 + 墨迹扩散。
const RING = "CLAUSELENS · 条款鉴定 · TERMS INSPECTED · ";

function Ring({ grade, ringId }) {
  return (
    <>
      <circle cx="100" cy="100" r="94" fill="none" strokeWidth="5" />
      <circle cx="100" cy="100" r="60" fill="none" strokeWidth="2" />
      <text className="stamp__ring">
        <textPath href={`#${ringId}`} startOffset="0" textLength="458" lengthAdjust="spacing">
          {RING}
        </textPath>
      </text>
      <text x="100" y="101" className="stamp__grade" textAnchor="middle" dominantBaseline="central">
        {grade}
      </text>
    </>
  );
}

export default function Stamp({ grade = "C", size = 168, animate = true, delay = 0.25, variant, onLand }) {
  const reduce = useReducedMotion();
  const live = useDevSetting("stamp");
  const v = ["1", "2", "3"].includes(String(variant)) ? String(variant) : live;
  const play = animate && !reduce;

  const roughId = v === "1" ? "stamp-rough" : `stamp-v${v}-rough`;
  const wearId = v === "1" ? "stamp-wear" : `stamp-v${v}-wear`;
  const speckleId = v === "1" ? "stamp-speckle" : `stamp-v${v}-speckle`;
  const ringAId = v === "1" ? "stamp-ring" : `stamp-v${v}-ring-a`;

  return (
    <div className={`stamp stamp--${grade} stamp--v${v}`} style={{ width: size, height: size }} role="img" aria-label={`等级 ${grade}`}>
      {play && (
        <motion.span
          className="stamp__ink"
          initial={{ scale: 0.6, opacity: 0 }}
          animate={{ scale: [0.6, 1.25, 1.4], opacity: [0, 0.5, 0] }}
          transition={{ duration: DUR.stamp + 0.3, delay: delay + DUR.stamp * 0.55, ease: EASE.out, times: [0, 0.35, 1] }}
        />
      )}
      <motion.svg
        viewBox="0 0 200 200"
        width={size}
        height={size}
        initial={play ? { scale: 1.3, rotate: -22, opacity: 0 } : false}
        animate={{ scale: 1, rotate: -8, opacity: 1 }}
        transition={{ duration: DUR.stamp, delay, ease: EASE.spring, opacity: { duration: DUR.stamp * 0.4, delay } }}
        onAnimationComplete={() => onLand && onLand()}
      >
        <defs>
          <path id={ringAId} d="M100,100 m-74,0 a74,74 0 1,1 148,0 a74,74 0 1,1 -148,0" />
          {v === "3" && <path id="stamp-v3-ring-b" d="M100,100 m-72,0 a72,72 0 1,1 144,0 a72,72 0 1,1 -144,0" />}
          <filter id={roughId} x="-5%" y="-5%" width="110%" height="110%">
            <feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="2" seed={v === "1" ? "7" : v === "2" ? "11" : "5"} result="n" />
            <feDisplacementMap in="SourceGraphic" in2="n" scale={v === "2" ? "1.6" : "2.2"} />
          </filter>
          <mask id={wearId}>
            <rect width="200" height="200" fill="#fff" />
            <rect width="200" height="200" fill="#000" filter={`url(#${speckleId})`} opacity=".55" />
          </mask>
          <filter id={speckleId}>
            <feTurbulence type="fractalNoise" baseFrequency="2.4" numOctaves="1" seed="3" />
            <feColorMatrix values="0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 -9 4.2" />
          </filter>
        </defs>

        {v === "1" && (
          <g filter={`url(#${roughId})`} mask={`url(#${wearId})`} className="stamp__body">
            <Ring grade={grade} ringId={ringAId} />
          </g>
        )}

        {v === "2" && (
          <g filter={`url(#${roughId})`} mask={`url(#${wearId})`} className="stamp__body">
            <rect x="9" y="9" width="182" height="182" rx="10" fill="none" strokeWidth="7" />
            <rect x="19.5" y="19.5" width="161" height="161" rx="4" fill="none" strokeWidth="1.8" />
            <text x="100" y="45" className="stamp__seal-cap" textAnchor="middle" dominantBaseline="central">
              等 级
            </text>
            <text x="100" y="103" className="stamp__grade" textAnchor="middle" dominantBaseline="central">
              {grade}
            </text>
            <text x="100" y="169" className="stamp__seal-cap stamp__seal-cap--tiny" textAnchor="middle" dominantBaseline="central">
              CLAUSELENS
            </text>
          </g>
        )}

        {v === "3" && (
          <>
            {/* 后层：青墨，向右下错开，压低不透明度 —— 套印没对准的那一枚 */}
            <g className="stamp__ghost" transform="translate(4.5 -3.5) rotate(-2.4 100 100)">
              <g filter={`url(#${roughId})`} mask={`url(#${wearId})`} className="stamp__body">
                <Ring grade={grade} ringId="stamp-v3-ring-b" outline={false} />
              </g>
            </g>
            <g filter={`url(#${roughId})`} mask={`url(#${wearId})`} className="stamp__body stamp__body--front">
              <Ring grade={grade} ringId={ringAId} />
            </g>
          </>
        )}
      </motion.svg>
    </div>
  );
}