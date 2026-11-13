import fs from "node:fs";
import { openSession, sleep } from "./lib/cdp.mjs";
const s = await openSession({ width: 1440, height: 1000 });
try {
  await s.open("http://127.0.0.1:4173/?demo=baidu", { theme: "geek", settle: 16000 });
  await s.evalJS(`localStorage.removeItem('cl:lens')`);
  await s.open("http://127.0.0.1:4173/?demo=baidu", { theme: "geek", settle: 16000 });
  const info = await s.evalJS(`(() => {
    const b = document.querySelector('.glens__ball'); const r = b.getBoundingClientRect();
    const sec = document.getElementById('reader') || document.querySelector('.rsec#reader');
    const sr = sec && sec.getBoundingClientRect();
    return { ball: [Math.round(r.left), Math.round(r.top)], section: sr && [Math.round(sr.left), Math.round(sr.top), Math.round(sr.width), Math.round(sr.height)], scrollY: Math.round(scrollY) };
  })()`);
  console.log(JSON.stringify(info.result.value));
  await s.evalJS(`document.getElementById('reader')?.scrollIntoView({ block: 'center' })`);
  await sleep(700);
  fs.writeFileSync("out/shots/lens-area5b.png", await s.screenshot(null, {}));
} finally { s.close(); }
