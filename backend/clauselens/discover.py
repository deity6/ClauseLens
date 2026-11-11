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
    # ── 中文语义路径（2026-11-12 覆盖报告：38 条里一条中文路径都没有，
    #    而国内中小站大量直接拿中文当路径；这些都能正常 URL 编码请求）──
    "/隐私政策", "/隐私政策.html", "/隐私声明", "/用户协议", "/用户协议.html",
    "/服务协议", "/服务条款", "/使用条款", "/法律声明", "/免责声明", "/版权声明",
    "/policy", "/policies", "/agreement", "/protocol", "/statement", "/legal.html",
    # 国内常见的「协议中心」结构
    "/terms/index.html", "/privacy/index.html", "/about/agreement.html", "/about/statement.html",
    "/static/privacy.html", "/static/terms.html", "/html/privacy.html", "/html/terms.html",
    "/info/privacy", "/info/terms", "/site/privacy", "/site/terms", "/company/privacy", "/company/terms",
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



_DOUBLE_SUFFIX = {"com", "net", "org", "gov", "edu", "co", "ac", "or", "ne", "go"}


def base_domain(host: str) -> str:
    """粗略取注册主域：`ow.blizzard.cn` 和 `wow.blizzard.cn` 都归到 `blizzard.cn`。

    只用来判「是不是同一家的站」，不做严格 PSL 解析——错了也只是少/多采信一条链接。
    """
    host = (host or "").lower().strip(".")
    parts = host.split(".")
    if len(parts) <= 2:
        return host
    if len(parts) >= 3 and parts[-2] in _DOUBLE_SUFFIX and len(parts[-1]) == 2:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


# 错误页 / 反爬挑战页的特征。它们有个共同点：正文里也大量出现「隐私」「政策」这类词
# （因为站点的页脚还在），所以只靠关键词密度分不出来，必须单独认。
_URL_POLICY_HINT = re.compile(r"/(privacy|terms|legal|policy|polity|agreement|tos|eula|gdpr)([./-]|$)", re.I)

_ERROR_PAGE = re.compile(
    r"(页面不存在|页面走丢|找不到(该|此|这个)?页面|您访问的页面|您要找的页面|"
    r"该页面(已被删除|不存在)|生产环境|"
    r"\b404\b|\b403\b|not\s*found|page\s+not\s+found|error\s+code|"
    r"just\s+a\s+moment|attention\s+required|checking\s+your\s+browser|"
    r"verify\s+you\s+are\s+human|enable\s+javascript\s+and\s+cookies|"
    r"访问被拒绝|请求被拦截|系统繁忙|服务异常|权限不足)", re.I)


def looks_like_error_page(text: str) -> bool:
    """像是「404 / WAF 挑战 / 登录墙」而不是条款正文。

    实测踩过（2026-11-12 覆盖报告）：
      - error.taobao.com 的错误页 976 字被当成隐私政策，给了 C 级；
      - ezg.com 被 Cloudflare 拦住，页面里那条 Cloudflare 自己的隐私政策被算成它的条款。
    """
    head = text[:600]
    if not _ERROR_PAGE.search(head):
        return False
    return len(text) < 2500      # 真条款动辄几千字，前 600 字里出现这些词的多半是错误页


def find_candidates(html: str, base_url: str, domain: str) -> list[Candidate]:
    soup = BeautifulSoup(html, "lxml")
    seen: dict[str, Candidate] = {}
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if href.startswith(("javascript:", "mailto:", "#", "tel:")):
            continue
        url = urljoin(base_url, href).split("#")[0]
        host = (urlparse(url).hostname or "").lower()
        # 只有同一主域（含其子域）的链接才采信。原来是「跨域只扣 3 分」，
        # 于是 ezg.com 的 Cloudflare 拦截页把 cloudflare.com/privacy 送成了它的条款。
        # taobao→alibaba 这类同集团跨域会因此丢掉——但宁可少一条，也不要贴错。
        if base_domain(host) != base_domain(domain):
            continue
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


# 解析前的硬上限：再大的页面也不是条款（条款正文很少超过 1MB），
# 而交给 lxml/BeautifulSoup 的代价是指数级上升的。
MAX_PARSE_CHARS = 2_000_000


