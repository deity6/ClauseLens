"""分析流水线：以生成器形式逐阶段产出事件（供 SSE 推送）。"""
from __future__ import annotations

import hashlib
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse, urlunparse

import requests

from . import discover, net, render
from .detect import detect, is_zh, split_sentences
from .jurisdiction import JURISDICTIONS, check, detect_jurisdiction
from .score import score
from .taxonomy import TAG_BY_ID

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / "data" / "cache"
CACHE_TTL = 24 * 3600
DOC_TYPE_ZH = {"privacy": "隐私政策", "terms": "用户协议", "cookie": "Cookie 政策", "other": "法律声明"}
GENERIC_ANCHOR = re.compile(r"^(?:点击|点此|这里|此处|查看|详情|more|here|click|link|了解更多)", re.I)
DEADLINE = 40  # 秒：整次分析的抓取预算
ANALYZE_BUDGET = 65  # 秒：首页 + 补探 + 抓取的总硬上限（走境外出口时单页会慢一些）


def _left(t0: float, cap: float) -> float:
    return max(3.0, cap - (time.monotonic() - t0))

# 文档 URL 里的语言路径段：/zh/... 与 /en/... 是同一份文档的不同语言版本
_LANG_SEG = re.compile(
    r"/(?:zh|zh-cn|zh-tw|zh-hans|zh-hant|en|en-us|en-gb|fr|de|es|ja|ko|ru|pt|it|nl|tr|ar|hi|id|vi|th|pl|sv|"
    r"da|fi|no|cs|hu|ro|el|he|uk|bg|sk|hr|sl|lt|lv|et|ca|fa|ur|ms|bn|ta)(?:[-_][a-z]{2,4})?(?=/)", re.I)
_HAN_RE = re.compile(r"[\u4e00-\u9fff]")
_LAT_RE = re.compile(r"[A-Za-z]")
_IPV4_RE = re.compile(r"^\d{1,3}(\.\d{1,3}){3}$")


def _url_dup_key(url: str) -> str:
    p = urlparse(url)
    return f"{p.netloc}{_LANG_SEG.sub('', p.path or '/').rstrip('/')}"


def _alt_host_url(url: str) -> str | None:
    """裸域 ↔ www 互换。

    很多站的裸域和 www 是两台机器、两张证书：裸域 TLS 挂掉而 www 正常，或者反过来。
    只试一种就下「没有条款」，等于把「我们没找对门」说成「对方没有」。
    实测（2026-11-12 覆盖报告）：cosmoplat-aiot.com 裸域证书失败、www 上有 13KB 静态隐私政策；
    appinn.net 裸域无 A 记录、www 200；doulor.cn 裸域超时、cloud. 子域正常。
    """
    p = urlparse(url)
    host = p.hostname or ""
    if not host or _IPV4_RE.match(host):
        return None                       # IP 不换
    if host.startswith("www."):
        alt = host[4:]
    elif host.count(".") == 1:
        alt = "www." + host               # 只有二级域才加 www，cloud.x.com 这类子域不动
    else:
        return None
    port = f":{p.port}" if p.port else ""
    return urlunparse(p._replace(netloc=alt + port))


def dominant_zh(texts: dict[str, str]) -> bool:
    """按字符量判主语言。不能只看开头——同一站点的文档顺序不保证先中文后英文。"""
    cjk = sum(len(_HAN_RE.findall(t[:20000])) for t in texts.values())
    lat = sum(len(_LAT_RE.findall(t[:20000])) for t in texts.values())
    return cjk >= lat * 0.25


def read_minutes(text: str) -> int:
    if is_zh(text):
        return max(1, round(len(text) / 400))
    return max(1, round(len(text.split()) / 230))


_registry: dict | None = None
REGISTRY = ROOT / "data" / "processed" / "registry.json"


SNAPSHOT_DIR = ROOT / "data" / "processed" / "snapshots"


def load_snapshot(ref: str | None, url: str) -> str | None:
    if not ref:
        return None
    p = (SNAPSHOT_DIR / ref).resolve()
    if SNAPSHOT_DIR.resolve() not in p.parents or not p.exists():
        return None
    try:
        return json.loads(p.read_text("utf-8")).get(url)
    except Exception:
        return None


