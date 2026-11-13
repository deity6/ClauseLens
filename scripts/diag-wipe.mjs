// 一次性诊断：主题像素转场中 canvas 的几何与状态
import { openSession, sleep } from "./lib/cdp.mjs";

const s = await openSession({ width: 1440, height: 900 });
try {
  await s.open("http://127.0.0.1:5177/", { theme: "light", settle: 1500 });
  const before = await s.evalJS(`(() => {
    const cv = document.querySelector('canvas.dotfield');
    return { theme: document.documentElement.dataset.theme, innerW: innerWidth, innerH: innerHeight, docW: document.documentElement.clientWidth,
             bodyScrollH: document.body.scrollHeight, hasDot: !!cv };
  })()`);
  console.log("before:", JSON.stringify(before.result.value));

  await s.evalJS(`document.querySelector('.tswitch__opt[title="切换到点阵主题"]')?.click()`);
  await sleep(120);
  const mid = await s.evalJS(`(() => {
    const cv = document.querySelector('canvas.theme-wipe');
    if (!cv) return { err: 'no canvas' };
    const r = cv.getBoundingClientRect();
    const cs = getComputedStyle(cv);
    return { rect: [r.x, r.y, r.width, r.height], backing: [cv.width, cv.height], styleW: cv.style.width, imageRendering: cs.imageRendering,
             theme: document.documentElement.dataset.theme, scrollbarGap: innerWidth - document.documentElement.clientWidth };
  })()`);
  console.log("mid@120:", JSON.stringify(mid.result.value));
  await sleep(500);
  const late = await s.evalJS(`(() => {
    const cv = document.querySelector('canvas.theme-wipe');
    if (!cv) return { gone: true, theme: document.documentElement.dataset.theme };
    const r = cv.getBoundingClientRect();
    return { rect: [r.x, r.y, r.width, r.height], backing: [cv.width, cv.height], theme: document.documentElement.dataset.theme };
  })()`);
  console.log("mid@620:", JSON.stringify(late.result.value));
  await sleep(400);
  const after = await s.evalJS(`({ theme: document.documentElement.dataset.theme, canvas: !!document.querySelector('canvas.theme-wipe') })`);
  console.log("after:", JSON.stringify(after.result.value));
} finally {
  s.close();
}
