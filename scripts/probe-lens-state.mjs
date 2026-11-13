import { openSession, sleep } from "./lib/cdp.mjs";
const s = await openSession({ width: 1440, height: 1000 });
try {
  await s.open("http://127.0.0.1:4173/?demo=baidu", { theme: "geek", settle: 16000 });
  const r = await s.evalJS(`(async () => {
    const t = document.querySelector('.reader__toggle');
    t?.scrollIntoView({ block: 'center' }); await new Promise(r => setTimeout(r, 400)); t?.click(); await new Promise(r => setTimeout(r, 1000));
    const mark = document.querySelector('.reader__body mark.hl');
    mark.scrollIntoView({ block: 'center' }); await new Promise(r => setTimeout(r, 400));
    const b = document.querySelector('.glens__ball').getBoundingClientRect();
    const m = mark.getClientRects()[0];
    return { reduce: matchMedia('(prefers-reduced-motion: reduce)').matches, live: document.querySelector('.glens__live')?.textContent?.slice(0, 40), rects: mark.getClientRects().length, b: [Math.round(b.left), Math.round(b.top)], m: [Math.round(m.left), Math.round(m.top), Math.round(m.width), Math.round(m.height)] };
  })()`);
  console.log(JSON.stringify(r.result.value));
} finally { s.close(); }
