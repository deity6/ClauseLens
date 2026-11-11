import sys
sys.path.insert(0, "scripts/bench")
from coverage import fetch_page, extract_text, looks_like_policy, find_policy_links
for u in ["https://www.appinn.net/", "https://lobste.rs/privacy"]:
    p = fetch_page(u, timeout=15)
    t = extract_text(p.get("html",""))[1] if p.get("html") else ""
    print("==", u, "status=", p["status"], "text=", len(t))
    print("   text head:", repr(t[:160]))
    for l in find_policy_links(p.get("html",""), p["final_url"])[:6]:
        print("   link", l["score"], l["url"])
