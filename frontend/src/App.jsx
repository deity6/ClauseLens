import { useCallback, useEffect, useState } from "react";
import { AnimatePresence, motion, MotionConfig } from "motion/react";
import { loadTaxonomy } from "./lib/taxonomy.js";
import { useAnalysis } from "./lib/useAnalysis.js";
import { pageVariants } from "./lib/motion.js";
import Home from "./components/Home.jsx";
import Waiting from "./components/Waiting.jsx";
import Result from "./components/Result.jsx";
import DevPanel from "./components/DevPanel.jsx";
import ThemeSwitch from "./components/ThemeSwitch.jsx";
import DotsBackdrop from "./components/DotsBackdrop.jsx";
import RidgeFoot from "./components/RidgeFoot.jsx";
import { useTheme } from "./lib/theme.js";
import { IconLens } from "./components/Icons.jsx";

function readURL() {
  const p = new URLSearchParams(location.search);
  const demo = p.get("demo");
  if (demo) return { kind: "demo", name: demo, q: `${demo}.com` };
  const q = p.get("q");
  if (q) return { kind: "sse", q };
  return null;
}

function writeURL(src) {
  const u = new URL(location.href);
  u.searchParams.delete("q");
  u.searchParams.delete("demo");
  if (src?.kind === "demo") u.searchParams.set("demo", src.name);
  else if (src?.kind === "sse") u.searchParams.set("q", src.q);
  history.pushState(null, "", u);
}

export default function App() {
  const [source, setSource] = useState(readURL);
  const [taxonomy, setTaxonomy] = useState(null);
  const theme = useTheme();
  const offline = source?.kind === "demo";
  const { state, cancel } = useAnalysis(source, taxonomy);

  useEffect(() => {
    loadTaxonomy({ offline: readURL()?.kind === "demo" }).then(setTaxonomy);
    const onPop = () => setSource(readURL());
    addEventListener("popstate", onPop);
    return () => removeEventListener("popstate", onPop);
  }, []);

  const go = useCallback((src) => {
    writeURL(src);
    setSource(src);
    scrollTo({ top: 0 });
  }, []);

  const view = !source ? "home" : state.result ? "result" : "waiting";

  useEffect(() => {
    if (view === "result") scrollTo({ top: 0 });
  }, [view]);

  return (
    <MotionConfig reducedMotion="user">
      {/* 点阵背景只在主题 B 挂载：A 主题的底纹是 CSS 画的，没必要养一块 canvas */}
      {theme === "geek" && <DotsBackdrop />}

      <div className="shell">
        <nav className="topbar">
          <button className="brand" onClick={() => go(null)} aria-label="回到首页">
            <IconLens width={20} height={20} />
            <span className="brand__zh">条款透镜</span>
            <span className="brand__en meta">CLAUSELENS</span>
          </button>
          <div className="topbar__right">
            {offline && <span className="meta topbar__demo">DEMO · 演示数据，不连接服务器</span>}
            <ThemeSwitch />
          </div>
        </nav>

        <main className="stage">
          <AnimatePresence mode="wait">
            <motion.div key={view} variants={pageVariants} initial="initial" animate="animate" exit="exit">
              {view === "home" && <Home onSubmit={(q) => go({ kind: "sse", q })} />}
              {view === "waiting" && (
                <Waiting
                  query={source.q}
                  state={state}
                  taxonomy={taxonomy}
                  onCancel={() => {
                    cancel();
                    go(null);
                  }}
                  onRetry={() => setSource({ ...source, nonce: (source.nonce || 0) + 1 })}
                  onHome={() => go(null)}
                />
              )}
              {view === "result" && taxonomy && <Result result={state.result} taxonomy={taxonomy} offline={offline} onAgain={() => go(null)} />}
            </motion.div>
          </AnimatePresence>
        </main>

        <RidgeFoot />
        <footer className="disclaimer">
          <span className="meta">CLAUSELENS · 条款透镜</span>
          <p>结果由程序自动分析，仅供参考，不构成法律意见。</p>
        </footer>
      </div>

      {/* 设计调试面板：只有 ?dev=1 才挂载，正常访问不产生任何 DOM / 样式变化 */}
      {new URLSearchParams(location.search).get("dev") === "1" && <DevPanel />}
    </MotionConfig>
  );
}
