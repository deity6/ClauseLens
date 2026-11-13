// 页脚的山脊点阵：Bencho 页脚那块 `.foot-field` 的移植。
//
// 密度场用的是它原文的 `to(x, y, H)`（见 AsciiField.jsx 里的 ridgeMask）：
// 三条正弦叠出天际线，线下越深越密，乘一层高频细纹，再 r^1.4 压出山脚的实。
// 渲染走同一套 ASCII 场：冷的地方是圆点，鼠标扫过的地方会冒出字符，再慢慢冷却回去。
import AsciiField, { ridgeMask } from "./AsciiField.jsx";
import { useTheme } from "../lib/theme.js";

export default function RidgeFoot() {
  const theme = useTheme();
  if (theme !== "geek") return null;
  return (
    <div className="ridgefoot" aria-hidden="true">
      <AsciiField className="ridgefoot__field" mask={ridgeMask} size={7} glyphs="Classic" reach={34} pull={0} trail={1.5} ambient />
    </div>
  );
}