def registry_lookup(domain: str) -> dict | None:
    """已收录站点：{name, docs:[{url,title,type,snapshot?}]}。snapshot 为抓取时的正文（SPA 页面兜底）。"""
    global _registry
    if _registry is None:
        try:
            _registry = json.loads(REGISTRY.read_text("utf-8")) if REGISTRY.exists() else {}
        except Exception:
            _registry = {}
    d = domain
    while d.count(".") >= 1:
        if d in _registry:
            return _registry[d]
        d = d.split(".", 1)[1]
    return None


# 结果结构变了就 +1：旧缓存自然失效，不会出现「新字段在旧结果里没有」的尴尬
CACHE_VERSION = "v3"


def _cache_key(q: net.Query) -> Path:
    raw = q.url if q.mode == "precise" else q.domain
    h = hashlib.sha1(f"{CACHE_VERSION}|{q.mode}|{raw}".encode()).hexdigest()[:16]
    return CACHE / f"{h}.json"


def tosdr_lookup(domain: str) -> dict | None:
    try:
        r = requests.get("https://api.tosdr.org/search/v5/", params={"query": domain}, timeout=6)
        for s in r.json().get("services", []):
            if domain in s.get("urls", []) and s.get("rating") not in (None, "N/A"):
                return {"id": s["id"], "name": s.get("name"), "rating": s["rating"],
                        "url": f"https://tosdr.org/en/service/{s['id']}"}
    except Exception:
        return None
    return None


def make_tldr(hits) -> list[dict]:
    """3–5 条一句话总结：坏的最多 3 条在前，好的最多 2 条。

    每项带 text（条款写了什么）和 means（这对普通人意味着什么，来自标签的 means_zh）。
    只有模型命中、没有规则锚点的负面标签（provisional）不进 TL;DR——
    TL;DR 是用户只扫一眼的那几行，不能放把握不足的结论。
    """
    def key(h):
        return -TAG_BY_ID[h.tag].weight * h.confidence
    bad = sorted([h for h in hits if TAG_BY_ID[h.tag].polarity in ("bad", "blocker") and not h.provisional], key=key)[:3]
    good = sorted([h for h in hits if TAG_BY_ID[h.tag].polarity == "good"], key=key)[:2]
    return [{"tag": h.tag, "polarity": TAG_BY_ID[h.tag].polarity,
             "text": TAG_BY_ID[h.tag].explain_zh,
             "means": TAG_BY_ID[h.tag].means_zh} for h in bad + good]


def _meta_site_name(html: str) -> str | None:
    """og:site_name / application-name —— 站点自己声明的名字，最可信。"""
    q_ = "[\"']"
    for pat in (rf"<meta[^>]+property={q_}og:site_name{q_}[^>]+content={q_}([^\"']{{1,40}})",
                rf"<meta[^>]+content={q_}([^\"']{{1,40}}){q_}[^>]+property={q_}og:site_name",
                rf"<meta[^>]+name={q_}application-name{q_}[^>]+content={q_}([^\"']{{1,40}})"):
        m = re.search(pat, html, re.I)
        if m:
            return m.group(1).strip()
    return None


def site_name(html: str, domain: str) -> str:
    """优先 og:site_name / application-name，其次 <title> 的第一段。"""
    meta = _meta_site_name(html)
    if meta:
        return meta
    m = re.search(r"<title[^>]*>([^<]{1,80})</title>", html, re.I)
    if m:
        name = re.split(r"\s[-_|·—–]\s|[|_·—–]|，|,", m.group(1).strip())[0].strip()
        if 1 <= len(name) <= 20:
            return name
    return domain


def analyze(raw: str, use_cache: bool = True):
    """对外入口：包一层，保证渲染用的浏览器在分析结束时一定关掉。"""
    rr = render.Renderer()
    try:
        yield from _analyze(raw, use_cache, rr)
    finally:
        rr.close()


