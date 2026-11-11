export function fmtChars(n) {
  if (n == null) return "";
  if (n < 10000) return `${n.toLocaleString("zh-CN")} 字`;
  return `${(n / 10000).toFixed(n < 100000 ? 1 : 0)} 万字`;
}

export function fmtMinutes(m) {
  if (m == null) return "";
  if (m < 60) return `${m} 分钟`;
  const h = Math.floor(m / 60);
  const r = m % 60;
  return r ? `${h} 小时 ${r} 分钟` : `${h} 小时`;
}

// 识别输入：纯域名 → 整站查找；带路径的网址 → 只分析这一页
export function detectMode(raw) {
  const s = (raw || "").trim();
  if (!s) return null;
  let u;
  try {
    u = new URL(/^[a-z]+:\/\//i.test(s) ? s : `https://${s}`);
  } catch {
    return { mode: "invalid" };
  }
  if (!/^[^.\s]+(\.[^.\s]+)+$/.test(u.hostname)) return { mode: "invalid" };
  const hasPath = (u.pathname && u.pathname !== "/") || u.search;
  return { mode: hasPath ? "precise" : "fuzzy", domain: u.hostname.replace(/^www\./, "") };
}

export const DOC_TYPE_ZH = { privacy: "隐私政策", terms: "服务条款", cookie: "Cookie 政策", other: "其他条款" };
