import { useEffect, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { DUR, EASE } from "../lib/motion.js";
import { GROUPS, POLARITY } from "../lib/taxonomy.js";
import { myVote, sendVote } from "../lib/feedback.js";
import { IconChevron, IconThumb, PolarityIcon } from "./Icons.jsx";

// 证据高亮只用后端给的命中区间（quote 内偏移 [[a,b],...]）。
// 没有区间（模型独立命中）就不猜关键词，整句淡底，避免把无关的词标出来。
export function Highlight({ text, spans }) {
  if (!spans?.length) return <span className="ev-whole">{text}</span>;
  const out = [];
  let at = 0;
  for (const [a, b] of [...spans].sort((x, y) => x[0] - y[0])) {
    const s = Math.max(a, at);
    if (b <= s) continue;
    if (s > at) out.push(text.slice(at, s));
    out.push(<mark key={s}>{text.slice(s, b)}</mark>);
    at = b;
  }
  if (at < text.length) out.push(text.slice(at));
  return out;
}

// 最近一次已知的计数（进程内缓存）。
// 抽屉开合会把 Votes 卸载再挂载，而父级传下来的 summary 是**页面加载时**那一份：
// 重挂载时如果直接拿 summary，刚投的那一票就「消失」了（数字退回投票前），
// 只有刷新页面才回来 —— 因为那时候 fetchSummary 已经包含它。
// 所以每投一次都把最新计数记在这里，重挂载时优先用它；服务端返回权威值时再覆盖。
const latestCnt = new Map();
const cntKey = (domain, tagId) => `${domain}|${tagId}`;

function Votes({ domain, tagId, summary, offline }) {
  const k = cntKey(domain, tagId);
  const [mine, setMine] = useState(() => myVote(domain, tagId));
  const [cnt, setCnt] = useState(() => latestCnt.get(k) || summary || { agree: 0, disagree: 0 });
  const [pulse, setPulse] = useState(null);
  useEffect(() => {
    const hit = latestCnt.get(k);
    if (hit) {
      setCnt(hit);
      return;
    }
    setCnt(summary || { agree: 0, disagree: 0 });
  }, [summary, k]);
  const vote = async (v) => {
    if (mine) return;
    setMine(v);
    setPulse(v);
    setCnt((c) => {
      const next = { ...c, [v]: (c[v] || 0) + 1 };
      latestCnt.set(k, next);
      return next;
    });
    const s = await sendVote({ domain, tag: tagId, vote: v, offline });
    if (s && s[tagId]) {
      latestCnt.set(k, s[tagId]);
      setCnt(s[tagId]);
    }
  };
  return (
    <div className="votes">
      <span className="votes__q">你认同这个判断吗？</span>
      {[
        ["agree", "认同"],
        ["disagree", "不认同"],
      ].map(([v, label]) => (
        <motion.button
          key={v}
          type="button"
          className={`vote ${mine === v ? "is-mine" : ""}`}
          disabled={!!mine}
          aria-pressed={mine === v}
          onClick={() => vote(v)}
          animate={pulse === v ? { scale: [1, 1.18, 1] } : {}}
          transition={{ duration: DUR.state, ease: EASE.spring }}
        >
          <IconThumb down={v === "disagree"} width={16} height={16} />
          {label}
          <motion.b key={cnt[v] || 0} initial={pulse === v ? { y: -8, opacity: 0 } : false} animate={{ y: 0, opacity: 1 }} transition={{ duration: DUR.state, ease: EASE.spring }}>
            {cnt[v] || 0}
          </motion.b>
        </motion.button>
      ))}
      {mine && <span className="votes__thanks meta">已记下 · THANKS</span>}
    </div>
  );
}

// 抽屉里的每一块依次浮出来：位移 + 高斯模糊由深到清，像对焦。
// 父级只负责排期（staggerChildren），子级只管自己的过渡。
const detailWrap = {
  hidden: {},
  show: { transition: { staggerChildren: 0.065, delayChildren: 0.06 } },
  exit: { transition: { staggerChildren: 0.03, staggerDirection: -1 } },
};
const detailItem = {
  hidden: { opacity: 0, y: 10, filter: "blur(7px)" },
  show: { opacity: 1, y: 0, filter: "blur(0px)", transition: { duration: 0.42, ease: [0.22, 0.61, 0.36, 1] } },
  exit: { opacity: 0, y: 4, filter: "blur(5px)", transition: { duration: 0.2, ease: "easeIn" } },
};

function TagDetail({ tag, meta, docs, domain, summary, offline, onJump }) {
  const [more, setMore] = useState(false);
  const ev = tag.evidence || [];
  const shown = more ? ev : ev.slice(0, 1);
  const docTitle = (id) => docs.find((d) => d.id === id)?.title || id;
  return (
    <motion.div className="tagdetail" variants={detailWrap} initial="hidden" animate="show" exit="exit">
      <motion.p variants={detailItem} className="tagdetail__explain">
        <span className="meta">这对你意味着什么</span>
        {meta?.explain_zh}
      </motion.p>
      {shown.map((e, i) => (
        <motion.figure key={i} variants={detailItem} className="evidence">
          <blockquote>
            <Highlight text={e.quote} spans={e.spans} />
          </blockquote>
          <figcaption>
            来自：{docTitle(e.doc)}
            {onJump && (
              <button type="button" className="linkbtn" onClick={() => onJump(e.doc, e.start, e.end)}>
                在原文中查看 →
              </button>
            )}
          </figcaption>
        </motion.figure>
      ))}
      {ev.length > 1 && (
        <motion.button variants={detailItem} type="button" className="linkbtn" onClick={() => setMore((m) => !m)}>
          {more ? "收起" : `还有 ${ev.length - 1} 处证据`}
        </motion.button>
      )}
      <motion.div variants={detailItem} className="tagdetail__conf">
        <span className="meta">CONFIDENCE</span>
        <span className="confbar">
          <motion.span initial={{ scaleX: 0 }} animate={{ scaleX: tag.confidence }} transition={{ duration: 0.8, ease: EASE.tail }} />
        </span>
        <span className="tagdetail__confnum">{Math.round(tag.confidence * 100)}%</span>
        <span className="meta">· {tag.source === "model" ? "模型判断" : tag.source === "rule+model" ? "规则 + 模型" : tag.source === "tosdr" ? "社区标注" : "规则匹配"}</span>
        {tag.provisional ? <span className="meta"> · 程序推测，待确认</span> : null}
      </motion.div>
      <motion.div variants={detailItem}>
        <Votes domain={domain} tagId={tag.id} summary={summary} offline={offline} />
      </motion.div>
    </motion.div>
  );
}

export default function TagWall({ tags, taxonomy, docs, domain, summary, offline, onJump }) {
  const reduce = useReducedMotion();
  const [open, setOpen] = useState(null);
  const groups = GROUPS.map((g) => ({
    ...g,
    items: tags.filter((t) => (POLARITY[taxonomy.byId[t.id]?.polarity]?.group || "neutral") === g.key),
  })).filter((g) => g.items.length);
  let n = 0;
  // 每个标签渲染成固定宽度的胶囊（宽度永远不变）。点开时不是让这条 <li> 撑满整行
  // （那样宽度一变，位置动画就只能靠 layout 补，视觉上会「跳一下」），
  // 而是把这一组拆成「前段 / 详情 / 后段」三块：详情独占一行，两段里的胶囊只是平移。
  const pill = (t) => {
    const meta = taxonomy.byId[t.id];
    const pol = meta?.polarity || "neutral";
    const isOpen = open === t.id;
    const delay = 0.04 * n++;
    return (
      <motion.li
        key={t.id}
        className={`tagrow ${isOpen ? "is-open" : ""}`}
        layout="position"
        initial={reduce ? { opacity: 0 } : { opacity: 0, scale: 0.88, y: 6 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        transition={{
          layout: { duration: 0.42, ease: [0.22, 0.61, 0.36, 1] },
          duration: DUR.enter,
          delay,
          ease: EASE.spring,
          opacity: { duration: DUR.state, delay, ease: EASE.enter },
        }}
      >
        <button
          type="button"
          className={`pill pill--${POLARITY[pol]?.cls}`}
          aria-expanded={isOpen}
          aria-controls={`tag-${t.id}`}
          onClick={() => setOpen(isOpen ? null : t.id)}
        >
          <PolarityIcon polarity={pol} width={15} height={15} />
          <span className="pill__name">{meta?.name_zh || t.id}</span>
          {pol === "blocker" && <span className="pill__flag">严重</span>}
          <IconChevron className="pill__chev" width={14} height={14} />
        </button>
      </motion.li>
    );
  };

  return (
    <div className="tagwall">
      {groups.map((g) => {
        const idx = open ? g.items.findIndex((t) => t.id === open) : -1;
        const openTag = idx >= 0 ? g.items[idx] : null;
        const head = idx >= 0 ? g.items.slice(0, idx + 1) : g.items;
        const tail = idx >= 0 ? g.items.slice(idx + 1) : [];
        return (
          <div key={g.key} className={`tgroup tgroup--${g.key} ${openTag ? "is-open" : ""}`}>
            <h3 className="tgroup__title">
              <PolarityIcon polarity={g.key} width={16} height={16} />
              {g.title}
              <span className="meta">
                {g.en} · {g.items.length}
              </span>
            </h3>
            <ul className="tgroup__list">{head.map(pill)}</ul>
            <AnimatePresence initial={false}>
              {openTag && (
                <motion.div
                  key={openTag.id}
                  id={`tag-${openTag.id}`}
                  className="tgroup__drawer"
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: "auto", opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  transition={{ height: { duration: 0.42, ease: [0.22, 0.61, 0.36, 1] }, opacity: { duration: 0.24, ease: EASE.out } }}
                >
                  <TagDetail
                    tag={openTag}
                    meta={taxonomy.byId[openTag.id]}
                    docs={docs}
                    domain={domain}
                    summary={summary?.[openTag.id]}
                    offline={offline}
                    onJump={onJump}
                  />
                </motion.div>
              )}
            </AnimatePresence>
            {tail.length > 0 && <ul className="tgroup__list">{tail.map(pill)}</ul>}
          </div>
        );
      })}
    </div>
  );
}
