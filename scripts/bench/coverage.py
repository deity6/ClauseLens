#!/usr/bin/env python3
"""站点覆盖测试：对线上分析服务逐个站点跑「模糊 / 精确」两种输入，记录失败码与阶段轨迹。

用法
----
    # 1) 探测条款路径（补全 sites 表里的 policy_url）
    python scripts/bench/coverage.py probe --sites scripts/bench/coverage_sites.json

    # 2) 串行跑覆盖矩阵（一次一个，间隔 >=1 秒），结果落 JSONL
    python scripts/bench/coverage.py run --out out/coverage.jsonl

    # 3) 对失败的站做根因诊断（状态码 / HTML 大小 / 正文长度 / SPA 空壳）
    python scripts/bench/coverage.py diagnose --results out/coverage.jsonl

    # 4) 从 JSONL 生成 markdown 总表
    python scripts/bench/coverage.py report --results out/coverage.jsonl

设计要点
--------
* **串行**：服务并发上限 3，这里强制一次一个，默认间隔 1.5 s（`--interval`）。
* **busy 重试**：收到 `code: busy` 等 15 s 重试一次（`--busy-wait`）。
* **不设短超时**：单次分析 5–40 s，默认读超时 200 s。
* **阶段轨迹**：把 SSE 里的 `stage` 事件全记下来——失败时"卡在哪一步"比失败码本身更有用
  （比如 `"渲染首页"` 出现过 = 走过了无头浏览器兜底）。
* **诊断复用后端判据**：能 import `backend/clauselens/discover.py` 时，用**服务同一套**
  `extract_text()` / `looks_like_policy()` 判页面，结论才和服务行为可比。import 不到
  就退化成简单正则（报告里会标注）。

站点列表是参数化的：默认读同目录 `coverage_sites.json`，`--sites` 可换任意一份。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

import requests

BENCH = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(os.path.dirname(BENCH))
DEFAULT_SITES = os.path.join(BENCH, "coverage_sites.json")

API = os.environ.get("CLAUSELENS_API", "https://lens.dohub.tech/api/analyze")

# 与服务同款浏览器 UA：诊断能否"绕过"阻塞时，UA 是第一个变量
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")

# 探条款链接用的锚文本/路径关键词
POLICY_RE = re.compile(
    r"隐私|条款|协议|政策|声明|服务条款|用户协议|个人信息|"
    r"privacy|terms|policy|policies|legal|tos\b|eula|agreement|gdpr|dpa\b", re.I)

# 探测顺序：先首页链接，再常见路径
COMMON_PATHS = [
    "/privacy", "/privacy-policy", "/privacy.html", "/privacy_policy",
    "/terms", "/terms-of-service", "/terms.html", "/terms-of-use",
    "/legal", "/legal/privacy", "/legal/terms", "/user-agreement",
    "/policies/privacy", "/policy/privacy", "/privacy/index.html",
    "/about/privacy", "/site/privacy", "/help/privacy",
]

# ── 后端判据（能 import 就用真正的，保证和服务口径一致） ─────────────────────
try:
    sys.path.insert(0, os.path.join(PROJ, "backend"))
    from clauselens import discover as _discover          # noqa: E402
    from clauselens import net as _net                    # noqa: E402

    def extract_text(html: str):
        return _discover.extract_text(html)

    def looks_like_policy(text: str) -> bool:
        return bool(_discover.looks_like_policy(text))

    def decode_body(raw: bytes, ctype: str = "") -> str:
        return _net.decode_body(raw, ctype)

    JUDGE = "backend.discover+net.decode_body"
except Exception:                                          # pragma: no cover
    JUDGE = "fallback"

    def decode_body(raw: bytes, ctype: str = "") -> str:
        """退化版：严格 UTF-8 → meta charset → GB18030。"""
        m = re.search(r"charset=([\w-]+)", ctype or "", re.I)
        cands = [m.group(1)] if m else []
        mm = re.search(rb'<meta[^>]+charset=["\']?([a-zA-Z0-9_-]+)', raw[:65536], re.I)
        if mm:
            cands.append(mm.group(1).decode("ascii", "ignore"))
        cands.append("utf-8")
        for enc in cands:
            try:
                return raw.decode(enc)
            except (UnicodeDecodeError, LookupError):
                continue
        try:
            return raw.decode("gb18030")
        except UnicodeDecodeError:
            return raw.decode("utf-8", "replace")

    _KEY = re.compile(r"隐私|个人信息|条款|协议|收集|使用|cookie|privacy|personal data|"
                      r"terms|collect|we may|consent|您同意", re.I)

    def extract_text(html: str):
        if not html:
            return "", ""
        m = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
        title = re.sub(r"<[^>]+>", "", m.group(1)).strip() if m else ""
        h = re.sub(r"<(script|style|noscript)\b.*?</\1>", " ", html, flags=re.I | re.S)
        h = re.sub(r"<br\s*/?>|</p>|</div>|</h[1-6]>", "\n", h, flags=re.I)
        t = re.sub(r"<[^>]+>", " ", h)
        t = re.sub(r"&nbsp;?", " ", t)
        t = re.sub(r"[ \t\u00a0]+", " ", t)
        t = re.sub(r"\n\s*\n+", "\n", t)
        return title, t.strip()

    def looks_like_policy(text: str) -> bool:
        return bool(text) and len(text) >= 150 and len(_KEY.findall(text[:20000])) >= 8


# ─────────────────────────────────────────────────────────────── SSE 单次调用
def sse_call(query: str, read_timeout: float = 200.0, busy_wait: float = 15.0,
             max_tries: int = 2) -> dict:
    """跑一次 /api/analyze，返回 {ok, code, status, documents, stages, elapsed, ...}。

    只有 busy 会重试（服务并发满时的正常反馈，不是站点问题）。
    """
    out: dict = {"q": query, "ok": False, "code": None, "status": None,
                 "documents": [], "stages": [], "elapsed": None, "tries": 0,
                 "error_zh": None, "chars": 0}
    for attempt in range(1, max_tries + 1):
        out["tries"] = attempt
        t0 = time.monotonic()
        try:
            res = _sse_once(query, read_timeout)
        except requests.exceptions.Timeout:
            out.update(code="client_timeout", elapsed=round(time.monotonic() - t0, 1),
                       error_zh=f"客户端读超时 {read_timeout}s")
            return out
        except requests.exceptions.RequestException as e:
            out.update(code="client_error", elapsed=round(time.monotonic() - t0, 1),
                       error_zh=f"{type(e).__name__}: {e}"[:200])
            return out
        out["elapsed"] = round(time.monotonic() - t0, 1)
        out["stages"] = res["stages"]
        out["http"] = res["http"]
        if res["result"] is not None:
            r = res["result"]
            docs = r.get("documents") or []
            out.update(ok=True, code="ok", status=200,
                       documents=[{"type": d.get("type"), "chars": d.get("chars"),
                                   "url": d.get("url"), "title": d.get("title")}
                                  for d in docs],
                       chars=sum(int(d.get("chars") or 0) for d in docs),
                       grade=(r.get("score") or {}).get("grade"),
                       score=(r.get("score") or {}).get("value"),
                       tags=len(r.get("tags") or []),
                       jurisdiction=(r.get("jurisdiction") or {}).get("code"),
                       snapshot_used=any("snapshot_at" in d for d in docs))
            return out
        err = res["error"] or {}
        out.update(code=err.get("code") or "no_result",
                   status=err.get("status"), error_zh=err.get("message_zh"))
        if out["code"] == "busy" and attempt < max_tries:
            time.sleep(busy_wait)          # 并发满：等 15 s 再来一次
            continue
        return out
    return out


def _sse_once(query: str, read_timeout: float) -> dict:
    """读一条 SSE 流，抽出 stages / result / error。"""
    stages: list[dict] = []
    result = None
    error = None
    http = None
    buf = b""
    deadline = time.monotonic() + read_timeout
    with requests.get(API, params={"q": query}, stream=True, timeout=(15, read_timeout),
                      headers={"Accept": "text/event-stream", "User-Agent": UA}) as r:
        http = r.status_code
        if http != 200:
            body = r.text[:400]
            raise requests.exceptions.RequestException(f"HTTP {http}: {body}")
        for chunk in r.iter_content(chunk_size=4096):
            if not chunk:
                continue
            buf += chunk
            while b"\n\n" in buf:
                frame, buf = buf.split(b"\n\n", 1)
                ev, data = _parse_frame(frame)
                if ev == "stage":
                    stages.append(data)
                elif ev == "result":
                    result = data
                elif ev == "error":
                    error = data
            if time.monotonic() > deadline:
                break
    # 收尾：流结束时可能残留最后一个帧
    if buf.strip():
        ev, data = _parse_frame(buf)
        if ev == "result":
            result = data
        elif ev == "error":
            error = data
    return {"stages": stages, "result": result, "error": error, "http": http}


def _parse_frame(frame: bytes) -> tuple[str | None, dict]:
    ev = None
    data_lines = []
    for line in frame.decode("utf-8", "replace").splitlines():
        if line.startswith("event:"):
            ev = line[6:].strip()
        elif line.startswith("data:"):
            data_lines.append(line[5:].strip())
    if not data_lines:
        return ev, {}
    try:
        return ev, json.loads("\n".join(data_lines))
    except json.JSONDecodeError:
        return ev, {}


# ──────────────────────────────────────────────────────────── 站点表 / 探测
def load_sites(path: str) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        sites = json.load(f)
    for i, s in enumerate(sites):
        s.setdefault("id", f"s{i + 1:02d}")
        s.setdefault("policy_url", "")
    return sites


def fetch_page(url: str, timeout: float = 25.0, ua: str | None = None) -> dict:
    """抓一页（不抛异常），记状态码 / 体积 / 正文长度。"""
    info = {"url": url, "status": None, "bytes": 0, "text_len": 0, "title": "",
            "err": None, "final_url": url, "ctype": ""}
    try:
        r = requests.get(url, timeout=(12, timeout), allow_redirects=True,
                         headers={"User-Agent": ua or UA, "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"})
        info["status"] = r.status_code
        info["final_url"] = r.url
        info["ctype"] = (r.headers.get("content-type") or "")[:60]
        info["bytes"] = len(r.content)
        if "html" in info["ctype"] or "text" in info["ctype"] or not info["ctype"]:
            # 用服务同款 decode_body 判定编码：自己猜 latin1 会把中文站读成乱码，
            # 后面的 looks_like_policy() 跟着全错，路径探测就白跑了
            html = decode_body(r.content, info["ctype"])
            title, text = extract_text(html)
            info.update(title=title[:100], text_len=len(text), html=html)
    except requests.exceptions.RequestException as e:
        info["err"] = f"{type(e).__name__}: {e}"[:200]
    return info


def find_policy_links(html: str, base_url: str) -> list[dict]:
    """从首页 HTML 里挑出像条款页的链接（按关键词打分排序）。"""
    seen, out = set(), []
    for m in re.finditer(r"<a\b([^>]*)>(.*?)</a>", html or "", re.I | re.S):
        attrs, inner = m.group(1), m.group(2)
        hm = re.search(r'href\s*=\s*["\']([^"\']{1,400})["\']', attrs, re.I)
        if not hm:
            continue
        href = hm.group(1).strip()
        if href.startswith(("javascript:", "mailto:", "tel:", "#")):
            continue
        text = re.sub(r"<[^>]+>", "", inner).strip()[:60]
        hay = f"{href} {text}"
        if not POLICY_RE.search(hay):
            continue
        url = urljoin(base_url, href).split("#")[0]
        if url in seen or url.startswith("data:"):
            continue
        seen.add(url)
        # 打分：路径命中强，锚文本命中弱；带 privacy/terms 的优先
        score = 0
        low = href.lower()
        for kw, w in (("privacy", 10), ("terms", 10), ("policy", 8), ("legal", 6),
                      ("agreement", 6), ("隐私", 10), ("条款", 10), ("协议", 8), ("政策", 8)):
            if kw in low:
                score += w
        if POLICY_RE.search(text):
            score += 3
        out.append({"url": url, "text": text, "score": score})
    out.sort(key=lambda d: -d["score"])
    return out[:8]


def cmd_probe(args) -> int:
    """只读探测：每个站首页有没有条款链接、常见路径哪些能命中。"""
    sites = load_sites(args.sites)
    print(f"# 判据来源: {JUDGE}   站点数: {len(sites)}", flush=True)
    for s in sites:
        if args.only and s["id"] not in args.only.split(","):
            continue
        dom = s["domain"]
        home = fetch_page(f"https://{dom}/")
        print(f"\n=== {s['id']} {s.get('name') or dom} [{s.get('category')}]", flush=True)
        print(f"    首页 https://{dom}/  status={home['status']} bytes={home['bytes']} "
              f"text={home['text_len']} title={home['title'][:40]!r}"
              f"{' err=' + home['err'] if home['err'] else ''}", flush=True)
        links = find_policy_links(home.get("html", ""), home["final_url"])
        if links:
            for l in links[:5]:
                print(f"    link score={l['score']:>2} {l['url']}  ({l['text'][:30]})", flush=True)
        else:
            print("    link: 首页没找到条款链接", flush=True)
        # 没有链接才探常见路径，省时间
        if not links or args.deep:
            for p in COMMON_PATHS[: (16 if args.deep else 8)]:
                u = f"https://{dom}{p}"
                pi = fetch_page(u, timeout=12)
                if pi["status"] == 200 and pi["text_len"] >= 120:
                    ok = looks_like_policy(
                        extract_text(pi.get("html", ""))[1]) if pi.get("html") else False
                    print(f"    path {p:<22} status={pi['status']} text={pi['text_len']:<6} "
                          f"policy={int(ok)}", flush=True)
                elif pi["status"] not in (404, 410, None):
                    print(f"    path {p:<22} status={pi['status']} text={pi['text_len']}", flush=True)
                time.sleep(0.3)
        time.sleep(args.interval)
    return 0


# ──────────────────────────────────────────────────────────────────── 跑矩阵
def cmd_run(args) -> int:
    sites = load_sites(args.sites)
    if args.only:
        keep = set(args.only.split(","))
        sites = [s for s in sites if s["id"] in keep or s["domain"] in keep]
    os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)

    done = set()
    if args.resume and os.path.exists(args.out):
        with open(args.out, encoding="utf-8") as f:
            for line in f:
                try:
                    r = json.loads(line)
                    done.add((r["site_id"], r["mode"]))
                except Exception:
                    pass
        print(f"# 续跑：已完成 {len(done)} 条", flush=True)

    print(f"# API={API}  站点={len(sites)}  判据={JUDGE}", flush=True)
    n = 0
    for s in sites:
        for mode in ("fuzzy", "precise"):
            q = s["domain"] if mode == "fuzzy" else s.get("policy_url")
            if mode == "precise" and not q:
                print(f"{s['id']} {mode:<8} SKIP 没有 policy_url", flush=True)
                continue
            if (s["id"], mode) in done:
                continue
            n += 1
            res = sse_call(q, read_timeout=args.timeout, busy_wait=args.busy_wait)
            rec = {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                   "site_id": s["id"], "name": s.get("name"), "category": s.get("category"),
                   "domain": s["domain"], "mode": mode, "q": q, **res}
            with open(args.out, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            flag = "OK  " if rec["ok"] else rec["code"]
            extra = (f"docs={len(rec['documents'])} chars={rec['chars']} grade={rec.get('grade')}"
                     if rec["ok"] else f"{rec.get('error_zh') or ''}")
            stages = " > ".join(str(st.get("stage")) for st in rec["stages"])
            print(f"{s['id']} {mode:<8} {flag:<16} {rec['elapsed']:>6}s  {extra}", flush=True)
            print(f"        stages: {stages[:160]}", flush=True)
            if n < args.max_calls:
                time.sleep(args.interval)     # 串行 + 间隔，别触发并发上限
        if args.max_calls and n >= args.max_calls:
            print(f"# 达到 --max-calls={args.max_calls}，先停", flush=True)
            break
    print(f"# 结果写入 {args.out}", flush=True)
    return 0


# ─────────────────────────────────────────────────────────────────── 诊断
def cmd_diagnose(args) -> int:
    """对失败的站做进一步诊断：是 SPA 空壳、内容太短、路径不对，还是被拒。"""
    recs = []
    with open(args.results, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                recs.append(json.loads(line))
    fails = [r for r in recs if not r["ok"]]
    sites = {s["domain"]: s for s in load_sites(args.sites)}
    if args.only_codes:
        keep = set(args.only_codes.split(","))
        fails = [r for r in fails if r["code"] in keep]
    if not fails:
        print("# 没有失败记录")
        return 0

    print(f"# 判据来源: {JUDGE}；诊断 {len(fails)} 条失败", flush=True)
    rows = []
    for r in fails:
        s = sites.get(r["domain"], {})
        target = r["q"] if r["mode"] == "precise" else f"https://{r['domain']}/"
        if r["mode"] == "precise" and not target.startswith("http"):
            target = r["q"]
        # 精确模式：诊断那个条款页；模糊模式：诊断首页 + 首页上的条款链接
        d = {"site_id": r["site_id"], "domain": r["domain"], "mode": r["mode"],
             "code": r["code"], "tested_url": target}
        pg = fetch_page(target if target.startswith("http") else f"https://{target}/")
        d.update(page_status=pg["status"], page_bytes=pg["bytes"], page_text=pg["text_len"],
                 page_title=pg["title"][:60], page_err=pg["err"])
        if pg.get("html"):
            _t, txt = extract_text(pg["html"])
            d["policy_verdict"] = looks_like_policy(txt)
            d["script_tags"] = len(re.findall(r"<script\b", pg["html"], re.I))
            # SPA 空壳特征：正文极短 + 大量 script + 有 root 挂载点
            d["spa_shell"] = (pg["text_len"] < 400 and d["script_tags"] >= 3
                              and bool(re.search(r'id=["\'](root|app|__next|__nuxt)["\']', pg["html"], re.I)))
        # 首页链接面（模糊模式最关键的证据）
        if r["mode"] == "fuzzy":
            links = find_policy_links(pg.get("html", ""), pg["final_url"])
            d["home_links"] = [l["url"] for l in links[:4]]
            d["home_link_n"] = len(links)
        # 换个 UA 再试一次，判断是不是 UA 级拦截
        if pg["status"] and pg["status"] >= 400:
            alt = fetch_page(target, ua=UA)
            d["ua_retry_status"] = alt["status"]
        rows.append(d)
        print(json.dumps(d, ensure_ascii=False), flush=True)
        time.sleep(args.interval)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(rows, f, ensure_ascii=False, indent=1)
        print(f"# 诊断写入 {args.out}")
    return 0


# ─────────────────────────────────────────────────────────────────── 报表
def cmd_report(args) -> int:
    recs = []
    with open(args.results, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                recs.append(json.loads(line))
    by_site: dict[str, dict] = {}
    for r in recs:
        e = by_site.setdefault(r["site_id"], {"meta": r, "fuzzy": None, "precise": None})
        e[r["mode"]] = r

    def cell(r):
        if r is None:
            return "—", ""
        if r["ok"]:
            return f"✅ {len(r['documents'])}篇/{r['chars']}字", ""
        return f"❌ {r['code']}" + (f"({r['status']})" if r.get("status") else ""), ""

    print("| # | 站点 | 类型 | 模糊 | 精确 | 耗时(模糊/精确) |")
    print("|---|---|---|---|---|---|")
    for sid, e in by_site.items():
        m = e["meta"]
        f_, _ = cell(e["fuzzy"])
        p_, _ = cell(e["precise"])
        ft = f"{e['fuzzy']['elapsed']}s" if e["fuzzy"] else "—"
        pt = f"{e['precise']['elapsed']}s" if e["precise"] else "—"
        print(f"| {sid} | {m['domain']} | {m.get('category')} | {f_} | {p_} | {ft}/{pt} |")

    for mode in ("fuzzy", "precise"):
        rs = [r for r in recs if r["mode"] == mode]
        ok = sum(1 for r in rs if r["ok"])
        print(f"\n{mode}: {ok}/{len(rs)} = {ok / len(rs) * 100:.1f}%" if rs else "")
    from collections import Counter
    c = Counter(r["code"] for r in recs if not r["ok"])
    print("\n失败分布:", dict(c))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sites", default=DEFAULT_SITES, help="站点表 JSON")
    ap.add_argument("--interval", type=float, default=1.5, help="两次请求间隔秒（>=1）")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("probe", help="探测条款路径")
    p.add_argument("--only", default="")
    p.add_argument("--deep", action="store_true", help="即使找到链接也探常见路径")
    p.set_defaults(func=cmd_probe)

    r = sub.add_parser("run", help="跑覆盖矩阵")
    r.add_argument("--out", default=os.path.join(PROJ, "out", "coverage.jsonl"))
    r.add_argument("--timeout", type=float, default=200.0)
    r.add_argument("--busy-wait", type=float, default=15.0)
    r.add_argument("--only", default="")
    r.add_argument("--max-calls", type=int, default=0)
    r.add_argument("--resume", action="store_true")
    r.set_defaults(func=cmd_run)

    d = sub.add_parser("diagnose", help="失败根因诊断")
    d.add_argument("--results", required=True)
    d.add_argument("--only-codes", default="")
    d.add_argument("--out", default="")
    d.set_defaults(func=cmd_diagnose)

    rp = sub.add_parser("report", help="生成 markdown 总表")
    rp.add_argument("--results", required=True)
    rp.set_defaults(func=cmd_report)

    args = ap.parse_args()
    args.interval = max(1.0, args.interval)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
