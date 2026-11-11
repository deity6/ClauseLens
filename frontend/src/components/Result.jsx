import { useEffect, useMemo, useRef, useState } from "react";
import { motion, useAnimationControls, useReducedMotion } from "motion/react";
import { DUR, EASE } from "../lib/motion.js";
import { POLARITY } from "../lib/taxonomy.js";
import { fetchSummary } from "../lib/feedback.js";
import { fmtChars, fmtMinutes } from "../lib/format.js";
import { IconAlert } from "./Icons.jsx";
import CountUp from "./CountUp.jsx";
import Stamp from "./Stamp.jsx";
import TagWall from "./TagWall.jsx";
import Radar from "./Radar.jsx";
import Compliance from "./Compliance.jsx";
import Reader from "./Reader.jsx";
import { IconLink, PolarityIcon } from "./Icons.jsx";

const GRADE_WORD = { A: "放心", B: "还行", C: "一般", D: "要留神", E: "慎重" };

// v1.1 结构化 tldr: [{tag, polarity, text, means}]；坏的在前，同组保持后端顺序。
// means = 这对普通人意味着什么（后端标签的 means_zh），渲染成每句下面的小字。
// 旧结果（只有 tldr_zh）按中性显示，不再反查。
function tldrItems(result) {
  const rank = { bad: 0, neutral: 1, good: 2 };
  const list = result.tldr?.length ? result.tldr : (result.tldr_zh || []).map((text) => ({ text, polarity: "neutral" }));
  return list
    .map((x, i) => ({
      s: x.text,
      means: x.means || "",
      i,
      pol: x.polarity || "neutral",
      group: POLARITY[x.polarity]?.group || "neutral",
    }))
    .sort((a, b) => rank[a.group] - rank[b.group] || a.i - b.i);
}

function Section({ n, en, title, children, className = "" }) {
  return (
    <motion.section
      className={`rsec ${className}`}
      initial={{ opacity: 0, y: 24 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.08 }}
      transition={{ duration: DUR.enter, ease: EASE.enter }}
    >
      <header className="rsec__head">
        <span className="meta">
          {n} · {en}
        </span>
        <h2>{title}</h2>
      </header>
      {children}
    </motion.section>
  );
}

