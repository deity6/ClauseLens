import { openSession, sleep } from "./lib/cdp.mjs";
const s = await openSession({ width: 1440, height: 900 });
try {
  await s.send("Runtime.enable");
  const errs = [];
  s.onFrame?.(() => {});
  await s.open("http://127.0.0.1:4173/", { theme: "geek", settle: 1500 });
  await s.evalJS(`window.scrollTo(0, document.body.scrollHeight)`);
  await sleep(600);
  const h1 = await s.evalJS(`(() => { const c = document.querySelector('.ridgefoot canvas'); return c ? c.toDataURL().length : 0; })()`);
  await sleep(900);
  const h2 = await s.evalJS(`(() => { const c = document.querySelector('.ridgefoot canvas'); return c ? c.toDataURL().length : 0; })()`);
  console.log("canvas dataURL len t1/t2:", h1.result.value, h2.result.value, "changed:", h1.result.value !== h2.result.value);
} finally { s.close(); }
