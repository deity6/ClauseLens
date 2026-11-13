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
    await new Promise(r => setTimeout(r, 400));
    const br = document.querySelector('.glens__ball').getBoundingClientRect();
    const mr = mark.getBoundingClientRect();
    return { ball: [Math.round(br.left + br.width/2), Math.round(br.top + br.height/2)], mark: [Math.round(mr.left + mr.width/2), Math.round(mr.top + mr.height/2)] };
  })()`);
  const g = geo.result.value;
  const mouse = (type, x, y, buttons = 1) => s.send("Input.dispatchMouseEvent", { type, x, y, button: type === "mouseReleased" ? "left" : "left", buttons, clickCount: 1 });
  await mouse("mousePressed", g.ball[0], g.ball[1]);
  for (let i = 1; i <= 18; i++) {
    await mouse("mouseMoved", g.ball[0] + (g.mark[0] - g.ball[0]) * i / 18, g.ball[1] + (g.mark[1] - g.ball[1]) * i / 18);
    await sleep(16);
  }
  await mouse("mouseReleased", g.mark[0], g.mark[1], 0);
  await sleep(1200);
  const out = await s.evalJS(`({ probe: window.__lensProbe || null, fx: document.querySelectorAll('canvas.glens__fx').length, hidden: document.querySelectorAll('mark.is-glens-hidden').length })`);
  console.log(JSON.stringify(out.result.value));
} finally { s.close(); }
