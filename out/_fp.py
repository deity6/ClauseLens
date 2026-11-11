import sys; sys.path.insert(0,"scripts/bench")
from coverage import fetch_page, extract_text, looks_like_policy
for u in ["https://error.taobao.com/tbpc/error.html", "https://www.alipay.com/"]:
    p=fetch_page(u, timeout=15)
    t=extract_text(p.get("html",""))[1] if p.get("html") else ""
    print("==",u,"status=",p["status"],"text=",len(t),"policy=",looks_like_policy(t))
    print("   ", repr(t[:300]))
