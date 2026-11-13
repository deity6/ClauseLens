import fs from "node:fs";
import { openSession, sleep } from "./lib/cdp.mjs";
const s = await openSession({ width: 1440, height: 1000 });
try {
  await s.open("http://127.0.0.1:4173/?demo=baidu", { theme: "geek", settle: 16000 });
  await s.evalJS(`(async () => {
    const t = [...document.querySelectorAll('.reader__toggle')][0];
    t?.scrollIntoView({ block: 'center' });
    await new Promise(r => setTimeout(r, 400));
    t?.click();
    await new Promise(r => setTimeout(r, 900));
    const lens = document.querySelector('.lens, .glass-lens, [class*="lens"]');
    lens?.scrollIntoView({ block: 'center' });
    await new Promise(r => setTimeout(r, 600));
    return !!lens;
  })()`);
  await sleep(500);
  fs.writeFileSync("out/shots/lens-state.png", await s.screenshot(null, {}));
  const info = await s.evalJS(`(() => {
    const nodes = [...document.querySelectorAll('[class*="lens"]')].slice(0, 6).map(n => n.className);
    return { nodes, hasCard: !!document.querySelector('[class*="translat"], [class*="card"]') };
  })()`);
  console.log(JSON.stringify(info.result.value));
} finally { s.close(); }
