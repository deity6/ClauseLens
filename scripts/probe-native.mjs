import { openSession, sleep } from "./lib/cdp.mjs";
const s = await openSession({ width: 1440, height: 1000 });
try {
  await s.open("http://127.0.0.1:4173/?demo=baidu", { theme: "geek", settle: 16000 });
  const geo = await s.evalJS(`(() => {
    const ball = document.querySelector('.glens__ball');
    window.__nativeDown = 0;
    ball.addEventListener('pointerdown', () => { window.__nativeDown++; }, { once: false });
    const br = ball.getBoundingClientRect();
    return { x: Math.round(br.left + br.width/2), y: Math.round(br.top + br.height/2) };
  })()`);
  const g = geo.result.value;
  await s.send("Input.dispatchMouseEvent", { type: "mousePressed", x: g.x, y: g.y, button: "left", buttons: 1, clickCount: 1 });
  await s.send("Input.dispatchMouseEvent", { type: "mouseReleased", x: g.x, y: g.y, button: "left", buttons: 0, clickCount: 1 });
  await sleep(400);
  const out = await s.evalJS(`({ native: window.__nativeDown, probe: window.__lensProbe || null })`);
  console.log(JSON.stringify(out.result.value));
} finally { s.close(); }
