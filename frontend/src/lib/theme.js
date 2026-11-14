// 主题状态：两套主题共用一份骨架，切换只改 <html data-theme>。
//
// 为什么不用 React context：主题要在首帧之前就生效（index.html 的内联首帧脚本已经在 CSS 之前写过一次），
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

/** 手机 / 平板：移动端 UA，或「粗指针 + 小屏」。
 *  不在文档解析早期用 matchMedia("(max-width)")) 判：那时移动端的布局视口还是 980px，会误判（见 index.html 里的内联首帧脚本）。
 *  screen 尺寸拿不到时（个别内置浏览器）退回视口宽度 —— 这个函数在 React 启动/媒体查询变化时才跑，那时视口是真的。 */
export function isMobileLike() {
  if (typeof window === "undefined" || typeof window.matchMedia !== "function") return false;
  const ua = /Android|iPhone|iPad|iPod|Mobile|HarmonyOS|MiuiBrowser/i.test(navigator.userAgent || "");
  if (ua) return true;
  const coarse = window.matchMedia("(pointer: coarse)").matches;
  if (!coarse) return false;
  const sc = window.screen || {};
  const shortSide = Math.min(sc.width || 0, sc.height || 0);
  // screen 量得到就按设备（不受缩放/横竖屏影响）；量不到才用视口。
  return shortSide > 0 ? shortSide <= 900 : window.matchMedia("(max-width: 900px)").matches;
}

/** 系统当前是深色还是浅色。 */
export function systemTheme() {
  if (typeof window === "undefined" || typeof window.matchMedia !== "function") return "light";
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "geek" : "light";
}

export function getTheme() {
  if (current) return current;
  const root = document.documentElement;
  const booted = root.dataset.themeBoot; // 首帧脚本跑过才会留下这个标记
  if (booted && THEMES.includes(root.dataset.theme)) {
    current = root.dataset.theme; // 首帧脚本已经算好了，直接沿用（避免挂载时再闪一次）
    return current;
  }
  // 首帧脚本没跑成（CSP 拦了、请求失败、拿到的是缓存里的旧 HTML）：不能相信 html 上的旧值，
  // 按同一套规则自己算一遍。否则手机上会一直停在浅色，只有手动点开关才出得来。
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
  const apply = () => {
    if (!isMobileLike() || stored()) return;
    const next = mq.matches ? "geek" : "light";
    if (next === getTheme()) return;
    applyTheme(next, { persist: false });
  };
  // 启动时先对齐一次：index.html 里的内联首帧脚本在少数环境（无头浏览器、手机里的内置浏览器、
  // 被 CSP/网络拦掉）可能在媒体查询/UA 还没生效时就跑完了或没跑成；这里补一次，再在头两秒补两次，
  // 保证最后一定落到系统那一套。手动选过主题（stored() 有值）时每次都直接返回，不会跟用户抢。
  apply();
  const t1 = setTimeout(apply, 400);
  const t2 = setTimeout(apply, 1500);
  mq.addEventListener?.("change", apply);
  addEventListener("pageshow", apply);
  return () => {
    clearTimeout(t1);
    clearTimeout(t2);
    mq.removeEventListener?.("change", apply);
    removeEventListener("pageshow", apply);
  };
}

export function prefersReducedMotion() {
  return matchMedia("(prefers-reduced-motion: reduce)").matches;
}
