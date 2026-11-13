// 评分徽章：纸主题还是那枚圆形钢印；点阵主题换成「用点阵画出来的等级字母」。
//
// 用的就是 ascii.txt 里那套 ASCII wake 的算法（见 AsciiField.jsx）：
// 字母先被光栅化成一张掩膜，掩膜里的格子是圆点，鼠标划过去会把点变成字符（@ # + …）再慢慢退回去。
// 这比再画一个方框+字母更像那个站的做法：徽章本身就是一块点阵屏。
import { useMemo } from "react";
import { motion, useReducedMotion } from "motion/react";
import Stamp from "./Stamp.jsx";
import AsciiField, { textMask } from "./AsciiField.jsx";
import { useTheme } from "../lib/theme.js";
import { DUR, EASE } from "../lib/motion.js";

export default function ScoreBadge({ grade = "C", score = 0, onLand }) {
  const theme = useTheme();
  const reduce = useReducedMotion();
  const mask = useMemo(() => textMask(grade, { weight: 700, fill: 1.0 }), [grade]);

  if (theme !== "geek") return <Stamp grade={grade} onLand={onLand} />;

  return (
    <motion.div
      className="scorebadge"
      role="img"
      aria-label={`等级 ${grade}，${score} 分`}
      initial={reduce ? { opacity: 0 } : { opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: DUR.enter, delay: reduce ? 0 : 0.2, ease: EASE.enter }}
      onAnimationComplete={() => onLand && onLand()}
    >
      <AsciiField
        className="scorebadge__field"
        mask={mask}
        size={5}
        glyphs="Classic"
        reach={55}
        pull={26}
        trail={1}
        reveal={820}
        ariaLabel={`等级 ${grade}`}
      />
      <div className="scorebadge__cap">
        <span>GRADE</span>
        <b>{grade}</b>
      </div>
    </motion.div>
  );
}