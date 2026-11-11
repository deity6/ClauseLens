const key = (domain, tag) => `clauselens.vote.${domain}.${tag}`;

export function myVote(domain, tag) {
  try {
    return localStorage.getItem(key(domain, tag));
  } catch {
    return null;
  }
}

export async function fetchSummary(domain) {
  try {
    const r = await fetch(`/api/feedback/summary?domain=${encodeURIComponent(domain)}`);
    if (r.ok) return await r.json();
  } catch {
    /* 离线：社区计数为空 */
  }
  return {};
}

export async function sendVote({ domain, tag, vote, offline }) {
  try {
    localStorage.setItem(key(domain, tag), vote);
  } catch {
    /* 隐私模式下 localStorage 不可写，投票仍提交 */
  }
  if (offline) return null;
  try {
    const r = await fetch("/api/feedback", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ domain, tag_id: tag, vote }),
    });
    if (r.ok) return (await r.json()).summary || null;
  } catch {
    /* 网络失败：本地已记住，计数只在本地 +1 */
  }
  return null;
}
