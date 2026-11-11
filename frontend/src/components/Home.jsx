import { useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { detectMode } from "../lib/format.js";
import { DUR, EASE } from "../lib/motion.js";
import { IconArrow, IconLens, IconRead, IconSearchDoc, IconStamp } from "./Icons.jsx";

const EXAMPLES = [
  { label: "百度", q: "baidu.com" },
  { label: "淘宝", q: "taobao.com" },
  { label: "微信", q: "weixin.qq.com" },
  { label: "抖音", q: "douyin.com" },
  { label: "GitHub", q: "github.com" },
  { label: "B站", q: "bilibili.com" },
];

const STEPS = [
  { n: "01", icon: IconSearchDoc, title: "找到条款", text: "从网站页脚和常见位置翻出服务条款、隐私政策" },
  { n: "02", icon: IconRead, title: "逐条阅读", text: "一句句读完，标出共享数据、单方改条款这类要点" },
  { n: "03", icon: IconStamp, title: "标签和评分", text: "给出 A–E 等级，每个结论都能点开看原文" },
];

const HINT = {
  fuzzy: "整站查找条款",
  precise: "只分析这一页",
  invalid: "看起来不像网址，试试 baidu.com",
};

export default function Home({ onSubmit, initial = "" }) {
  const [v, setV] = useState(initial);
  const m = detectMode(v);
  const submit = (q) => {
    const s = (q ?? v).trim();
    if (!s || detectMode(s)?.mode === "invalid") return;
    onSubmit(s);
  };
  return (
    <section className="home">
      <div className="home__meta meta">
        <span>REPORT № —</span>
        <span>CLAUSE INSPECTION</span>
      </div>
      <h1 className="home__title">
        注册前，<br className="br-sm" />
        先看看你<em>同意了什么</em>
      </h1>
      <p className="home__sub">输入一个网站，替你读完条款，标出要留神的地方。</p>

      <form
        className="query"
        onSubmit={(e) => {
          e.preventDefault();
          submit();
        }}
      >
        <label className="query__field">
          <IconLens className="query__icon" width={22} height={22} />
          <span className="sr-only">网站或条款网址</span>
          <input
            value={v}
            onChange={(e) => setV(e.target.value)}
            placeholder="输入网站，比如 baidu.com 或条款页面的网址"
            autoFocus
            spellCheck={false}
            autoCapitalize="off"
            autoComplete="off"
            inputMode="url"
            enterKeyHint="search"
          />
          <button type="submit" className="query__go" disabled={!m || m.mode === "invalid"} aria-label="开始查看">
            <span>查看</span>
            <IconArrow />
          </button>
        </label>
        <div className="query__hint meta" aria-live="polite">
          <AnimatePresence mode="wait" initial={false}>
            {m && (
              <motion.span
                key={m.mode}
                className={`hint hint--${m.mode}`}
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -4 }}
                transition={{ duration: DUR.micro, ease: EASE.out }}
              >
                <i className="hint__dot" />
                {HINT[m.mode]}
                {m.domain && m.mode !== "invalid" ? <b> · {m.domain}</b> : null}
              </motion.span>
            )}
          </AnimatePresence>
        </div>
      </form>

      <div className="chips" role="list" aria-label="热门示例">
        <span className="meta chips__lead">试试</span>
        {EXAMPLES.map((x) => (
          <button key={x.q} role="listitem" type="button" className="chip" onClick={() => submit(x.q)}>
            {x.label}
          </button>
        ))}
      </div>

      <ol className="steps">
        {STEPS.map((s, i) => (
          <motion.li
            key={s.n}
            className="step"
            initial={{ opacity: 0, y: 14 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: DUR.enter, delay: 0.18 + i * 0.08, ease: EASE.enter }}
          >
            <span className="meta step__n">STEP {s.n}</span>
            <s.icon className="step__icon" width={26} height={26} />
            <h3>{s.title}</h3>
            <p>{s.text}</p>
          </motion.li>
        ))}
      </ol>
    </section>
  );
}
