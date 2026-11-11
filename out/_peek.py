import json
recs=[json.loads(l) for l in open("out/coverage.jsonl",encoding="utf-8") if l.strip()]
for r in recs:
    if r["site_id"] in ("s36","s05","s27","s31","s09") :
        print(r["site_id"], r["mode"], "ok=",r["ok"], "chars=",r["chars"])
        for d in r["documents"]:
            print("    doc", d["type"], d["chars"], d["url"][:95])
