import { openSession, sleep } from "./lib/cdp.mjs";
const s = await openSession({ width: 1440, height: 900 });
try {
  await s.open("http://127.0.0.1:4173/", { theme: "geek", settle: 1500 });
  await s.evalJS(`window.scrollTo(0, document.body.scrollHeight)`);
  await sleep(1200);
  const sum = () => `(() => { const c = document.querySelector('.ridgefoot canvas'); const g = c.getContext('2d'); const d = g.getImageData(0,0,c.width,c.height).data; let a=0; for (let i=3;i<d.length;i+=4) if (d[i]>0) a++; return a; })()`;
  const a = await s.evalJS(sum());
  await sleep(1200);
  const b = await s.evalJS(sum());
  console.log("opaque pixel counts:", a.result.value, b.result.value);
} finally { s.close(); }
