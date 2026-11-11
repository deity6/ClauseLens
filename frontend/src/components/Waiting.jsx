import { useEffect, useMemo, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { RAIL, railIndex } from "../lib/useAnalysis.js";
import { DOC_TYPE_ZH, fmtChars, fmtMinutes } from "../lib/format.js";
import { DUR, EASE } from "../lib/motion.js";
import { POLARITY } from "../lib/taxonomy.js";
import CountUp from "./CountUp.jsx";
import { IconDoc, PolarityIcon } from "./Icons.jsx";

// 文案池按轨道阶段切换；{n}/{m}/{f} 由真实事件数据填入，拿不到就跳过含占位的句子
const QUIPS = {
  find: ["正在敲门，看看这个网站在不在家", "先确认一下你要查的是哪一家", "正在找到这个网站"],
  dig: ["正在页脚角落里翻找那行灰色小字…", "条款通常藏在最不显眼的地方", "翻到了 {f} 份条款，一份份打开看", "有些条款要点两三层链接才找得到"],
  read: ["正在逐字阅读，比律师便宜一点", "发现一处“包括但不限于”，眉头一皱", "读到第 {n} 条了，你本来要读 {m}", "“我们可能会”出现的次数，正在数", "在找“随时修改”和“不另行通知”"],
  stamp: ["正在盖章，请勿晃动", "印泥蘸好了，对准位置", "把分数算清楚再落章"],
};

function useQuip(pool, vars) {
  const list = useMemo(
    () =>
      pool
        .filter((s) => [...s.matchAll(/\{(\w)\}/g)].every((m) => vars[m[1]] != null))
        .map((s) => s.replace(/\{(\w)\}/g, (_, k) => vars[k])),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [pool, vars.n, vars.m, vars.f]
  );
  const [i, setI] = useState(0);
  useEffect(() => {
    setI(0);
    const t = setInterval(() => setI((x) => x + 1), 2600);
    return () => clearInterval(t);
  }, [pool]);
  return list.length ? list[i % list.length] : "";
}

const PASTE_TIP = (
  <>
    知道条款页地址就直接粘整条（带 <code>/privacy</code> 这种路径），会只分析那一页
  </>
);
// 按错误 code 给标题与建议；message_zh 由后端给，原样显示
const ERRORS = {
  rate_limited: { title: "查得有点快", tips: ["歇一分钟再点“再试一次”"] },
  network: { title: "连不上服务器", tips: ["确认后端服务已启动（端口 8787）", "离线看效果可以用 ?demo=baidu"] },
  bad_input: { title: "这个网址看不懂", tips: ["输入像 baidu.com 这样的域名，或条款页面的完整网址"] },
  not_found: { title: "没找到条款页面", tips: [PASTE_TIP, "有些网站的页面要靠脚本才能显示，暂时读不到"] },
  blocked: { title: "网站拒绝了访问", tips: [PASTE_TIP, "我们不绕过网站的验证，换一个页面试试"] },
  blocked_by_site: { title: "对方不让我们读", tips: ["页面能连上，但站点拒绝了程序访问（付费墙 / 反爬 / 登录限制）", "这不是「没有条款」，换一个镜像或搜公开副本"] },
  fetch_failed: { title: "条款页面打不开", tips: [PASTE_TIP, "也可能是对方网站暂时不稳定，稍后再试"] },
  timeout: { title: "等太久了", tips: ["对方网站响应很慢，稍后再试", PASTE_TIP] },
  unreachable: { title: "连不上这个网站", tips: ["可能是网络限制或网站暂时不可用", "换一个网站，或稍后再试"] },
  default: { title: "这次没能读到条款", tips: [PASTE_TIP, "稍后再试一次"] },
};

const LINES = 15;
// 纸上的“文字行”宽度：固定伪随机，避免每次渲染跳动
const lineWidths = Array.from({ length: LINES }, (_, i) => 52 + ((i * 47) % 44));

export default function Waiting({ query, state, taxonomy, onCancel, onRetry, onHome }) {
  const reduce = useReducedMotion();
  const ri = state.stage ? railIndex(state.stage) : -1;
  const railKey = RAIL[Math.max(0, ri)].key;
  const minutes = state.docs.reduce((a, d) => a + (d.read_minutes || 0), 0);
  const quip = useQuip(QUIPS[railKey], {
    n: state.clauses ? Math.max(1, Math.round(state.clauses * Math.max(0.3, state.progress))) : null,
    m: minutes ? fmtMinutes(minutes) : null,
    f: state.found || null,
  });
  const scanning = !state.error && (railKey === "dig" || railKey === "read");
  const counts = state.tags.reduce((a, t) => ((a[POLARITY[t.polarity]?.group || "neutral"] += 1), a), { bad: 0, good: 0, neutral: 0 });

  if (state.error) {
    const E = ERRORS[state.error.code] || ERRORS.default;
    return (
      <section className="waiting waiting--error" role="alert">
        <div className="meta">ERROR · {String(state.error.code || "unknown").toUpperCase()}</div>
        <h2 className="waiting__errtitle">{E.title}</h2>
        <p className="waiting__errmsg">{state.error.message_zh || "出了点问题。"}</p>
        {E.tips.length > 0 && (
          <ul className="waiting__tips">
            {E.tips.map((t, i) => (
              <li key={i}>{t}</li>
            ))}
          </ul>
        )}
        <div className="row-actions">
          <button className="btn btn--ink" onClick={onRetry}>
            再试一次
          </button>
          <button className="btn" onClick={onHome}>
            换个网站
          </button>
        </div>
      </section>
    );
  }

  return (
    <section className="waiting" aria-busy="true">
      <header className="waiting__head">
        <div className="meta">INSPECTING · {query}</div>
        <button className="btn btn--ghost btn--sm" onClick={onCancel}>
          取消
        </button>
      </header>

      <ol className="rail" aria-label="分析进度">
        {RAIL.map((r, i) => {
          const st = i < ri ? "done" : i === ri ? "active" : "todo";
          return (
            <li key={r.key} className={`rail__step rail__step--${st}`}>
              <span className="rail__mark" aria-hidden="true">
                {st === "done" ? (
                  <svg viewBox="0 0 20 20" width="20" height="20">
                    <motion.path
                      d="M5 10.5 8.5 14 15 6.5"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      initial={{ pathLength: reduce ? 1 : 0 }}
                      animate={{ pathLength: 1 }}
                      transition={{ duration: DUR.state, ease: EASE.out }}
                    />
                  </svg>
                ) : (
                  <i />
                )}
              </span>
              <span className="rail__label">{r.label}</span>
              {i < RAIL.length - 1 && (
                <span className="rail__bar">
                  <span style={{ transform: `scaleX(${i < ri ? 1 : 0})` }} />
                </span>
              )}
            </li>
          );
        })}
      </ol>
      <p className="sr-only" aria-live="polite">
        {ri >= 0 ? `当前：${RAIL[ri].label}` : "准备中"}
      </p>

      <div className="waiting__stage">
        <motion.div
          className={`paper ${scanning ? "paper--scanning" : ""}`}
          initial={reduce ? { opacity: 0 } : { y: 120, opacity: 0, rotate: 2 }}
          animate={{ y: 0, opacity: 1, rotate: -1.2 }}
          transition={{ duration: DUR.enter + 0.2, ease: EASE.enter }}
          aria-hidden="true"
        >
          <div className="paper__head">
            <span className="paper__title">{state.docs.at(-1)?.title || "服务条款"}</span>
            <span className="meta">{state.docs.length ? `DOC ${String(state.docs.length).padStart(2, "0")}` : "DOC —"}</span>
          </div>
          <div className="paper__lines">
            {lineWidths.map((w, i) => (
              <span key={i} className="paper__line" style={{ width: `${w}%`, "--i": i }} />
            ))}
          </div>
          {scanning && <div className="paper__scan" />}
          {railKey === "stamp" && (
            <motion.div
              className="paper__stampghost"
              initial={reduce ? { opacity: 0 } : { scale: 1.4, opacity: 0, rotate: -20 }}
              animate={{ scale: 1, opacity: 0.85, rotate: -8 }}
              transition={{ duration: DUR.stamp, ease: EASE.spring }}
            />
          )}
        </motion.div>

        <div className="waiting__side">
        <div className="quip">
          <AnimatePresence mode="wait">
            <motion.p
              key={quip}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              transition={{ duration: DUR.state, ease: EASE.enter }}
            >
              {quip}
            </motion.p>
          </AnimatePresence>
          <span className="quip__sub meta">{state.message || " "}</span>
        </div>
          <div className="tray" aria-label="已发现的标签">
          <div className="tray__head">
            <span className="meta">FOUND · {String(state.tags.length).padStart(2, "0")}</span>
            <span className="tray__counts">
              <b className="c-bad">{counts.bad}</b> 处要留神 · <b className="c-good">{counts.good}</b> 处不错
            </span>
          </div>
          <ul className="tray__list">
            <AnimatePresence initial={false}>
              {state.tags.map((t, i) => {
                const meta = taxonomy?.byId[t.id];
                const cls = POLARITY[t.polarity]?.cls || "neutral";
                // 从纸面方向“拎出来”：起点在左侧纸张上，回弹落入托盘
                const from = reduce
                  ? { opacity: 0 }
                  : { opacity: 0, x: -180 - (i % 3) * 30, y: -30 + (i % 5) * 16, scale: 0.6, rotate: -8 + (i % 4) * 5 };
                return (
                  <motion.li
                    key={t.id}
                    className={`ttag ttag--${cls}`}
                    initial={from}
                    animate={{ opacity: 1, x: 0, y: 0, scale: 1, rotate: 0 }}
                    transition={{ duration: DUR.enter, ease: EASE.spring, opacity: { duration: DUR.state, ease: EASE.enter } }}
                  >
                    <PolarityIcon polarity={t.polarity} width={14} height={14} />
                    {meta?.name_zh || t.id}
                  </motion.li>
                );
              })}
            </AnimatePresence>
          </ul>
          {!state.tags.length && <p className="tray__empty">读到要点会放在这里</p>}
        </div>
        </div>
      </div>

      <div className="docs">
        <ul className="docs__list">
          <AnimatePresence initial={false}>
            {state.docs.map((d, i) => (
              <motion.li
                key={`${d.title}-${i}`}
                className="doccard"
                initial={reduce ? { opacity: 0 } : { opacity: 0, y: 16, scale: 0.96 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                transition={{ duration: DUR.enter, ease: EASE.enter }}
              >
                <IconDoc className="doccard__icon" />
                <div className="doccard__body">
                  <div className="doccard__title">{d.title}</div>
                  <div className="doccard__meta">
                    {DOC_TYPE_ZH[d.type] || "条款"} · <span className="nowrap">{fmtChars(d.chars)}</span> ·{" "}
                    <span className="nowrap">正常人要读 {fmtMinutes(d.read_minutes)}</span>
                  </div>
                </div>
              </motion.li>
            ))}
          </AnimatePresence>
        </ul>
        <div className="saved">
          <span className="meta">TIME SAVED</span>
          <span className="saved__line">
            已替你省下 <CountUp className="saved__num" value={minutes} duration={0.9} /> 分钟
          </span>
        </div>
      </div>
    </section>
  );
}
