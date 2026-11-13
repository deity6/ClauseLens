import { openSession, sleep } from "./lib/cdp.mjs";
const s = await openSession({ width: 1440, height: 900 });
try {
  await s.open("http://127.0.0.1:4173/", { theme: "geek", settle: 1500 });
  await s.evalJS(`window.scrollTo(0, document.body.scrollHeight)`);
  await sleep(1500);
  const r = await s.evalJS(`({ ticks: window.__amb || 0, bubblesSeen: (document.querySelector('.ridgefoot canvas')||{}).width })`);
  console.log(JSON.stringify(r.result.value));
} finally { s.close(); }
