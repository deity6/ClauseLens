"""统计 data/processed/ 下各语料规模；--dedupe 时对 cn_docs.jsonl 去重并剔除新闻/博客页（原地重写）。

用法：python scripts/corpus_stats.py [--dedupe]
输出：打印 JSON 统计；同时写 data/processed/corpus_stats.json，供 CORPUS.md 引用。
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROC = ROOT / "data" / "processed"
RAW_CN = ROOT / "data" / "raw" / "cn"
sys.path.insert(0, str(Path(__file__).resolve().parent))


def load(name: str) -> list[dict]:
    p = PROC / name
    return [json.loads(l) for l in p.open(encoding="utf-8")] if p.exists() else []


def dedupe_cn() -> None:
    """按 (domain, sha1) 去重，并用 harvest_cn.NEWS_URL 剔除新闻/博客页（剔除的写入 raw/cn/rejected.jsonl）。"""
    from harvest_cn import NEWS_URL
    rows, seen = [], set()
    with (RAW_CN / "rejected.jsonl").open("a", encoding="utf-8", newline="\n") as rej:
        for r in load("cn_docs.jsonl"):
            if NEWS_URL.search(r["url"]):
                rej.write(json.dumps({k: r[k] for k in ("domain", "url", "title")}, ensure_ascii=False) + "\n")
                continue
            k = (r["domain"], r["sha1"])
            if k not in seen:
                seen.add(k)
                rows.append(r)
    with (PROC / "cn_docs.jsonl").open("w", encoding="utf-8", newline="\n") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def main() -> None:
    if "--dedupe" in sys.argv:
        dedupe_cn()
    from cn_sites import SITES
    st = {}
    ota = load("ota_docs.jsonl")
    st["ota"] = {"docs": len(ota), "services": len({r["service"] for r in ota}),
                 "repos": len({r["source_repo"] for r in ota}), "chars": sum(r["chars"] for r in ota),
                 "lang": dict(Counter(r["lang"] for r in ota).most_common()),
                 "top_doc_types": dict(Counter(r["doc_type"] for r in ota).most_common(8))}
    cn = load("cn_docs.jsonl")
    ok = {r["domain"] for r in cn}
    fails = [json.loads(l) for l in (RAW_CN / "failures.jsonl").open(encoding="utf-8")] if (RAW_CN / "failures.jsonl").exists() else []
    failed = [d for d, _, _ in SITES if d not in ok]
    reasons = Counter()
    for d in failed:  # 每个失败站点各原因计一次
        rs = {f["reason"].split(":")[0].split("(")[0].strip() for f in fails if f["domain"] == d}
        reasons.update(rs)
    st["cn_crawl"] = {"sites_listed": len(SITES), "sites_ok": len(ok), "sites_failed": len(failed),
                      "docs": len(cn), "chars": sum(r["chars"] for r in cn),
                      "doc_type": dict(Counter(r["doc_type"] for r in cn)),
                      "rendered_docs": sum(1 for r in cn if r.get("render")),
                      "cross_site_dup_texts": len(cn) - len({r["sha1"] for r in cn}),
                      "failed_sites": failed, "fail_reasons": dict(reasons.most_common())}
    for key, docs, extra in (("capp130", "capp130_docs.jsonl", "capp130_sentences.jsonl"), ("ca4p483", "ca4p483_docs.jsonl", None)):
        d = load(docs)
        st[key] = {"docs": len(d), "chars": sum(r["chars"] for r in d)}
        if extra:
            s = load(extra)
            st[key]["sentences"] = len(s)
            st[key]["labeled_sentences"] = sum(1 for r in s if r["label"])
    (PROC / "corpus_stats.json").write_text(json.dumps(st, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(st, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
