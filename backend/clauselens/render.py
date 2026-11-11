"""无头浏览器渲染：给纯前端路由的 SPA 兜底。

为什么需要：很多站点（Discourse、各种 Vue/React 后台面板）对**任何路径**都返回同一份
index.html 空壳，正文只在浏览器执行 JS 后才出现。静态抓取拿到的正文可能只有十几个字
（`cloud.doulor.cn` 的 /、/terms、/privacy 三页返回的 HTML 一模一样，都是 13644 字节、
提取出 12 个字的 "Doulor Cloud"），再怎么加路径、改正则都读不出来。

代价：一次渲染 5–10 秒（启动浏览器 + 页面加载 + 等 networkidle），所以只在
「静态提取的正文短到明显是空壳」时才调用，而且每次分析有次数上限。
"""
from __future__ import annotations

import os
import threading

from .net import UA, Page

# 一次分析里最多渲染几个页面（每个 5–10 秒，渲染太多次会把 60 秒预算吃光）
MAX_RENDERS = int(os.environ.get("CLAUSELENS_MAX_RENDERS", "3"))
RENDER_TIMEOUT_MS = int(os.environ.get("CLAUSELENS_RENDER_TIMEOUT_MS", "25000"))
RENDER_IDLE_MS = int(os.environ.get("CLAUSELENS_RENDER_IDLE_MS", "1200"))


# 启动参数分两档（实测数据，AWS t3.micro，cloud.doulor.cn/privacy）：
#   --single-process  3 进程 / RSS 280 MB / 2.8s   ← 省，但 Chromium 单进程模式有崩溃概率
#   常规多进程        6 进程 / RSS 480 MB / 5.9s   ← 稳
# 策略：默认走省的那套；渲染失败（返回 None）时自动退回稳的那套重试一次。
_COMMON_ARGS = [
    "--disable-gpu",
    "--disable-dev-shm-usage",
    "--no-sandbox",
    "--disable-background-networking",
    "--disable-sync",
    "--no-first-run",
    "--disable-extensions",
    "--metrics-recording-only",
]
SINGLE_ARGS = _COMMON_ARGS + ["--single-process", "--js-flags=--max-old-space-size=128"]
LEAN_ARGS = _COMMON_ARGS + ["--js-flags=--max-old-space-size=160", "--renderer-process-limit=1"]

_disabled = False
_unavailable_reason = ""

# 全局只允许一个 Chromium 在工作。AWS t3.micro 只有 908MB，两个浏览器实例同时跑
# 会互相抢内存、双双超时（实测：并发查三个 SPA 站时其中一个必然失败）。
_RENDER_LOCK = threading.Lock()


def available() -> bool:
    global _disabled, _unavailable_reason
    if _disabled:
        return False
    try:
        import playwright.sync_api  # noqa: F401
    except Exception as e:  # 没装 playwright 就静默降级
        _disabled = True
        _unavailable_reason = f"playwright 不可用: {type(e).__name__}"
        return False
    return True


def unavailable_reason() -> str:
    return _unavailable_reason


def _launch(pw, args=None):
    """优先用系统已装的 Edge / Chrome，不额外下载 chromium。"""
    last = None
    for kw in ({"channel": "msedge"}, {"channel": "chrome"}, {}):
        try:
            return pw.chromium.launch(headless=True, args=args or _COMMON_ARGS, **kw)
        except Exception as e:
            last = e
    raise RuntimeError(f"没有可用的浏览器: {last}")


def render(url: str) -> Page | None:
    """渲染一个页面，返回执行完 JS 之后的 HTML。失败返回 None。

    单次调用会新起一个浏览器（约 2–3 秒）。一次分析要渲染多页时用 Renderer 复用。
    """
    with Renderer() as r:
        return r.render(url)


class Renderer:
    """可复用的渲染器：一次分析只启动一次浏览器。

    `cloud.doulor.cn` 这种站首页和条款页都要渲染，每次重开浏览器的话，三次渲染光启动
    就多花近 10 秒，直接把 60 秒预算吃光，最后一份文档永远抓不到。
    """

    def __init__(self):
        self._pw = None
        self._browser = None
        self._ctx = None
        self._single = True      # 是否正在用省内存模式；失败后退回 False

    def _start(self) -> None:
        from playwright.sync_api import sync_playwright
        self._pw = sync_playwright().start()
        try:
            self._browser = _launch(self._pw, SINGLE_ARGS if self._single else LEAN_ARGS)
        except Exception:
            self._single = False        # 单进程起不来就用多进程
            self._browser = _launch(self._pw, LEAN_ARGS)
        self._ctx = self._browser.new_context(
            user_agent=UA, locale="zh-CN", viewport={"width": 1440, "height": 1000})

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
        with _RENDER_LOCK:          # 串行化：宁可排队，也不要两个浏览器抢内存
            page = self._render_inner(url, timeout_ms)
            if page is None and self._single:
                # 单进程模式对某些页面会崩（这是它唯一的代价）。崩了就把这套实例丢掉，
                # 换成稳定的多进程模式重来一次——慢 ~3 秒，但不会再失败。
                self._single = False
                self.close()
                page = self._render_inner(url, timeout_ms)
            return page

    def _render_inner(self, url: str, timeout_ms: int | None = None) -> Page | None:
        tmo = RENDER_TIMEOUT_MS if timeout_ms is None else max(4000, min(RENDER_TIMEOUT_MS, timeout_ms))
        try:
            if self._ctx is None:
                self._start()
            page = self._ctx.new_page()
            try:
                # 图片/媒体/字体一律不加载：条款正文是纯文本，加载它们只会拖慢
                page.route("**/*", lambda route: route.abort()
                           if route.request.resource_type in ("image", "media", "font") else route.continue_())
                resp = None
                try:
                    resp = page.goto(url, wait_until="domcontentloaded", timeout=tmo)
                except Exception:
                    return None
                try:
                    page.wait_for_load_state("networkidle", timeout=min(RENDER_IDLE_MS, tmo // 3))
                except Exception:
                    pass
                page.wait_for_timeout(300)
                html = page.content()
                status = getattr(resp, "status", 200) or 200
                return Page(url, int(status), "text/html; charset=utf-8", html)
            finally:
                try:
                    page.close()
                except Exception:
                    pass
        except Exception:
            self.close()   # 浏览器崩了就丢弃，下次重开
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
