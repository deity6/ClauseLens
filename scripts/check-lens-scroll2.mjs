import fs from "node:fs";
import { openSession, sleep } from "./lib/cdp.mjs";
const s = await openSession({ width: 1440, height: 1000 });
try {
  await s.open("http://127.0.0.1:4173/?demo=baidu", { theme: "geek", settle: 16000 });
  await s.evalJS(`localStorage.removeItem('cl:lens')`);
  await s.open("http://127.0.0.1:4173/?demo=baidu", { theme: "geek", settle: 16000 });
  await s.evalJS(`(async () => { const t = document.querySelector('.reader__toggle'); t?.scrollIntoView({block:'center'}); await new Promise(r=>setTimeout(r,500)); t?.click(); await new Promise(r=>setTimeout(r,1200)); window.scrollBy(0,-120); await new Promise(r=>setTimeout(r,400)); return true; })()`);
  const grab = `(() => { const b = document.querySelector('.glens__ball'); const r = b.getBoundingClientRect(); return { top: Math.round(r.top), scrollY: Math.round(window.scrollY), fx: document.querySelectorAll('.glens__fx').length }; })()`;
  const a = await s.evalJS(grab);
  fs.writeFileSync("out/shots/lens-scroll-a.png", await s.screenshot(null, {}));
  await s.evalJS(`window.scrollBy(0, 200)`);
  await sleep(600);
  const b = await s.evalJS(grab);
  fs.writeFileSync("out/shots/lens-scroll-b.png", await s.screenshot(null, {}));
  console.log("A:", JSON.stringify(a.result.value), "B:", JSON.stringify(b.result.value));
} finally { s.close(); }
