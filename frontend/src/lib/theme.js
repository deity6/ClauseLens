// 主题状态：两套主题共用一份骨架，切换只改 <html data-theme>。
//
// 为什么不用 React context：主题要在首帧之前就生效（index.html 里的内联脚本已经写过一次），
// 而且 canvas（点阵背景、转场）也要读它。用模块级单例 + 订阅，任何地方都能同步拿到当前值。
//
// 主题名：
//   light = 「验光单」暖纸（默认）
//   geek  = 「点阵 · SPECTRAL SCAN」近黑点阵
// 不跟随系统：这个工具是给人「捧着看一份文件」的，光线由用户自己决定。
import { useEffect, useState } from "react";

const KEY = "cl:theme";
const THEMES = ["light", "geek"];

export const THEME_META = {
  light: { label: "纸", en: "PAPER", color: "#ffffff" },
  geek: { label: "点阵", en: "DOT", color: "#07070a" },
};

let current = null;
const listeners = new Set();

function stored() {
  try {
    const v = localStorage.getItem(KEY);
    return THEMES.includes(v) ? v : null;
  } catch {
    return null;
  }
}

export function getTheme() {
  if (current) return current;
  const attr = document.documentElement.dataset.theme;
  current = THEMES.includes(attr) ? attr : stored() || "light";
  return current;
}

export function otherTheme(t = getTheme()) {
  return t === "geek" ? "light" : "geek";
}

export function subscribe(fn) {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

/** 直接落地主题（不做动画）。转场由 ThemeWipe 在合适的一帧调用它。 */
export function applyTheme(next, { persist = true } = {}) {
  const theme = THEMES.includes(next) ? next : "light";
  const root = document.documentElement;
  root.dataset.theme = theme;
  root.style.colorScheme = theme === "geek" ? "dark" : "light";
  document.querySelector('meta[name="theme-color"]')?.setAttribute("content", THEME_META[theme].color);
  current = theme;
  if (persist) {
    try {
      localStorage.setItem(KEY, theme);
    } catch {
      /* 隐身模式：不记住也不报错 */
    }
  }
  listeners.forEach((fn) => fn(theme));
}

export function useTheme() {
  const [t, setT] = useState(getTheme);
  useEffect(() => subscribe(setT), []);
  return t;
}

export function prefersReducedMotion() {
  return matchMedia("(prefers-reduced-motion: reduce)").matches;
}