def _strip_scripts(html: str) -> str:
    """线性复杂度地剥掉 <script>…</script>。

    **不能用正则** `<script[^>]*>.*?</script>`：只要页面里有一个**未闭合**的 <script>，
    `.*?` 就会一路回溯到字符串末尾，复杂度退化成 O(n²)。实测 0.48MB 的畸形页面要 86.8 秒，
    按二次增长外推 5MB 约 2.5 小时——期间 GIL 被占满，uvicorn 单进程等于整个 API 停摆。
    只要攻击者让自己的域名返回一份含大量 `<script` 的 HTML，一个请求就够（2026-11-12 安全审计 S1）。

    这里改成两指针扫描：找 `<script`、找它之后的第一个 `</script>`、跳过，全程 O(n)。
    找不到闭合标签时**丢弃剩余全部内容**——那本来就是被截断的脚本。
    """
    out, i, n = [], 0, len(html)
    close = "</script>"
    while i < n:
        j = html.find("<script", i)
        if j < 0:
            out.append(html[i:])
            break
        out.append(html[i:j])
        k = html.find(close, j)
        if k < 0:
            break
        i = k + len(close)
    return "".join(out)


_BLOCK = {"p", "div", "li", "h1", "h2", "h3", "h4", "h5", "h6", "tr", "section", "article", "br", "dd", "dt", "td", "blockquote", "pre"}


def extract_text(html: str) -> tuple[str, str]:
    """返回 (title, 正文)。保留段落换行；优先 article/main。

    SPA 兜底：`<noscript>` 里往往就是整页正文的静态版本（Discourse 论坛尤其如此），
    正文提取结果太短时改用那份，否则会得到 0 字、被误判成「这个页面不是条款」。
    """
    # 超大页面先用正则把 script 整体删掉再交给解析器：Discourse 的 HTML 有 130 万字符、
    # 其中 90% 是 <script>，BeautifulSoup 建整棵树要好几秒
    if len(html) > MAX_PARSE_CHARS:
        html = html[:MAX_PARSE_CHARS]
    if "<script" in html:
        html = _strip_scripts(html)
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
    # 原来对每个 block 节点做 insert_before/insert_after（每个都是一次 DOM 改动，
    # 几千个节点就是几千次，且每次都要重新定位——也是超时的一部分）。
    # get_text(separator) 一次遍历即可，行为等价：每个块之间本来就要有换行。
    for br in root.find_all("br"):
        br.replace_with("\n")
    raw = root.get_text("\n")
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


def looks_like_policy(text: str, url: str = "") -> bool:
    """判断一段正文像不像条款/隐私政策。

    以前是硬门槛「至少 600 字 + 8 个关键词」，于是写得简洁的条款页全被判死
    （dnsneko.com 的隐私政策只有 492 字，内容完整，照样被丢掉）。
    现在短页面不再一刀切，改为要求**更高的关键词密度**——404 页、登录页、空白壳
    的关键词密度都很低，仍会被挡住。
    """
    # 150 字的下限挡掉过真正简短的声明：lobste.rs 的隐私政策正文只有 125 字，
    # 内容是真的（"我们不收集…"那种极简声明），却被门槛卡掉（2026-11-12 覆盖报告 s39）。
    # 放到 100 字，同时把短页的关键词密度要求提上去，免得放过导航页。
    if not text or len(text) < 100:
        return False
    if looks_like_error_page(text):
        return False
    # URL 自己就写着 /privacy、/terms：用户点进去（或自己贴过来）的，只要正文不是空壳
    # 就采信。lobste.rs 的隐私声明只有 125 字，还是「This is the Internet, you have no privacy.」
    # 这种口语，关键词密度天然低，纯靠密度判会被误杀（覆盖报告 s39）。
    if url and _URL_POLICY_HINT.search(urlparse(url).path or "") and len(text) >= 100:
        return True
    head = text[:20000]
    hits = len(_POLICY_KEY.findall(head))
    if len(text) < 160:
        # 100–160 字的极简声明：几乎每一句都要沾条款词汇才算
        return hits >= 3 and hits * 100 >= len(head)
    if len(text) < 600:
        # 150–600 字的短页：每 150 字至少命中 1 个关键词，且总数 ≥ 4
        return hits >= 4 and hits * 150 >= len(head)
    return hits >= 8
