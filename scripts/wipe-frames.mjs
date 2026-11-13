#!/usr/bin/env node
// 主题转场逐帧录像：点右上角开关，用 CDP screencast 按浏览器真实帧率抓 JPEG，存成序列帧。
//
//   node scripts/wipe-frames.mjs <url> <outDir> [--from=light] [--to=geek] [--w=1440] [--h=900] [--ms=1600]
//
// 为什么用 screencast 而不是「定时截屏」：Page.captureScreenshot 单张要 100–200ms，
// 会把 1.1 秒的转场采样成 3–4 张，时间标签全是错的；screencast 是浏览器推帧，时间戳可信。
// 输出：<outDir>/f###-<t>ms.jpg（转场开始前 1 帧 + 转场期间所有帧）。

import fs from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";
const { launchBrowser } = await import(pathToFileURL("C:/Users/Deity/.dsh/tools/browser-launcher.mjs").href);

const argv = process.argv.slice(2);
const pos = argv.filter((a) => !a.startsWith("--"));
const flag = (n, d) => {
  const hit = argv.find((a) => a.startsWith(`--${n}=`));
  return hit ? hit.split("=").slice(1).join("=") : d;
};
const url = pos[0] || "http://127.0.0.1:5177/";
const outDir = pos[1] || "out/shots/wipe";
const FROM = flag("from", "light");
const TO = flag("to", "geek");
const W = Number(flag("w", 1440));
const H = Number(flag("h", 900));
const MS = Number(flag("ms", 1600));
const PORT = 9400 + Math.floor(Math.random() * 400);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const b = launchBrowser({ url: "about:blank", headless: true, port: PORT });
let ws;
try {
  let ver = null;
  for (let i = 0; i < 100 && !ver; i++) {
    try {
      ver = await (await fetch(`http://127.0.0.1:${PORT}/json/version`)).json();
    } catch {
      await sleep(250);
    }
  }
  const list = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json();
  const page = list.find((t) => t.type === "page");
  ws = new WebSocket(page.webSocketDebuggerUrl);
  await new Promise((res, rej) => {
    ws.addEventListener("open", res, { once: true });
    ws.addEventListener("error", rej, { once: true });
  });
  let id = 0;
  const pending = new Map();
  const frames = [];
  let recording = false;
  ws.addEventListener("message", (ev) => {
    const m = JSON.parse(ev.data);
    if (m.method === "Page.screencastFrame") {
      // 必须立刻 ack，否则 Chrome 会掐掉推流（上一版就是攒到最后才 ack，只收到 3 帧）
      ws.send(JSON.stringify({ id: ++id, method: "Page.screencastFrameAck", params: { sessionId: m.params.sessionId } }));
      if (recording) frames.push({ data: m.params.data, at: Date.now() });
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
  const evalJS = (expression) => send("Runtime.evaluate", { expression, returnByValue: true });

  await send("Page.enable");
  await send("Runtime.enable");
  await send("Emulation.setDeviceMetricsOverride", { width: W, height: H, deviceScaleFactor: 1, mobile: false });
  await send("Page.navigate", { url });
  await evalJS(`localStorage.setItem('cl:theme', ${JSON.stringify(FROM)})`);
  await send("Page.reload", { ignoreCache: true });
  for (let i = 0; i < 100; i++) {
    const { result } = await evalJS("document.readyState");
    if (result.value === "complete") break;
    await sleep(100);
  }
  await sleep(1500);
  fs.mkdirSync(outDir, { recursive: true });
  for (const f of fs.readdirSync(outDir)) if (/^f\d+.*\.jpg$/.test(f)) fs.unlinkSync(path.join(outDir, f));

  await send("Page.startScreencast", { format: "jpeg", quality: 82, everyNthFrame: 1, maxWidth: W, maxHeight: H });
  await sleep(260);
  recording = true;
  const t0 = Date.now();
  await evalJS(`document.querySelector('.tswitch__opt[title=${JSON.stringify(TO === "geek" ? "切换到点阵主题" : "切换到纸主题")}]')?.click()`);
  await sleep(MS);
  recording = false;
  await send("Page.stopScreencast");

  let n = 0;
  for (const f of frames) {
    const at = f.at - t0;
    if (at < -260) continue;
    const name = `f${String(n++).padStart(3, "0")}-${String(at).padStart(5, "0")}ms.jpg`;
    fs.writeFileSync(path.join(outDir, name), Buffer.from(f.data, "base64"));
  }
  console.log(`OK ${outDir}/  ${n} frames, ${MS}ms window`);
} catch (e) {
  console.error("FAILED:", e.message);
  process.exitCode = 1;
} finally {
  try {
    ws?.close();
  } catch {}
  b.close();
}