"""发现条款文档 + 正文提取。"""
from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from . import net

DOC_PATTERNS = [
    # (doc_type, 锚文本/URL 正则, 基础分)
    ("privacy", re.compile(r"隐私(?:权)?(?:政策|保护|声明|条款)|个人信息(?:保护|处理)(?:政策|规则)?|privacy", re.I), 10),
    ("terms", re.compile(r"(?:用户|服务|使用|软件许可(?:及服务)?|会员)(?:协议|条款)|服务条款|使用条款|terms(?: of (?:service|use))?|\btos\b|user agreement|conditions", re.I), 9),
    ("cookie", re.compile(r"cookie", re.I), 5),
    ("other", re.compile(r"法律(?:声明|条款)|免责声明|legal|版权声明|copyright|duty", re.I), 3),
]

COMMON_PATHS = [
    # 根目录 / 一级目录
    "/privacy", "/privacy-policy", "/privacy.html", "/privacy_policy", "/privacy-policy.html",
    "/terms", "/terms-of-service", "/terms.html", "/terms-of-use", "/tos",
    "/user-agreement", "/legal", "/legal/privacy", "/legal/terms", "/legal/privacy-policy",
    "/policies/privacy", "/policies/terms", "/policy/privacy", "/policy/terms",
    # 「关于/法律」目录，中文站常把一堆声明放在这里
    "/about/privacy", "/about/terms", "/about/legal", "/about/agreement", "/about/policy",
    "/about/privacy.html", "/about/terms.html", "/about/privacy.php", "/about/terms.php",
    "/help/privacy", "/support/privacy", "/legal/privacy.html", "/legal/terms.html",
    # 中文站的习惯写法
    "/agreement.html", "/protocol.html", "/yinsi", "/yinsi.html", "/terms.php", "/privacy.php",
]

# 从一份已知声明页推出同目录兄弟页用的文件名（保留原扩展名）
SIBLING_STEMS = ["privacy", "terms", "agreement", "policy", "user-agreement", "protocol",
                 "legal", "copyright", "disclaimer", "service"]


def sibling_paths(urls: list[str]) -> list[str]:
    """`/about/copyright.html` 这个链接能当线索：同目录下往往还躺着 privacy.html、agreement.html。

    很多站点首页只挂一条「版权声明」，隐私政策和用户协议就在隔壁，靠这个能捡回来。
    """
    out: list[str] = []
    for u in urls:
        seg = urlparse(u).path.rstrip("/").split("/")
        if len(seg) < 2 or not seg[-1]:
            continue
        last = seg[-1]
        stem, dot, ext = last.rpartition(".")
        ext = f".{ext}" if dot else ""
        directory = "/".join(seg[:-1]) + "/"
        for name in SIBLING_STEMS:
            if name == (stem or "").lower():
                continue
            out.append(directory + name + ext)
            if ext:
                out.append(directory + name)
    return out


def _probe_one(base: str, path: str) -> "Candidate | None":
    """（保留给单条探测用；批量走 probe_paths）"""
    url = urljoin(base, path)
    try:
        page = net.fetch(url, net.safe_session(), max_redirects=3)
    except Exception:
        return None
    if page.status >= 400:
        return None
    title, text = extract_text(page.text)
    if not looks_like_policy(text):
        return None
    return Candidate(url, title or path, guess_doc_type(title, url, text), 10)


def probe_paths(base: str, paths: list[str], tried: set[str] | None = None,
                limit: int = 18, workers: int = 6, deadline: float = 14.0) -> list[Candidate]:
    """并发探常见路径，只留真的存在、且正文像条款的。

    以前是「一个候选都没有才试 COMMON_PATHS 的前 6 条」，于是只要首页捞到一条『版权声明』
    就再也不往下试了（coolapk 就是这样漏掉隐私政策的）。现在按覆盖率补探。
    """
    import time
    from concurrent.futures import ThreadPoolExecutor, as_completed

    tried = tried or set()
    todo: list[str] = []
    for path in paths:
        u = urljoin(base, path).split("#")[0]
        if u.rstrip("/") in tried or u in tried or u in todo:
            continue
        todo.append(u)
        if len(todo) >= limit:
            break
    if not todo:
        return []
    out: list[Candidate] = []
    t0 = time.monotonic()
    seen_bodies: set[str] = set()
    pool = ThreadPoolExecutor(max_workers=workers)
    try:
        futs = {pool.submit(net.fetch, u, net.safe_session(), 3): u for u in todo}
        for fut in as_completed(futs, timeout=deadline + 6):
            if time.monotonic() - t0 > deadline:
                break
            try:
                page = fut.result()
            except Exception:
                continue
            if page.status >= 400:
                continue
            # Discourse 这类站对任何路径都返回同一份 index.html，解析 132 万字符要好几秒；
            # 按内容头部去重，同一份只解析一次
            head = page.text[:2000]
            if head in seen_bodies:
                continue
            seen_bodies.add(head)
            if len(page.text) > 3_000_000:
                continue
            # 必须先用 extract_text 剥掉脚本再判：SPA 页面前两万字全是 JS/CSS，
            # 直接拿原始 HTML 判「像不像条款」会一律判 false（小宇宙就是这么漏掉的）
            title, text = extract_text(page.text)
            if not looks_like_policy(text):
                continue
            url = futs[fut]
            out.append(Candidate(url, title or url, guess_doc_type(title, url, text), 10))
    except Exception:
        pass
    finally:
        pool.shutdown(wait=False)
    return out

