"""FastAPI 服务。运行：python -m uvicorn clauselens.api:app --app-dir backend --port 8787"""
from __future__ import annotations

import asyncio
import gzip
import hashlib
import json
import threading
import time
from collections import defaultdict
from ipaddress import ip_address, ip_network
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from .net import _DOMAIN_RE
from .pipeline import analyze
from .taxonomy import TAG_BY_ID, public_taxonomy

ROOT = Path(__file__).resolve().parents[2]
FEEDBACK = ROOT / "data" / "feedback.jsonl"
DIST = ROOT / "frontend" / "dist"
_lock = threading.Lock()


class StaticGZip(BaseHTTPMiddleware):
    """只压缩静态资源。

    字体改造后 CSS 从 29 KB 涨到 214 KB（里面全是 @font-face 的 unicode-range 声明），
    uvicorn 默认裸传，gzip 后只要 72 KB。SSE 必须排除——压缩会把事件缓冲住，
    等待态的进度条就不动了。
    """

    async def dispatch(self, request, call_next):
        response = await call_next(request)
        if (request.url.path.startswith("/api/")
                or response.headers.get("content-encoding")
                or "gzip" not in (request.headers.get("accept-encoding") or "")):
            return response
        body = b"".join([chunk async for chunk in response.body_iterator])
        headers = dict(response.headers)
        headers.pop("content-length", None)
        if len(body) < 1400:
            return Response(content=body, status_code=response.status_code,
                            headers=headers, media_type=response.media_type)
        comp = gzip.compress(body, 6)
        headers["content-encoding"] = "gzip"
        headers["content-length"] = str(len(comp))
        headers["vary"] = "Accept-Encoding"
        return Response(content=comp, status_code=response.status_code,
                        headers=headers, media_type=response.media_type)


# 生产不暴露交互式文档与 openapi.json：它们会把所有路由和参数结构一次性交出去，
# 对本项目没有任何用处（前端只调 /api/*）。本地调试时临时改成默认值即可。
app = FastAPI(title="ClauseLens", docs_url=None, redoc_url=None, openapi_url=None)
app.add_middleware(StaticGZip)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
                   allow_methods=["*"], allow_headers=["*"])

# 同时进行的分析数上限。每个分析可能拉起一个 Chromium（~480MB），
# AWS t3.micro 只有 908MB，不设上限时三路并发就会把机器压到 swap。
_analyze_slots = threading.BoundedSemaphore(2)
# SSE 的硬上限（秒）：超过它一定发 error 事件而不是静默断开。
# 观察到的现象：notion.so 那种渲染卡死的站，120 秒过去前端既不拿到 result 也不拿到 error，
# 只能一直转圈——比报错还糟，因为用户不知道发生了什么。
ANALYZE_HARD_LIMIT = 100
# 简单的每 IP 限流：分析 10 次/分钟
_hits: dict[str, list[float]] = defaultdict(list)
_fb_hits: dict[str, list[float]] = defaultdict(list)



# Cloudflare 的出口网段（https://www.cloudflare.com/ips-v4、ips-v6，2026-11 取）。
# 只用来判断「直连我们的对端是不是 Cloudflare 边缘」——是才敢相信它带来的 CF-Connecting-IP。
# 不这么判的话，任何人自己加一个 `CF-Connecting-IP: 1.2.3.4` 就能一次换一个限流桶
# （/api/analyze 的 10 次/分钟、/api/feedback 的去重同时失效）。
_CF_NETS = tuple(
    ip_network(x)
    for x in (
        # IPv4
        "173.245.48.0/20", "103.21.244.0/22", "103.22.200.0/22", "103.31.4.0/22",
        "141.101.64.0/18", "108.162.192.0/18", "190.93.240.0/20", "188.114.96.0/20",
        "197.234.240.0/22", "198.41.128.0/17", "162.158.0.0/15", "104.16.0.0/13",
        "104.24.0.0/14", "172.64.0.0/13", "131.0.72.0/22",
        # IPv6
        "2400:cb00::/32", "2606:4700::/32", "2803:f800::/32", "2405:b500::/32",
        "2405:8100::/32", "2a06:98c0::/29", "2c0f:f248::/32",
    )
)


