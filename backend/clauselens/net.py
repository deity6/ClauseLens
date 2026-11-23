"""输入解析 + 安全抓取（SSRF 防护、体积/超时限制）。"""
from __future__ import annotations

import ipaddress
import os
import re
import socket
import threading
import time
from dataclasses import dataclass
from urllib.parse import urlparse, urljoin

import requests
import requests.adapters
import urllib3
import urllib3.connection

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/130.0 Safari/537.36 ClauseLens/0.1")
MAX_BYTES = 5 * 1024 * 1024
TIMEOUT = (6, 10)      # (连接, 单次读取)
TOTAL_TIMEOUT = 20     # 单个页面总耗时上限
ALLOWED_PORTS = {None, 80, 443, 8080, 8443}

# 可选境外出口：直连失败时把请求改走这里。两种写法：
#   cloud:<machine-id>     → 借云端容器的 exec 跑一次 curl（不暴露端口、无常驻进程）；
#                            `instabox:<machine-id>` 是等价旧写法，仍然认
#   socks5h://host:port     → 走 SOCKS 代理；必须 socks5h，让远端解析域名
# 空字符串 = 关闭，行为与以前完全一致。
EGRESS = (os.environ.get("CLAUSELENS_EGRESS") or "").strip()
_FALLBACK_CODES = {"fetch_failed", "timeout", "unreachable"}

# 某个域名直连失败过一次，就记住它——同一次分析里后面还有十几次请求要打这个站，
# 每次都白等 6 秒连接超时的话，光超时就吃掉一分多钟。
_EGRESS_HINTS: dict[str, float] = {}
EGRESS_HINT_TTL = 6 * 3600

_DOMAIN_RE = re.compile(r"^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$", re.I)


@dataclass
class Query:
    input: str
    mode: str          # fuzzy | precise
    domain: str
    url: str           # 精准模式为原 URL，模糊模式为首页

    def to_dict(self):
        return {"input": self.input, "mode": self.mode, "domain": self.domain, "url": self.url}


class BadInput(ValueError):
    pass


def parse_query(raw: str) -> Query:
    s = (raw or "").strip()
    if not s or len(s) > 2000:
        raise BadInput("请输入一个网址或域名，例如 baidu.com")
    has_scheme = re.match(r"^[a-z][a-z0-9+.-]*://", s, re.I)
    if has_scheme and not s.lower().startswith(("http://", "https://")):
        raise BadInput("只支持 http / https 网址")
    u = urlparse(s if has_scheme else "https://" + s)
    host = (u.hostname or "").lower().rstrip(".")
    try:
        host = host.encode("idna").decode("ascii")
    except UnicodeError:
        raise BadInput("这个域名看起来不太对")
    if not _DOMAIN_RE.match(host):
        raise BadInput("这个域名看起来不太对，试试 baidu.com 这样的格式")
    path = u.path or ""
    precise = bool(path.strip("/")) or bool(u.query)
    domain = host[4:] if host.startswith("www.") else host
    if precise:
        return Query(s, "precise", domain, u.geturl())
    return Query(s, "fuzzy", domain, f"https://{host}/")


def _ip_ok(ip_str: str) -> bool:
    ip = ipaddress.ip_address(ip_str.split("%")[0])
    if isinstance(ip, ipaddress.IPv6Address):
        # IPv4 映射 / 兼容 / NAT64 / 6to4 地址：取出内嵌的 IPv4 再判断
        if ip.ipv4_mapped:
            ip = ip.ipv4_mapped
        elif ip in ipaddress.ip_network("64:ff9b::/96") or ip in ipaddress.ip_network("::/96"):
            ip = ipaddress.IPv4Address(int(ip) & 0xFFFFFFFF)
        elif ip.sixtofour:
            ip = ip.sixtofour
    return ip.is_global and not ip.is_multicast


def _is_public_host(host: str) -> bool:
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        raise FetchError("unreachable", "从我们这边连不上这个网站")
    return all(_ip_ok(info[4][0]) for info in infos)


