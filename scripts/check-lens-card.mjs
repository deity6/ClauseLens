import fs from "node:fs";
import { openSession, sleep } from "./lib/cdp.mjs";
const s = await openSession({ width: 1440, height: 1000 });
try {
  await s.open("http://127.0.0.1:4173/?demo=baidu", { theme: "geek", settle: 16000 });
  const ok = await s.evalJS(`(async () => {
    const t = document.querySelector('.reader__toggle');
    t?.scrollIntoView({ block: 'center' });
    await new Promise(r => setTimeout(r, 500));
    t?.click();
    await new Promise(r => setTimeout(r, 1200));
    const mark = document.querySelector('.reader__body mark.hl');
    if (!mark) return 'no mark';
    mark.scrollIntoView({ block: 'center' });
    await new Promise(r => setTimeout(r, 600));
    const r = mark.getBoundingClientRect();
    const ball = document.querySelector('.glens__ball');
    const br = ball.getBoundingClientRect();
    // 把球拖到高亮句上
    const fire = (type, x, y) => ball.dispatchEvent(new PointerEvent(type, { bubbles: true, clientX: x, clientY: y, pointerId: 1, pointerType: 'mouse', button: 0, buttons: 1 }));
    const sx = br.left + br.width / 2, sy = br.top + br.height / 2;
    const tx = r.left + r.width / 2, ty = r.top + r.height / 2;
    fire('pointerdown', sx, sy);
    for (let i = 1; i <= 12; i++) { fire('pointermove', sx + (tx - sx) * i / 12, sy + (ty - sy) * i / 12); await new Promise(res => setTimeout(res, 16)); }
    fire('pointerup', tx, ty);
    await new Promise(res => setTimeout(res, 1400));
    return { card: !!document.querySelector('.glens__card'), text: document.querySelector('.glens__card-body')?.textContent?.slice(0, 60) };
  })()`);
  console.log(JSON.stringify(ok.result.value));
  await sleep(300);
  fs.writeFileSync("out/shots/lens-card.png", await s.screenshot(null, {}));
} finally { s.close(); }
