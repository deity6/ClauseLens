import fs from "node:fs";
import { openSession, sleep } from "./lib/cdp.mjs";
const s = await openSession({ width: 1440, height: 1000 });
try {
  await s.open("http://127.0.0.1:4173/?demo=baidu", { theme: "geek", settle: 16000 });
  await s.evalJS(`localStorage.removeItem('cl:lens')`);
  await s.open("http://127.0.0.1:4173/?demo=baidu", { theme: "geek", settle: 16000 });
  await s.evalJS(`(async () => { const t = document.querySelector('.reader__toggle'); t?.scrollIntoView({block:'center'}); await new Promise(r=>setTimeout(r,500)); t?.click(); await new Promise(r=>setTimeout(r,1200)); return true; })()`);
  await sleep(600);
  const g = `(() => { const b = document.querySelector('.glens__ball'); const r = b.getBoundingClientRect(); return { x: Math.round(r.left), y: Math.round(r.top), w: Math.round(r.width) }; })()`;
  const a = await s.evalJS(g);
  fs.writeFileSync("out/shots/lens-fix-a.png", await s.screenshot(null, {}));
  await s.evalJS(`window.scrollBy(0, 220)`);
  await sleep(500);
  const b = await s.evalJS(g);
  fs.writeFileSync("out/shots/lens-fix-b.png", await s.screenshot(null, {}));
  console.log("ball:", JSON.stringify(a.result.value), "after scroll:", JSON.stringify(b.result.value));
} finally { s.close(); }
