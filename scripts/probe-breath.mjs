import { openSession, sleep } from "./lib/cdp.mjs";
const s = await openSession({ width: 1440, height: 900 });
try {
  await s.open("http://127.0.0.1:4173/", { theme: "geek", settle: 1500 });
  const sum = `(() => { const c = document.querySelector('canvas.dotsbackdrop'); if (!c) return -1; const g = c.getContext('2d'); const d = g.getImageData(0, 0, c.width, Math.min(c.height, 300)).data; let n = 0; for (let i = 3; i < d.length; i += 4) n += d[i]; return n; })()`;
  const a = await s.evalJS(sum);
  await s.evalJS(`window.scrollTo(0, 260)`);
  await sleep(260);
  const b = await s.evalJS(sum);
  await sleep(600);
  const c = await s.evalJS(sum);
  console.log("dots opaque:", a.result.value, b.result.value, c.result.value);
} finally { s.close(); }