export default function Result({ result, taxonomy, offline, onAgain }) {
  const reduce = useReducedMotion();
  const shake = useAnimationControls();
  const [summary, setSummary] = useState({});
  const [focus, setFocus] = useState(null);
  const [readerOpen, setReaderOpen] = useState(false);
  const jumpSeq = useRef(0);
  const [copied, setCopied] = useState(false);
  const { site, score, documents: docs, stats, jurisdiction, tosdr } = result;
  const domain = site.domain;

  useEffect(() => {
    if (!offline) fetchSummary(domain).then(setSummary);
  }, [domain, offline]);

  const tagsByDim = useMemo(() => {
    const m = {};
    for (const t of result.tags) {
      const meta = taxonomy.byId[t.id];
      if (!meta) continue;
      (m[meta.dimension] ||= []).push({ id: t.id, name: meta.name_zh, cls: POLARITY[meta.polarity]?.cls });
    }
    return m;
  }, [result.tags, taxonomy]);

  const tldr = useMemo(() => tldrItems(result), [result]);

  // 一次动作：展开原文 + 定位到证据。这里只发请求，不滚动 ——
  // 滚动要等面板展开、正文切好之后才量得出落点，交给 Reader 按这次请求执行。
  // 每次点击 seq +1，Reader 用它判断「这是一次新请求」，不会被开合状态重复触发。
  const jump = (doc, start, end) => {
    setReaderOpen(true);
    setFocus({ doc, start, end, seq: ++jumpSeq.current });
  };

  const share = async () => {
    const url = `${location.origin}${location.pathname}?q=${encodeURIComponent(result.query?.input || domain)}`;
    try {
      await navigator.clipboard.writeText(url);
    } catch {
      window.prompt("复制这个链接", url);
    }
    setCopied(true);
    setTimeout(() => setCopied(false), 1800);
  };

  const landed = () => {
    if (reduce) return;
    // 印章落定后，整个报告头被“震”一下：一次 3px 下沉 + 回弹，不来回抖
    shake.start({ y: [0, 3, -1, 0], transition: { duration: DUR.state, ease: EASE.out, times: [0, 0.3, 0.7, 1] } });
  };

  const word = GRADE_WORD[score.grade] || "";

  return (
    <div className="result">
      <motion.header className="rhead" animate={shake}>
        <div className="rhead__main">
          <div className="meta rhead__no">
            REPORT · {domain.toUpperCase()} · {new Date(docs[0]?.fetched_at || Date.now()).toISOString().slice(0, 10)}
          </div>
          <div className="rhead__site">
            <img src={site.favicon} alt="" width={28} height={28} className="rhead__fav" onError={(e) => (e.currentTarget.style.visibility = "hidden")} />
            <h1>{site.name || domain}</h1>
          </div>
          <div className="rhead__domain">{domain}</div>
          <div className="rhead__score">
            <CountUp className={`rhead__num c-g-${score.grade}`} value={score.value} duration={1.3} delay={0.2} />
            <span className="rhead__of">/ 100</span>
            <span className={`rhead__word c-g-${score.grade}`}>{word}</span>
          </div>
          <p className="rhead__metaline">
            共 {docs.length} 份文档 · {fmtChars(stats.total_chars)} · 阅读需 {fmtMinutes(stats.read_minutes)} · 适用：{jurisdiction.name_zh}
            {jurisdiction.laws?.length ? `（${jurisdiction.laws.slice(0, 2).join("、")}${jurisdiction.laws.length > 2 ? "…" : ""}）` : ""}
          </p>
          {tosdr?.rating && (
            <p className="rhead__tosdr meta">
              ToS;DR 社区评级：
              <a href={tosdr.url} target="_blank" rel="noreferrer noopener" className={`c-g-${tosdr.rating}`}>
                {tosdr.rating}
              </a>
            </p>
          )}
        </div>
        <div className="rhead__stamp">
          <Stamp grade={score.grade} onLand={landed} />
        </div>
      </motion.header>

      {result.warnings?.length > 0 && (
        <div className="rnotice">
          {result.warnings.map((w) => (
            <p key={w.code} className="rnotice__item">
              <IconAlert width={15} height={15} />
              <span>{w.message_zh}</span>
            </p>
          ))}
        </div>
      )}

      {tldr.length > 0 && (
      <Section n="01" en="TL;DR" title="一句话总结" className="rsec--tldr">
        <ul className="tldr">
          {tldr.map((x, i) => (
            <motion.li
              key={x.s}
              className={`tldr__item tldr__item--${x.group}`}
              initial={{ opacity: 0, x: -10 }}
              whileInView={{ opacity: 1, x: 0 }}
              viewport={{ once: true }}
              transition={{ duration: DUR.enter, delay: 0.06 * i, ease: EASE.enter }}
            >
              <span className={`tldr__dot c-${POLARITY[x.pol]?.cls}`}>
                <PolarityIcon polarity={x.pol} width={14} height={14} />
              </span>
              {/* .tldr__item 是 flex，句子和小字要包一层，否则小字会跟圆点并排 */}
              <span className="tldr__line">
                {x.s}
                {x.means && <small className="tldr-means">{x.means}</small>}
              </span>
            </motion.li>
          ))}
        </ul>
      </Section>
      )}

      {result.tags.length > 0 && (
      <Section n="02" en="FINDINGS" title="条款里写了什么">
        <p className="rsec__lead">点开任一标签，看它对你意味着什么、原文怎么写的。</p>
        <TagWall tags={result.tags} taxonomy={taxonomy} docs={docs} domain={domain} summary={summary} offline={offline} onJump={result.texts ? jump : null} />
      </Section>
      )}

      <Section n="03" en="DIMENSIONS" title="六个方面的得分">
        <p className="rsec__lead">分数越高越友好。把鼠标放在维度上，看看是哪些条款拉低或抬高了它。</p>
        <Radar dims={score.dimensions} dimMeta={taxonomy.dimensions} tagsByDim={tagsByDim} grades={taxonomy.grades} />
      </Section>

      <Section n="04" en="COMPLIANCE" title="该写的写了吗">
        <Compliance items={result.compliance || []} jurisdiction={jurisdiction} docs={docs} onJump={result.texts ? jump : null} />
      </Section>

      {result.texts && (
        <section className="rsec" id="reader">
          <header className="rsec__head">
            <span className="meta">05 · SOURCE</span>
            <h2>原文</h2>
          </header>
          <Reader docs={docs} texts={result.texts} tags={result.tags} taxonomy={taxonomy} focus={focus} open={readerOpen} setOpen={setReaderOpen} />
        </section>
      )}

      <footer className="rfoot">
        <button className="btn btn--ink" onClick={onAgain}>
          再查一个
        </button>
        <button className={`btn ${copied ? "is-done" : ""}`} onClick={share}>
          <IconLink width={16} height={16} />
          {copied ? "链接已复制" : "复制分享链接"}
        </button>
      </footer>
    </div>
  );
}
