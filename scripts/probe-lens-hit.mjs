import { openSession, sleep } from "./lib/cdp.mjs";
const s = await openSession({ width: 1440, height: 1000 });
try {
  await s.open("http://127.0.0.1:4173/?demo=baidu", { theme: "geek", settle: 16000 });
  await s.evalJS(`localStorage.removeItem('cl:lens')`);
  await s.open("http://127.0.0.1:4173/?demo=baidu", { theme: "geek", settle: 16000 });
  const r = await s.evalJS(`(async () => {
    const t = document.querySelector('.reader__toggle');
    t?.scrollIntoView({ block: 'center' });
    await new Promise(r => setTimeout(r, 500));
    t?.click();
    await new Promise(r => setTimeout(r, 1200));
    const mark = document.querySelector('.reader__body mark.hl');
    mark.scrollIntoView({ block: 'center' });
    await new Promise(r => setTimeout(r, 500));
    const ball = document.querySelector('.glens__ball');
    const mr = mark.getBoundingClientRect();
    const br = ball.getBoundingClientRect();
    // 直接把球移到 mark 正上方（一次移动，避免 offset 问题）
    const ev = (type, x, y) => ball.dispatchEvent(new PointerEvent(type, { bubbles: true, clientX: x, clientY: y, pointerId: 11, pointerType: 'mouse', button: 0, buttons: 1 }));
    ev('pointerdown', br.left + br.width/2, br.top + br.height/2);
    ev('pointermove', mr.left + mr.width/2, mr.top + mr.height/2);
    ev('pointerup', mr.left + mr.width/2, mr.top + mr.height/2);
    await new Promise(r => setTimeout(r, 1200));
    const nb = ball.getBoundingClientRect();
    const cx = nb.left + nb.width/2, cy = nb.top + nb.height/2;
    const stack = document.elementsFromPoint(cx, cy).slice(0, 6).map(e => e.tagName + '.' + (e.className || '').toString().slice(0, 30));
    return { ball: [Math.round(nb.left), Math.round(nb.top)], mark: [Math.round(mr.left), Math.round(mr.top), Math.round(mr.width), Math.round(mr.height)], center: [Math.round(cx), Math.round(cy)], stack, fx: document.querySelectorAll('canvas.glens__fx').length };
  })()`);
  console.log(JSON.stringify(r.result.value, null, 1));
} finally { s.close(); }
