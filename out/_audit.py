import json
from urllib.parse import urlparse
recs=[json.loads(l) for l in open("out/coverage.jsonl",encoding="utf-8") if l.strip()]
def used_fetch(r): return any(s.get("stage")=="fetch" for s in r["stages"])
def cached(r): return any(s.get("cached") for s in r["stages"])
print("=== 所有成功结果的文档归属检查 ===")
for r in recs:
    if not r["ok"]: continue
    dom=r["domain"]
    flags=[]
    for d in r["documents"]:
        h=(urlparse(d["url"]).hostname or "").lower()
        same = h==dom or h.endswith("."+dom)
        # 集团/法务域放宽：同注册域或常见 CDN 法务域
        if not same: flags.append(f"跨域:{h}")
        if d["chars"]<600: flags.append(f"过短:{d['chars']}")
        if "error" in h or "/error" in d["url"]: flags.append("错误页")
    if flags:
        print(f"  {r['site_id']} {r['mode']:<8} {dom:<22} fetch={used_fetch(r)} cached={cached(r)} -> {'; '.join(sorted(set(flags)))}")
print()
print("=== 分类统计 ===")
for mode in ("fuzzy","precise"):
    rs=[r for r in recs if r["mode"]==mode]; ok=[r for r in rs if r["ok"]]
    live=[r for r in ok if used_fetch(r)]
    nonlive=[r for r in ok if not used_fetch(r)]
    print(f"{mode}: 总{len(rs)} 成功{len(ok)} | 实时{len(live)} 非实时{len(nonlive)}")
    print(f"    实时里的站点: {sorted(r['site_id'] for r in live)}")
    print(f"    非实时里的站点: {sorted(r['site_id'] for r in nonlive)}")
