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
    await new Promise(r => setTimeout(r, 500));
    const mr = mark.getBoundingClientRect();
    const cx = mr.left + 40, cy = mr.top + mr.height / 2;
    const el = document.elementFromPoint(cx, cy);
    const cs = getComputedStyle(mark);
    return {
      markRect: [Math.round(mr.left), Math.round(mr.top), Math.round(mr.width), Math.round(mr.height)],
      at: el && el.tagName + '.' + (el.className || '').toString().slice(0, 40),
      markPE: cs.pointerEvents,
      markDisplay: cs.display,
      markInline: cs.display === 'inline' || cs.display === 'inline-block',
      bodyPE: getComputedStyle(document.querySelector('.reader__body')).pointerEvents,
    };
  })()`);
  console.log(JSON.stringify(r.result.value, null, 1));
} finally { s.close(); }
