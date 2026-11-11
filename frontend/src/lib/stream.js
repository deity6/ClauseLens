// 分析事件源：真实 SSE 或演示回放。两者都只产出 contract.md §3 里的事件，
// 等待态只认这些事件，不自己编进度。
// 样例含原文全文（几百 KB），按需加载，不进主包
const DEMOS = {
  baidu: () => import("../data/sample-baidu.json"),
  github: () => import("../data/sample-github.json"),
};

const EVENTS = ["stage", "document", "tag", "result", "error"];

// 真实 SSE。返回关闭函数。
export function openSSE(q, onEvent) {
  const es = new EventSource(`/api/analyze?q=${encodeURIComponent(q)}`);
  let done = false;
  for (const ev of EVENTS) {
    es.addEventListener(ev, (e) => {
      let data = null;
      try {
        data = JSON.parse(e.data);
      } catch {
        return;
      }
      if (ev === "result" || ev === "error") {
        done = true;
        es.close();
      }
      onEvent(ev, data);
    });
  }
  es.onerror = () => {
    if (done) return;
    // EventSource 断线后会自动重连并重新跑一遍分析，这里直接收口为错误态
    done = true;
    es.close();
    onEvent("error", { code: "network", message_zh: "连不上服务器，请确认服务已启动。" });
  };
  return () => {
    done = true;
    es.close();
  };
}

// 演示：按真实后端的事件顺序，用样例结果合成一条事件流，并给出近似真实的到达间隔。
export function demoEvents(sample) {
  const out = [];
  let t = 300;
  const push = (gap, ev, data) => {
    t += gap;
    out.push([t, ev, data]);
  };
  const domain = sample.query.domain;
  push(0, "stage", { stage: "resolve", message: `正在找到 ${domain}`, query: sample.query });
  push(1100, "stage", { stage: "discover", found: sample.documents.length });
  for (const [i, d] of sample.documents.entries()) {
    push(700, "stage", { stage: "fetch", message: `正在打开「${d.title}」`, index: i + 1 });
    push(650, "document", { title: d.title, type: d.type, chars: d.chars, read_minutes: d.read_minutes });
  }
  push(500, "stage", { stage: "extract" });
  push(600, "stage", { stage: "analyze", progress: 0.3, clauses: sample.stats.clauses });
  for (const tag of sample.tags) {
    push(260 + ((tag.id.length * 37) % 180), "tag", { id: tag.id, polarity: tag.__polarity || null });
  }
  push(500, "stage", { stage: "analyze", progress: 1.0 });
  push(400, "stage", { stage: "score" });
  push(1500, "result", sample);
  return out;
}

export function openDemo(name, onEvent, taxonomy) {
  const load = DEMOS[name];
  if (!load) {
    onEvent("error", { code: "not_found", message_zh: `没有叫 ${name} 的演示样例，试试 ?demo=baidu 或 ?demo=github。` });
    return () => {};
  }
  let timers = [];
  let closed = false;
  load().then((mod) => {
    if (closed) return;
    timers = demoEvents(mod.default).map(([at, ev, data]) =>
      setTimeout(() => {
        if (ev === "tag" && !data.polarity) data = { ...data, polarity: taxonomy?.byId[data.id]?.polarity || "neutral" };
        onEvent(ev, data);
      }, at)
    );
  });
  return () => {
    closed = true;
    timers.forEach(clearTimeout);
  };
}

// 有缓存时后端会在几十毫秒内吐完所有事件，等待态一闪而过、读不出过程。
// 节拍器只给“显示”设最小间隔，不改变事件的顺序和内容，也不凭空制造事件。
const MIN_GAP = { stage: 420, document: 520, tag: 150, result: 900, error: 0 };

export function pace(onEvent) {
  const q = [];
  let timer = null;
  let last = 0;
  let closed = false;
  const pump = () => {
    timer = null;
    if (closed || !q.length) return;
    const [ev, data] = q[0];
    const wait = Math.max(0, last + MIN_GAP[ev] - performance.now());
    if (wait > 0) {
      timer = setTimeout(pump, wait);
      return;
    }
    q.shift();
    last = performance.now();
    onEvent(ev, data);
    if (q.length) timer = setTimeout(pump, 0);
  };
  return {
    push(ev, data) {
      q.push([ev, data]);
      if (!timer) pump();
    },
    close() {
      closed = true;
      clearTimeout(timer);
    },
  };
}
