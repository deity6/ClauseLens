"""中文站点条款语料采集。

流程：首页 → 锚文本找条款链接 →（不足时）anysearch 搜直达链接 → 抓取 → 提取正文。
约束：只抓公开页面；不登录、不绕验证码；每主机 ≥1s 间隔；超时 20s；单页 ≤5MB；
仅 http/https 且拒绝内网地址（防 SSRF）。可断点续跑：已处理过的 domain 跳过（--force 重跑）。

用法：python scripts/harvest_cn.py [--workers 8] [--limit N] [--only taobao.com,jd.com] [--force]
输出：data/processed/cn_docs.jsonl、data/raw/cn/failures.jsonl、data/raw/cn/html/<domain>/*.html
"""
from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import re
import socket
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cn_sites import SITES  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "cn"
OUT = ROOT / "data" / "processed" / "cn_docs.jsonl"
FAIL = RAW / "failures.jsonl"
DONE = RAW / "done.txt"
SEARCH_CLI = Path.home() / ".claude" / "skills" / "anysearch" / "scripts" / "anysearch_cli.py"

TIMEOUT = 20
MAX_BYTES = 5 * 1024 * 1024
TOTAL_TIMEOUT = 60  # 单页下载总时长上限（TIMEOUT 只管单次读取）
MIN_INTERVAL = 1.0
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36 ClauseLensResearch/0.1"

PRIVACY_KW = ("隐私", "个人信息保护", "个人信息处理", "儿童个人信息")
TERMS_KW = ("用户协议", "服务协议", "服务条款", "使用条款", "用户服务协议", "注册协议", "使用协议", "用户条款", "平台协议", "会员协议", "许可协议")
OTHER_KW = ("必读", "法律声明", "免责声明", "知识产权声明", "规则中心", "社区公约", "cookie", "Cookie")

# 首页与搜索都找不到时，探测常见路径（每主机限速照常生效）
COMMON_PATHS = [("privacy", "/privacy"), ("privacy", "/privacy.html"), ("terms", "/agreement"),
                ("terms", "/terms"), ("terms", "/protocol"), ("other", "/legal")]

_host_lock = threading.Lock()
_host_next: dict[str, float] = {}
_write_lock = threading.Lock()
_search_sem = threading.Semaphore(2)


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def classify(s: str) -> str | None:
    if any(k in s for k in PRIVACY_KW):
        return "privacy"
    if any(k in s for k in TERMS_KW):
        return "terms"
    if any(k in s for k in OTHER_KW):
        return "other"
    return None


def classify_url(url: str) -> str | None:
    low = url.lower()
    if "privacy" in low or "yinsi" in low:
        return "privacy"
    if re.search(r"terms|agreement|protocol|xieyi|duty|legal|license|tos", low):
        return "terms"
    return None


def host_ok(url: str) -> str | None:
    """返回拒绝原因；None 表示可抓。"""
    try:
        p = urlparse(url)
        p.hostname
    except ValueError:
        return "URL 格式错误"
    if p.scheme not in ("http", "https") or not p.hostname:
        return "非 http(s) 链接"
    try:
        infos = socket.getaddrinfo(p.hostname, None)
    except socket.gaierror:
        return "DNS 解析失败"
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            return f"解析到内网地址 {ip}"
    return None


def throttle(host: str) -> None:
    while True:
        with _host_lock:
            t = time.monotonic()
            nxt = _host_next.get(host, 0.0)
            if t >= nxt:
                _host_next[host] = t + MIN_INTERVAL
                return
            wait = nxt - t
        time.sleep(wait)


