// 检查 ASCII 场的指针唤醒：在页脚山脊上划一道，应该能看到字符冒出来
import fs from "node:fs";
import { openSession, sleep } from "./lib/cdp.mjs";

const s = await openSession({ width: 1440, height: 900 });
try {
  await s.open("http://127.0.0.1:4173/", { theme: "geek", settle: 2000 });
  await s.evalJS(`window.scrollTo(0, document.body.scrollHeight)`);
  await sleep(600);
  const before = await s.screenshot(null, {});
  fs.writeFileSync("out/shots/asc-before.png", before);
  // 在页脚山脊上从左到右划一道（y≈820）
  for (let x = 200; x <= 1200; x += 40) {
    await s.send("Input.dispatchMouseEvent", { type: "mouseMoved", x, y: 780, button: "none", pointerType: "mouse" });
    await sleep(16);
  }
  await sleep(250);
  fs.writeFileSync("out/shots/asc-after.png", await s.screenshot(null, {}));
  const state = await s.evalJS(`({ canvases: document.querySelectorAll('.asc-canvas').length, ridge: !!document.querySelector('.ridgefoot'), badge: !!document.querySelector('.scorebadge') })`);
  console.log(JSON.stringify(state.result.value));
} finally {
  s.close();
}
