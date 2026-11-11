import { useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { DUR, EASE } from "../lib/motion.js";
import { IconCheck, IconDot, IconQuestion } from "./Icons.jsx";
import { Highlight } from "./TagWall.jsx";

// 「未在条款中找到」用中性色和空心圆：写没写是事实，不代表网站违规。
// 用红色叉号会让整页看着像判了罪，和页脚那句免责说明互相打架。
const STATUS = {
  found: { icon: IconCheck, label: "找到", cls: "good" },
  missing: { icon: IconDot, label: "未在条款中找到", cls: "muted" },
  unclear: { icon: IconQuestion, label: "写得不清楚", cls: "warn" },
};

// v1.1：evidence = {doc, quote, start, end, match_start, match_end}，偏移都相对 evidence.doc 那份文档；
// 命中词在 quote 内的区间 = match_* - start。
const matchSpan = (e) => (e.match_start != null && e.match_end > e.match_start ? [[e.match_start - e.start, e.match_end - e.start]] : null);

export default function Compliance({ items, jurisdiction, docs, onJump }) {
  const [open, setOpen] = useState(null);
  const found = items.filter((x) => x.status === "found").length;
  return (
    <div className="compliance">
      <p className="compliance__lead">
        按 <b>{jurisdiction.name_zh}</b> 的法律要求，检查这些条款有没有写清楚
        <span className="meta">
          {" "}
          · {found}/{items.length} FOUND
        </span>
      </p>
      <ul className="checklist">
        {items.map((c) => {
          const s = STATUS[c.status] || STATUS.unclear;
          const can = !!c.evidence;
          const isOpen = open === c.id;
          const ev = c.evidence;
          return (
            <li key={c.id} className={`check check--${s.cls} ${isOpen ? "is-open" : ""}`}>
              <button type="button" className="check__row" disabled={!can} aria-expanded={can ? isOpen : undefined} onClick={() => setOpen(isOpen ? null : c.id)}>
                <span className={`check__mark c-${s.cls}`}>
                  <s.icon width={16} height={16} />
                </span>
                <span className="check__item">{c.item_zh}</span>
                <span className="check__law meta">{c.law}</span>
                <span className={`check__status c-${s.cls}`}>{s.label}</span>
              </button>
              <AnimatePresence initial={false}>
                {isOpen && (
                  <motion.div
                    className="check__drawer"
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: "auto", opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    transition={{ duration: DUR.state, ease: EASE.out }}
                  >
                    <figure className="evidence">
                      <blockquote>
                        …<Highlight text={ev.quote} spans={matchSpan(ev)} />…
                      </blockquote>
                      {ev.doc && onJump && (
                        <figcaption>
                          来自：{docs.find((d) => d.id === ev.doc)?.title || ev.doc}
                          <button type="button" className="linkbtn" onClick={() => onJump(ev.doc, ev.start, ev.end)}>
                            在原文中查看 →
                          </button>
                        </figcaption>
                      )}
                    </figure>
                  </motion.div>
                )}
              </AnimatePresence>
            </li>
          );
        })}
      </ul>
      <p className="fineprint">“未在条款中找到”只代表程序没在文本里读到相关表述，不代表网站违法；可能写在了别的页面。</p>
    </div>
  );
}