def _is_cloudflare_ip(ip: str) -> bool:
    try:
        addr = ip_address(ip)
    except ValueError:
        return False
    return any(addr in net for net in _CF_NETS)


def _client_ip(request: Request) -> str:
    """真实客户端 IP。

    链路：浏览器 → lens.dohub.tech（CF Pages Function）→ api.dohub.tech（Caddy → uvicorn）。
    uvicorn 看到的对端永远是 127.0.0.1（Caddy）；Caddy 会把真实对端覆盖写进 X-Real-IP。
    只有当这个对端本身是 Cloudflare 边缘时，才认它带来的 CF-Connecting-IP（真用户 IP）；
    直连源站的人带什么头都不算数——否则伪造一个 CF-Connecting-IP 就能每请求换一个限流桶。
    """
    peer = request.client.host if request.client else "?"
    real_peer = (request.headers.get("x-real-ip") or "").strip() or peer
    if _is_cloudflare_ip(real_peer):
        cf = (request.headers.get("cf-connecting-ip") or "").strip()
        if cf:
            return cf
    return real_peer


def _rate_ok(ip: str, limit=10, window=60, table: dict | None = None) -> bool:
    tab = _hits if table is None else table
    now = time.time()
    arr = [t for t in tab.get(ip, ()) if now - t < window]
    if len(arr) >= limit:
        tab[ip] = arr
        return False
    arr.append(now)
    tab[ip] = arr
    # 表只增不减会一直吃内存：条目太多时清掉已经过期的
    if len(tab) > 5000:
        for k in [k for k, v in tab.items() if not v or now - v[-1] >= window]:
            tab.pop(k, None)
    return True


@app.get("/api/taxonomy")
def taxonomy():
    return public_taxonomy()


@app.get("/api/analyze")
async def api_analyze(q: str, request: Request, nocache: int = 0):
    ip = _client_ip(request)
    if not _rate_ok(ip):
        msg = {"code": "rate_limited", "message_zh": "查得太快啦，歇一分钟再来"}

        async def limited():
            yield f"event: error\ndata: {json.dumps(msg, ensure_ascii=False)}\n\n"
        return StreamingResponse(limited(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})

    # 并发闸门：满了就直接回「正在忙」，而不是排队把内存压垮。
    # 每个分析可能拉起一个 Chromium（~480MB），908MB 的机器经不起三路并行。
    if not _analyze_slots.acquire(blocking=False):
        msg = {"code": "busy", "message_zh": "这会儿查的人有点多，等十几秒再试一次"}
        async def busy():
            yield f"event: error\ndata: {json.dumps(msg, ensure_ascii=False)}\n\n"
        return StreamingResponse(busy(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})

    queue: asyncio.Queue = asyncio.Queue()
    loop = asyncio.get_running_loop()

    def worker():
        try:
            for ev, data in analyze(q, use_cache=not nocache):
                loop.call_soon_threadsafe(queue.put_nowait, (ev, data))
        except Exception as e:  # noqa
            loop.call_soon_threadsafe(queue.put_nowait, ("error", {"code": "internal", "message_zh": "分析时出了点问题，请稍后再试"}))
        finally:
            _analyze_slots.release()      # 无论成功、失败还是客户端提前断开，都要放回
            loop.call_soon_threadsafe(queue.put_nowait, None)

    threading.Thread(target=worker, daemon=True).start()

    async def stream():
        # 硬保证：这条流一定会以 result 或 error 结束，绝不静默断开。
        # 实测踩过（2026-11-12 覆盖报告 s23）：notion.so 渲染卡死后，128 秒过去前端既不
        # 拿到 result 也不拿到 error，只能一直转圈——比报错更糟，因为用户不知道发生了什么。
        t0 = time.monotonic()
        while True:
            left = ANALYZE_HARD_LIMIT - (time.monotonic() - t0)
            if left <= 0:
                yield ("event: error\ndata: " +
                       json.dumps({"code": "timeout", "message_zh": "这个站太慢，分析超时了。换个页面或稍后再试"}, ensure_ascii=False) + "\n\n")
                break
            try:
                item = await asyncio.wait_for(queue.get(), timeout=left)
            except asyncio.TimeoutError:
                yield ("event: error\ndata: " +
                       json.dumps({"code": "timeout", "message_zh": "这个站太慢，分析超时了。换个页面或稍后再试"}, ensure_ascii=False) + "\n\n")
                break
            if item is None:
                break
            ev, data = item
            yield f"event: {ev}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


