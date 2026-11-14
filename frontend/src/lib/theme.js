// 主题状态：两套主题共用一份骨架，切换只改 <html data-theme>。
//
// 为什么不用 React context：主题要在首帧之前就生效（index.html 里的内联脚本已经写过一次），
// 而且 canvas（点阵背景、转场）也要读它。用模块级单例 + 订阅，任何地方都能同步拿到当前值。
//
// 主题名：
//   light = 「验光单」暖纸（默认）
//   geek  = 「点阵 · SPECTRAL SCAN」近黑点阵
//
// 跟随规则（2026-11-14 改）：
//   · 桌面（鼠标 + 宽屏）：不跟随系统 —— 这个工具是「捧着看一份文件」，光线由用户自己决定；
//   · 手机 / 平板（窄屏 + 粗指针）：**用户没手动选过时跟随系统深浅色**，系统深色就上点阵主题，
//     系统浅色就回纸主题；手动拨过一次开关之后就以用户的选择为准（存 localStorage['cl:theme']）。
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

/** 手机 / 平板：窄屏 +（粗指针 或 移动端 UA）。桌面窄窗口不算。 */
export function isMobileLike() {
  if (typeof window === "undefined" || typeof window.matchMedia !== "function") return false;
  const narrow = window.matchMedia("(max-width: 900px)").matches;
  const coarse = window.matchMedia("(pointer: coarse)").matches;
  const ua = /Android|iPhone|iPad|iPod|Mobile|HarmonyOS|MiuiBrowser/i.test(navigator.userAgent || "");
  return narrow && (coarse || ua);
}

/** 系统当前是深色还是浅色。 */
export function systemTheme() {
  if (typeof window === "undefined" || typeof window.matchMedia !== "function") return "light";
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "geek" : "light";
}

export function getTheme() {
  if (current) return current;
  const attr = document.documentElement.dataset.theme;
  if (THEMES.includes(attr)) {
    current = attr; // index.html 的内联脚本已经在首帧前算好了
    return current;
  }
  current = stored() || (isMobileLike() ? systemTheme() : "light");
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

/**
 * 移动端跟随系统：系统深浅色一变就跟着换（不写入 localStorage，所以「没手动选过」这件事不被破坏）。
 * 手动拨过开关（localStorage 有值）之后就不再跟随。
 */
export function startSystemThemeSync() {
  if (typeof window === "undefined" || typeof window.matchMedia !== "function") return () => {};
  const mq = window.matchMedia("(prefers-color-scheme: dark)");
  const onChange = () => {
    if (!isMobileLike() || stored()) return;
    const next = mq.matches ? "geek" : "light";
    if (next === getTheme()) return;
    applyTheme(next, { persist: false });
  };
  mq.addEventListener?.("change", onChange);
  return () => mq.removeEventListener?.("change", onChange);
}

export function prefersReducedMotion() {
  return matchMedia("(prefers-reduced-motion: reduce)").matches;
}