class _GuardedConnMixin:
    """连接建立后检查对端真实 IP（防 DNS 重绑定 / TOCTOU）。"""

    def _new_conn(self):
        sock = super()._new_conn()
        try:
            peer = sock.getpeername()[0]
        except OSError:
            sock.close()
            raise
        if not _ip_ok(peer):
            sock.close()
            raise _BlockedPeer(f"blocked peer {peer}")
        _tls.sock = sock  # 供 watchdog 在总超时到点时强制断开
        return sock


_tls = threading.local()


class _BlockedPeer(OSError):
    pass


class _GuardedHTTPConnection(_GuardedConnMixin, urllib3.connection.HTTPConnection):
    pass


class _GuardedHTTPSConnection(_GuardedConnMixin, urllib3.connection.HTTPSConnection):
    pass


class _GuardedAdapter(requests.adapters.HTTPAdapter):
    def init_poolmanager(self, *args, **kwargs):
        super().init_poolmanager(*args, **kwargs)
        self.poolmanager.pool_classes_by_scheme = {"http": _HTTPPool, "https": _HTTPSPool}
        self.poolmanager.key_fn_by_scheme = dict(self.poolmanager.key_fn_by_scheme)


class _HTTPPool(urllib3.HTTPConnectionPool):
    ConnectionCls = _GuardedHTTPConnection


class _HTTPSPool(urllib3.HTTPSConnectionPool):
    ConnectionCls = _GuardedHTTPSConnection


def safe_session() -> requests.Session:
    s = requests.Session()
    s.trust_env = False  # 不走环境代理（否则对端 IP 是代理，校验失效）
    ad = _GuardedAdapter(max_retries=0)
    s.mount("http://", ad)
    s.mount("https://", ad)
    return s


def egress_session() -> requests.Session:
    """走境外出口的 session。

    与 safe_session 的区别：不做「连接建立后校验对端 IP」这一步——对端是代理，不是目标站。
    域名层校验（parse_query 的格式 + 字面量 IP 拒绝）仍然有效，代价是这一层挡不住 DNS 重绑定；
    出口是我们自己的中转机，它只转发 TCP，不接受代理协议以外的指令。
    """
    s = requests.Session()
    s.trust_env = False
    if EGRESS:
        s.proxies = {"http": EGRESS, "https": EGRESS}
    ad = requests.adapters.HTTPAdapter(max_retries=0)
    s.mount("http://", ad)
    s.mount("https://", ad)
    return s


class FetchError(Exception):
    def __init__(self, code: str, message_zh: str):
        super().__init__(message_zh)
        self.code = code
        self.message_zh = message_zh


@dataclass
class Page:
    url: str
    status: int
    content_type: str
    text: str


def decode_body(raw: bytes, content_type: str = "") -> str:
    """编码判定：HTTP 头声明 → 严格 UTF-8 → <meta charset> → GB18030 兜底。"""
    m = re.search(r"charset=([\w-]+)", content_type or "", re.I)
    cands = [m.group(1)] if m else []
    cands.append("utf-8")
    mm = re.search(rb'<meta[^>]+charset=["\']?([a-zA-Z0-9_-]+)', raw[:65536], re.I)
    if mm:
        cands.append(mm.group(1).decode("ascii", "ignore"))
    cands.append("gb18030")
    for enc in cands:
        if enc.lower() in ("gb2312", "gbk"):
            enc = "gb18030"
        try:
            return raw.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return raw.decode("utf-8", errors="replace")


def _host_of(url: str) -> str:
    try:
        return (urlparse(url).hostname or "").lower()
    except Exception:
        return ""


def _hint_active(host: str) -> bool:
    exp = _EGRESS_HINTS.get(host)
    return bool(exp and exp > time.time())


def _set_hint(host: str) -> None:
    if host:
        _EGRESS_HINTS[host] = time.time() + EGRESS_HINT_TTL


