# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, "scripts/bench")
from coverage import fetch_page, extract_text, looks_like_policy
import urllib3; urllib3.disable_warnings()

CAND = [
 ("s01","https://tool.lu/privacy"), ("s01","https://tool.lu/terms"), ("s01","https://tool.lu/about"),
 ("s02","https://xiezuocat.com/privacy"), ("s02","https://metaso.cn/privacy"),
 ("s03","https://www.appinn.net/privacy/"), ("s04","https://luolei.org/privacy/"),
 ("s06","https://hojoai.com/privacy-policy"), ("s06","https://hojoai.com/zh-hans/privacy"),
 ("s09","https://www.taobao.com/go/chn/taobao/terms/privacy_policy.php"),
 ("s10","https://about.jd.com/privacy/"), ("s10","https://help.jd.com/user/issue/list-112.html"),
 ("s11","https://www.bilibili.com/blackboard/privacy-pc.html"),
 ("s13","https://www.xiaohongshu.com/crown/community/privacy"),
 ("s13","https://www.xiaohongshu.com/protocols/privacy"),
 ("s16","https://everhour.com/policy"),
 ("s36","https://www.alipay.com/privacy.htm"), ("s36","https://render.alipay.com/p/f/fd-j1xcs5me/privacy.html"),
 ("s39","https://lobste.rs/about"), ("s39","https://lobste.rs/privacy"),
 ("s05","https://www.ezg.com/zh/privacy-policy"),
 ("s07","https://www.cosmoplat-aiot.com/policy-agreement/1.html"),
]
for sid, u in CAND:
    p = fetch_page(u, timeout=15)
    verdict = ""
    if p.get("html"):
        verdict = "policy=%d" % looks_like_policy(extract_text(p["html"])[1])
    print("%-4s %-62s status=%-4s bytes=%-8s text=%-6s %s %s" % (
        sid, u[:62], p["status"], p["bytes"], p["text_len"], verdict, (p["err"] or "")[:70]), flush=True)
