import { openSession } from "./lib/cdp.mjs";
const s = await openSession({ width: 1440, height: 1000 });
try {
  await s.open("http://127.0.0.1:4173/?demo=baidu", { theme: "geek", settle: 16000 });
  const r = await s.evalJS(`(async () => {
    const t = document.querySelector('.reader__toggle');
    t?.scrollIntoView({ block: 'center' }); await new Promise(r => setTimeout(r, 400)); t?.click(); await new Promise(r => setTimeout(r, 1200));
    const ball = document.querySelector('.glens__ball');
    const br = ball.getBoundingClientRect();
    const cx = Math.round(br.left + br.width/2), cy = Math.round(br.top + br.height/2);
    const top = document.elementFromPoint(cx, cy);
    const cs = getComputedStyle(ball);
    return { rect: [Math.round(br.left), Math.round(br.top), Math.round(br.width)], center: [cx, cy], top: top && top.className, pe: cs.pointerEvents, vis: cs.visibility, op: cs.opacity, z: cs.zIndex };
  })()`);
  console.log(JSON.stringify(r.result.value));
} finally { s.close(); }
