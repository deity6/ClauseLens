import fs from "node:fs";
import { openSession, sleep } from "./lib/cdp.mjs";
const s = await openSession({ width: 1440, height: 900 });
try {
  await s.open("http://127.0.0.1:4173/", { theme: "geek", settle: 1800 });
  // 滚动呼吸：滚一段，立刻截
  await s.evalJS(`window.scrollTo(0, 300)`);
  await sleep(120);
  fs.writeFileSync("out/shots/breath-1.png", await s.screenshot(null, {}));
  await sleep(700);
  fs.writeFileSync("out/shots/breath-2.png", await s.screenshot(null, {}));
  // 底部山脊：滚到底，隔 1.2s 两帧
  await s.evalJS(`window.scrollTo(0, document.body.scrollHeight)`);
  await sleep(900);
  fs.writeFileSync("out/shots/ridge-t1.png", await s.screenshot(null, {}));
  await sleep(1400);
  fs.writeFileSync("out/shots/ridge-t2.png", await s.screenshot(null, {}));
  console.log("ok");
} finally { s.close(); }
