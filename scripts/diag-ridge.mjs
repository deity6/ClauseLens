import { openSession } from "./lib/cdp.mjs";

const s = await openSession({ width: 1440, height: 900 });
try {
  await s.open("http://127.0.0.1:4173/", { theme: "geek", settle: 2200 });
  const r = await s.evalJS(`(() => {
    const rf = document.querySelector('.ridgefoot');
    const asc = rf && rf.querySelector('.asc');
    const cv = rf && rf.querySelector('canvas');
    const rect = rf && rf.getBoundingClientRect();
    const ar = asc && asc.getBoundingClientRect();
    const cs = cv && getComputedStyle(cv);
    // 统计画布上有没有非透明像素
    let ink = 0;
    if (cv) { const g = cv.getContext('2d'); const d = g.getImageData(0,0,cv.width,cv.height).data; for (let i=3;i<d.length;i+=4*97) if (d[i] > 0) ink++; }
    return {
      ridge: !!rf, asc: !!asc,
      rect: rect && [Math.round(rect.x), Math.round(rect.y), Math.round(rect.width), Math.round(rect.height)],
      ascRect: ar && [Math.round(ar.x), Math.round(ar.y), Math.round(ar.width), Math.round(ar.height)],
      cv: cv && [cv.width, cv.height, cs.color, cs.display],
      ink,
      shellPad: getComputedStyle(document.querySelector('.shell')).paddingBottom,
      docH: document.documentElement.scrollHeight,
    };
  })()`);
  console.log(JSON.stringify(r.result.value, null, 1));
} finally {
  s.close();
}