import { openSession } from "./lib/cdp.mjs";

const s = await openSession({ width: 1440, height: 1000 });
try {
  await s.open("http://127.0.0.1:4173/?demo=baidu", { theme: "geek", settle: 16000 });
  const r = await s.evalJS(`(() => {
    const out = {};
    const bar = document.querySelector('.dimbar');
    if (bar) {
      const fill = bar.querySelector('.dimbar__fill');
      const track = bar.querySelector('.dimbar__track');
      const fr = fill && fill.getBoundingClientRect();
      const tr = track && track.getBoundingClientRect();
      out.dimbar = {
        fillClass: fill && fill.className,
        fillRect: fr && [Math.round(fr.x), Math.round(fr.y), Math.round(fr.width), Math.round(fr.height)],
        fillBg: fill && getComputedStyle(fill).background.slice(0, 80),
        fillOpacity: fill && getComputedStyle(fill).opacity,
        fillTransform: fill && getComputedStyle(fill).transform,
        trackRect: tr && [Math.round(tr.x), Math.round(tr.y), Math.round(tr.width), Math.round(tr.height)],
        trackBg: track && getComputedStyle(track).background.slice(0, 60),
      };
    }
    const vote = document.querySelector('.vote');
    const votes = document.querySelector('.votes');
    out.vote = { html: votes ? votes.innerHTML.slice(0, 400) : null, cls: vote && vote.className };
    const paper = document.querySelector('.paper');
    const line = document.querySelector('.paper__line');
    out.paper = {
      has: !!paper,
      linesAfter: line ? getComputedStyle(line, '::after').content : null,
      lineStyle: line ? getComputedStyle(line).backgroundImage.slice(0, 60) : null,
      vars: line ? line.style.cssText : null,
    };
    // 找 publication 里 hl 标记
    out.readerHl = document.querySelectorAll('.reader__body mark.hl').length;
    return out;
  })()`);
  console.log(JSON.stringify(r.result.value, null, 1));
} finally {
  s.close();
}