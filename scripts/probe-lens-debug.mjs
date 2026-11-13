import { openSession, sleep } from "./lib/cdp.mjs";
const s = await openSession({ width: 1440, height: 1000 });
try {
  await s.open("http://127.0.0.1:4173/?demo=baidu", { theme: "geek", settle: 16000 });
  const r = await s.evalJS(`(async () => {
    const t = document.querySelector('.reader__toggle');
    t?.scrollIntoView({ block: 'center' });
    await new Promise(r => setTimeout(r, 400));
    t?.click();
    await new Promise(r => setTimeout(r, 1200));
    const mark = document.querySelector('.reader__body mark.hl');
    mark.scrollIntoView({ block: 'center' });
    await new Promise(r => setTimeout(r, 400));
    const ball = document.querySelector('.glens__ball');
    const br = ball.getBoundingClientRect();
    const mr = mark.getBoundingClientRect();
    const ev = (type, x, y) => ball.dispatchEvent(new PointerEvent(type, { bubbles: true, clientX: x, clientY: y, pointerId: 13, pointerType: 'mouse', button: 0, buttons: 1 }));
    ev('pointerdown', br.left + br.width/2, br.top + br.height/2);
    ev('pointermove', mr.left + mr.width/2, mr.top + mr.height/2);
    ev('pointerup', mr.left + mr.width/2, mr.top + mr.height/2);
    await new Promise(r => setTimeout(r, 900));
    return { probe: window.__lensProbe || null, fx: document.querySelectorAll('canvas.glens__fx').length, hidden: document.querySelectorAll('mark.is-glens-hidden').length };
  })()`);
  console.log(JSON.stringify(r.result.value));
} finally { s.close(); }
