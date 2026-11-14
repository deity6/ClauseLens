// 把 index.html 里那段内联「首帧主题」脚本的 sha256 写进 public/_headers 的 CSP。
//
// 为什么需要：线上 CSP 是 `script-src 'self'`，内联 <script> 没有 hash 会被浏览器直接拦掉
// （2026-11-14 就踩过一次：手机上「跟随系统深色」整个没生效，因为脚本根本没跑）。
// 放在 npm run build 的 prebuild：改脚本 => 构建前自动重算，不会出现「脚本改了、hash 还是旧的」。
// 只读 index.html 与 public/_headers，两者都入库；不生成别的文件。
import { createHash } from "node:crypto";
import fs from "node:fs";
import path from "node:path";

const ROOT = path.resolve(import.meta.dirname, "..");
const htmlPath = path.join(ROOT, "index.html");
const headersPath = path.join(ROOT, "public", "_headers");

// 浏览器按「HTML 解析后的脚本文本」算 hash：换行统一成 \n，所以这里也先统一
const html = fs.readFileSync(htmlPath, "utf8").replace(/\r\n/g, "\n");
const block = html.match(/<!--\s*theme-boot:start[\s\S]*?-->\s*(<script>([\s\S]*?)<\/script>)\s*<!--\s*theme-boot:end\s*-->/);
if (!block) {
  console.error("✗ index.html 里找不到 <!-- theme-boot:start --> … <script>…</script> … <!-- theme-boot:end -->");
  process.exit(1);
}
const code = block[2];
if (code.includes("</script")) {
  console.error("✗ 内联脚本里不能出现 </script（想写字符串请用 \"<\\/script\"）");
  process.exit(1);
}
const hash = "sha256-" + createHash("sha256").update(code, "utf8").digest("base64");

const headers = fs.readFileSync(headersPath, "utf8");
// 只改 CSP 那一行里的 script-src：保留 'self'，把旧的 sha256-… 换成新的
// （不能用「替换前后是否相同」判断有没有命中：hash 没变时结果本来就一样）
const cspRe = /(Content-Security-Policy:[^\n]*?script-src 'self')((?: 'sha256-[A-Za-z0-9+/=]+')*)/;
if (!cspRe.test(headers)) {
  console.error("✗ public/_headers 的 CSP 里找不到 `script-src 'self'`，没法挂 hash");
  process.exit(1);
}
const next = headers.replace(cspRe, `$1 '${hash}'`);
fs.writeFileSync(headersPath, next, "utf8");
console.log(`CSP script-src hash: ${hash}`);