def _drop_hint(host: str) -> None:
    _EGRESS_HINTS.pop(host, None)


def _via_egress(url: str, kind: str, target: str, max_redirects: int, total_timeout: float | None) -> Page:
    if kind == "instabox":
        return _fetch_instabox(url, target, total_timeout or TOTAL_TIMEOUT)
    return _fetch_once(url, None, max_redirects, total_timeout, egress=True)


def fetch(url: str, session: requests.Session | None = None, max_redirects: int = 5,
          total_timeout: float | None = None) -> Page:
    """抓取一个公开网页；直连失败且配了境外出口（CLAUSELENS_EGRESS）时改走出口重试一次。

    出口存在的理由：本机 DNS 被污染（signal.org 解析到 31.13.90.33、duckduckgo.com 解析到
    108.160.169.175）或被 SNI 阻断的站点，直连永远拿不到内容，换出口就能读到。
    """
    kind, target = _egress_kind()
    host = _host_of(url)
    if kind and _hint_active(host):
        try:
            return _via_egress(url, kind, target, max_redirects, total_timeout)
        except FetchError:
            pass   # 出口也不行了，再退回直连碰碰运气
    try:
        page = _fetch_once(url, session, max_redirects, total_timeout, egress=False)
        _drop_hint(host)
        return page
    except FetchError as e:
        if not kind or e.code not in _FALLBACK_CODES:
            raise
        page = _via_egress(url, kind, target, max_redirects, total_timeout)
        _set_hint(host)
        return page


def _egress_kind() -> tuple[str | None, str]:
    # `cloud:` 是文档里用的中性写法，`instabox:` 保留兼容；两者等价
    for prefix in ("cloud:", "instabox:"):
        if EGRESS.startswith(prefix):
            return "instabox", EGRESS.split(":", 1)[1].strip()
    if EGRESS:
        return "socks5", EGRESS
    return None, ""


