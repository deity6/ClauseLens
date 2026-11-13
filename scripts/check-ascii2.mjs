import fs from "node:fs";
import { openSession, sleep } from "./lib/cdp.mjs";
const s = await openSession({ width: 1440, height: 900 });
try {
  await s.open("http://127.0.0.1:4173/", { theme: "geek", settle: 1800 });
  await s.evalJS(`window.scrollTo(0, document.body.scrollHeight)`);
  await sleep(500);
  const ok = await s.evalJS(`(async () => {
    const el = document.querySelector('.ridgefoot .asc');
    const r = el.getBoundingClientRect();
    const fire = (type, x, y) => el.dispatchEvent(new PointerEvent(type, { bubbles: true, clientX: x, clientY: y, pointerType: 'mouse', button: 0 }));
    fire('pointerenter', r.left + 60, r.top + r.height * 0.6);
    for (let i = 0; i <= 30; i++) {
      fire('pointermove', r.left + 60 + i * 30, r.top + r.height * 0.6);
      await new Promise(res => setTimeout(res, 20));
    }
    await new Promise(res => setTimeout(res, 300));
    return { rect: [Math.round(r.left), Math.round(r.top), Math.round(r.width), Math.round(r.height)] };
  })()`);
  console.log(JSON.stringify(ok.result.value));
  fs.writeFileSync("out/shots/asc-wake.png", await s.screenshot(null, {}));
} finally { s.close(); }
