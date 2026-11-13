// 右上角的主题开关：纸 ⇄ 点阵。
//
// 换成了 Bencho 的「液态开关」（components/LiquidToggle.jsx，MIT）：两个主题不是「开/关」，
// 但一颗会流过去的水滴刚好把「从这边走到那边」说清楚了，也比原来的分段控件轻。
// 分工没变：真正改 data-theme 的仍然是 theme-wipe（它在像素帷幕铺满那一帧落地），
// 这个组件只负责发起（onChange），位置反过来由 theme === "geek" 驱动（on）。
import LiquidToggle from "./LiquidToggle.jsx";
import { useTheme } from "../lib/theme.js";
import { isWiping, startThemeWipe } from "../lib/theme-wipe.js";

export default function ThemeSwitch() {
  const theme = useTheme();

  return (
    <LiquidToggle
      on={theme === "geek"}
      onChange={(next) => {
        // 转场进行中（~1.14s）不响应：连点只会让像素帷幕自己撞自己
        if (isWiping()) return;
        const nextTheme = next ? "geek" : "light";
        if (nextTheme === theme) return;
        startThemeWipe(nextTheme);
      }}
    />
  );
}
