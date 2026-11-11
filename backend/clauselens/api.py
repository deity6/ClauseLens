"""FastAPI 服务。运行：python -m uvicorn clauselens.api:app --app-dir backend --port 8787"""
from __future__ import annotations

import asyncio
import gzip
import hashlib
import json
import threading
import time
from collections import defaultdict
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


app = FastAPI(title="ClauseLens")
app.add_middleware(StaticGZip)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
                   allow_methods=["*"], allow_headers=["*"])

# 同时进行的分析数上限。每个分析可能拉起一个 Chromium（~480MB），
# AWS t3.micro 只有 908MB，不设上限时三路并发就会把机器压到 swap。
_analyze_slots = threading.BoundedSemaphore(3)
# 简单的每 IP 限流：分析 10 次/分钟
_hits: dict[str, list[float]] = defaultdict(list)
_fb_hits: dict[str, list[float]] = defaultdict(list)



def _client_ip(request: Request) -> str:
    """真实客户端 IP。

    生产链路是 浏览器 → lens.dohub.tech(CF Pages Function) → api.dohub.tech，
    后端直接看到的 request.client.host 是 Cloudflare 边缘节点 IP——实测同一客户端连续三次请求
    落到 172.71.x / 104.22.x 三个不同地址。拿它当限流键会变成"所有用户共享一个桶"（互相误伤），
    当投票去重键则完全失效（同一个人可以无限投）。

    CF-Connecting-IP 是 Cloudflare 自己填的真实客户端 IP，优先用它；直连源站（无 CF）时回退到
    socket 对端，再退到 X-Real-IP（我们自己的 Caddy 会设，但它可能被伪造，所以排最后）。
    """
    for h in ("cf-connecting-ip", "x-real-ip"):
        v = (request.headers.get(h) or "").strip()
        if v:
            return v
    return request.client.host if request.client else "?"


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
        while True:
            item = await queue.get()
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


# 反馈的内存索引：启动时读一次，之后写入时同步更新，summary 不再每次扫全文件
_fb_counts: dict[str, dict[str, dict[str, int]]] = {}
_voted: set[str] = set()
_fb_loaded = False
FB_IP_SALT = "clauselens-vote"     # 只用于同一 IP 去重，不是安全哈希
FB_ROTATE_BYTES = 8 * 1024 * 1024


def _fb_index(r: dict) -> None:
    dom, tag, vote = r.get("domain"), r.get("tag_id"), r.get("vote")
    if not dom or not tag or vote not in ("agree", "disagree"):
        return
    d = _fb_counts.setdefault(dom, {}).setdefault(tag, {"agree": 0, "disagree": 0})
    d[vote] += 1
    h = r.get("ip_hash")
    if h:
        _voted.add(f"{h}|{dom}|{tag}")


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
    ip_hash = hashlib.sha1(f"{FB_IP_SALT}|{ip}".encode()).hexdigest()[:12]
    _fb_ensure()
    with _lock:
        if f"{ip_hash}|{dom}|{fb.tag_id}" in _voted:
            raise HTTPException(409, "这个标签你已经投过了")
    rec = {"domain": dom, "tag_id": fb.tag_id, "vote": fb.vote, "comment": fb.comment,
           "ip_hash": ip_hash, "at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    FEEDBACK.parent.mkdir(parents=True, exist_ok=True)
    with _lock:
        _fb_index(rec)
        with FEEDBACK.open("a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        # 文件按体积滚动；内存计数保留，不受滚动影响
        try:
            if FEEDBACK.stat().st_size > FB_ROTATE_BYTES:
                FEEDBACK.replace(FEEDBACK.with_name("feedback.jsonl.1"))
        except OSError:
            pass
        return {"ok": True, "summary": json.loads(json.dumps(_fb_counts.get(dom, {})))}


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
