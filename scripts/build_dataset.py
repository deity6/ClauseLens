"""Build processed ToS;DR dataset (safe to re-run any time; uses whatever raw data exists).

Sources (merged in scripts/tosdr_sources.py):
  data/raw/zenodo_tosdr/*.csv   ToS;DR full dump, Zenodo record 15012282 (2023-07, GPL-3.0) -- base
  data/raw/tosdr/               live API (scripts/harvest_tosdr.py) -- newer ratings / points override
  Incomplete Zenodo files (size mismatch) are skipped with a warning.

Outputs (data/processed/):
  sites.jsonl         contract §5 sites record (+ service_id, slug, rating_source, n_points, split)
  tosdr_points.jsonl  {domain, service_id, point_id, case_id, case_title, classification,
                       weight, quote_text, doc_name, source_url, ...}  approved + non-empty quote only
  cases.json          {case_id: {title, classification, weight, topic_id, count, n_services, n_quotes}}
  split.json          {"seed":42, "train":[domain...], "test":[domain...]} services with approved points,
                      grouped by primary domain (stable hash rule in tosdr_common.py, ~80/20)
  tosdr_site_docs.jsonl {domain, service_id, rating, split, docs:[{id,name,url,text}]}  rating A-E only
  case_top.md         top-40 cases by occurrence

  --no-docs skips the (slow, 267 MB) site-docs step.
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent))
import tosdr_sources as src  # noqa: E402
from tosdr_common import SEED, is_rated, is_test, primary_domain  # noqa: E402
from tosdr_sources import clean  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "processed"


def write_jsonl(p: Path, rows) -> None:
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def write_json(p: Path, obj) -> None:
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(obj, ensure_ascii=False, indent=1) + "\n")


NL = "\n"
MAX_DOCS_PER_SITE = 4
MAX_DOC_CHARS = 300_000


def doc_priority(d: dict):
    """Terms / privacy documents first, then longer documents."""
    n = (d.get("name") or "").lower()
    core = 0 if any(k in n for k in ("terms", "privacy", "conditions", "tos", "eula", "agreement")) else 1
    return (core, -len(d["text"]), d["id"])


def html_to_text(html: str) -> str:
    soup = BeautifulSoup(html or "", "lxml")
    for t in soup(["script", "style", "noscript"]):
        t.decompose()
    for br in soup.find_all("br"):
        br.replace_with(NL)
    block = ["p", "div", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "section", "article", "table", "ul", "ol"]
    for t in soup.find_all(block):
        t.insert_before(NL)
        t.insert_after(NL)
    lines = [" ".join(l.split()) for l in soup.get_text().splitlines()]
    out, blank = [], False
    for l in lines:
        if l:
            out.append(l); blank = False
        elif not blank and out:
            out.append(""); blank = True
    return clean(NL.join(out).strip())


def main() -> None:
    no_docs = "--no-docs" in sys.argv
    OUT.mkdir(parents=True, exist_ok=True)
    details = src.api_details()
    services = src.load_services(details)
    cases = src.load_cases()
    doc_meta = src.load_document_meta()
    points = src.load_points(details)

    # ---- domains (first non-onion url; duplicates get a #tosdr<id> suffix) ----
    domain_of, used = {}, set()
    for sid, s in sorted(services.items()):
        dom = primary_domain(s.get("urls"))
        dom = f"{dom}#tosdr{sid}" if dom and dom in used else (dom or f"tosdr:{s.get('slug') or sid}")
        used.add(dom)
        domain_of[sid] = dom

    # ---- points ----
    out_points, case_count, case_services = [], Counter(), defaultdict(set)
    n_points_by_sid = Counter()
    for pid, p in sorted(points.items()):
        sid, cid = p.get("service_id"), p.get("case_id")
        if sid not in services or cid is None:
            continue
        case_count[cid] += 1
        case_services[cid].add(sid)
        n_points_by_sid[sid] += 1
        if not p.get("quote_text"):
            continue
        c = cases.get(cid, {})
        doc = doc_meta.get(p.get("document_id")) or {}
        out_points.append({
            "domain": domain_of[sid], "service_id": sid, "point_id": pid,
            "case_id": cid, "case_title": c.get("title"), "classification": c.get("classification"),
            "weight": c.get("weight"), "quote_text": p["quote_text"],
            "quote_start": p.get("quote_start"), "quote_end": p.get("quote_end"),
            "document_id": p.get("document_id"), "doc_name": doc.get("name"), "doc_url": doc.get("url"),
            "source_url": p.get("source_url") or doc.get("url"), "source": p.get("source"),
            "updated_at": p.get("updated_at"),
        })
    write_jsonl(OUT / "tosdr_points.jsonl", out_points)

    # ---- cases ----
    n_quotes = Counter(p["case_id"] for p in out_points)
    cases_out = {}
    for cid, n in case_count.most_common():
        c = cases.get(cid, {})
        cases_out[str(cid)] = {"id": cid, "title": c.get("title"), "classification": c.get("classification"),
                               "weight": c.get("weight"), "topic_id": c.get("topic_id"), "count": n,
                               "n_services": len(case_services[cid]), "n_quotes": n_quotes[cid]}
    write_json(OUT / "cases.json", cases_out)

    # ---- split: services with approved points or an A-E rating ----
    in_scope = {sid for sid in services if n_points_by_sid[sid] or is_rated(services[sid])}
    train = sorted(domain_of[s] for s in in_scope if not is_test(services[s]))
    test = sorted(domain_of[s] for s in in_scope if is_test(services[s]))
    assert not set(train) & set(test)
    write_json(OUT / "split.json", {
        "seed": SEED, "unit": "service, grouped by primary domain: sha256('42:'+domain) % 100 < 20 -> test",
        "train": train, "test": test})

    # ---- sites ----
    docs_of = defaultdict(list)
    for d in doc_meta.values():
        if d.get("service_id") is not None and d.get("url"):
            docs_of[d["service_id"]].append(d["url"])
    sites = []
    for sid in sorted(in_scope):
        s = services[sid]
        sites.append({
            "domain": domain_of[sid], "name": s.get("name"), "tosdr_id": sid, "service_id": sid,
            "slug": s.get("slug"), "rating": s.get("rating"), "rating_source": s.get("rating_source"),
            "lang": None, "jurisdiction_hint": None, "doc_urls": sorted(set(docs_of[sid])),
            "urls": s.get("urls") or [], "n_points": n_points_by_sid[sid],
            "is_comprehensively_reviewed": s.get("is_comprehensively_reviewed"),
            "split": "test" if is_test(s) else "train", "source": "tosdr", "fetched_at": s.get("fetched_at"),
        })
    write_jsonl(OUT / "sites.jsonl", sites)

    # ---- site docs (rated A-E only; streamed) ----
    n_site_docs = n_site_docs_test = 0
    if not no_docs:
        rated = {sid for sid in in_scope if is_rated(services[sid])}
        by_sid = defaultdict(list)
        for d in src.iter_document_texts(rated):
            by_sid[d["service_id"]].append({
                "id": d["id"], "name": d["name"], "url": d["url"], "text": html_to_text(d.pop("text_html")),
                "updated_at": d.get("updated_at"), "source": d["source"]})
        tmp = OUT / "tosdr_site_docs.jsonl.tmp"
        with open(tmp, "w", encoding="utf-8", newline="\n") as f:
            for sid in sorted(by_sid):
                docs = sorted((x for x in by_sid[sid] if x["text"]), key=doc_priority)[:MAX_DOCS_PER_SITE]
                for x in docs:
                    x["truncated"] = len(x["text"]) > MAX_DOC_CHARS
                    x["text"] = x["text"][:MAX_DOC_CHARS]
                docs.sort(key=lambda x: x["id"])
                if not docs:
                    continue
                s = services[sid]
                rec = {"domain": domain_of[sid], "service_id": sid, "rating": s.get("rating"),
                       "rating_source": s.get("rating_source"),
                       "split": "test" if is_test(s) else "train", "docs": docs}
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                n_site_docs += 1
                n_site_docs_test += rec["split"] == "test"
        tmp.replace(OUT / "tosdr_site_docs.jsonl")

    # ---- case_top.md ----
    srcs = Counter(p["source"] for p in out_points)
    lines = ["# ToS;DR 最常见 case（前 40）", "",
             "由 `scripts/build_dataset.py` 生成。统计口径：status=approved 的 point"
             f"（Zenodo 2023-07 快照 + ToS;DR API 增量）。服务 {len(in_scope)} 个，approved point "
             f"{sum(case_count.values())} 条，带原文引用 {len(out_points)} 条（{dict(srcs)}），case 种类 {len(cases_out)}。", "",
             "| # | case id | title | classification | 出现次数 | 服务数 | 带引用 |", "|---|---|---|---|---|---|---|"]
    for i, c in enumerate(list(cases_out.values())[:40], 1):
        t = (c["title"] or "").replace("|", "\\|")
        lines.append(f"| {i} | {c['id']} | {t} | {c['classification']} | {c['count']} | {c['n_services']} | {c['n_quotes']} |")
    (OUT / "case_top.md").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")

    print(f"services_known={len(services)} sites={len(sites)} approved_points={sum(case_count.values())} "
          f"quoted_points={len(out_points)} {dict(srcs)} cases={len(cases_out)} train={len(train)} test={len(test)} "
          f"site_docs={'skipped' if no_docs else n_site_docs} (test={n_site_docs_test})")


if __name__ == "__main__":
    main()
