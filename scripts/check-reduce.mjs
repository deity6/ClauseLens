// 降级验收：prefers-reduced-motion 下切主题不应出现 canvas / 粒子，且 200ms 内完成切换
import { openSession, sleep } from "./lib/cdp.mjs";

const s = await openSession({ width: 1280, height: 900 });
try {
  await s.send("Emulation.setEmulatedMedia", {
    features: [{ name: "prefers-reduced-motion", value: "reduce" }],
  });
  await s.open("http://127.0.0.1:4173/", { theme: "light", settle: 1200 });
  const reduce = await s.evalJS(`matchMedia('(prefers-reduced-motion: reduce)').matches`);
  console.log("reduce active:", reduce.result.value);
  await s.evalJS(`document.querySelector('.tswitch__opt[title="切换到点阵主题"]')?.click()`);
  await sleep(60);
  const t60 = await s.evalJS(
    `({ theme: document.documentElement.dataset.theme, canvas: !!document.querySelector('canvas.theme-wipe') })`
  );
  await sleep(400);
  const t460 = await s.evalJS(
    `({ theme: document.documentElement.dataset.theme, canvas: !!document.querySelector('canvas.theme-wipe'), dots: !!document.querySelector('canvas.dotfield'), sweeping: document.querySelectorAll('.cl-sweep').length })`
  );
  console.log("t=60ms:", JSON.stringify(t60.result.value));
  console.log("t=460ms:", JSON.stringify(t460.result.value));

  // 再切回去，确认反向也不建 canvas
  await s.evalJS(`document.querySelector('.tswitch__opt[title="切换到纸主题"]')?.click()`);
  await sleep(200);
  const back = await s.evalJS(
    `({ theme: document.documentElement.dataset.theme, canvas: !!document.querySelector('canvas.theme-wipe') })`
  );
  console.log("back t=200ms:", JSON.stringify(back.result.value));
} finally {
  s.close();
}