def fetch(session: requests.Session, url: str) -> tuple[str | None, str, str]:
    """返回 (html, final_url, error)。"""
    cur = url
    for _ in range(6):  # 手动跟随重定向，每跳都做 SSRF 检查
        bad = host_ok(cur)
        if bad:
            return None, cur, bad
        throttle(urlparse(cur).hostname)
        try:
            r = session.get(cur, timeout=TIMEOUT, stream=True, allow_redirects=False)
        except requests.exceptions.Timeout:
            return None, cur, "超时"
        except requests.exceptions.SSLError:
            return None, cur, "TLS 错误"
        except requests.exceptions.RequestException as e:
            return None, cur, f"连接错误: {type(e).__name__}"
        if r.status_code in (301, 302, 303, 307, 308) and r.headers.get("Location"):
            cur = urljoin(cur, r.headers["Location"])
            r.close()
            continue
        if r.status_code != 200:
            r.close()
            return None, cur, f"HTTP {r.status_code}"
        ctype = r.headers.get("Content-Type", "")
        if ctype and "html" not in ctype and "text" not in ctype:
            r.close()
            return None, cur, f"非 HTML ({ctype.split(';')[0]})"
        buf = bytearray()
        t0 = time.monotonic()
        try:
            for chunk in r.iter_content(65536):
                buf += chunk
                if len(buf) > MAX_BYTES:
                    r.close()
                    return None, cur, "超过 5MB"
                if time.monotonic() - t0 > TOTAL_TIMEOUT:
                    r.close()
                    return None, cur, "下载总时长超时"
        except requests.exceptions.RequestException as e:
            r.close()
            return None, cur, f"读取中断: {type(e).__name__}"
        enc = r.encoding if (r.encoding and "charset" in ctype.lower()) else None
        if not enc:
            m = re.search(rb'charset=["\']?([\w-]+)', bytes(buf[:4096]))
            enc = m.group(1).decode() if m else None
        if not enc:
            try:
                return bytes(buf).decode("utf-8"), cur, ""
            except UnicodeDecodeError:
                enc = "gb18030"
        if enc.lower() in ("gb2312", "gbk"):
            enc = "gb18030"
        try:
            html = bytes(buf).decode(enc, errors="replace")
        except LookupError:
            html = bytes(buf).decode("utf-8", errors="replace")
        return html, cur, ""
    return None, cur, "重定向过多"


def allowed(url: str, hosts: tuple[str, ...], domain: str) -> bool:
    try:
        h = (urlparse(url).hostname or "").lower()
    except ValueError:
        return False
    base = domain.split("/")[0]
    return any(h == s or h.endswith("." + s) for s in hosts + (base,))


def find_links(html: str, base_url: str, hosts, domain) -> list[tuple[str, str, str]]:
    soup = BeautifulSoup(html, "lxml")
    out, seen = [], set()
    for a in soup.find_all("a", href=True):
        text = " ".join(a.get_text(" ", strip=True).split())[:60] or a.get("title", "")
        href = a["href"].strip()
        if href.startswith(("javascript:", "mailto:", "#", "tel:")):
            continue
        try:
            url = urljoin(base_url, href).split("#")[0]
            urlparse(url).hostname
        except ValueError:
            continue
        dt = classify(text)
        if not dt:
            dt = classify_url(url)
        if dt and url not in seen and allowed(url, hosts, domain):
            seen.add(url)
            out.append((dt, url, text))
    return out


def search_links(name: str, domain: str, hosts) -> list[tuple[str, str, str]]:
    out = []
    base = domain.split("/")[0]
    for q in (f"{name} 隐私政策 site:{base}", f"{name} 用户协议 site:{base}", f"{name} 隐私政策", f"{name} 用户服务协议"):
        with _search_sem:
            try:
                p = subprocess.run([sys.executable, str(SEARCH_CLI), "search", q, "--zone", "cn", "-m", "10"],
                                   capture_output=True, text=True, encoding="utf-8", timeout=60)
                txt = p.stdout
            except Exception:
                continue
        # 结果是 Markdown 块：### n. 标题 / - **URL**: ... / 摘要；摘要里常引用官方原链接
        for block in re.split(r"\n(?=###\s*\d+\.)", txt):
            m = re.match(r"###\s*\d+\.\s*(.+)", block)
            if not m:
                continue
            title = m.group(1).strip()
            for url in re.findall(r"https?://[A-Za-z0-9\-._~:/?#\[\]@!$&'*+,;=%]+", block):
                url = url.rstrip(".,;").split("#")[0]
                if not allowed(url, hosts, domain) or re.search(r"\.(png|jpg|gif|css|js|ico)$", url, re.I):
                    continue
                dt = classify(title) or classify_url(url)
                if dt:
                    out.append((dt, url, "search:" + title[:50]))
    return out


DROP_TAGS = ("script", "style", "noscript", "nav", "header", "footer", "aside", "form", "iframe", "svg", "button", "select")


