import { openSession, sleep } from "./lib/cdp.mjs";
const s = await openSession({ width: 1440, height: 1000 });
try {
  await s.open("http://127.0.0.1:4173/?demo=baidu", { theme: "geek", settle: 16000 });
  const geo = await s.evalJS(`(async () => {
    const t = document.querySelector('.reader__toggle');
    t?.scrollIntoView({ block: 'center' });
    await new Promise(r => setTimeout(r, 400));
    t?.click();
    await new Promise(r => setTimeout(r, 1200));
    const mark = document.querySelector('.reader__body mark.hl');
    mark.scrollIntoView({ block: 'center' });
    await new Promise(r => setTimeout(r, 500));
    const b = document.querySelector('.glens__ball').getBoundingClientRect();
    const m = mark.getClientRects()[0];
    return { bx: Math.round(b.left + b.width/2), by: Math.round(b.top + b.height/2), mx: Math.round(m.left + m.width/2), my: Math.round(m.top + m.height/2) };
  })()`);
  const g = geo.result.value;
  console.log("start", JSON.stringify(g));
  await s.send("Input.dispatchMouseEvent", { type: "mousePressed", x: g.bx, y: g.by, button: "left", buttons: 1, clickCount: 1 });
  for (let i = 1; i <= 16; i++) {
    const x = g.bx + (g.mx - g.bx) * i / 16, y = g.by + (g.my - g.by) * i / 16;
    await s.send("Input.dispatchMouseEvent", { type: "mouseMoved", x: Math.round(x), y: Math.round(y), button: "left", buttons: 1 });
    await sleep(18);
  }
  await s.send("Input.dispatchMouseEvent", { type: "mouseReleased", x: g.mx, y: g.my, button: "left", buttons: 0, clickCount: 1 });
  await sleep(1500);
  const fs2 = await import("node:fs"); fs2.writeFileSync("out/shots/lens-v4.png", await s.screenshot(null, {}));
  const out = await s.evalJS(`(() => ({ fx: document.querySelectorAll('canvas.glens__fx').length, hidden: document.querySelectorAll('mark.is-glens-hidden').length, hitFlag: document.querySelector('.glens__ball')?.dataset.hit, ball: (() => { const r = document.querySelector('.glens__ball').getBoundingClientRect(); return [Math.round(r.left), Math.round(r.top)]; })() }))()`);
  console.log("after", JSON.stringify(out.result.value));
} finally { s.close(); }