def _instabox_key() -> str:
    k = (os.environ.get("INSTABOX_API_KEY") or "").strip()
    if k:
        return k
    p = os.path.expanduser("~/.secrets/instabox/instabox.dsh.api_key")
    try:
        with open(p, encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return ""


def _fetch_instabox(url: str, machine_id: str, budget: float) -> Page:
    """让 InstaBox 容器里的 curl 抓一次，压缩后 base64 取回。

    不发布端口、不起常驻进程，所以没有"开放代理被滥用"的面；代价是每次多 1–2 秒的
    API 往返，因此只在直连失败时触发。
    """
    import base64
    import gzip
    import json

    p = urlparse(url)
    if p.scheme not in ("http", "https") or not p.hostname:
        raise FetchError("blocked", "这个地址不能访问")
    try:
        if p.port not in ALLOWED_PORTS:
            raise FetchError("blocked", "只支持常见网页端口")
    except ValueError:
        raise FetchError("blocked", "这个地址不能访问")
    if not _DOMAIN_RE.match(p.hostname.lower().rstrip(".")):
        raise FetchError("blocked", "这个地址不是公开网站")
    key = _instabox_key()
    if not key:
        raise FetchError("fetch_failed", "境外出入口没有配置密钥")

    secs = max(5, min(20, int(budget)))
    u = url.replace("'", "'\\''")
    a = UA.replace("'", "'\\''")
    cmd = (
        f"curl -sSL --max-time {secs} --compressed -A '{a}' -D /tmp/cl_h -o /tmp/cl_b "
        f"-w '%{{http_code}}' '{u}' > /tmp/cl_code 2>/dev/null || echo ERR > /tmp/cl_code; "
        f'echo "CODE=$(cat /tmp/cl_code)"; '
        f'echo "TYPE=$(grep -i "^content-type:" /tmp/cl_h | tail -1 | tr -d \\"\\r\\" | cut -d" " -f2-)"; '
        f'echo "B64=$(head -c 800000 /tmp/cl_b 2>/dev/null | gzip -9 | base64 -w0)"'
    )
    try:
        r = requests.post(
            f"https://api.instabox.sh/v1/machines/{machine_id}/exec",
            headers={"X-API-Key": key, "Content-Type": "application/json"},
            data=json.dumps({"cmd": cmd, "timeoutSeconds": secs + 25}).encode(),
            timeout=secs + 40,
        )
        r.raise_for_status()
        out = (r.json() or {}).get("stdout") or ""
    except Exception:
        raise FetchError("fetch_failed", "打不开这个网站")

    code, ctype, b64 = "0", "", ""
    for line in out.splitlines():
        if line.startswith("CODE="):
            code = line[5:].strip()
        elif line.startswith("TYPE="):
            ctype = line[5:].strip()
        elif line.startswith("B64="):
            b64 = line[4:].strip()
    if not code.isdigit() or code == "0":
        raise FetchError("fetch_failed", "打不开这个网站")
    try:
        raw = gzip.decompress(base64.b64decode(b64)) if b64 else b""
    except Exception:
        raw = b""
    if not raw and int(code) >= 400:
        raise FetchError("fetch_failed", "打不开这个网站")
    return Page(url, int(code), ctype, decode_body(raw[:MAX_BYTES], ctype))


def _fetch_once(url: str, session: requests.Session | None, max_redirects: int,
                total_timeout: float | None, egress: bool) -> Page:
    """抓取一个公开网页。

    - 每一跳重定向都重新校验；连接建立后再校验对端真实 IP（防 DNS 重绑定）
    - 只允许常见 Web 端口
    - 总时长默认 TOTAL_TIMEOUT；调用方可以给更小的 total_timeout 来把整次分析的预算
      分摊到每个页面上（否则队列里三个慢页面就能把 40 秒预算撑成 60 秒）
    - 到点由 watchdog 强制断开 socket，慢速滴流也会按时中断
    """
    if session is not None:
        sess = session
    elif egress:
        sess = egress_session()
    else:
        sess = safe_session()
    if not egress and not any(isinstance(a, _GuardedAdapter) for a in sess.adapters.values()):
        sess = safe_session()
    cur = url
    t0 = time.monotonic()
    budget = TOTAL_TIMEOUT if total_timeout is None else max(1.0, min(TOTAL_TIMEOUT, total_timeout))

    def left() -> float:
        return budget - (time.monotonic() - t0)

    for _ in range(max_redirects + 1):
        p = urlparse(cur)
        if p.scheme not in ("http", "https") or not p.hostname:
            raise FetchError("blocked", "这个地址不能访问")
        try:
            port = p.port
        except ValueError:
            raise FetchError("blocked", "这个地址不能访问")
        if port not in ALLOWED_PORTS:
            raise FetchError("blocked", "只支持常见网页端口")
        if egress:
            # 出口模式下本地 DNS 可能被污染或直接不可用，解析失败不阻断（远端会重新解析）；
            # 但解析出来确实是内网地址，仍然拒绝
            try:
                if not _is_public_host(p.hostname):
                    raise FetchError("blocked", "这个地址不是公开网站")
            except FetchError as fe:
                if fe.code != "unreachable":
                    raise
        elif not _is_public_host(p.hostname):
            raise FetchError("blocked", "这个地址不是公开网站")
        if left() <= 0:
            raise FetchError("timeout", "网站响应太慢了")
        try:
            r = sess.get(cur, headers={"User-Agent": UA, "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"},
                         timeout=(min(TIMEOUT[0], left()), min(TIMEOUT[1], left())), allow_redirects=False, stream=True)
        except requests.Timeout:
            raise FetchError("timeout", "网站响应太慢了")
        except requests.ConnectionError as e:
            if _is_blocked_peer(e):
                raise FetchError("blocked", "这个地址不是公开网站")
            raise FetchError("fetch_failed", "打不开这个网站")
        except requests.RequestException:
            raise FetchError("fetch_failed", "打不开这个网站")
        if r.is_redirect or r.status_code in (301, 302, 303, 307, 308):
            loc = r.headers.get("Location")
            r.close()
            if not loc:
                break
            cur = urljoin(cur, loc)
            continue
        buf = bytearray()
        kill = _DeadlineKiller(max(0.05, left()), r.raw).start()
        try:
            raw = r.raw
            while len(buf) <= MAX_BYTES:
                remain = left()
                if remain <= 0:
                    raise FetchError("timeout", "网站响应太慢了")
                _set_read_timeout(raw, min(TIMEOUT[1], remain))
                chunk = raw.read(8192, decode_content=True)
                if not chunk:
                    break
                buf.extend(chunk)
        except FetchError:
            r.close()
            raise
        except Exception as e:  # urllib3 ReadTimeout / ProtocolError / ChunkedEncodingError 等
            r.close()
            if kill.fired or left() <= 0 or _is_timeout(e):
                raise FetchError("timeout", "网站响应太慢了")
            if not buf:
                raise FetchError("fetch_failed", "打不开这个网站")
        finally:
            kill.cancel()
        if kill.fired:
            r.close()
            raise FetchError("timeout", "网站响应太慢了")
        r.close()
        ctype = r.headers.get("Content-Type", "")
        return Page(cur, r.status_code, ctype, decode_body(bytes(buf[:MAX_BYTES]), ctype))
    raise FetchError("fetch_failed", "重定向次数太多")


def _is_timeout(e: BaseException) -> bool:
    """判断异常链里是否有读超时（urllib3 的 ReadTimeoutError 不继承 requests.Timeout）。"""
    seen = set()
    while e is not None and id(e) not in seen:
        seen.add(id(e))
        if isinstance(e, (TimeoutError, socket.timeout)):
            return True
        if type(e).__name__ in ("ReadTimeoutError", "ReadTimeout", "TimeoutError"):
            return True
        e = e.__cause__ or e.__context__ or (e.args[0] if e.args and isinstance(e.args[0], BaseException) else None)
    return False


def _is_blocked_peer(e: BaseException) -> bool:
    seen = set()
    while e is not None and id(e) not in seen:
        seen.add(id(e))
        if isinstance(e, _BlockedPeer) or "blocked peer" in str(e):
            return True
        e = e.__cause__ or e.__context__ or (e.args[0] if e.args and isinstance(e.args[0], BaseException) else None)
    return False


def _socket_of(raw):
    """从 urllib3 的响应对象反查底层 socket，拿不到就退回连接建立时记录的。"""
    try:
        return raw._fp.fp.raw._sock  # http.client.HTTPResponse → SocketIO → socket
    except Exception:
        return getattr(_tls, "sock", None)


class _DeadlineKiller:
    """到点强制断开当前线程正在读的 socket。

    为什么必须这么做：urllib3 的 `read(amt)` 内部会循环 recv 直到攒够 amt 字节或 EOF，
    socket 超时只管**单次** recv。所以对端只要每隔 < TIMEOUT[1] 秒滴一个字节，
    read(8192) 就永远不返回，总超时形同虚设（实测 60s 才因对端断开而退出）。
    """

    def __init__(self, seconds: float, raw=None):
        self.fired = False
        self._sock = _socket_of(raw) if raw is not None else getattr(_tls, "sock", None)
        self._timer = threading.Timer(max(0.05, seconds), self._fire)
        self._timer.daemon = True

    def _fire(self):
        self.fired = True
        sock = self._sock
        if sock is not None:
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass

    def start(self):
        self._timer.start()
        return self

    def cancel(self):
        self._timer.cancel()


def _set_read_timeout(raw, seconds: float) -> None:
    """把底层 socket 的超时收紧到剩余时间（管的是"完全没有数据"的挂起）。"""
    sock = _socket_of(raw)
    if sock is None:
        return
    try:
        sock.settimeout(max(0.5, seconds))
    except OSError:
        pass