def extract(html: str) -> tuple[str, str]:
    soup = BeautifulSoup(html, "lxml")
    title = (soup.title.get_text(strip=True) if soup.title else "")[:200]
    for t in soup(DROP_TAGS):
        t.decompose()
    for t in soup.find_all(attrs={"class": re.compile(r"(^|\b)(nav|menu|footer|header|sidebar|breadcrumb)", re.I)}):
        if len(t.get_text(strip=True)) < 2000:
            t.decompose()
    body = soup.body or soup
    total = len(body.get_text(strip=True)) or 1
    # 选包含 ≥70% 正文、且最深的容器
    best = body
    for el in body.find_all(["article", "main", "section", "div"]):
        n = len(el.get_text(strip=True))
        if n >= 0.7 * total and n < len(best.get_text(strip=True)) + 1:
            best = el
    for br in best.find_all("br"):
        br.replace_with("\n")
    lines = []
    for el in best.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "td", "pre", "blockquote", "div"]):
        if el.find(["p", "li", "div", "h1", "h2", "h3", "h4", "table"]):
            continue  # 只取叶子块，避免重复
        s = " ".join(el.get_text(" ", strip=True).split())
        if s:
            if el.name and el.name[0] == "h" and el.name[1:].isdigit():
                s = "#" * int(el.name[1]) + " " + s
            lines.append(s)
    text = "\n".join(lines)
    if len(text) < 0.5 * total:  # 结构不规则，退回整体文本
        text = "\n".join(l.strip() for l in best.get_text("\n").splitlines() if l.strip())
    return title, text


def cjk_ratio(s: str) -> float:
    if not s:
        return 0.0
    return len(re.findall(r"[一-鿿]", s)) / len(s)


BAD_URL = re.compile(r"login|passport|signin|register\b|/search|keyword=|question|/issue/|/notice/", re.I)
# 新闻、博客、论坛、FAQ：标题含「隐私」也不是条款原文，一律排除
NEWS_URL = re.compile(r"blog\.csdn|/article/details/|ttarticle|newsDetail|36kr\.com/p/|/news\b|faqDetail|/garage/", re.I)


def valid_doc(text: str, title: str = "", url: str = "") -> str | None:
    if NEWS_URL.search(url):
        return "新闻/博客/FAQ 页，非条款原文"
    if BAD_URL.search(url) and not classify(title):
        return "登录/搜索/帮助页，非条款正文"
    if len(text) < 800:
        return f"正文过短({len(text)}字)，疑似 SPA/JS 渲染"
    if cjk_ratio(text) < 0.2:
        return "非中文正文"
    head = title + text[:1500]
    if not (classify(head) or re.search(r"声明|规则|政策|条款|协议", head)):
        return "标题与开头不含条款关键词"
    if len(re.findall(r"个人信息|协议|条款|同意|授权|责任|权利", text)) < 8:
        return "条款用语过少，疑似非条款页"
    return None


def append(path: Path, rec: dict) -> None:
    with _write_lock:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


# ---- 无头浏览器渲染（--render）：用于 SPA；不登录、不处理验证码 ----
RENDER = False
CHROME = None  # 浏览器可执行文件路径（--chrome），默认用 playwright 自带
_tls = threading.local()


def _browser():
    if getattr(_tls, "ctx", None) is None:
        from playwright.sync_api import sync_playwright
        _tls.pw = sync_playwright().start()
        kw = {"executable_path": CHROME} if CHROME else {}
        _tls.browser = _tls.pw.chromium.launch(**kw)
        _tls.ctx = _tls.browser.new_context(user_agent=UA, locale="zh-CN")

        def guard(route):  # 每个请求（含重定向、子资源）都做 SSRF 检查；丢弃图片/媒体/字体
            rq = route.request
            if rq.resource_type in ("image", "media", "font") or host_ok(rq.url):
                return route.abort()
            return route.continue_()
        _tls.ctx.route("**/*", guard)
    return _tls.ctx


def fetch_rendered(url: str) -> tuple[str | None, str, str]:
    bad = host_ok(url)
    if bad:
        return None, url, bad
    throttle(urlparse(url).hostname)
    pg = _browser().new_page()
    try:
        resp = pg.goto(url, timeout=TIMEOUT * 1000, wait_until="domcontentloaded")
        if resp is not None and resp.status >= 400:
            return None, pg.url, f"HTTP {resp.status}"
        try:
            pg.wait_for_load_state("networkidle", timeout=8000)
        except Exception:
            pass
        html = pg.content()
        if len(html.encode()) > MAX_BYTES:
            return None, pg.url, "超过 5MB"
        return html, pg.url, ""
    except Exception as e:
        return None, url, f"渲染失败: {type(e).__name__}"
    finally:
        pg.close()


