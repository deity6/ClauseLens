import json, statistics
recs=[json.loads(l) for l in open("out/coverage.jsonl",encoding="utf-8") if l.strip()]
def rf(r): return any(s.get("stage")=="fetch" for s in r["stages"])
def rr(r): return any(s.get("stage")=="render" for s in r["stages"])
for m in ("fuzzy","precise"):
    rs=[r for r in recs if r["mode"]==m]
    print(f"{m}: n={len(rs)} 中位耗时={statistics.median([r['elapsed'] for r in rs]):.1f}s 总耗时={sum(r['elapsed'] for r in rs):.0f}s 用过渲染={sum(1 for r in rs if rr(r))}")
ok=[r for r in recs if r["ok"]]
print("OK 里用过渲染:", [r['site_id']+':'+r['mode'] for r in ok if rr(r)])
print("全部 77 次总耗时:", round(sum(r["elapsed"] for r in recs)))
print("最长:", max(recs, key=lambda r: r["elapsed"])["site_id"], max(r["elapsed"] for r in recs))
