import { openSession, sleep } from "./lib/cdp.mjs";
const s = await openSession({ width: 1440, height: 1000 });
try {
  await s.send("Runtime.enable");
  await s.open("http://127.0.0.1:4173/?demo=baidu", { theme: "geek", settle: 16000 });
  await s.evalJS(`(async () => { const t = document.querySelector('.reader__toggle'); t?.scrollIntoView({block:'center'}); await new Promise(r=>setTimeout(r,400)); t?.click(); await new Promise(r=>setTimeout(r,1000)); return true; })()`);
  const before = await s.evalJS(`(() => { const b = document.querySelector('.glens__ball'); const r = b.getBoundingClientRect(); return [Math.round(r.left), Math.round(r.top)]; })()`);
  const p = before.result.value;
  await s.send("Input.dispatchMouseEvent", { type: "mousePressed", x: p[0] + 56, y: p[1] + 56, button: "left", buttons: 1, clickCount: 1 });
  for (let i = 1; i <= 10; i++) { await s.send("Input.dispatchMouseEvent", { type: "mouseMoved", x: p[0] + 56 - i * 20, y: p[1] + 56 - i * 10, button: "left", buttons: 1 }); await sleep(16); }
  await s.send("Input.dispatchMouseEvent", { type: "mouseReleased", x: p[0] - 144, y: p[1] - 44, button: "left", buttons: 0, clickCount: 1 });
  await sleep(500);
  const after = await s.evalJS(`(() => { const b = document.querySelector('.glens__ball'); const r = b.getBoundingClientRect(); return [Math.round(r.left), Math.round(r.top)]; })()`);
  console.log("before", JSON.stringify(p), "after", JSON.stringify(after.result.value));
  console.log("errors:", JSON.stringify(s.errors().map(e => (e.exception?.description || e.text || '').split('\n')[0]).slice(0, 4)));
} finally { s.close(); }
