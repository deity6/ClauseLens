#!/usr/bin/env node
// 本地截图（CDP，无第三方依赖：Node 24 自带 WebSocket）
//
//   node scripts/shot.mjs <url> <out.png> [--w=1440] [--h=900] [--wait=1200] [--full] [--theme=geek]
//
// 用途：改完前端当场看一眼形态（AGENTS §5.5：别只信 build 退出码）。
// 走 ~/.dsh/tools/browser-launcher.mjs 的固定 profile 池，无头实例随进程退出。

import fs from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";
const { launchBrowser } = await import(pathToFileURL("C:/Users/Deity/.dsh/tools/browser-launcher.mjs").href);

const argv = process.argv.slice(2);
const pos = argv.filter((a) => !a.startsWith("--"));
const flag = (name, def) => {
  const hit = argv.find((a) => a.startsWith(`--${name}=`));
  return hit ? hit.split("=").slice(1).join("=") : def;
};
const url = pos[0];
const out = pos[1] || "shot.png";
const W = Number(flag("w", 1440));
const H = Number(flag("h", 900));
const WAIT = Number(flag("wait", 1200));
// 固定 9333 会和同时在跑的另一个截图脚本抢端口（scan-doc 那轮撞过两次）
const PORT = 9400 + Math.floor(Math.random() * 400);
const FULL = argv.includes("--full");
const THEME = flag("theme", "");
const SCROLL = Number(flag("scroll", 0));
if (!url) {
  console.error("usage: node scripts/shot.mjs <url> <out.png> [--w --h --wait --full --theme --scroll]");
  process.exit(2);
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const b = launchBrowser({ url: "about:blank", headless: true, port: PORT });
let ws;
try {
  // 等 CDP 端口活
  let ver = null;
  for (let i = 0; i < 100 && !ver; i++) {
    try {
      ver = await (await fetch(`http://127.0.0.1:${PORT}/json/version`)).json();
    } catch {
      await sleep(250);
    }
  }
  if (!ver) throw new Error("CDP 端口没起来");
  const list = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json();
  const page = list.find((t) => t.type === "page");
  if (!page) throw new Error("没有 page target");

  ws = new WebSocket(page.webSocketDebuggerUrl);
  await new Promise((res, rej) => {
    ws.addEventListener("open", res, { once: true });
    ws.addEventListener("error", rej, { once: true });
  });

  let id = 0;
  const pending = new Map();
  ws.addEventListener("message", (ev) => {
    const msg = JSON.parse(ev.data);
    if (msg.id && pending.has(msg.id)) {
      const { res, rej } = pending.get(msg.id);
      pending.delete(msg.id);
      msg.error ? rej(new Error(JSON.stringify(msg.error))) : res(msg.result);
    }
  });
  const send = (method, params = {}) =>
    new Promise((res, rej) => {
      const mid = ++id;
      pending.set(mid, { res, rej });
      ws.send(JSON.stringify({ id: mid, method, params }));
    });

  await send("Page.enable");
  await send("Runtime.enable");
  await send("Emulation.setDeviceMetricsOverride", { width: W, height: H, deviceScaleFactor: 1, mobile: false });
  await send("Page.navigate", { url });

  // 等 load + 额外等待（字体、动效、SSE 首屏）
  for (let i = 0; i < 100; i++) {
    const { result } = await send("Runtime.evaluate", { expression: "document.readyState", returnByValue: true });
    if (result.value === "complete") break;
    await sleep(100);
  }
  if (THEME) {
    // 走真实路径：写 localStorage（index.html 的内联脚本首帧就认它）再重载，
    // 这样 React 状态、html::after 这些也跟着对，不会出现「DOM 换了但开关还显示旧主题」。
    await send("Runtime.evaluate", {
      expression: `localStorage.setItem('cl:theme', ${JSON.stringify(THEME)})`,
    });
    await send("Page.reload", { ignoreCache: true });
    await sleep(500); // 等新文档真的开始加载；否则这一轮会立刻读到旧文档的 readyState=complete
    for (let i = 0; i < 100; i++) {
      const { result } = await send("Runtime.evaluate", { expression: "document.readyState", returnByValue: true });
      if (result.value === "complete") break;
      await sleep(100);
    }
  }
  if (SCROLL) {
    await send("Runtime.evaluate", { expression: `window.scrollTo(0, ${SCROLL})` });
  }
  // 结果页分区是进场动画：整页截图前先滚一遍，否则首屏以下会是空的
  if (argv.includes("--through")) {
    await send("Runtime.evaluate", {
      expression: `(async () => { const H = document.body.scrollHeight; for (let y = 0; y < H; y += 360) { window.scrollTo(0, y); await new Promise(r => setTimeout(r, 90)); } window.scrollTo(0, H); await new Promise(r => setTimeout(r, 260)); window.scrollTo(0, 0); await new Promise(r => setTimeout(r, 420)); return H; })()`,
      awaitPromise: true,
    });
  }
  await sleep(WAIT);

  const params = { format: "png", captureBeyondViewport: FULL };
  if (FULL) {
    const { cssContentSize } = await send("Page.getLayoutMetrics");
    params.clip = { x: 0, y: 0, width: W, height: Math.min(cssContentSize.height, 12000), scale: 1 };
  }
  const shot = await send("Page.captureScreenshot", params);
  fs.mkdirSync(path.dirname(path.resolve(out)), { recursive: true });
  fs.writeFileSync(out, Buffer.from(shot.data, "base64"));
  console.log(`OK ${out} ${W}x${H}${FULL ? " (full)" : ""}`);
} catch (e) {
  console.error("SHOT FAILED:", e.message);
  process.exitCode = 1;
} finally {
  try {
    ws?.close();
  } catch {}
  b.close();
}