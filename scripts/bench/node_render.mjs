/**
 * 只跑 JS 引擎、不跑浏览器的对照实验：jsdom / happy-dom。
 *
 * 输入：node node_render.mjs <node-jsdom|node-jsdom-poly|node-happy-dom> <url>
 * 输出：一行 JSON {html, note, errors, scripts}
 *
 * 这两种方案的共同点：没有布局引擎，没有渲染，只有 DOM + 脚本执行。
 * 差别在于 jsdom 的 API 更全但慢，happy-dom 快但缺件多。
 */
import { createRequire } from 'node:module';

const scheme = process.argv[2];
const url = process.argv[3];
const require = createRequire(import.meta.url);
const out = { html: '', note: '', errors: 0, scripts: 0 };

const SETTLE_MS = 9000;

function polyfill(window) {
  // SPA 运行时常见的必需品；jsdom/happy-dom 都没有实现
  window.IntersectionObserver = class {
    constructor(cb) { this.cb = cb; }
    observe(el) { this.cb([{ isIntersecting: true, target: el, intersectionRatio: 1 }], this); }
    unobserve() {} disconnect() {} takeRecords() { return []; }
  };
  window.ResizeObserver = class {
    constructor(cb) { this.cb = cb; }
    observe() {} unobserve() {} disconnect() {}
  };
  if (!window.matchMedia) {
    window.matchMedia = (q) => ({
      matches: false, media: q, onchange: null,
      addListener() {}, removeListener() {}, addEventListener() {}, removeEventListener() {},
      dispatchEvent() { return false; },
    });
  }
  window.requestIdleCallback = window.requestIdleCallback ||
    ((cb) => setTimeout(() => cb({ didTimeout: false, timeRemaining: () => 50 }), 1));
  window.cancelIdleCallback = window.cancelIdleCallback || clearTimeout;
  window.scrollTo = window.scrollTo || (() => {});
  if (!window.fetch) window.fetch = (...a) => fetch(...a);
}

async function main() {
  const res = await fetch(url, {
    headers: {
      'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 ' +
        '(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36',
      'accept-language': 'zh-CN,zh;q=0.9,en;q=0.8',
    },
    redirect: 'follow',
  });
  const html = await res.text();
  out.status = res.status;
  out.server_bytes = html.length;
  out.scripts = (html.match(/<script\b/gi) || []).length;

  if (scheme === 'node-happy-dom') {
    const { Window } = require('happy-dom');
    const window = new Window({ url, settings: { disableJavaScriptEvaluation: false } });
    if (scheme.endsWith('poly')) polyfill(window);
    window.document.write(html);
    await new Promise((r) => setTimeout(r, SETTLE_MS));
    out.html = window.document.documentElement.outerHTML;
  } else {
    const { JSDOM, VirtualConsole } = require('jsdom');
    const vc = new VirtualConsole();
    vc.on('jsdomError', () => { out.errors += 1; });
    vc.on('error', () => { out.errors += 1; });
    const dom = new JSDOM(html, {
      url,
      runScripts: 'dangerously',
      resources: 'usable',
      pretendToBeVisual: true,
      virtualConsole: vc,
      beforeParse(window) {
        if (scheme === 'node-jsdom-poly') polyfill(window);
      },
    });
    await new Promise((r) => setTimeout(r, SETTLE_MS));
    out.html = dom.serialize();
    try { dom.window.close(); } catch { /* ignore */ }
  }
  out.note = `scheme=${scheme} settle=${SETTLE_MS}ms js_errors=${out.errors}`;
}

main().then(() => {
  process.stdout.write(JSON.stringify(out));
}).catch((e) => {
  out.note = `FATAL ${e && e.message ? e.message : e}`;
  process.stdout.write(JSON.stringify(out));
  process.exitCode = 1;
});
