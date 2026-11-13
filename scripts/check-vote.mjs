import fs from "node:fs";
import { openSession, sleep } from "./lib/cdp.mjs";
const s = await openSession({ width: 1440, height: 900 });
try {
  await s.open("http://127.0.0.1:4173/?demo=baidu", { theme: "geek", settle: 16000 });
  await s.evalJS(`(async () => {
    const pill = document.querySelector('.pill');
    pill?.scrollIntoView({ block: 'center' });
    await new Promise(r => setTimeout(r, 300));
    pill?.click();
    await new Promise(r => setTimeout(r, 600));
    document.querySelector('.vote')?.scrollIntoView({ block: 'center' });
    await new Promise(r => setTimeout(r, 300));
    document.querySelector('.vote')?.click();
    await new Promise(r => setTimeout(r, 500));
    return true;
  })()`);
  await sleep(400);
  fs.writeFileSync("out/shots/fix-vote.png", await s.screenshot(null, {}));
  const info = await s.evalJS(`(() => { const v = document.querySelector('.vote.is-mine'); const b = v && v.querySelector('b'); return { mine: !!v, color: b && getComputedStyle(b).color, bg: v && getComputedStyle(v).backgroundColor }; })()`);
  console.log(JSON.stringify(info.result.value));
} finally { s.close(); }
