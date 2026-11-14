// 投票：本机先落、先显示；离开页面 / 下次打开 / 攒满 5 分钟才批量同步到后端。
//
// 为什么不点一次就 POST 一次：
//   · 用户会连着改（认同 → 改不认同 → 撤掉），每一次点击都发请求纯属浪费；
//   · 后端要的只是「这个人对这个标签最终投了什么」，中间态没有价值。
// 为什么后端还是得记「谁投了什么」：撤回/换票要把旧票从计数里减掉，不记就退不回去。
// 所以同步发的是「最终状态」（vote=null 表示撤回），重复提交幂等——sendBeacon 那一发没等到
// 响应也不怕，下次打开重发一遍不会多算。
//
// 显示口径：counts 是「所有人（含我上次同步上去的那一票）」，
// 界面要的是「所有人 - 我上次的 + 我现在的」，否则撤回时数字不会立刻掉下来。
const VOTE = "clauselens.vote."; // {domain}.{tag} → agree | disagree（本机当前选择）
const SYNCED = "clauselens.synced."; // 同上，上一次和服务端对齐时的值
const DOMAINS = "clauselens.vote.domains"; // 记过票的域名清单（离开页面时要知道给谁发）
const MAX_UNSYNCED_MS = 5 * 60 * 1000; // 页面一直开着没离开时的兜底同步

const counts = new Map(); // domain → {tag: {agree, disagree}}
const listeners = new Set();
let lastChange = 0;
let flushing = null;
let syncOn = true; // 演示模式（离线）只在本机记，不发请求

const key = (prefix, domain, tag) => `${prefix}${domain}.${tag}`;
const read = (k) => {
  try {
    return localStorage.getItem(k);
  } catch {
    return null;
  }
};
const write = (k, v) => {
  try {
    if (v == null) localStorage.removeItem(k);
    else localStorage.setItem(k, v);
  } catch {
    /* 隐私模式下不可写：本次页面内仍然有效 */
  }
};
const norm = (v) => (v === "agree" || v === "disagree" ? v : null);
// 「撤回了」要留个痕：直接删 key 的话，pendingVotes 就找不到这条改动，
// 撤回永远同步不上去。所以取消写 "none"，对外仍读成 null。
const NONE = "none";

export const localVote = (domain, tag) => norm(read(key(VOTE, domain, tag)));
export const syncedVote = (domain, tag) => norm(read(key(SYNCED, domain, tag)));

function rememberDomain(domain) {
  let list = [];
  try {
    const raw = JSON.parse(read(DOMAINS) || "[]");
    if (Array.isArray(raw)) list = raw;
  } catch {
    list = [];
  }
  if (!list.includes(domain)) write(DOMAINS, JSON.stringify([...list, domain].slice(-50)));
}

function knownDomains() {
  try {
    const list = JSON.parse(read(DOMAINS) || "[]");
    return Array.isArray(list) ? list : [];
  } catch {
    return [];
  }
}

function localTags(domain) {
  const prefix = key(VOTE, domain, "");
  const out = [];
  try {
    for (let i = 0; i < localStorage.length; i++) {
      const k = localStorage.key(i);
      if (k && k.startsWith(prefix)) out.push(k.slice(prefix.length));
    }
  } catch {
    /* 读不到 storage 就当没投过 */
  }
  return out;
}

/** 还没同步上去的改动：本机值和「上次对齐值」不一致的标签。 */
export function pendingVotes(domain) {
  const out = [];
  for (const tag of localTags(domain)) {
    const v = norm(read(key(VOTE, domain, tag)));
    const s = norm(read(key(SYNCED, domain, tag)));
    if (v !== s) out.push({ tag_id: tag, vote: v });
  }
  return out;
}

export function subscribe(fn) {
  listeners.add(fn);
  return () => listeners.delete(fn);
}
const notify = () => listeners.forEach((fn) => fn());

export function getCounts(domain, tag) {
  return counts.get(domain)?.[tag] || { agree: 0, disagree: 0 };
}

