"""泛用性探针：拿一批站点跑完整分析，统计成功率、失败码和耗时。

用法：
    python scripts/probe_sites.py                    # 跑内置的 40 个站点
    python scripts/probe_sites.py baidu.com github.com
    python scripts/probe_sites.py --file sites.txt   # 每行一个域名

输出：控制台逐条结果 + 末尾汇总 + eval/probe_results.json
需要境外出口时先设环境变量：
    $env:CLAUSELENS_EGRESS = "instabox:<machine-id>"
"""
import json
import sys
import time
import traceback
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from clauselens.pipeline import analyze  # noqa: E402

DEFAULT = [
    # 中文中小站
    "juejin.cn", "segmentfault.com", "v2ex.com", "gitee.com", "oschina.net",
    "sspai.com", "xiaoyuzhoufm.com", "ifanr.com", "jianshu.com", "csdn.net",
    "ruanyifeng.com", "coolapk.com", "hostloc.com", "52pojie.cn", "tianyancha.com",
    # 英文中小站
    "overreacted.io", "danluu.com", "jvns.ca", "simonwillison.net", "cuttle.xyz",
    "fastmail.com", "proton.me", "tutanota.com", "mastodon.social", "bsky.app",
    "signal.org", "eff.org", "archive.org", "duckduckgo.com", "stackoverflow.com",
    "vercel.com", "netlify.com", "digitalocean.com", "heroku.com", "linode.com",
    "medium.com", "notion.so", "figma.com", "obsidian.md", "todoist.com",
]


def targets() -> list[str]:
    args = sys.argv[1:]
    if args[:1] == ["--file"]:
        return [ln.strip() for ln in Path(args[1]).read_text(encoding="utf-8").splitlines()
                if ln.strip() and not ln.startswith("#")]
    return args or DEFAULT


def main() -> int:
    rows, names = [], targets()
    for i, dom in enumerate(names, 1):
        t0 = time.monotonic()
        rec = {"domain": dom, "ok": False, "code": "", "msg": "", "docs": 0,
               "doc_urls": [], "tags": 0, "grade": "", "score": None, "warnings": []}
        try:
            for ev, data in analyze(dom, use_cache=False):
                if ev == "error":
                    rec["code"] = data.get("code", "?")
                    rec["msg"] = (data.get("message_zh") or "")[:80]
                    break
                if ev == "result":
                    rec["ok"] = True
                    rec["docs"] = len(data["documents"])
                    rec["doc_urls"] = [f"{d['type']}:{d['url']}" for d in data["documents"]]
                    rec["tags"] = len(data["tags"])
                    rec["warnings"] = [w["code"] for w in data.get("warnings", [])]
                    rec["grade"] = data["score"]["grade"]
                    rec["score"] = data["score"]["value"]
        except Exception as e:
            rec["code"] = "EXCEPTION"
            rec["msg"] = f"{type(e).__name__}: {e}"[:120]
            rec["tb"] = traceback.format_exc()[-500:]
        rec["sec"] = round(time.monotonic() - t0, 1)
        rows.append(rec)
        tail = (f"docs={rec['docs']} tags={rec['tags']} {rec['grade']} {rec['score']}"
                + (f" warn={','.join(rec['warnings'])}" if rec["warnings"] else "")) if rec["ok"] \
            else f"{rec['code']} {rec['msg']}"
        print(f"[{i:2}/{len(names)}] {'OK  ' if rec['ok'] else 'FAIL'} {dom:<22} {rec['sec']:>5.1f}s {tail}")

    ok = sum(1 for r in rows if r["ok"])
    print(f"\n=== {ok}/{len(rows)} 成功 ({ok * 100 // max(1, len(rows))}%) ===")
    print("失败码分布:", dict(Counter(r["code"] for r in rows if not r["ok"])))
    if ok:
        print("成功站平均耗时: %.1fs" % (sum(r["sec"] for r in rows if r["ok"]) / ok))
    out = ROOT / "eval" / "probe_results.json"
    out.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    print("明细 ->", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
