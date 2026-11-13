import fs from "node:fs";
import { openSession, sleep } from "./lib/cdp.mjs";
const s = await openSession({ width: 1440, height: 1000 });
try {
  await s.open("http://127.0.0.1:4173/?demo=baidu", { theme: "geek", settle: 16000 });
  await s.evalJS(`localStorage.removeItem('cl:lens')`);
  await s.open("http://127.0.0.1:4173/?demo=baidu", { theme: "geek", settle: 16000 });
  const geo = await s.evalJS(`(async () => {
    document.getElementById('reader')?.scrollIntoView({ block: 'center' });
    await new Promise(r => setTimeout(r, 600));
    const t = document.querySelector('.reader__toggle'); t?.click();
    await new Promise(r => setTimeout(r, 1200));
    const mark = document.querySelector('.reader__body mark.hl');
    mark.scrollIntoView({ block: 'center' });
    await new Promise(r => setTimeout(r, 500));
    const b = document.querySelector('.glens__ball').getBoundingClientRect();
    const m = mark.getClientRects()[0];
    return { bx: Math.round(b.left + b.width/2), by: Math.round(b.top + b.height/2), mx: Math.round(m.left + m.width/2), my: Math.round(m.top + m.height/2), ballVisible: b.top > 0 && b.top < innerHeight };
  })()`);
  const g = geo.result.value;
  console.log("geo", JSON.stringify(g));
  fs.writeFileSync("out/shots/lens-at-reader.png", await s.screenshot(null, {}));
  if (g.ballVisible) {
    await s.send("Input.dispatchMouseEvent", { type: "mousePressed", x: g.bx, y: g.by, button: "left", buttons: 1, clickCount: 1 });
    for (let i = 1; i <= 14; i++) { await s.send("Input.dispatchMouseEvent", { type: "mouseMoved", x: Math.round(g.bx + (g.mx - g.bx) * i / 14), y: Math.round(g.by + (g.my - g.by) * i / 14), button: "left", buttons: 1 }); await sleep(18); }
    await s.send("Input.dispatchMouseEvent", { type: "mouseReleased", x: g.mx, y: g.my, button: "left", buttons: 0, clickCount: 1 });
    await sleep(1200);
    const st = await s.evalJS(`(() => { const cv = document.querySelector('canvas.glens__fx'); return { fx: !!cv, cvTop: cv && Math.round(cv.getBoundingClientRect().top), host: cv && cv.parentElement.className }; })()`);
    console.log("hit", JSON.stringify(st.result.value));
    await s.evalJS(`window.scrollBy(0, 120)`);
    await sleep(400);
    const st2 = await s.evalJS(`(() => { const cv = document.querySelector('canvas.glens__fx'); return { cvTop: cv && Math.round(cv.getBoundingClientRect().top) }; })()`);
    console.log("after scroll", JSON.stringify(st2.result.value));
    fs.writeFileSync("out/shots/lens-hit-final.png", await s.screenshot(null, {}));
  }
} finally { s.close(); }
