"""ToS;DR public API harvester (resumable).

Usage:
  python scripts/harvest_tosdr.py services
  python scripts/harvest_tosdr.py details [--target 1200] [--max 3000]
  python scripts/harvest_tosdr.py cases
  python scripts/harvest_tosdr.py points [--services 1000]
  python scripts/harvest_tosdr.py documents [--train-docs 150]
  python scripts/harvest_tosdr.py all        # services -> details -> cases -> points
  python scripts/harvest_tosdr.py longrun    # details -> cases -> documents/points interleaved

documents: full text (HTML) of documents of rated (A-E) services: every test-split
service + the first N rated train-split services (split rule in tosdr_common.py).

All subcommands skip what's already on disk. Only one harvester process should
run at a time (the rate limiter is per-process). Default pace: <= 0.77 req/s.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from tosdr_common import is_rated, is_test  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "tosdr"
SERVICE_DIR = RAW / "service"
SERVICES_FILE = RAW / "services.jsonl"
POINTS_FILE = RAW / "points.jsonl"
POINTS_FAILED = RAW / "points_failed.jsonl"
CASES_FILE = RAW / "cases.json"
ORDER_FILE = RAW / "details_order.json"
DOC_DIR = RAW / "documents"
LOG_FILE = RAW / "harvest.log"
API = "https://api.tosdr.org"
MIN_INTERVAL = 1.3  # seconds between requests (~0.77 req/s)

log = logging.getLogger("harvest")


# ---------- helpers ----------

def clean(obj):
    """Recursively replace lone surrogates / undecodable chars in strings."""
    if isinstance(obj, str):
        return obj.encode("utf-8", errors="replace").decode("utf-8", errors="replace")
    if isinstance(obj, list):
        return [clean(x) for x in obj]
    if isinstance(obj, dict):
        return {clean(k): clean(v) for k, v in obj.items()}
    return obj


def dumps(obj) -> str:
    return json.dumps(clean(obj), ensure_ascii=False)


def write_json(path: Path, obj) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(clean(obj), ensure_ascii=False, indent=1))
        f.write("\n")
    os.replace(tmp, path)


def append_jsonl(path: Path, obj) -> None:
    with open(path, "a", encoding="utf-8", newline="\n") as f:
        f.write(dumps(obj) + "\n")
        f.flush()


def read_jsonl(path: Path):
    if not path.exists():
        return []
    out = []
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    log.warning("skip corrupt line in %s", path.name)
    return out


class Client:
    def __init__(self):
        self.s = requests.Session()
        self.s.headers["User-Agent"] = "ClauseLens-research-harvester/0.1 (polite; <=1 req/s)"
        self.last = 0.0
        self.count = 0

    def get(self, path: str, params: dict) -> dict | None:
        """Returns parsed JSON, or None on 404 / permanent failure."""
        backoff = 10.0
        for attempt in range(8):
            wait = MIN_INTERVAL - (time.monotonic() - self.last)
            if wait > 0:
                time.sleep(wait)
            self.last = time.monotonic()
            self.count += 1
            try:
                r = self.s.get(API + path, params=params, timeout=40)
            except requests.RequestException as e:
                log.warning("net error %s %s: %s (retry in %.0fs)", path, params, e, backoff)
                time.sleep(backoff)
                backoff = min(backoff * 2, 300)
                continue
            if r.status_code == 429:
                reset = r.headers.get("Retry-After") or r.headers.get("X-RateLimit-Reset") or "5"
                try:
                    delay = max(float(reset), 5.0) + attempt * 5
                except ValueError:
                    delay = 10.0
                log.warning("429 on %s %s, sleep %.0fs", path, params, delay)
                time.sleep(delay)
                continue
            if r.status_code == 404:
                return None
            if r.status_code >= 500:
                log.warning("HTTP %s on %s %s (retry in %.0fs)", r.status_code, path, params, backoff)
                time.sleep(backoff)
                backoff = min(backoff * 2, 300)
                continue
            if r.status_code != 200:
                log.warning("HTTP %s on %s %s, giving up", r.status_code, path, params)
                return None
            try:
                return clean(json.loads(r.content.decode("utf-8", errors="replace")))
            except json.JSONDecodeError:
                log.warning("bad JSON on %s %s (retry)", path, params)
                time.sleep(backoff)
                continue
        log.error("giving up on %s %s", path, params)
        return None


# ---------- subcommands ----------

def cmd_services(c: Client, args) -> None:
    existing = read_jsonl(SERVICES_FILE)
    seen = {s["id"] for s in existing}
    pages_done_file = RAW / "services_pages.json"
    pages_done = set(json.loads(pages_done_file.read_text("utf-8"))) if pages_done_file.exists() else set()
    page, end = 1, None
    while end is None or page <= end:
        if page in pages_done and end is not None:
            page += 1
            continue
        d = c.get("/service/v3/", {"page": page})
        if d is None:
            log.error("services page %d failed", page)
            page += 1
            continue
        end = d.get("page", {}).get("end", page)
        if page not in pages_done:
            new = 0
            for s in d.get("services", []):
                if s["id"] not in seen:
                    seen.add(s["id"])
                    append_jsonl(SERVICES_FILE, s)
                    new += 1
            pages_done.add(page)
            write_json(pages_done_file, sorted(pages_done))
            log.info("services page %d/%d: +%d (total %d)", page, end, new, len(seen))
        page += 1
    log.info("services done: %d", len(seen))


def detail_order(services: list[dict]) -> list[int]:
    rated = [s for s in services if s.get("rating") not in (None, "N/A", "")]
    unrated = [s for s in services if s.get("rating") in (None, "N/A", "")]
    rated.sort(key=lambda s: (not s.get("is_comprehensively_reviewed"), str(s.get("rating")), s["id"]))
    # N/A: comprehensively reviewed first, then most recently updated (more likely to have points)
    unrated.sort(key=lambda s: (not s.get("is_comprehensively_reviewed"), "".join(
        chr(0x10FFFF - ord(ch)) for ch in str(s.get("updated_at") or ""))))
    return [s["id"] for s in rated] + [s["id"] for s in unrated]


def load_detail(sid: int) -> dict | None:
    p = SERVICE_DIR / f"{sid}.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text("utf-8", errors="replace"))
    except json.JSONDecodeError:
        return None


def cmd_details(c: Client, args) -> None:
    SERVICE_DIR.mkdir(parents=True, exist_ok=True)
    services = read_jsonl(SERVICES_FILE)
    if not services:
        sys.exit("run `services` first")
    order = detail_order(services)
    write_json(ORDER_FILE, order)
    with_points = fetched = 0
    for sid in order:
        if with_points >= args.target:
            break
        if fetched >= args.max:
            break
        d = load_detail(sid)
        if d is None:
            d = c.get("/service/v3/", {"id": sid})
            if d is None:
                d = {"id": sid, "_missing": True, "points": [], "documents": []}
            d["_fetched_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            write_json(SERVICE_DIR / f"{sid}.json", d)
        fetched += 1
        if d.get("points"):
            with_points += 1
        if fetched % 25 == 0:
            log.info("details %d fetched, %d with points (req=%d)", fetched, with_points, c.count)
    log.info("details done: %d fetched, %d with points", fetched, with_points)


def iter_details():
    for p in sorted(SERVICE_DIR.glob("*.json")):
        try:
            yield json.loads(p.read_text("utf-8", errors="replace"))
        except json.JSONDecodeError:
            continue


def cmd_cases(c: Client, args) -> None:
    cases = json.loads(CASES_FILE.read_text("utf-8")) if CASES_FILE.exists() else {}
    seen_in_details: dict[str, dict] = {}
    for d in iter_details():
        for pt in d.get("points") or []:
            cs = pt.get("case")
            if cs and cs.get("id") is not None:
                seen_in_details.setdefault(str(cs["id"]), cs)
    todo = [k for k in seen_in_details if k not in cases]
    log.info("cases: %d seen, %d to fetch", len(seen_in_details), len(todo))
    for i, cid in enumerate(todo):
        d = c.get("/case/v3/", {"id": cid})
        rec = d if d else dict(seen_in_details[cid], _from="service_detail")
        rec["_fetched_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        cases[cid] = rec
        if (i + 1) % 20 == 0 or i + 1 == len(todo):
            write_json(CASES_FILE, cases)
            log.info("cases %d/%d", i + 1, len(todo))
    write_json(CASES_FILE, cases)
    log.info("cases done: %d", len(cases))


def points_todo(args) -> list[tuple[int, int]]:
    order = json.loads(ORDER_FILE.read_text("utf-8")) if ORDER_FILE.exists() else []
    done = {p["id"] for p in read_jsonl(POINTS_FILE)} | {p["id"] for p in read_jsonl(POINTS_FAILED)}
    todo = []
    n_services = 0
    for sid in order:
        d = load_detail(sid)
        if d is None:
            continue
        if not d.get("points"):
            continue
        n_services += 1
        if n_services > args.services:
            break
        for pt in d["points"]:
            if pt.get("status") == "approved" and pt["id"] not in done:
                todo.append((sid, pt["id"]))
    log.info("points: %d already done, %d to fetch (from %d services)", len(done), len(todo),
             min(n_services, args.services))
    return todo


def fetch_point(c: Client, sid: int, pid: int) -> None:
    d = c.get("/point/v1/", {"id": pid})
    if d is None:
        append_jsonl(POINTS_FAILED, {"id": pid, "service_id": sid})
    else:
        d["service_id"] = sid
        d["_fetched_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        append_jsonl(POINTS_FILE, d)


def cmd_points(c: Client, args) -> None:
    todo = points_todo(args)
    for i, (sid, pid) in enumerate(todo):
        fetch_point(c, sid, pid)
        if (i + 1) % 100 == 0:
            log.info("points %d/%d", i + 1, len(todo))
    log.info("points done")


def documents_todo(args) -> list[tuple[int, int, bool]]:
    order = json.loads(ORDER_FILE.read_text("utf-8")) if ORDER_FILE.exists() else []
    DOC_DIR.mkdir(parents=True, exist_ok=True)
    have = {int(p.stem) for p in DOC_DIR.glob("*.json")}
    test_q, train_q, n_train = [], [], 0
    for sid in order:
        d = load_detail(sid)
        if not d or d.get("_missing") or not is_rated(d):
            continue
        test = is_test(d)
        if not test:
            if n_train >= args.train_docs:
                continue
            n_train += 1
        for doc in d.get("documents") or []:
            if doc.get("id") is not None and doc["id"] not in have:
                (test_q if test else train_q).append((sid, doc["id"], test))
    log.info("documents: %d on disk, todo test=%d train=%d", len(have), len(test_q), len(train_q))
    return test_q + train_q


def fetch_document(c: Client, sid: int, did: int, test: bool) -> None:
    d = c.get("/document/v1/", {"id": did})
    rec = (d or {}).get("parameters") or {"id": did, "_missing": True}
    rec["_service_id"] = sid
    rec["_split"] = "test" if test else "train"
    rec["_fetched_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    write_json(DOC_DIR / f"{did}.json", rec)


def cmd_documents(c: Client, args) -> None:
    todo = documents_todo(args)
    for i, t in enumerate(todo):
        fetch_document(c, *t)
        if (i + 1) % 25 == 0:
            log.info("documents %d/%d", i + 1, len(todo))
    log.info("documents done")


def cmd_mixed(c: Client, args) -> None:
    """Interleave documents and points on one rate limiter (2 docs : 1 point until docs run out)."""
    docs, pts = documents_todo(args), points_todo(args)
    i = j = k = 0
    while i < len(docs) or j < len(pts):
        if i < len(docs) and (k % 3 != 2 or j >= len(pts)):
            fetch_document(c, *docs[i]); i += 1
        else:
            fetch_point(c, *pts[j]); j += 1
        k += 1
        if k % 100 == 0:
            log.info("mixed: documents %d/%d, points %d/%d (req=%d)", i, len(docs), j, len(pts), c.count)
    log.info("mixed done: documents %d, points %d", i, j)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["services", "details", "cases", "points", "documents", "all", "longrun"])
    ap.add_argument("--target", type=int, default=1200, help="details: stop after N services with points (order: rated first)")
    ap.add_argument("--max", type=int, default=4000, help="details: hard cap on fetched services")
    ap.add_argument("--services", type=int, default=1000, help="points: first N services (with points) in details order")
    ap.add_argument("--train-docs", type=int, default=150, help="documents: rated train-split services to include")
    args = ap.parse_args()

    RAW.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.FileHandler(LOG_FILE, encoding="utf-8"), logging.StreamHandler(sys.stdout)],
    )
    c = Client()
    steps = {"all": ["services", "details", "cases", "points"],
             "longrun": ["details", "cases", "mixed"]}.get(args.cmd, [args.cmd])
    fns = {"services": cmd_services, "details": cmd_details, "cases": cmd_cases, "points": cmd_points,
           "documents": cmd_documents, "mixed": cmd_mixed}
    for step in steps:
        log.info("=== %s ===", step)
        fns[step](c, args)
    log.info("finished %s (requests=%d)", args.cmd, c.count)


if __name__ == "__main__":
    main()