def harvest_site(domain: str, name: str, hosts) -> dict:
    s = requests.Session()
    s.headers.update({"User-Agent": UA, "Accept-Language": "zh-CN,zh;q=0.9"})
    if RENDER:
        def fetch(_s, u):  # noqa: F811 — 本站点内改用渲染抓取
            return fetch_rendered(u)
    else:
        fetch = globals()["fetch"]
    fails, cands = [], []
    home_html, home_url = None, ""
    for u in (f"https://{domain}/", f"https://www.{domain}/", f"http://www.{domain}/"):
        if u.startswith("https://www.") and domain.count(".") >= 2 and not domain.endswith((".com.cn", ".net.cn")):
            continue
        home_html, home_url, err = fetch(s, u)
        if home_html:
            break
        fails.append({"stage": "home", "url": u, "reason": err})
    if home_html:
        cands = find_links(home_html, home_url, hosts, domain)
        if not cands:
            fails.append({"stage": "discover", "url": home_url, "reason": "首页未找到条款链接（可能 JS 渲染）"})
    if len({c[0] for c in cands if c[0] != "other"}) < 2:
        cands += search_links(name, domain, hosts)
    if len({c[0] for c in cands if c[0] != "other"}) < 2 and home_html:
        root = f"{urlparse(home_url).scheme}://{urlparse(home_url).netloc}"
        cands += [(dt, root + path, "probe") for dt, path in COMMON_PATHS]
    # 每类最多取 3 个候选，总数 ≤ 8
    picked, per = [], {}
    seen = set()
    for dt, url, anchor in cands:
        if url in seen or per.get(dt, 0) >= 4:
            continue
        seen.add(url)
        per[dt] = per.get(dt, 0) + 1
        picked.append((dt, url, anchor))
    picked = picked[:10]
    if not picked:
        fails.append({"stage": "discover", "url": "", "reason": "首页与搜索均未找到条款链接"})
    docs, hashes = 0, set()
    hdir = RAW / "html" / domain.replace("/", "_")
    for dt, url, anchor in picked:
        html, final, err = fetch(s, url)
        if not html:
            fails.append({"stage": "doc", "url": url, "reason": err})
            continue
        title, text = extract(html)
        bad = valid_doc(text, title, final)
        if bad:
            fails.append({"stage": "doc", "url": final, "reason": bad})
            continue
        h = hashlib.sha1(text.encode()).hexdigest()
        if h in hashes:
            continue
        hashes.add(h)
        hdir.mkdir(parents=True, exist_ok=True)
        (hdir / f"{h[:12]}.html").write_text(html, encoding="utf-8", newline="\n")
        dt2 = classify(title) or dt
        append(OUT, {"domain": domain, "name": name, "doc_type": dt2, "url": final, "title": title,
                     "anchor": anchor, "text": text, "chars": len(text), "sha1": h, "fetched_at": now(),
                     "render": RENDER})
        docs += 1
    for f in fails:
        append(FAIL, {"domain": domain, "name": name, **f, "render": RENDER, "at": now()})
    with _write_lock:
        with DONE.open("a", encoding="utf-8", newline="\n") as f:
            f.write(domain + "\n")
    return {"domain": domain, "docs": docs, "fails": len(fails)}


def safe_harvest(domain: str, name: str, hosts) -> dict:
    try:
        return harvest_site(domain, name, hosts)
    except Exception as e:  # 单站异常不影响整体；不写 done，下次续跑会重试
        append(FAIL, {"domain": domain, "name": name, "stage": "crash", "url": "", "reason": f"{type(e).__name__}: {e}"[:300], "at": now()})
        return {"domain": domain, "docs": 0, "fails": 1}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--only", default="")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--render", action="store_true", help="用无头浏览器渲染（SPA 兜底）")
    ap.add_argument("--chrome", default="", help="浏览器可执行文件路径")
    ap.add_argument("--retry-failed", action="store_true", help="只处理 cn_docs.jsonl 里还没有文档的站点")
    a = ap.parse_args()
    global RENDER, CHROME
    RENDER, CHROME = a.render, (a.chrome or None)
    RAW.mkdir(parents=True, exist_ok=True)
    done = set(DONE.read_text(encoding="utf-8").split()) if DONE.exists() and not a.force else set()
    sites = [x for x in SITES if x[0] not in done]
    if a.retry_failed:
        have = {json.loads(l)["domain"] for l in OUT.open(encoding="utf-8")} if OUT.exists() else set()
        sites = [x for x in SITES if x[0] not in have]
    if a.only:
        want = set(a.only.split(","))
        sites = [x for x in SITES if x[0] in want]
    if a.limit:
        sites = sites[: a.limit]
    print(f"待处理 {len(sites)} 个站点", flush=True)
    ok = 0
    with ThreadPoolExecutor(a.workers) as ex:
        for i, r in enumerate(ex.map(lambda x: safe_harvest(*x), sites), 1):
            ok += r["docs"] > 0
            print(f"[{i}/{len(sites)}] {r['domain']}: docs={r['docs']} fails={r['fails']}", flush=True)
    print(f"完成：{ok}/{len(sites)} 个站点至少 1 篇文档")


if __name__ == "__main__":
    main()
