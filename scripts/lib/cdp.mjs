// CDP 会话小工具（截图/录像脚本共用）
// 只用 Node 24 自带的 WebSocket + fetch，不引第三方依赖。
import { pathToFileURL } from "node:url";

const { launchBrowser } = await import(pathToFileURL("C:/Users/Deity/.dsh/tools/browser-launcher.mjs").href);

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

export { sleep };

/** 起一个无头 Edge 并连上它的 page target。 */
export async function openSession({ width = 1440, height = 900 } = {}) {
  const port = 9400 + Math.floor(Math.random() * 400);
  const b = launchBrowser({ url: "about:blank", headless: true, port });
  let ver = null;
  for (let i = 0; i < 100 && !ver; i++) {
    try {
      ver = await (await fetch(`http://127.0.0.1:${port}/json/version`)).json();
    } catch {
      await sleep(250);
    }
  }
  if (!ver) throw new Error("CDP 端口没起来");
  const list = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
  const page = list.find((t) => t.type === "page");
  if (!page) throw new Error("没有 page target");

  const ws = new WebSocket(page.webSocketDebuggerUrl);
  await new Promise((res, rej) => {
    ws.addEventListener("open", res, { once: true });
    ws.addEventListener("error", rej, { once: true });
  });

  let id = 0;
  const pending = new Map();
  const onFrame = [];
  const exceptions = [];
  ws.addEventListener("message", (ev) => {
    const m = JSON.parse(ev.data);
    if (m.method === "Runtime.exceptionThrown") {
      exceptions.push(m.params.exceptionDetails);
      return;
    }
    if (m.method === "Page.screencastFrame") {
      ws.send(JSON.stringify({ id: ++id, method: "Page.screencastFrameAck", params: { sessionId: m.params.sessionId } }));
      onFrame.forEach((fn) => fn(m.params));
      return;
    }
    if (m.id && pending.has(m.id)) {
      const { res, rej } = pending.get(m.id);
      pending.delete(m.id);
      m.error ? rej(new Error(JSON.stringify(m.error))) : res(m.result);
    }
  });

  const send = (method, params = {}) =>
    new Promise((res, rej) => {
      const mid = ++id;
      pending.set(mid, { res, rej });
      ws.send(JSON.stringify({ id: mid, method, params }));
    });
  const evalJS = (expression) => send("Runtime.evaluate", { expression, returnByValue: true, awaitPromise: true });

  await send("Page.enable");
  await send("Runtime.enable");
  await send("Emulation.setDeviceMetricsOverride", { width, height, deviceScaleFactor: 1, mobile: false });

  /** 打开页面（可带主题），等到 load 后再多等 settle 毫秒。 */
  const open = async (url, { theme, settle = 1200, scrollThrough = false } = {}) => {
    await send("Page.navigate", { url });
    if (theme) {
      await evalJS(`localStorage.setItem('cl:theme', ${JSON.stringify(theme)})`);
      await send("Page.reload", { ignoreCache: false });
    }
    for (let i = 0; i < 120; i++) {
      const { result } = await evalJS("document.readyState");
      if (result.value === "complete") break;
      await sleep(100);
    }
    if (settle) await sleep(settle);
    // 结果页的分区用 whileInView 才淡入：整页截图前必须先滚一遍，否则 02/03/04 是空的
    if (scrollThrough) {
      await evalJS(`(async () => {
        const H = document.body.scrollHeight;
        for (let y = 0; y < H; y += 360) { window.scrollTo(0, y); await new Promise(r => setTimeout(r, 90)); }
        window.scrollTo(0, H);
        await new Promise(r => setTimeout(r, 260));
        window.scrollTo(0, 0);
        await new Promise(r => setTimeout(r, 420));
        return H;
      })()`);
    }
  };

  const screenshot = async (file, { full = false } = {}) => {
    const params = { format: "png", captureBeyondViewport: full };
    if (full) {
      const { cssContentSize } = await send("Page.getLayoutMetrics");
      params.clip = { x: 0, y: 0, width, height: Math.min(cssContentSize.height, 12000), scale: 1 };
    }
    const s = await send("Page.captureScreenshot", params);
    return Buffer.from(s.data, "base64");
  };

  return {
    send,
    evalJS,
    open,
    screenshot,
    onFrame: (fn) => onFrame.push(fn),
    errors: () => exceptions,
    close: () => {
      try {
        ws.close();
      } catch {}
      b.close();
    },
  };
}