import { openSession, sleep } from "./lib/cdp.mjs";
const s = await openSession({ width: 1440, height: 1000 });
try {
  await s.open("http://127.0.0.1:4173/?demo=baidu", { theme: "geek", settle: 16000 });
  await s.evalJS(`(async () => { const t = document.querySelector('.reader__toggle'); t?.scrollIntoView({block:'center'}); await new Promise(r=>setTimeout(r,400)); t?.click(); await new Promise(r=>setTimeout(r,900)); return true; })()`);
  const info = await s.evalJS(`(() => {
    const ball = document.querySelector('.glens__ball');
    const ev = (type, x, y) => ball.dispatchEvent(new PointerEvent(type, { bubbles: true, clientX: x, clientY: y, pointerId: 3, pointerType: 'mouse', button: 0, buttons: 1 }));
    const r = ball.getBoundingClientRect();
    ev('pointerdown', r.left + 20, r.top + 20);
    ev('pointerup', r.left + 40, r.top + 40);
    const ae = document.activeElement;
    const cs = getComputedStyle(ball);
    return {
      active: ae && (ae.className || ae.tagName),
      ballOutline: cs.outlineStyle + ' ' + cs.outlineWidth + ' ' + cs.outlineColor,
      ballRadius: cs.borderRadius,
      focusVisible: ball.matches(':focus-visible'),
      focus: ball.matches(':focus'),
    };
  })()`);
  console.log(JSON.stringify(info.result.value));
} finally { s.close(); }
