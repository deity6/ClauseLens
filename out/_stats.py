# -*- coding: utf-8 -*-
import json, statistics
recs=[json.loads(l) for l in open("out/coverage.jsonl",encoding="utf-8") if l.strip()]
def used_fetch(r): return any(s.get("stage")=="fetch" for s in r["stages"])
def used_render(r): return any(s.get("stage")=="render" for s in r["stages"])
for mode in ("fuzzy","precise"):
    rs=[r for r in recs if r["mode"]==mode]
    ok=[r for r in rs if r["ok"]]
    live=[r for r in ok if used_fetch(r)]
    snap=[r for r in ok if not used_fetch(r)]
    print(f"== {mode}: 总 {len(rs)}  成功 {len(ok)} ({len(ok)/len(rs)*100:.1f}%)")
    print(f"   实时抓取成功 {len(live)}   registry快照成功 {len(snap)}  ({len(snap)/len(ok)*100:.0f}% of OK)")
    print(f"   其中用到渲染 {sum(1 for r in ok if used_render(r))}")
    print(f"   快照站点: {sorted(r['site_id'] for r in snap)}")
    lat=[r["elapsed"] for r in ok if used_fetch(r)]
    if lat: print(f"   实时成功耗时 中位 {statistics.median(lat):.1f}s  最大 {max(lat):.1f}s")
print()
from collections import Counter
c=Counter(r["code"] for r in recs if not r["ok"]); print("失败分布:", dict(c))
print("总调用:", len(recs), " 总成功:", sum(1 for r in recs if r["ok"]))
# 精确模式里 188 字那种过短命中
for r in recs:
    if r["ok"] and r["chars"]<600:
        print(f"  [短] {r['site_id']} {r['mode']} chars={r['chars']} docs={[d['chars'] for d in r['documents']]} grade={r.get('grade')}")
