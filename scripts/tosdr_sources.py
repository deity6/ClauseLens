"""Load + merge ToS;DR sources: Zenodo CSV dump (record 15012282, 2023-07, GPL-3.0) and live API raw files.

Precedence: Zenodo is the base; API data (data/raw/tosdr) overrides where newer
(service rating/name/urls from services.jsonl & service/*.json, cases from cases.json,
points from points.jsonl / service details).
"""
from __future__ import annotations

import csv
import io
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW_API = ROOT / "data" / "raw" / "tosdr"
RAW_ZEN = ROOT / "data" / "raw" / "zenodo_tosdr"
ZENODO_SIZES = {  # expected byte sizes (Zenodo API listing); partial downloads are ignored
    "points.csv": 17316610, "cases.csv": 87139, "topics.csv": 7917,
    "documents.csv": 267789157, "services.csv": 1319970,
}
ZENODO_URL = "https://zenodo.org/records/15012282"

csv.field_size_limit(min(sys.maxsize, 2**31 - 1))


def clean(s):
    if isinstance(s, str):
        return s.encode("utf-8", errors="replace").decode("utf-8", errors="replace")
    return s


def nul(v):
    """Zenodo CSV uses the literal NULL for SQL nulls."""
    return None if v in (None, "NULL") else v


def to_int(v):
    v = nul(v)
    try:
        return int(v) if v not in (None, "") else None
    except ValueError:
        return None


def zenodo_ok(name: str) -> bool:
    p = RAW_ZEN / name
    ok = p.exists() and p.stat().st_size == ZENODO_SIZES[name]
    if p.exists() and not ok:
        print(f"[warn] {name} incomplete ({p.stat().st_size}/{ZENODO_SIZES[name]} B), skipped", file=sys.stderr)
    return ok


def iter_csv(name: str):
    with open(RAW_ZEN / name, "rb") as fb:
        text = io.TextIOWrapper(fb, encoding="utf-8", errors="replace", newline="")
        yield from csv.DictReader((line.replace("\0", "") for line in text))


