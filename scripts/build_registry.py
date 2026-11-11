"""生成 data/processed/registry.json：已收录站点的条款直链 + 正文快照（脚本渲染站点的兜底）。

来源：cn_docs.jsonl（中文主流站点）。每站每类取最长的 1 份（privacy / terms），共 ≤3 份。
站名取 cn_docs 里的 name 字段。快照截断 300000 字。

用法：python scripts/build_registry.py
"""
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"
TYPE_ZH = {"privacy": "隐私政策", "terms": "用户协议", "other": "法律声明"}


def main():
    by = defaultdict(list)
    for line in open(PROC / "cn_docs.jsonl", encoding="utf-8"):
        r = json.loads(line)
        if r.get("chars", 0) < 1500:
            continue
        by[r["domain"]].append(r)
    reg = {}
    for dom, docs in by.items():
        picked = []
        for t in ("privacy", "terms", "other"):
            cands = sorted([d for d in docs if d["doc_type"] == t], key=lambda d: -d["chars"])
            if cands and (t != "other" or len(picked) < 2):
                picked.append(cands[0])
        if not picked:
            continue
        reg[dom] = {
            "name": docs[0].get("name") or dom,
            "docs": [{"url": d["url"], "title": (d.get("title") or "")[:30] or TYPE_ZH[d["doc_type"]], "type": d["doc_type"],
                      "snapshot": d["text"][:300000], "snapshot_at": d.get("fetched_at")} for d in picked],
        }
    n_cn = len(reg)
    # ToS;DR 站点：只登记条款直链（无快照），按服务的所有域名索引；中文快照优先
    for line in open(PROC / "sites.jsonl", encoding="utf-8"):
        r = json.loads(line)
        urls = [u for u in r.get("doc_urls", []) if u.startswith("http")]
        if not urls:
            continue
        pri = sorted(urls, key=lambda u: (0 if "privacy" in u.lower() else 1 if any(k in u.lower() for k in ("terms", "tos")) else 2))[:5]
        entry = {"name": r.get("name") or r["domain"], "source": "tosdr",
                 "docs": [{"url": u.split("#")[0], "title": "", "type": ""} for u in pri]}
        for d in [r["domain"]] + [u for u in r.get("urls", [])[:20] if "." in u and not u.endswith(".onion")]:
            reg.setdefault(d, entry)
    print("cn sites", n_cn)
    (PROC / "registry.json").write_text(json.dumps(reg, ensure_ascii=False), "utf-8")
    print("sites", len(reg), "docs", sum(len(v["docs"]) for v in reg.values()))


if __name__ == "__main__":
    main()
