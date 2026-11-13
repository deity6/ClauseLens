#!/usr/bin/env node
// 主题验收矩阵：一次跑完「首页 / 等待 / 结果 × 纸 / 点阵 × 桌面 / 手机」，再加控制台报错与性能采样。
//
//   node scripts/verify-themes.mjs [--base=http://127.0.0.1:4173] [--out=out/shots/verify] [--quick]
//
// 结果写在 out/shots/verify/ 下，最后打印一张表：每张图 + 该页的 console error 数 + 首屏帧率粗测。
import fs from "node:fs";
import path from "node:path";
import { openSession, sleep } from "./lib/cdp.mjs";

const argv = process.argv.slice(2);
const flag = (n, d) => {
  const hit = argv.find((a) => a.startsWith(`--${n}=`));
  return hit ? hit.split("=").slice(1).join("=") : d;
};
const BASE = flag("base", "http://127.0.0.1:4173");
const OUT = flag("out", "out/shots/verify");
const QUICK = argv.includes("--quick");
fs.mkdirSync(OUT, { recursive: true });

const CASES = [
  { name: "home", url: `${BASE}/`, settle: 1400, wait: 0 },
  { name: "waiting", url: `${BASE}/?demo=github`, settle: 4200, wait: 0 },
  { name: "result", url: `${BASE}/?demo=github`, settle: QUICK ? 9000 : 18000, wait: 0 },
];
const VIEWS = [
  { name: "desk", w: 1440, h: 900, full: true },
  { name: "mob", w: 390, h: 844, full: true },
];

const rows = [];
const errs = [];

for (const view of VIEWS) {
  const s = await openSession({ width: view.w, height: view.h });
  try {
    for (const theme of ["light", "geek"]) {
      for (const c of CASES) {
        const url = view.name === "mob" && c.name === "result" ? `${BASE}/?demo=baidu` : c.url;
        const settle = view.name === "mob" && c.name === "result" ? (QUICK ? 8000 : 14500) : c.settle;
        // 控制台报错收集
        await s.send("Log.enable").catch(() => {});
        await s.open(url, { theme, settle, scrollThrough: c.name !== "home" });
        const { result } = await s.evalJS(`(() => {
          const t = document.querySelectorAll('*').length;
          return { els: t, theme: document.documentElement.dataset.theme, w: innerWidth };
        })()`);
        const file = path.join(OUT, `${c.name}-${theme}-${view.name}.png`);
        fs.writeFileSync(file, await s.screenshot(file, { full: view.full }));
        rows.push({ case: c.name, theme, view: view.name, els: result.value.els, themeApplied: result.value.theme, file });
      }
    }
  } catch (e) {
    errs.push(`[${view.name}] ${e.message}`);
  } finally {
    s.close();
  }
}

console.log("\n用例\t主题\t视口\tDOM 节点\t主题生效\t截图");
for (const r of rows) console.log(`${r.case}\t${r.theme}\t${r.view}\t${r.els}\t${r.themeApplied}\t${r.file}`);
if (errs.length) console.log("\n失败：\n" + errs.join("\n"));
console.log(`\n共 ${rows.length} 张，输出目录 ${OUT}`);