/** 界面要显示的数字：服务端计数 − 我上次那一票 + 我现在这一票。 */
export function displayCounts(domain, tag) {
  const base = getCounts(domain, tag);
  const local = localVote(domain, tag);
  const synced = syncedVote(domain, tag);
  const out = { agree: base.agree || 0, disagree: base.disagree || 0 };
  for (const v of ["agree", "disagree"]) {
    if (synced === v) out[v] = Math.max(0, out[v] - 1);
    if (local === v) out[v] += 1;
  }
  return out;
}

/** 本机改票（agree / disagree / null=撤回）。不发请求，显示立刻跟上。 */
export function setVote(domain, tag, vote) {
  const v = norm(vote);
  write(key(VOTE, domain, tag), v || NONE);
  rememberDomain(domain);
  lastChange = Date.now();
  notify();
}

/** 把「有没有这一票」记回本地（服务端说投过、本机没有时用）。 */
function adoptSynced(domain, tag, vote) {
  write(key(SYNCED, domain, tag), norm(vote));
}

export async function loadVoteState(domain, { offline = false } = {}) {
  syncOn = !offline;
  if (offline) return;
  try {
    const r = await fetch(`/api/feedback/state?domain=${encodeURIComponent(domain)}`);
    if (!r.ok) return;
    const data = await r.json();
    counts.set(domain, data.counts || {});
    const mine = data.mine || {};
    const tags = new Set([...localTags(domain), ...Object.keys(mine)]);
    for (const tag of tags) {
      const m = norm(mine[tag]);
      const seen = read(key(VOTE, domain, tag)) != null || read(key(SYNCED, domain, tag)) != null;
      // 换设备 / 清过缓存：服务端记得我投过，认回来，免得界面以为我没投。
      // 本机有记录（哪怕是 "none" 撤回）就不认——那是本机更新的意图，别被服务端的旧值盖掉。
      if (!seen && m) write(key(VOTE, domain, tag), m);
      adoptSynced(domain, tag, m);
      if (localVote(domain, tag) == null && m == null && read(key(VOTE, domain, tag)) === NONE) {
        write(key(VOTE, domain, tag), null); // 撤回早就同步过了，本地不用再留痕
      }
    }
    notify();
    flushVotes(domain).catch(() => {});
  } catch {
    /* 网络失败：界面按本机状态显示，下次再同步 */
  }
}

/** 批量同步：一次请求带上这个域名下所有还没对齐的标签。 */
export function flushVotes(domain) {
  if (!syncOn) return Promise.resolve();
  flushing = (flushing || Promise.resolve()).then(() => doFlush(domain)).catch(() => {});
  return flushing;
}

async function doFlush(domain) {
  const domains = domain ? [domain] : knownDomains();
  for (const d of domains) {
    const votes = pendingVotes(d);
    if (!votes.length) continue;
    const r = await fetch("/api/feedback/batch", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ domain: d, votes }),
    });
    if (!r.ok) continue;
    const data = await r.json();
    for (const { tag_id, vote } of votes) {
      adoptSynced(d, tag_id, vote);
      if (!vote) write(key(VOTE, d, tag_id), null); // 撤回已确认，本地不再留痕
    }
    if (data.counts) counts.set(d, data.counts);
    notify();
  }
}

/** 页面要走了：没有等待响应的时间，用 sendBeacon 发最后一发（不标记已同步，失败下次重发）。 */
function beaconFlush() {
  if (!syncOn) return;
  for (const d of knownDomains()) {
    const votes = pendingVotes(d);
    if (!votes.length) continue;
    const body = JSON.stringify({ domain: d, votes });
    try {
      const blob = new Blob([body], { type: "application/json" });
      if (navigator.sendBeacon && navigator.sendBeacon("/api/feedback/batch", blob)) continue;
    } catch {
      /* fallthrough 到 keepalive fetch */
    }
    fetch("/api/feedback/batch", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body,
      keepalive: true,
    }).catch(() => {});
  }
}

if (typeof window !== "undefined") {
  addEventListener("pagehide", beaconFlush);
  addEventListener("visibilitychange", () => {
    if (document.visibilityState === "hidden") beaconFlush();
  });
  // 兜底：页面一直开着、用户也一直没离开，攒太久就自己同步一次
  setInterval(() => {
    if (lastChange && Date.now() - lastChange > MAX_UNSYNCED_MS) flushVotes();
  }, 30_000);
}
