"""无头渲染：Lightpanda 为主、Chromium 单进程兜底。

实测（2026-11-12，t3.micro 908 MB）：
  Lightpanda 1.0.0  48.2 / 118.2 / 81.6 MB，1 进程，1.9 / 2.6 / 4.8 s（doulor / lobehub / blizzard）
  原 Playwright      537.4 / 684.7 / 617.9 MB，7 进程（其中 100–130 MB 是 node driver）
所以主路径换成 Lightpanda；它渲染不出来的站（notion.com 这类重客户端 Next.js）回落到
Chromium --single-process（313.7–359.5 MB，2 进程）。

为什么需要：很多站点对任何路径都返回同一份 index.html 空壳，正文只在浏览器执行 JS 后才出现。
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import threading

from .net import Page

MAX_RENDERS = int(os.environ.get("CLAUSELENS_MAX_RENDERS", "3"))
RENDER_TIMEOUT_MS = int(os.environ.get("CLAUSELENS_RENDER_TIMEOUT_MS", "25000"))
RENDER_IDLE_MS = int(os.environ.get("CLAUSELENS_RENDER_IDLE_MS", "1200"))

# ---- Lightpanda ----------------------------------------------------------
LP_BIN = os.environ.get("CLAUSELENS_LIGHTPANDA") or shutil.which("lightpanda") or ""
# 不能传 net.UA：Lightpanda 拒绝任何含 "Mozilla" 的 UA（启动即 fatal: invalid user-agent），
# 默认 UA 是 Lightpanda/1.0，这里只加后缀。
LP_UA_SUFFIX = os.environ.get("CLAUSELENS_UA_SUFFIX", " ClauseLens/0.1")
LP_LOCALE = os.environ.get("CLAUSELENS_LOCALE", "zh-CN")
LP_WAIT_MS = int(os.environ.get("CLAUSELENS_LP_WAIT_MS", "8000"))

# ---- Chromium 兜底 ------------------------------------------------------
PW_ARGS = [
    "--disable-gpu", "--no-sandbox", "--single-process", "--disable-dev-shm-usage",
    "--no-zygote", "--renderer-process-limit=1",
    "--blink-settings=imagesEnabled=false",
    "--js-flags=--max-old-space-size=96 --max-semi-space-size=2",
    "--disable-features=site-per-process,IsolateOrigins,Translate,BackForwardCache",
    "--disable-background-networking", "--disable-component-update", "--disable-breakpad",
]
MAX_PW_FALLBACK = int(os.environ.get("CLAUSELENS_PW_FALLBACK", "1"))   # 每次分析最多几次兜底
MIN_FREE_MB = int(os.environ.get("CLAUSELENS_MIN_FREE_MB", "420"))    # 不够就不冒险起 Chromium

# 全局只允许一个渲染任务在跑：908 MB 上两个 180 MB 还行，但两个 Chromium 一定互相挤死
_RENDER_LOCK = threading.Lock()
_disabled = False
_unavailable_reason = ""


def _lp_available() -> bool:
    return bool(LP_BIN) and os.access(LP_BIN, os.X_OK)


def available() -> bool:
    global _disabled, _unavailable_reason
    if _disabled:
        return False
    if _lp_available():
        return True
    try:
        import playwright.sync_api  # noqa: F401
    except Exception as e:
        _disabled = True
        _unavailable_reason = f"lightpanda 与 playwright 都不可用: {type(e).__name__}"
        return False
    return True


def unavailable_reason() -> str:
    return _unavailable_reason


def _mem_available_mb() -> float:
    try:
        for line in open("/proc/meminfo"):
            if line.startswith("MemAvailable:"):
                return int(line.split()[1]) / 1024
    except OSError:
        pass
    return 9999.0


_TAG = re.compile(r"<(script|style)\b.*?</\1>|<[^>]+>", re.I | re.S)


def _visible_text_len(html: str) -> int:
    """粗算正文长度，只用来判断「是不是还是空壳」，不参与判据。"""
    txt = _TAG.sub(" ", html)
    return len(" ".join(txt.split()))


class Renderer:
    """一次分析复用一个实例；Lightpanda 侧没有常驻状态，Chromium 侧按需启动。"""

    def __init__(self):
        self._pw = None
        self._browser = None
        self._ctx = None
        self._fallbacks = 0

    # ---------- 对外 ----------
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False

    def close(self) -> None:
        for obj, meth in ((self._ctx, "close"), (self._browser, "close"), (self._pw, "stop")):
            if obj is None:
                continue
            try:
                getattr(obj, meth)()
            except Exception:
                pass
        self._pw = self._browser = self._ctx = None

    def render(self, url: str, timeout_ms: int | None = None) -> Page | None:
        if not available():
            return None
        tmo = RENDER_TIMEOUT_MS if timeout_ms is None else max(4000, min(RENDER_TIMEOUT_MS, timeout_ms))
        with _RENDER_LOCK:
            page = self._render_lightpanda(url, tmo)
            if page is not None and _visible_text_len(page.text) >= 400:
                return page
            # 还是空壳（或 Lightpanda 不在）→ 用 Chromium 补一次，但要先确认内存够
            if not _lp_available():
                return self._render_chromium(url, tmo) or page
            if self._fallbacks >= MAX_PW_FALLBACK or _mem_available_mb() < MIN_FREE_MB:
                return page
            self._fallbacks += 1
            return self._render_chromium(url, tmo) or page

    # ---------- Lightpanda ----------
    def _render_lightpanda(self, url: str, tmo_ms: int) -> Page | None:
        cmd = [
            LP_BIN, "fetch", "--json", "--dump", "html", url,
            "--locale", LP_LOCALE,
            "--wait-until", "networkidle", "--wait-ms", str(LP_WAIT_MS),
            "--load-resources", "stylesheet",
            "--block-private-networks",
            "--user-agent-suffix", LP_UA_SUFFIX,
            "--terminate-ms", str(tmo_ms),
        ]
        try:
            p = subprocess.run(cmd, capture_output=True, timeout=tmo_ms / 1000 + 5)
        except (OSError, subprocess.TimeoutExpired):
            return None
        if p.returncode != 0:
            # 导航/等待失败（若加 --fail-on-http-error，HTTP 4xx/5xx 也会是 22）
            return None
        try:
            obj = json.loads(p.stdout.decode("utf-8", "replace"))
        except ValueError:
            return None
        html = obj.get("content") or ""
        if len(html) < 200:
            return None
        return Page(url, int(obj.get("http_status") or 200), "text/html; charset=utf-8", html)

    # ---------- Chromium 兜底 ----------
    def _start_chromium(self) -> None:
        from playwright.sync_api import sync_playwright
        self._pw = sync_playwright().start()
        for kw in ({"channel": "chromium"}, {}):      # channel="chromium" 才是完整 chromium
            try:
                self._browser = self._pw.chromium.launch(headless=True, args=PW_ARGS, **kw)
                break
            except Exception:
                continue
        if self._browser is None:
            raise RuntimeError("Chromium 起不来")
        self._ctx = self._browser.new_context(
            locale=LP_LOCALE, viewport={"width": 1440, "height": 1000})

    def _render_chromium(self, url: str, tmo_ms: int) -> Page | None:
        try:
            if self._ctx is None:
                self._start_chromium()
            page = self._ctx.new_page()
            try:
                page.route("**/*", lambda r: r.abort()
                           if r.request.resource_type in ("image", "media", "font") else r.continue_())
                resp = page.goto(url, wait_until="domcontentloaded", timeout=tmo_ms)
                try:
                    page.wait_for_load_state("networkidle", timeout=min(RENDER_IDLE_MS, tmo_ms // 3))
                except Exception:
                    pass
                page.wait_for_timeout(300)
                html = page.content()
                return Page(url, int(getattr(resp, "status", 200) or 200),
                            "text/html; charset=utf-8", html)
            finally:
                try:
                    page.close()
                except Exception:
                    pass
        except Exception:
            self.close()
            return None


class Budget:
    """一次分析里的渲染次数配额。"""

    def __init__(self, limit: int | None = None):
        self.limit = MAX_RENDERS if limit is None else limit
        self.used = 0

    def take(self) -> bool:
        if self.used >= self.limit:
            return False
        self.used += 1
        return True


def render(url: str, timeout_ms: int | None = None) -> Page | None:
    """单页一次性渲染（会新起一个进程）。多次渲染请用 Renderer 复用。"""
    with Renderer() as r:
        return r.render(url, timeout_ms)