import { useEffect, useRef } from "react";
import { motion, useReducedMotion } from "motion/react";
import { DUR, EASE } from "../lib/motion.js";
import "./ScanDoc.css";

// 等待页中央那张「文档纸」。
// A 主题（data-theme="light"）：结构、尺寸、类名与旧版一致（.paper / .paper__* 的观感全靠
//   styles.css，这里一条都不覆盖），只多了几个在 A 下 display:none 的装饰层。
// B 主题（data-theme="geek"）：同一张纸变成点阵文档——点行、扫描头、四角角标、等宽读数。

const LINES = 15;
const ROW_H = 7; // 与 styles.css 的 .paper__line 高度一致，改了要同步
const ROW_GAP = 11; // 与 .paper__lines 的 gap 一致（窄屏 8px，但比例几乎不变，见下）
const BODY_H = LINES * ROW_H + (LINES - 1) * ROW_GAP; // 259px

// 纸上的“文字行”宽度：固定伪随机，避免每次渲染跳动（沿用旧版 Waiting 的算法，A 主题观感不变）
const WIDTHS = Array.from({ length: LINES }, (_, i) => 52 + ((i * 47) % 44));

// 每行开始“打印”的时刻 = 扫描头的亮线走到该行中心的时刻，取一个扫描周期里的比例。
// 扫描头元素撑满 .paper__lines 的高度、从 translateY(-100%) 走到 0，所以纵坐标 y 处的比例就是 y / BODY_H。
// 用比例而不是毫秒：窄屏把行距改成 8px 后，行距/行区高度的比值几乎不变，两边依旧对得上。
const printAt = (i) => (i * (ROW_H + ROW_GAP) + ROW_H / 2) / BODY_H;

const pad2 = (n) => String(n).padStart(2, "0");
// 千分位固定用 en-US：读数栏要的是 1,284 这种机器读数，不跟随系统语言
const group = (n) => (n > 0 ? n.toLocaleString("en-US") : "0");

export default function ScanDoc({ title, docs = [], percent = 0, scanning = false, stamp = false }) {
  const reduce = useReducedMotion();
  const rootRef = useRef(null);

  // 逐帧动效在标签页不可见时暂停：CSS 动画在后台标签里照样计时，
  // 切回来会看到“跳过一大段”，所以显式按住 animation-play-state。
  useEffect(() => {
    const el = rootRef.current;
    if (!el) return;
    const sync = () => {
      if (document.hidden) el.setAttribute("data-paused", "");
      else el.removeAttribute("data-paused");
    };
    sync();
    document.addEventListener("visibilitychange", sync);
    return () => document.removeEventListener("visibilitychange", sync);
  }, []);

  const chars = docs.reduce((a, d) => a + (d.chars || 0), 0);
  const pct = Math.max(0, Math.min(99, Math.round(percent)));
  const line = Math.min(LINES, Math.max(1, Math.round((pct / 100) * LINES)));
  const printing = scanning && !reduce;

  return (
    <motion.div
      ref={rootRef}
      className={`paper scandoc${scanning ? " paper--scanning" : ""}`}
      data-print={printing ? "" : undefined}
      data-reduce={reduce ? "" : undefined}
      initial={reduce ? { opacity: 0 } : { y: 120, opacity: 0, rotate: 2 }}
      animate={{ y: 0, opacity: 1, rotate: -1.2 }}
      transition={{ duration: DUR.enter + 0.2, ease: EASE.enter }}
      aria-hidden="true"
    >
      <div className="paper__head">
        <span className="paper__title">{title || "服务条款"}</span>
        <span className="meta">{docs.length ? `DOC ${pad2(docs.length)}` : "DOC —"}</span>
      </div>

      <div className="paper__lines">
        {WIDTHS.map((w, i) => (
          <span
            key={i}
            className="paper__line"
            style={{ width: `${w}%`, "--i": i, "--sd-at": printAt(i).toFixed(4) }}
          />
        ))}
        {/* B 主题的扫描头：放在行区里，扫描进度才对得上每一行（A 主题下不显示） */}
        {printing && <div className="scandoc__beam" />}
      </div>

      {/* A 主题的整纸扫描光带，位置与旧版完全一致 */}
      {scanning && <div className="paper__scan" />}

      {stamp && (
        <motion.div
          className="paper__stampghost"
          initial={reduce ? { opacity: 0 } : { scale: 1.4, opacity: 0, rotate: -20 }}
          animate={{ scale: 1, opacity: 0.85, rotate: -8 }}
          transition={{ duration: DUR.stamp, ease: EASE.spring }}
        >
          {/* 落章鬼影里的记号：B 主题下是方形双线框 + 等级待定的占位（A 主题下隐藏） */}
          <span className="scandoc__stampmark">?</span>
          <span className="scandoc__stamplabel">LEVEL</span>
        </motion.div>
      )}

      <span className="scandoc__corner" data-c="tl" />
      <span className="scandoc__corner" data-c="tr" />
      <span className="scandoc__corner" data-c="bl" />
      <span className="scandoc__corner" data-c="br" />

      {/* 左下角机器读数：数字全部来自真实事件（阶段推进 / 文档字数），拿到多少写多少 */}
      <div className="scandoc__readout">
        <span>
          SCAN <b>{pad2(pct)}%</b>
        </span>
        <span className="scandoc__sep">·</span>
        <span>
          LINE <b>{pad2(line)}/{LINES}</b>
        </span>
        <span className="scandoc__sep">·</span>
        <span>
          <b>{group(chars)}</b> CH
        </span>
      </div>
    </motion.div>
  );
}