class Feedback(BaseModel):
    domain: str = Field(max_length=253)
    tag_id: str = Field(max_length=64)
    vote: str = Field(pattern="^(agree|disagree)$")
    comment: str | None = Field(default=None, max_length=200)


class VoteChange(BaseModel):
    tag_id: str = Field(max_length=64)
    vote: str | None = Field(default=None, pattern="^(agree|disagree)$")   # None = 撤回


class VoteBatch(BaseModel):
    domain: str = Field(max_length=253)
    votes: list[VoteChange] = Field(default_factory=list, max_length=200)


# 反馈的内存索引：启动时读一次，之后写入时同步更新，summary 不再每次扫全文件
_fb_counts: dict[str, dict[str, dict[str, int]]] = {}
# 每个 (ip_hash|domain|tag) 当前投的是哪一边。投票可以改、可以撤，所以这里存的是「最终状态」，
# 计数就是所有状态之和——不是追加式累加（那样换票/撤回没法把旧票退回去）。
_voted: dict[str, str] = {}
_fb_loaded = False
# 投票去重用的盐：**不能硬编码**。审计实测 sha1("clauselens-vote|104.22.20.8")[:12] 能和
# feedback.jsonl 里的 ip_hash 精确对上——等于把 IP 明文存进了文件（GDPR/PIPL 意义的个人信息）。
# 改成首次启动时随机生成、落在 data/.vote_salt（600 权限），之后复用。
def _vote_salt() -> str:
    import secrets
    path = ROOT / "data" / ".vote_salt"
    try:
        if path.exists():
            v = path.read_text(encoding="utf-8").strip()
            if len(v) >= 32:
                return v
        path.parent.mkdir(parents=True, exist_ok=True)
        v = secrets.token_hex(24)
        path.write_text(v, encoding="utf-8")
        try:
            path.chmod(0o600)
        except Exception:
            pass
        return v
    except Exception:
        return secrets.token_hex(24)   # 落盘失败就退化成进程内随机（重启后旧哈希失效，可接受）


FB_IP_SALT = _vote_salt()
FB_ROTATE_BYTES = 8 * 1024 * 1024


def _hash_ip(ip: str) -> str:
    return hashlib.sha1(f"{FB_IP_SALT}|{ip}".encode()).hexdigest()[:12]


def _vote_key(ip_hash: str, dom: str, tag: str) -> str:
    return f"{ip_hash}|{dom}|{tag}"


def _apply_vote(dom: str, tag: str, ip_hash: str | None, vote: str | None) -> str | None:
    """把某人的票设成 vote（None = 撤回），返回改之前的值。调用方持 _lock。"""
    d = _fb_counts.setdefault(dom, {}).setdefault(tag, {"agree": 0, "disagree": 0})
    if not ip_hash:                 # 没有哈希的老记录：只计数，不能改
        if vote:
            d[vote] += 1
        return None
    key = _vote_key(ip_hash, dom, tag)
    old = _voted.get(key)
    if old == vote:
        return old
    if old:
        d[old] = max(0, d[old] - 1)
    if vote:
        d[vote] += 1
        _voted[key] = vote
    else:
        _voted.pop(key, None)
    return old


def _fb_index(r: dict) -> None:
    dom, tag, vote = r.get("domain"), r.get("tag_id"), r.get("vote")
    if not dom or not tag or vote not in ("agree", "disagree", None):
        return
    _apply_vote(dom, tag, r.get("ip_hash"), vote)


def _fb_payload(dom: str, ip_hash: str) -> dict:
    counts = json.loads(json.dumps(_fb_counts.get(dom, {})))
    prefix = f"{ip_hash}|{dom}|"
    mine = {k[len(prefix):]: v for k, v in _voted.items() if k.startswith(prefix)}
    return {"ok": True, "summary": counts, "counts": counts, "mine": mine}


