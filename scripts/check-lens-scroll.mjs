import fs from "node:fs";
import { openSession, sleep } from "./lib/cdp.mjs";
const s = await openSession({ width: 1440, height: 1000 });
try {
  await s.open("http://127.0.0.1:4173/?demo=baidu", { theme: "geek", settle: 16000 });
  await s.evalJS(`(async () => { const t = document.querySelector('.reader__toggle'); t?.scrollIntoView({block:'center'}); await new Promise(r=>setTimeout(r,400)); t?.click(); await new Promise(r=>setTimeout(r,1000)); return true; })()`);
  await sleep(400);
  // 记录滚动前后：球在屏幕上的位置 + 球内画布是否变化
  const before = await s.evalJS(`(() => { const b = document.querySelector('.glens__ball'); const r = b.getBoundingClientRect(); const c = document.querySelector('.glens__mag canvas, .glens__mag'); return { y: Math.round(r.top), html: (c && c.innerHTML.length) || 0 }; })()`);
  fs.writeFileSync("out/shots/lens-scroll-1.png", await s.screenshot(null, {}));
  await s.evalJS(`window.scrollBy(0, 240)`);
  await sleep(500);
  const after = await s.evalJS(`(() => { const b = document.querySelector('.glens__ball'); const r = b.getBoundingClientRect(); return { y: Math.round(r.top) }; })()`);
  fs.writeFileSync("out/shots/lens-scroll-2.png", await s.screenshot(null, {}));
  console.log("ball screen y before/after:", before.result.value.y, after.result.value.y);
} finally { s.close(); }