def _analyze(raw: str, use_cache: bool, rr) -> "object":
    """yield (event, data)"""
    t_all = time.monotonic()
    rb = render.Budget()   # 本次分析最多渲染几个页面
    try:
        q = net.parse_query(raw)
    except net.BadInput as e:
        yield "error", {"code": "bad_input", "message_zh": str(e)}
        return
    yield "stage", {"stage": "resolve", "message": f"正在找到 {q.domain}", "query": q.to_dict()}

    ck = _cache_key(q)
    if use_cache and ck.exists() and time.time() - ck.stat().st_mtime < CACHE_TTL:
        res = json.loads(ck.read_text("utf-8"))
        yield "stage", {"stage": "discover", "found": len(res["documents"]), "cached": True}
        for d in res["documents"]:
            yield "document", {"title": d["title"], "type": d["type"], "chars": d["chars"], "read_minutes": d["read_minutes"]}
        yield "stage", {"stage": "analyze", "progress": 1.0}
        for t in res["tags"]:
            yield "tag", {"id": t["id"], "polarity": TAG_BY_ID[t["id"]].polarity}
        yield "stage", {"stage": "score"}
        yield "result", res
        return

    sess = requests.Session()
    tosdr_future = ThreadPoolExecutor(1).submit(tosdr_lookup, q.domain)

    # ── discover
    docs_to_fetch: list[tuple[str, str, str, int]] = []  # (url, title, type, 队列深度)
    snapshots: dict[str, tuple] = {}
    fail_codes: list[str] = []
    homepage_html = ""
    reg = registry_lookup(q.domain) if q.mode == "fuzzy" else None
    reg_main: list[tuple] = []   # 主域上已收录的条款（可信）
    reg_off: list[tuple] = []    # 子域 / 外部域上的条目（可能是别的产品，只作兜底）
    if reg:
        for d in reg.get("docs", []):
            snap_text = d.get("snapshot") or load_snapshot(d.get("snapshot_ref"), d["url"])
            if snap_text:
                snapshots[d["url"].rstrip("/")] = (snap_text, d.get("snapshot_at"))
            host = (urlparse(d["url"]).hostname or "").lower()
            row = (d["url"], d.get("title", ""), d.get("type", ""), 0)
            (reg_main if host in (q.domain, f"www.{q.domain}") else reg_off).append(row)

    home_cands: list[discover.Candidate] = []
    homepage_url = q.url
    if q.mode == "precise":
        docs_to_fetch.append((q.url, "", "", 0))
    elif any(row[2] == "privacy" and row[0].rstrip("/") in snapshots for row in reg_main):
        # 主域上已收录隐私政策正文：直接用它，省掉一次首页往返
        docs_to_fetch += reg_main + reg_off
    else:
        # 主站首页先翻一遍：registry 里可能收的是子域产品（如 baidu.com 收成了
        # 百度地图开放平台、百度手机卫士），命中 registry 就不翻首页会让用户查到别的产品
        try:
            home = net.fetch(q.url, sess, total_timeout=min(net.TOTAL_TIMEOUT, _left(t_all, ANALYZE_BUDGET)))
        except net.FetchError as _e:
            # 裸域和 www 经常不是同一台服务器/同一张证书。实测踩过：
            #   cosmoplat-aiot.com 裸域 TLS 失败，但 www.cosmoplat-aiot.com 有 13KB 的静态隐私政策；
            #   appinn.net 裸域没有 A 记录，www 正常 200；
            #   doulor.cn 裸域超时，cloud. 子域正常。
            # 只凭裸域失败就判「没有条款」，是把「我们没找对门」说成了「对方没有」。
            alt = _alt_host_url(q.url)
            if alt and _left(t_all, ANALYZE_BUDGET) > 8:
                yield "stage", {"stage": "resolve", "message": f"裸域打不开，换 {urlparse(alt).hostname} 再试一次"}
                # 再失败就让外层 except 接住并记 fail_codes（不在这里吞掉）
                home = net.fetch(alt, sess, total_timeout=min(net.TOTAL_TIMEOUT, _left(t_all, ANALYZE_BUDGET)))
            else:
                raise
            homepage_html = home.text
            homepage_url = home.url
            home_cands = discover.find_candidates(home.text, home.url, q.domain)
            if not home_cands:
                _, htext = discover.extract_text(home.text)
                # 首页正文短得离谱 = 服务端只给了空壳（纯前端路由站），渲染一次再找链接
                if len(htext) < 400 and rb.take() and _left(t_all, ANALYZE_BUDGET) > 12:
                    rh = rr.render(home.url, timeout_ms=int(_left(t_all, ANALYZE_BUDGET) * 1000))
                    if rh is not None:
                        rtitle, rtext = discover.extract_text(rh.text)
                        if len(rtext) > len(htext):
                            homepage_html = rh.text
                            home_cands = discover.find_candidates(rh.text, home.url, q.domain)
                            yield "stage", {"stage": "discover",
                                            "message": f"这个站的正文要跑脚本才有，已渲染首页（{len(rtext)} 字）"}
            docs_to_fetch += [(c.url, c.title, c.doc_type, 0) for c in home_cands]
        except net.FetchError as e:
            fail_codes.append(e.code)
            yield "stage", {"stage": "discover", "message": f"首页打不开（{e.message_zh}），试试常见路径"}
        # 覆盖率不足就补探：翻一翻已发现声明页的同目录兄弟，再试常见路径。
        # 小站首页常常只挂一条「版权声明」，隐私政策就在隔壁；也有的首页压根没有静态链接。
        found_types = {c.doc_type for c in home_cands}
        if not {"privacy", "terms"} <= found_types:
            sibs = discover.sibling_paths([c.url for c in home_cands])
            paths = sibs + (discover.COMMON_PATHS if not home_cands else discover.COMMON_PATHS[:8])
            tried = {c.url for c in home_cands} | {row[0] for row in docs_to_fetch}
            extra = discover.probe_paths(homepage_url, paths, tried=tried,
                                         limit=26 if not home_cands else 22,
                                         deadline=min(14.0, _left(t_all, ANALYZE_BUDGET) * 0.4))
            if extra:
                home_cands = home_cands + extra
                docs_to_fetch += [(c.url, c.title, c.doc_type, 0) for c in extra]
        docs_to_fetch += reg_main
        if not home_cands:
            # 首页什么都没发现（SPA / 脚本渲染）时才用子域条目兜底
            docs_to_fetch += reg_off
    yield "stage", {"stage": "discover", "found": len(docs_to_fetch)}

    # ── fetch + extract
    documents, texts = [], {}
    # 渲染跑过、但渲染完正文仍然短得不像条款的次数（用来把「没找到」和
    # 「渲染了也没拿到」分开——后者用户重试也没用，得换页面）
    render_empty = 0
    seen_hash, seen_url, seen_lang = set(), set(), set()
    seen_final: set[str] = set()   # 最终 URL（跟随重定向之后）的去重键
    queue = list(docs_to_fetch)
    have_types = set()
    fetched = 0
    t_start = time.monotonic()
    fetch_deadline = min(DEADLINE, _left(t_all, ANALYZE_BUDGET))
    while queue and len(documents) < 4 and fetched < 10 and time.monotonic() - t_start < fetch_deadline:
        # 先补齐缺的类型（隐私 / 协议）
        queue.sort(key=lambda x: (x[2] in have_types, x[3]))
        url, title, dtype, depth = queue.pop(0)
        key = url.rstrip("/")
        lkey = _url_dup_key(url)
        if key in seen_url or lkey in seen_lang:
            continue
        seen_url.add(key)
        seen_lang.add(lkey)
        fetched += 1
        yield "stage", {"stage": "fetch", "message": f"正在打开「{title or urlparse(url).path or url}」", "index": fetched}
        snap, snap_at = snapshots.get(key, (None, None))
        budget = fetch_deadline - (time.monotonic() - t_start)
        try:
            page = net.fetch(url, sess, total_timeout=budget)
            if page.status >= 400:
                # 401/402/403/429 常常是「对脚本关、对浏览器开」（JS 挑战、UA 指纹、付费墙的
                # 前端判定）。用户自己在浏览器里能打开，我们也可以用浏览器去读同一个人人都能看的页面。
                if page.status in (401, 402, 403, 429) and rb.take() and _left(t_all, ANALYZE_BUDGET) > 15:
                    yield "stage", {"stage": "render",
                                    "message": f"对方拒绝了普通请求（HTTP {page.status}），改用浏览器再试一次"}
                    rp = rr.render(url, timeout_ms=int(_left(t_all, ANALYZE_BUDGET) * 1000))
                    if rp is not None and rp.status < 400:
                        page = rp
                    else:
                        raise net.FetchError(f"http_{page.status}", f"HTTP {page.status}")
                else:
                    # 带上状态码：401/402/403/429 和「打不开」是完全不同的两件事
                    raise net.FetchError(f"http_{page.status}", f"HTTP {page.status}")
            ptitle, text = discover.extract_text(page.text)
            if not snap and len(text) < 400 and rb.take() and _left(t_all, ANALYZE_BUDGET) > 12:
                # 同样是空壳：这一页的正文要执行 JS 才出现
                yield "stage", {"stage": "render",
                                "message": f"「{(title or urlparse(url).path or url)[:30]}」正文要跑脚本才有，正在用浏览器渲染"}
                rp = rr.render(page.url, timeout_ms=int(_left(t_all, ANALYZE_BUDGET) * 1000))
                if rp is not None:
                    rt2, rtext = discover.extract_text(rp.text)
                    if len(rtext) > len(text):
                        ptitle, text = rt2, rtext
                    elif len(rtext) < 400:
                        render_empty += 1
            if snap and not discover.looks_like_policy(text):
                raise net.FetchError("spa", "脚本渲染页面")
            used_snapshot = None
        except net.FetchError as e:
            fail_codes.append(e.code)
            if not snap:
                continue
            page = net.Page(url, 200, "text/plain", "")
            ptitle, text = "", snap
            used_snapshot = snap_at or "archived"
        # 二跳：法律声明 / 条款汇总页里再找隐私政策、用户协议
        if depth == 0 and not snap:
            for c in discover.find_candidates(page.text, page.url, q.domain):
                if (c.doc_type in ("privacy", "terms") and c.url.rstrip("/") not in seen_url
                        and c.score >= 12 and not GENERIC_ANCHOR.search(c.title)):
                    queue.append((c.url, c.title, c.doc_type, 1))
        if not discover.looks_like_policy(text):
            continue
        # 首页本身很少是条款页：它的正文是「欢迎/介绍/导航」，页脚那段隐私小字会被算进去。
        # 实测 alipay 精确模式命中首页 185 字，还被判成 C 级（2026-11-12 覆盖报告 s36）。
        # 只挡「根路径 + 短正文」，长首页（有些站把条款直接铺在首页）不受影响。
        if len(text) < 800 and urlparse(page.url).path.rstrip("/") in ("", "/index.html", "/index.htm"):
            continue
        # 重定向常常落到同一份文档的另一个语言版本上（help.github.com/articles/github-terms-of-service/
        # → docs.github.com/zh/site-policy/...），这一层只能在拿到最终 URL 后判
        fkey = _url_dup_key(page.url)
        if fkey in seen_final:
            continue
        seen_final.add(fkey)
        h = hashlib.sha1(text[:5000].encode()).hexdigest()
        if h in seen_hash:
            continue
        seen_hash.add(h)
        dtype = dtype or discover.guess_doc_type(ptitle or title, page.url, text)
        did = f"d{len(documents) + 1}"
        doc = {"id": did, "type": dtype, "title": (title if 2 <= len(title) <= 30 else "") or ptitle or DOC_TYPE_ZH.get(dtype, "条款"),
               "url": page.url, "host": (urlparse(page.url).hostname or "").lower(),
               "chars": len(text), "read_minutes": read_minutes(text),
               "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
        if used_snapshot:
            doc["snapshot_at"] = used_snapshot
        documents.append(doc)
        texts[did] = text
        have_types.add(dtype)
        yield "document", {k: doc[k] for k in ("title", "type", "chars", "read_minutes")}

    if not documents:
        if fail_codes and all(c in ("unreachable", "timeout") for c in fail_codes):
            yield "error", {"code": "unreachable", "message_zh": f"从我们的服务器连不上 {q.domain}（可能是网络限制或网站暂时不可用），稍后再试，或换一个网站。"}
            return
        # 对方的 HTTP 状态码比「没找到」有用得多：402 是人家要钱、403 是反爬、429 是限流，
        # 这些都不是「页面不存在」，说成「没找到条款」会把用户带到错误的方向。
        http_codes = [int(c[5:]) for c in fail_codes if c.startswith("http_")]
        if http_codes:
            from collections import Counter
            top, _n = Counter(http_codes).most_common(1)[0]
            hint = {
                401: "这个页面要登录才能看。",
                402: "这个站要求付费 API 才能自动读取（它明确拒绝了程序访问）。",
                403: "这个站拒绝了自动访问（通常有反爬或 WAF）。",
                404: "这个地址不存在，检查一下路径是不是写错了。",
                405: "这个站不接受这种请求方式。",
                406: "这个站拒绝按我们的请求格式返回内容。",
                429: "这个站限流了，过一会儿再试。",
                451: "这个页面因法律原因不可用。",
            }.get(top, "")
            if not hint:
                hint = "对方服务器出错（5xx），稍后再试。" if top >= 500 else f"对方返回了 HTTP {top}。"
            tail = "可以换一个能打开的镜像站点，或直接搜它公开的条款副本。" if top in (401, 402, 403) else ""
            yield "error", {"code": "blocked_by_site", "status": top,
                            "message_zh": f"{q.domain} 的页面能连上，但对方拒绝了我们（HTTP {top}）。{hint}{tail}"}
            return
        if render_empty:
            hint = ("这个站的正文要跑脚本才有，我们渲染过了但拿到的仍然不是条款（可能是登录墙、"
                    "地区限制，或者条款根本不在这个页面）。如果你手上有具体的条款页地址，直接粘整条会更好。")
        else:
            hint = ("可能是这个站把条款放在登录后、整页由脚本渲染，或者压根没有公开条款。"
                    "如果你知道条款页地址，把整条粘进来（带 /privacy 这种路径）会只分析那一页。")
        yield "error", {"code": "not_found", "message_zh": f"没有找到 {q.domain} 的条款页面。{hint}"}
        return

    # ── analyze
    all_sents = []
    for did, text in texts.items():
        all_sents += split_sentences(did, text)
    yield "stage", {"stage": "analyze", "progress": 0.3, "clauses": len(all_sents)}
    hits = detect(all_sents)
    for h in hits:
        yield "tag", {"id": h.tag, "polarity": TAG_BY_ID[h.tag].polarity, "provisional": h.provisional}
    yield "stage", {"stage": "analyze", "progress": 1.0}

    # ── score + jurisdiction
    yield "stage", {"stage": "score"}
    full = "\n".join(texts.values())
    zh = dominant_zh(texts)
    jur, basis = detect_jurisdiction(q.domain, full + "\n" + homepage_html[-20000:], zh)
    # 待确认的负面标签只按一半权重计分
    sc = score([(h.tag, h.confidence * (0.5 if h.provisional else 1.0)) for h in hits])
    try:
        tosdr = tosdr_future.result(timeout=5)
    except Exception:
        tosdr = None

    # 结论站不住的时候要主动说，别让用户以为「0 个标签 = 这个网站很干净」
    warnings = []
    if len(full) < 2500:
        warnings.append({"code": "thin_docs",
                         "message_zh": f"只读到 {len(full)} 字的条款，内容太少，等级和标签都不可靠——"
                                       "可能是这个站把条款放在 App 里或登录后才给看。"})
    if not hits:
        warnings.append({"code": "no_tags",
                         "message_zh": "没在条款里认出任何值得提醒的点。多半是抓到的页面太短或不是隐私政策/用户协议，"
                                       "不代表这个网站没问题。"})
    elif sum(1 for h in hits if not h.provisional) < 2:
        warnings.append({"code": "few_tags",
                         "message_zh": "只认出很少的条款要点，等级参考价值有限。"})

    res = {
        "query": q.to_dict(),
        "site": {"name": q.domain, "domain": q.domain,
                 "favicon": f"https://www.google.com/s2/favicons?domain={q.domain}&sz=64"},
        "jurisdiction": {"code": jur, "name_zh": JURISDICTIONS[jur]["name_zh"], "basis": basis,
                         "laws": JURISDICTIONS[jur]["laws"]},
        "documents": documents,
        "score": sc,
        "tags": [{"id": h.tag, "confidence": h.confidence, "source": h.source,
                  "provisional": h.provisional, "evidence": h.evidence} for h in hits],
        "compliance": check(jur, texts, zh),
        "tldr": make_tldr(hits),
        "tldr_zh": [x["text"] for x in make_tldr(hits)],
        "stats": {"total_chars": len(full), "read_minutes": sum(d["read_minutes"] for d in documents),
                  "clauses": len(all_sents)},
        "warnings": warnings,
        "tosdr": tosdr,
        "lang": "zh" if zh else "en",
        "texts": {did: t[:300000] for did, t in texts.items()},
    }
    # 站名：站点自报的名字 → 已收录的品牌名 → <title> 第一段（"百度一下，你就知道" 这种不可靠）
    nm = _meta_site_name(homepage_html) if homepage_html else None
    if not nm and reg and reg.get("name"):
        nm = reg["name"]
    if not nm and homepage_html:
        nm = site_name(homepage_html, "")
    if nm:
        res["site"]["name"] = nm
    CACHE.mkdir(parents=True, exist_ok=True)
    ck.write_text(json.dumps(res, ensure_ascii=False), "utf-8")
    yield "result", res