def _append_feedback(dom: str, tag: str, vote: str | None, ip_hash: str, comment: str | None = None) -> None:
    """追加一条变更记录（vote=null 表示撤回）。调用方持 _lock。"""
    rec = {"domain": dom, "tag_id": tag, "vote": vote, "comment": comment,
           "ip_hash": ip_hash, "at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    FEEDBACK.parent.mkdir(parents=True, exist_ok=True)
    with FEEDBACK.open("a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    # 文件按体积滚动；内存计数保留，不受滚动影响
    try:
        if FEEDBACK.stat().st_size > FB_ROTATE_BYTES:
            FEEDBACK.replace(FEEDBACK.with_name("feedback.jsonl.1"))
    except OSError:
        pass


def _fb_ensure() -> None:
    global _fb_loaded
    if _fb_loaded:
        return
    with _lock:
        if _fb_loaded:
            return
        if FEEDBACK.exists():
            for line in FEEDBACK.read_text("utf-8").splitlines():
                try:
                    _fb_index(json.loads(line))
                except Exception:
                    continue
        _fb_loaded = True


def _norm_domain(s: str) -> str:
    d = (s or "").strip().lower().rstrip(".")
    return d[4:] if d.startswith("www.") else d


@app.post("/api/feedback")
def feedback(fb: Feedback, request: Request):
    ip = _client_ip(request)
    if not _rate_ok(f"fb:{ip}", limit=60, window=60, table=_fb_hits):
        raise HTTPException(429, "投得太频繁了，歇一分钟再来")
    if fb.tag_id not in TAG_BY_ID:
        raise HTTPException(400, "未知标签")
    dom = _norm_domain(fb.domain)
    if len(dom) > 253 or not _DOMAIN_RE.match(dom):
        raise HTTPException(400, "域名格式不对")
    ip_hash = _hash_ip(ip)
    _fb_ensure()
    with _lock:
        # 同一个值重复提交是幂等的（老客户端会重试）；换票/撤回走这里也能落地
        if _apply_vote(dom, fb.tag_id, ip_hash, fb.vote) != fb.vote:
            _append_feedback(dom, fb.tag_id, fb.vote, ip_hash, fb.comment)
        return _fb_payload(dom, ip_hash)


@app.post("/api/feedback/batch")
def feedback_batch(b: VoteBatch, request: Request):
    """前端攒着的一次「本地改动」：一次请求把若干标签的最终票态同步上来。

    每项都是 set 语义（vote=null 表示撤回），重复提交幂等 ——
    页面离开时用 sendBeacon 发的那一发没等到响应，下次打开重发也不会多算。
    """
    ip = _client_ip(request)
    if not _rate_ok(f"fb:{ip}", limit=30, window=60, table=_fb_hits):
        raise HTTPException(429, "投得太频繁了，歇一分钟再来")
    dom = _norm_domain(b.domain)
    if len(dom) > 253 or not _DOMAIN_RE.match(dom):
        raise HTTPException(400, "域名格式不对")
    ip_hash = _hash_ip(ip)
    _fb_ensure()
    changed = 0
    with _lock:
        for ch in b.votes[:200]:
            if ch.tag_id not in TAG_BY_ID:
                continue            # 前端比后端新时，未知标签跳过，不让整批失败
            if _apply_vote(dom, ch.tag_id, ip_hash, ch.vote) != ch.vote:
                _append_feedback(dom, ch.tag_id, ch.vote, ip_hash)
                changed += 1
        payload = _fb_payload(dom, ip_hash)
    payload["changed"] = changed
    return payload


@app.get("/api/feedback/state")
def feedback_state(domain: str, request: Request):
    """计数 + 「我投了什么」。前端靠 mine 在换设备/清缓存后也认得出自己的票。"""
    _fb_ensure()
    dom = _norm_domain(domain)
    ip_hash = _hash_ip(_client_ip(request))
    with _lock:
        return _fb_payload(dom, ip_hash)


@app.get("/api/feedback/summary")
def summary(domain: str):
    _fb_ensure()
    with _lock:
        return json.loads(json.dumps(_fb_counts.get(_norm_domain(domain), {})))


if DIST.exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/{path:path}")
    def spa(path: str):
        f = DIST / path
        if path and f.is_file() and DIST in f.resolve().parents:
            return FileResponse(f)
        return FileResponse(DIST / "index.html")