def read_jsonl(p: Path):
    if not p.exists():
        return []
    rows = []
    with open(p, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return rows


def api_details() -> dict[int, dict]:
    out = {}
    for p in sorted((RAW_API / "service").glob("*.json")) if (RAW_API / "service").exists() else []:
        try:
            d = json.loads(p.read_text("utf-8", errors="replace"))
        except json.JSONDecodeError:
            continue
        if not d.get("_missing"):
            out[d["id"]] = d
    return out


def load_services(details: dict[int, dict]) -> dict[int, dict]:
    sv: dict[int, dict] = {}
    if zenodo_ok("services.csv"):
        for r in iter_csv("services.csv"):
            sid = to_int(r["id"])
            if sid is None:
                continue
            sv[sid] = {
                "id": sid, "name": clean(nul(r["name"])), "slug": nul(r["slug"]),
                "urls": [u.strip() for u in (nul(r["url"]) or "").split(",") if u.strip()],
                "rating": nul(r["rating"]), "rating_source": "zenodo-2023",
                "is_comprehensively_reviewed": r["is_comprehensively_reviewed"] == "True",
                "fetched_at": None,
            }
    for s in read_jsonl(RAW_API / "services.jsonl"):  # live list: current rating for every service
        cur = sv.setdefault(s["id"], {"id": s["id"], "fetched_at": None})
        cur.update({"name": clean(s.get("name")), "slug": s.get("slug"), "urls": s.get("urls") or cur.get("urls") or [],
                    "rating": s.get("rating"), "rating_source": "api",
                    "is_comprehensively_reviewed": s.get("is_comprehensively_reviewed")})
    for sid, d in details.items():
        cur = sv.setdefault(sid, {"id": sid})
        cur.update({"name": clean(d.get("name")), "slug": d.get("slug"), "urls": d.get("urls") or cur.get("urls") or [],
                    "rating": d.get("rating"), "rating_source": "api",
                    "is_comprehensively_reviewed": d.get("is_comprehensively_reviewed"),
                    "fetched_at": d.get("_fetched_at")})
    return sv


def load_cases() -> dict[int, dict]:
    cs: dict[int, dict] = {}
    if zenodo_ok("cases.csv"):
        for r in iter_csv("cases.csv"):
            cid = to_int(r["id"])
            if cid is not None:
                cs[cid] = {"id": cid, "title": clean(nul(r["title"])), "classification": nul(r["classification"]),
                           "weight": to_int(r["score"]), "topic_id": to_int(r["topic_id"]),
                           "description": clean(nul(r["description"]))}
    p = RAW_API / "cases.json"
    if p.exists():
        for k, c in json.loads(p.read_text("utf-8", errors="replace")).items():
            cid = int(k)
            cs.setdefault(cid, {"id": cid}).update({
                kk: c.get(kk) for kk in ("title", "classification", "weight", "topic_id", "description")
                if c.get(kk) is not None})
    return cs


def load_document_meta() -> dict[int, dict]:
    """id -> {id, name, url, service_id}. Zenodo documents.csv (streamed, text dropped) + API detail docs."""
    docs: dict[int, dict] = {}
    if zenodo_ok("documents.csv"):
        for r in iter_csv("documents.csv"):
            did = to_int(r["id"])
            if did is not None:
                docs[did] = {"id": did, "name": clean(nul(r["name"])), "url": nul(r["url"]),
                             "service_id": to_int(r["service_id"])}
    for sid, d in api_details().items():
        for doc in d.get("documents") or []:
            if doc.get("id") is not None:
                docs.setdefault(doc["id"], {}).update({"id": doc["id"], "name": clean(doc.get("name")),
                                                       "url": doc.get("url"), "service_id": sid})
    return docs


def iter_document_texts(service_ids: set[int]):
    """Yield {id,name,url,service_id,text_html,updated_at,source} for documents of the given services."""
    seen = set()
    p = RAW_API / "documents"
    for f in sorted(p.glob("*.json")) if p.exists() else []:
        try:
            d = json.loads(f.read_text("utf-8", errors="replace"))
        except json.JSONDecodeError:
            continue
        sid = d.get("_service_id") or d.get("service_id")
        if not d.get("_missing") and d.get("text") and sid in service_ids:
            seen.add(d["id"])
            yield {"id": d["id"], "name": clean(d.get("name")), "url": d.get("url"), "service_id": sid,
                   "text_html": d["text"], "updated_at": d.get("updated_at"), "source": "api"}
    if zenodo_ok("documents.csv"):
        for r in iter_csv("documents.csv"):
            did, sid = to_int(r["id"]), to_int(r["service_id"])
            if did in seen or sid not in service_ids or not nul(r["text"]):
                continue
            yield {"id": did, "name": clean(nul(r["name"])), "url": nul(r["url"]), "service_id": sid,
                   "text_html": r["text"], "updated_at": nul(r["updated_at"]), "source": "zenodo-2023"}


def load_points(details: dict[int, dict]) -> dict[int, dict]:
    """Approved points: id -> {id, service_id, case_id, document_id, quote_text, quote_start, quote_end,
    source_url, updated_at, source}. quote_text may be empty (point known only from API detail)."""
    pts: dict[int, dict] = {}
    if zenodo_ok("points.csv"):
        for r in iter_csv("points.csv"):
            if r["status"] != "approved":
                continue
            pid = to_int(r["id"])
            if pid is None:
                continue
            pts[pid] = {"id": pid, "service_id": to_int(r["service_id"]), "case_id": to_int(r["case_id"]),
                        "document_id": to_int(r["document_id"]),
                        "quote_text": clean((nul(r["quote_text"]) or "").strip()),
                        "quote_start": to_int(r["quote_start"]), "quote_end": to_int(r["quote_end"]),
                        "source_url": nul(r["source"]), "updated_at": nul(r["updated_at"]),
                        "source": "zenodo-2023"}
    # API service details: membership/status is current; adds points created after 2023
    for sid, d in details.items():
        for pt in d.get("points") or []:
            cid = (pt.get("case") or {}).get("id")
            if pt.get("status") != "approved":
                pts.pop(pt["id"], None)  # no longer approved
                continue
            cur = pts.setdefault(pt["id"], {"id": pt["id"], "quote_text": "", "source": "api"})
            cur.update({"service_id": sid, "case_id": cid, "source_url": pt.get("source") or cur.get("source_url"),
                        "document_id": pt.get("document_id") or cur.get("document_id")})
    for p in read_jsonl(RAW_API / "points.jsonl"):  # /point/v1 full records
        if p.get("status") != "approved":
            pts.pop(p["id"], None)
            continue
        q = clean((p.get("quote_text") or "").strip())
        cur = pts.setdefault(p["id"], {"id": p["id"]})
        cur.update({"service_id": p.get("service_id") or cur.get("service_id"),
                    "case_id": (p.get("case") or {}).get("id") or cur.get("case_id"),
                    "document_id": p.get("document_id") or cur.get("document_id"),
                    "quote_text": q or cur.get("quote_text", ""),
                    "quote_start": p.get("quote_start"), "quote_end": p.get("quote_end"),
                    "source_url": p.get("source") or cur.get("source_url"),
                    "updated_at": p.get("updated_at"), "fetched_at": p.get("_fetched_at"), "source": "api"})
    return pts
