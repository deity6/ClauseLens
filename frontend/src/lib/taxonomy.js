import localTaxonomy from "../data/taxonomy.json";

let cache = null;

export async function loadTaxonomy({ offline } = {}) {
  if (cache) return cache;
  if (!offline) {
    try {
      const r = await fetch("/api/taxonomy");
      if (r.ok) {
        cache = index(await r.json());
        return cache;
      }
    } catch {
      /* 后端不在：退回随包字典 */
    }
  }
  cache = index(localTaxonomy);
  return cache;
}

export function index(t) {
  const byId = Object.fromEntries(t.tags.map((x) => [x.id, x]));
  return { ...t, byId };
}

export const POLARITY = {
  blocker: { group: "bad", label: "严重", cls: "bad" },
  bad: { group: "bad", label: "需要注意", cls: "bad" },
  good: { group: "good", label: "还不错", cls: "good" },
  neutral: { group: "neutral", label: "一般说明", cls: "neutral" },
};

export const GROUPS = [
  { key: "bad", title: "需要注意", en: "WATCH OUT" },
  { key: "good", title: "还不错", en: "GOOD" },
  { key: "neutral", title: "一般说明", en: "NOTED" },
];

export function gradeOf(v, grades) {
  const g = (grades || [{ grade: "A", min: 85 }, { grade: "B", min: 70 }, { grade: "C", min: 55 }, { grade: "D", min: 40 }, { grade: "E", min: 0 }]);
  return (g.find((x) => v >= x.min) || g[g.length - 1]).grade;
}

export const DIM_ORDER = ["privacy", "sharing", "rights", "control", "liability", "content"];
