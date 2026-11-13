import { openSession, sleep } from "./lib/cdp.mjs";
const s = await openSession({ width: 1440, height: 900 });
try {
  await s.send("Runtime.enable");
  await s.open("http://127.0.0.1:4173/", { theme: "geek", settle: 1500 });
  await s.evalJS(`window.scrollTo(0, document.body.scrollHeight)`);
  await sleep(1200);
  const errs = s.errors().map(e => (e.exception?.description || e.text || '').split('\n')[0]);
  console.log(JSON.stringify(errs.slice(0, 6), null, 1));
  const changed = await s.evalJS(`(async () => { const c = document.querySelector('.ridgefoot canvas'); if(!c) return 'no canvas'; const a = c.toDataURL().length; await new Promise(r=>setTimeout(r,900)); return [a, c.toDataURL().length]; })()`);
  console.log("dataURL:", JSON.stringify(changed.result.value));
} finally { s.close(); }