NOISE_TAGS = ["script", "style", "svg", "nav", "header", "footer", "form", "iframe", "button"]
# 注意 noscript 不在这里：Discourse 这类 SPA（NodeLoc、很多论坛）会把整份正文放进
# <noscript> 里给爬虫看，服务端 HTML 里 script 占 90%+，删掉 noscript 就等于删掉正文。


@dataclass
class Candidate:
    url: str
    title: str
    doc_type: str
    score: float


def classify_link(text: str, href: str) -> tuple[str, float] | None:
    blob = f"{text} {href}"
    best = None
    for dtype, pat, base in DOC_PATTERNS:
        if pat.search(text):
            s = base + 3
        elif pat.search(href):
            s = base
        else:
            continue
        if best is None or s > best[1]:
            best = (dtype, s)
    if best and len(text) > 40:  # 长段落里提到"隐私"不算链接
        best = (best[0], best[1] - 6)
    return best if best and best[1] > 0 else None


def find_candidates(html: str, base_url: str, domain: str) -> list[Candidate]:
    soup = BeautifulSoup(html, "lxml")
    seen: dict[str, Candidate] = {}
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if href.startswith(("javascript:", "mailto:", "#", "tel:")):
            continue
        url = urljoin(base_url, href).split("#")[0]
        host = (urlparse(url).hostname or "").lower()
        if not (host == domain or host.endswith("." + domain)):
            # 允许常见的集团法务域（如 taobao → alibaba 的政策页），但降权
            off = True
        else:
            off = False
        text = " ".join(a.get_text(" ", strip=True).split())[:80] or a.get("title", "")
        c = classify_link(text, href)
        if not c:
            continue
        dtype, s = c
        if off:
            s -= 3
        if url not in seen or seen[url].score < s:
            seen[url] = Candidate(url, text or url, dtype, s)
    cands = sorted(seen.values(), key=lambda c: -c.score)
    # 每类保留前 2
    out, per = [], {}
    for c in cands:
        if per.get(c.doc_type, 0) >= 2:
            continue
        per[c.doc_type] = per.get(c.doc_type, 0) + 1
        out.append(c)
    return out[:6]


def guess_doc_type(title: str, url: str, text: str) -> str:
    c = classify_link(title or "", url)
    if c:
        return c[0]
    head = text[:400]
    if re.search(r"隐私|个人信息|privacy", head, re.I):
        return "privacy"
    if re.search(r"协议|条款|terms|agreement", head, re.I):
        return "terms"
    return "other"


_BLOCK = {"p", "div", "li", "h1", "h2", "h3", "h4", "h5", "h6", "tr", "section", "article", "br", "dd", "dt", "td", "blockquote", "pre"}


def extract_text(html: str) -> tuple[str, str]:
    """返回 (title, 正文)。保留段落换行；优先 article/main。

    SPA 兜底：`<noscript>` 里往往就是整页正文的静态版本（Discourse 论坛尤其如此），
    正文提取结果太短时改用那份，否则会得到 0 字、被误判成「这个页面不是条款」。
    """
    # 超大页面先用正则把 script 整体删掉再交给解析器：Discourse 的 HTML 有 130 万字符、
    # 其中 90% 是 <script>，BeautifulSoup 建整棵树要好几秒
    if len(html) > 400_000:
        html = re.sub(r"<script\b[^>]*>.*?</script>", "", html, flags=re.S | re.I)
    soup = BeautifulSoup(html, "lxml")
    title = (soup.title.get_text(strip=True) if soup.title else "")[:120]
    noscript_text = "\n".join(
        t for t in (n.get_text("\n", strip=True) for n in soup.find_all("noscript")) if len(t) > 400)
    for t in soup(NOISE_TAGS):
        t.decompose()
    root = soup.find("article") or soup.find("main") or soup.find(attrs={"role": "main"}) or soup.body or soup
    # 若 article 太短，退回 body
    if len(root.get_text(strip=True)) < 500 and soup.body is not None:
        root = soup.body
    for br in root.find_all("br"):
        br.replace_with("\n")
    for el in root.find_all(_BLOCK):
        el.insert_before("\n")
        el.insert_after("\n")
    raw = root.get_text("")
    lines = [" ".join(l.split()) for l in raw.splitlines()]
    lines = [l for l in lines if l]
    # 去掉重复短行（菜单残留）
    seen, out = set(), []
    for l in lines:
        if len(l) < 30 and l in seen:
            continue
        seen.add(l)
        out.append(l)
    text = "\n".join(out)
    if len(text) < 600 and len(noscript_text) > len(text) * 2:
        return title, noscript_text
    return title, text


_POLICY_KEY = re.compile(
    r"个人信息|隐私|协议|条款|同意|收集|第三方|使用者|用户|服务|"
    r"personal (?:data|information)|privacy|terms|agree|third part|user data|service", re.I)


def looks_like_policy(text: str) -> bool:
    """判断一段正文像不像条款/隐私政策。

    以前是硬门槛「至少 600 字 + 8 个关键词」，于是写得简洁的条款页全被判死
    （dnsneko.com 的隐私政策只有 492 字，内容完整，照样被丢掉）。
    现在短页面不再一刀切，改为要求**更高的关键词密度**——404 页、登录页、空白壳
    的关键词密度都很低，仍会被挡住。
    """
    if not text or len(text) < 150:
        return False
    head = text[:20000]
    hits = len(_POLICY_KEY.findall(head))
    if len(text) < 600:
        # 150–600 字的短页：每 150 字至少命中 1 个关键词，且总数 ≥ 4
        return hits >= 4 and hits * 150 >= len(head)
    return hits >= 8
