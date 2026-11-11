import json
from urllib.parse import urlparse
recs=[json.loads(l) for l in open("out/coverage.jsonl",encoding="utf-8") if l.strip()]
sites={s["id"]:s for s in json.load(open("scripts/bench/coverage_sites.json",encoding="utf-8"))}
def used_fetch(r): return any(s.get("stage")=="fetch" for s in r["stages"])
def is_cached(r): return any(s.get("cached") for s in r["stages"])
by={}
for r in recs: by.setdefault(r["site_id"],{})[r["mode"]]=r

def nature(r):
    if r is None: return "—"
    if not r["ok"]: return "—"
    if is_cached(r): return "缓存"
    if not used_fetch(r): return "快照"
    return "实时"
def cell(r):
    if r is None: return "—"
    if r["ok"]:
        n=nature(r)
        return f"✅ {len(r['documents'])}篇/{r['chars']}字（{n}）"
    c=r["code"]
    if r.get("status"): c+=f" {r['status']}"
    return f"❌ {c}"
print("| # | 站点 | 类型 | 模糊 | 精确 | 耗时 模/精 |")
print("|---|---|---|---|---|---|")
for sid in sorted(by):
    e=by[sid]; m=sites[sid]
    ft=f"{e['fuzzy']['elapsed']}s" if e.get("fuzzy") else "—"
    pt=f"{e['precise']['elapsed']}s" if e.get("precise") else "—"
    print(f"| {sid} | {m['domain']} | {m['category']} | {cell(e.get('fuzzy'))} | {cell(e.get('precise'))} | {ft}/{pt} |")
