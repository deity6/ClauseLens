import fs from "node:fs";
import { openSession, sleep } from "./lib/cdp.mjs";
const s = await openSession({ width: 1440, height: 1000 });
try {
  await s.open("http://127.0.0.1:4173/?demo=baidu", { theme: "geek", settle: 16000 });
  await s.evalJS(`localStorage.removeItem('cl:lens')`);
  await s.open("http://127.0.0.1:4173/?demo=baidu", { theme: "geek", settle: 16000 });
  const res = await s.evalJS(`(async () => {
    const t = document.querySelector('.reader__toggle');
    t?.scrollIntoView({ block: 'center' });
    await new Promise(r => setTimeout(r, 500));
    t?.click();
    await new Promise(r => setTimeout(r, 1200));
    const mark = document.querySelector('.reader__body mark.hl');
    mark.scrollIntoView({ block: 'center' });
    await new Promise(r => setTimeout(r, 500));
    const ball = document.querySelector('.glens__ball');
    const br = ball.getBoundingClientRect();
    const mr = mark.getBoundingClientRect();
    const fire = (type, x, y) => ball.dispatchEvent(new PointerEvent(type, { bubbles: true, clientX: x, clientY: y, pointerId: 9, pointerType: 'mouse', button: 0, buttons: 1 }));
    const sx = br.left + br.width / 2, sy = br.top + br.height / 2;
    const tx = mr.left + mr.width / 2, ty = mr.top + mr.height / 2;
    fire('pointerdown', sx, sy);
    for (let i = 1; i <= 14; i++) { fire('pointermove', sx + (tx - sx) * i / 14, sy + (ty - sy) * i / 14); await new Promise(r => setTimeout(r, 16)); }
    fire('pointerup', tx, ty);
    await new Promise(r => setTimeout(r, 1500));
    return {
      ball: [Math.round(ball.getBoundingClientRect().left), Math.round(ball.getBoundingClientRect().top), Math.round(ball.getBoundingClientRect().width)],
      hiddenMark: document.querySelectorAll('mark.is-glens-hidden').length,
      fx: document.querySelectorAll('canvas.glens__fx').length,
      cloneTranslated: [...document.querySelectorAll('.glens__mag mark.hl')].some(m => m.textContent.length > 40),
    };
  })()`);
  console.log(JSON.stringify(res.result.value));
  fs.writeFileSync("out/shots/lens-v3.png", await s.screenshot(null, {}));
} finally { s.close(); }
