// 截图验收：自己拉起一个无头 Edge（临时 profile，用完即关），经 CDP 截图。
// 用法：node scripts/shot.mjs <url> <out.png> [--w 1440] [--h 1000] [--wait 2000] [--full] [--dark] [--click "<css>"] [--scroll <css>]
// 不改系统深浅色：--dark 只在这个无头实例里模拟 prefers-color-scheme。
import { spawn } from "node:child_process";
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const args = process.argv.slice(2);
const url = args[0];
const out = args[1];
const opt = (k, d) => {
  const i = args.indexOf(`--${k}`);
  return i < 0 ? d : args[i + 1];
};
const has = (k) => args.includes(`--${k}`);
const W = +opt("w", 1440);
const H = +opt("h", 1000);
const WAIT = +opt("wait", 2000);
const clicks = args.flatMap((a, i) => (a === "--click" ? [args[i + 1]] : []));
const scrollSel = opt("scroll", null);

const EDGE = "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe";
const port = 9300 + Math.floor(Math.random() * 500);
const profile = mkdtempSync(join(tmpdir(), "cl-shot-"));
const edge = spawn(EDGE, ["--headless=new", `--remote-debugging-port=${port}`, `--user-data-dir=${profile}`, "--no-first-run", "--disable-gpu", "about:blank"], {
  stdio: "ignore",
});

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
let ws;
try {
  let target;
  for (let i = 0; i < 50 && !target; i++) {
    await sleep(200);
    try {
      const list = await (await fetch(`http://127.0.0.1:${port}/json`)).json();
      target = list.find((t) => t.type === "page");
    } catch {}
  }
  if (!target) throw new Error("edge did not start");
  ws = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((r) => ws.addEventListener("open", r, { once: true }));
  let id = 0;
  const pending = new Map();
  ws.addEventListener("message", (e) => {
    const m = JSON.parse(e.data);
    if (m.id && pending.has(m.id)) {
      pending.get(m.id)(m);
      pending.delete(m.id);
    }
  });
  const send = (method, params = {}) =>
    new Promise((res, rej) => {
      const i = ++id;
      pending.set(i, (m) => (m.error ? rej(new Error(method + ": " + m.error.message)) : res(m.result)));
      ws.send(JSON.stringify({ id: i, method, params }));
    });
  const evalJs = async (expr) => (await send("Runtime.evaluate", { expression: expr, awaitPromise: true, returnByValue: true })).result.value;

  await send("Page.enable");
  await send("Runtime.enable");
  const mobile = W < 640;
  await send("Emulation.setDeviceMetricsOverride", { width: W, height: H, deviceScaleFactor: 1, mobile });
  const feats = [];
  if (has("dark")) feats.push({ name: "prefers-color-scheme", value: "dark" });
  if (has("light")) feats.push({ name: "prefers-color-scheme", value: "light" });
  if (has("reduce")) feats.push({ name: "prefers-reduced-motion", value: "reduce" });
  if (feats.length) await send("Emulation.setEmulatedMedia", { features: feats });
  await send("Page.navigate", { url });
  await sleep(WAIT);
  const boxes = opt("boxes", "");
  if (boxes) await evalJs(`window.__boxes=${JSON.stringify(boxes)}`);
  for (const c of clicks) {
    await evalJs(`(()=>{const el=document.querySelector(${JSON.stringify(c)}); if(el){el.scrollIntoView({block:'center'}); el.click();} return !!el})()`);
    await sleep(900);
  }
  if (scrollSel) {
    await evalJs(`(()=>{const el=document.querySelector(${JSON.stringify(scrollSel)}); el&&el.scrollIntoView({block:'start'}); })()`);
    await sleep(1500);
  }
  // 诊断：横向溢出的元素
  const overflow = await evalJs(`(()=>{const w=document.documentElement.clientWidth;return [...document.querySelectorAll('body *')].filter(e=>{const r=e.getBoundingClientRect();return r.width>0&&(r.right>w+1)}).slice(0,8).map(e=>e.className&&e.className.baseVal===undefined?e.tagName+'.'+e.className:e.tagName)})()`);
  if (overflow?.length) console.log("overflow:", overflow.join(" | "));
  if (has("audit")) {
    const rep = await evalJs(`(()=>{
      const W=document.documentElement.clientWidth, out={W, H:document.documentElement.scrollHeight, trunc:[], overlap:[], lowContrast:[], boxes:{}, small:[]};
      const lum=c=>{const m=c.match(/[\d.]+/g); if(!m) return null; const [r,g,b]=m.slice(0,3).map(v=>{v/=255;return v<=.03928?v/12.92:Math.pow((v+.055)/1.055,2.4)}); return {L:.2126*r+.7152*g+.0722*b, a:m[3]==null?1:+m[3]}};
      const bgOf=e=>{for(let x=e;x;x=x.parentElement){const c=getComputedStyle(x).backgroundColor; const l=lum(c); if(l&&l.a>.5) return l.L;} return lum(getComputedStyle(document.body).backgroundColor).L};
      const name=e=>e.tagName.toLowerCase()+(typeof e.className==='string'&&e.className?'.'+e.className.trim().split(/\s+/).join('.'):'');
      for(const e of document.querySelectorAll('body *')){
        const r=e.getBoundingClientRect(); if(!r.width) continue;
        const cs=getComputedStyle(e);
        if((cs.overflow==='hidden'||cs.textOverflow==='ellipsis')&&e.scrollWidth>e.clientWidth+2&&e.children.length===0) out.trunc.push(name(e)+': '+e.textContent.slice(0,30));
        if(e.childNodes.length&&[...e.childNodes].some(n=>n.nodeType===3&&n.textContent.trim())){
          const fg=lum(cs.color); if(fg){const bg=bgOf(e); const [a,b]=[fg.L,bg].sort((x,y)=>y-x); const cr=(a+.05)/(b+.05); if(cr<3.2&&cs.opacity!=='0') out.lowContrast.push(name(e)+' '+cr.toFixed(2)+' "'+e.textContent.trim().slice(0,16)+'"');}
          if(parseFloat(cs.fontSize)<11) out.small.push(name(e)+' '+cs.fontSize);
        }
      }
      // 同一父元素下兄弟的重叠
      for(const p of document.querySelectorAll('body *')){
        const kids=[...p.children].filter(k=>{const r=k.getBoundingClientRect();return r.width&&r.height&&getComputedStyle(k).position!=='absolute'});
        for(let i=0;i<kids.length;i++)for(let j=i+1;j<kids.length;j++){const a=kids[i].getBoundingClientRect(),b=kids[j].getBoundingClientRect(); const ox=Math.min(a.right,b.right)-Math.max(a.left,b.left), oy=Math.min(a.bottom,b.bottom)-Math.max(a.top,b.top); if(ox>3&&oy>3) out.overlap.push(name(kids[i])+' x '+name(kids[j])+' '+Math.round(ox)+'x'+Math.round(oy));}
      }
      for(const sel of (window.__boxes||'').split('|').filter(Boolean)){const e=document.querySelector(sel); if(e){const r=e.getBoundingClientRect(); out.boxes[sel]=[r.left,r.top+scrollY,r.width,r.height].map(Math.round)}}
      out.trunc=out.trunc.slice(0,15); out.overlap=[...new Set(out.overlap)].slice(0,20); out.lowContrast=[...new Set(out.lowContrast)].slice(0,20); out.small=[...new Set(out.small)].slice(0,10);
      return out})()`);
    console.log(JSON.stringify(rep, null, 1));
  }
  const ex = opt("eval", null);
  if (ex) console.log("eval:", JSON.stringify(await evalJs(ex), null, 1));
  let clip;
  if (has("full")) {
    const h = await evalJs("document.documentElement.scrollHeight");
    await send("Emulation.setDeviceMetricsOverride", { width: W, height: Math.min(h, 16000), deviceScaleFactor: 1, mobile });
    // whileInView 的元素需要进入视口才会播放；视口拉高后等它们播完
    await sleep(1800);
  }
  const shot = await send("Page.captureScreenshot", { format: "png", clip, captureBeyondViewport: false });
  writeFileSync(out, Buffer.from(shot.data, "base64"));
  console.log("saved", out);
} finally {
  try {
    ws?.close();
  } catch {}
  edge.kill();
  await sleep(500);
  try {
    rmSync(profile, { recursive: true, force: true });
  } catch {}
}
