import { openSession } from "./lib/cdp.mjs";

const s = await openSession({ width: 1280, height: 900 });
try {
  for (const base of ["http://127.0.0.1:4173", "http://127.0.0.1:5177"]) {
    await s.open(`${base}/`, { theme: "geek", settle: 1500 });
    const r = await s.evalJS(`({
      theme: document.documentElement.dataset.theme,
      dots: !!document.querySelector('.dotsbackdrop'),
      stat: !!document.querySelector('.dotsstatic'),
      field: !!document.querySelector('.dotfield'),
      inter: getComputedStyle(document.body).fontFamily,
      script: [...document.scripts].map(s => s.src).filter(Boolean).map(s => s.split('/').pop())
    })`);
    console.log(base, JSON.stringify(r.result.value));
  }
} finally {
  s.close();
}