#!/usr/bin/env python3
"""轻量渲染方案实测：能不能拿到渲染后的正文 + 进程树 RSS 峰值 + 单页耗时。

用法（在服务器上，用项目 venv 的 python 跑，只 import 不改项目代码）：

    PYTHONDONTWRITEBYTECODE=1 ~/clauselens/.venv/bin/python bench.py matrix \
        --schemes pw-shell,pw-chromium,lp-cli --out ~/bench/results.jsonl

    # 单跑一个组合（子进程模式，方便被外层硬超时）
    bench.py run pw-flags lobehub
"""
from __future__ import annotations

import argparse
import json
import os
import re
import signal
import subprocess
import sys
import time

BENCH = os.path.dirname(os.path.abspath(__file__))
PROJ = os.environ.get("CLAUSELENS_HOME", os.path.expanduser("~/clauselens"))
sys.path.insert(0, os.path.join(PROJ, "backend"))
sys.path.insert(0, BENCH)

from clauselens import discover                     # noqa: E402
from clauselens.net import UA                       # noqa: E402
from proc_rss import Sampler, child_pids            # noqa: E402

LP = os.path.expanduser("~/bench/lp/lightpanda")

TARGETS = {
    "doulor": "https://cloud.doulor.cn/privacy",     # Vue SPA，静态 12 字 / 渲染后 1271 字
    "lobehub": "https://lobehub.com/privacy",        # Next.js + Cloudflare，静态 402
    "blizzard": "https://ow.blizzard.cn/",           # 网易 Vue 站，要从链接里找条款页
    # 泛化抽检：项目 PROGRESS.md 里点名的脚本渲染站 + 两个典型 Next/React 站
    "taobao": "https://www.taobao.com/",
    "zhihu": "https://www.zhihu.com/term/privacy",
    "notion": "https://www.notion.com/privacy",
}

# Playwright 自带的两套 Chromium：默认 headless 用的是 chromium-headless-shell，
# channel="chromium" 才是完整 chromium 的 --headless=new。
PW_ARGS_BASE = ["--disable-gpu", "--no-sandbox"]

# 压内存的 flag 组合（每条都对应一处内存/进程开销，见报告）
PW_ARGS_TUNED = PW_ARGS_BASE + [
    "--disable-dev-shm-usage",              # 不往 /dev/shm 写，t3.micro 只有 64MB 的 shm
    "--no-zygote",                          # 少一个 zygote 进程
    "--renderer-process-limit=1",           # 只留一个 renderer 配额
    "--disable-features=site-per-process,IsolateOrigins,Translate,BackForwardCache,"
    "CalculateNativeWinOcclusion,MediaRouter,OptimizationHints,HeavyAdIntervention",
    "--js-flags=--max-old-space-size=96 --max-semi-space-size=2",
    "--blink-settings=imagesEnabled=false",
    "--disable-background-networking",
    "--disable-component-update",
    "--disable-domain-reliability",
    "--disable-breakpad",
    "--mute-audio",
    "--no-first-run",
    "--disable-extensions",
    "--disable-software-rasterizer",
]

PW_SCHEMES = {
    "pw-shell": dict(channel=None, args=PW_ARGS_BASE),
    "pw-chromium": dict(channel="chromium", args=PW_ARGS_BASE),
    "pw-flags": dict(channel=None, args=PW_ARGS_TUNED),
    "pw-single": dict(channel=None, args=PW_ARGS_TUNED + ["--single-process"]),
    "pw-flags-full": dict(channel="chromium", args=PW_ARGS_TUNED),
    # 更激进的压法：单进程 + V8 老生代/新生代都掐到最小
    "pw-single2": dict(channel=None, args=["--disable-gpu", "--no-sandbox", "--single-process",
                                          "--disable-dev-shm-usage",
                                          "--js-flags=--max-old-space-size=64 "
                                          "--max-semi-space-size=1"]),
    # 不合并进程，只把 GPU 拉进主进程（比 --single-process 稳一点）
    "pw-inproc": dict(channel=None, args=PW_ARGS_TUNED + ["--in-process-gpu"]),
}

POLICY_LINK = re.compile(r"隐私|条款|协议|政策|privacy|terms|policy|agreement|legal|tos", re.I)
DRIVER_MARKERS = ("playwright/driver", "ms-playwright")


# --------------------------------------------------------------------------- 判定
def judge(html: str, url: str) -> dict:
    """复刻项目里的判据：extract_text() + looks_like_policy()，外加链接面。"""
    if not html:
        return dict(title="", text_len=0, is_policy=False, n_links=0, policy_links=[], html_zh=False)
    try:
        title, text = discover.extract_text(html)
        ok = discover.looks_like_policy(text)
    except Exception as e:                                    # 解析炸了不算成功
        return dict(title="", text_len=0, is_policy=False, n_links=0,
                    policy_links=[], err=f"{type(e).__name__}: {e}"[:120])
    hrefs = re.findall(r'<a\b[^>]+href="([^"]{1,300})"', html, re.I)
    plinks = [h for h in hrefs if POLICY_LINK.search(h)]
    return dict(title=title[:80], text_len=len(text), is_policy=bool(ok),
                n_links=len(hrefs), policy_links=plinks[:8],
                zh=bool(re.search(r"[\u4e00-\u9fff]{8,}", text)))


# ------------------------------------------------------------------- pw (chromium)
def run_pw(scheme: str, url: str, out: dict) -> None:
    from playwright.sync_api import sync_playwright

    cfg = PW_SCHEMES[scheme]
    smp = Sampler(lambda: child_pids(DRIVER_MARKERS))
    t0 = time.time()
    with sync_playwright() as pw:
        exe = pw.chromium.executable_path
        out["exe"] = os.path.relpath(exe, os.path.expanduser("~/.cache/ms-playwright")) \
            if exe.startswith(os.path.expanduser("~/.cache/ms-playwright")) else exe
        kw = dict(headless=True, args=cfg["args"])
        if cfg["channel"]:
            kw["channel"] = cfg["channel"]
        smp.start()
        t_launch = time.time()
        browser = pw.chromium.launch(**kw)
        out["launch_s"] = round(time.time() - t_launch, 2)
        try:
            ctx = browser.new_context(user_agent=UA, locale="zh-CN",
                                      viewport={"width": 1440, "height": 1000})
            page = ctx.new_page()
            page.route("**/*", lambda r: r.abort()
                       if r.request.resource_type in ("image", "media", "font") else r.continue_())
            t1 = time.time()
            resp = page.goto(url, wait_until="domcontentloaded", timeout=30000)
            try:
                page.wait_for_load_state("networkidle", timeout=4000)
            except Exception:
                out["note"] = "networkidle 超时"
            page.wait_for_timeout(300)
            out["html"] = page.content()
            out["page_s"] = round(time.time() - t1, 2)
            out["status"] = getattr(resp, "status", None) or 200
            browser.close()
        finally:
            try:
                browser.close()
            except Exception:
                pass
    out["wall_s"] = round(time.time() - t0, 2)
    smp.stop()
    out.update(peak_rss_mb=smp.peak_rss_mb, peak_pss_mb=smp.peak_pss_mb,
               peak_swap_mb=smp.peak_swap_mb, peak_procs=smp.peak_procs,
               min_avail_mb=round(smp.min_avail, 1),
               top=[f"{c}:{b // 1048576}MB" for c, b in smp.peak_detail])


# --------------------------------------------------------------- lightpanda CLI
def run_lp_cli(scheme: str, url: str, out: dict) -> None:
    """scheme: lp-cli / lp-cli-wait / lp-cli-res / lp-cli-full / lp-cli-strip"""
    args = [LP, "fetch", "--json", "--dump", "html", url]
    if scheme == "lp-cli-wait":
        args[-1:-1] = ["--wait-until", "networkidle", "--wait-ms", "8000",
                       "--terminate-ms", "25000"]
    if scheme == "lp-cli-res":
        args[-1:-1] = ["--load-resources", "stylesheet", "--load-resources", "worker",
                       "--wait-ms", "8000"]
    if scheme == "lp-cli-full":
        # 推荐配置：等网络真正静下来 + 载入外部样式表（否则 display:none 的菜单会混进正文）
        args[-1:-1] = ["--wait-until", "networkidle", "--wait-ms", "8000",
                       "--load-resources", "stylesheet", "--terminate-ms", "25000"]
    if scheme == "lp-cli-strip":
        args[-1:-1] = ["--wait-until", "networkidle", "--wait-ms", "8000",
                       "--load-resources", "stylesheet", "--strip-mode", "shell",
                       "--terminate-ms", "25000"]
    if scheme == "lp-rec":
        # 推荐配置：等网络静默 + 载样式表（隐藏元素不混进正文）+ 中文语言标签
        # （--locale 同时决定 navigator.language / Accept-Language / Intl，
        #   不设的话 i18n 站点会返回英文版）
        args[-1:-1] = ["--wait-until", "networkidle", "--wait-ms", "8000",
                       "--load-resources", "stylesheet", "--locale", "zh-CN",
                       "--terminate-ms", "25000"]
    out["cmd"] = " ".join(["lightpanda", "fetch", "--dump", "html"] +
                          [a for a in args[4:-1] if a != url])
    t0 = time.time()
    proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    smp = Sampler([proc.pid], markers=("lightpanda",))
    smp.start()
    raw, err = proc.communicate(timeout=120)
    out["wall_s"] = round(time.time() - t0, 2)
    out["rc"] = proc.returncode
    smp.stop()
    out.update(peak_rss_mb=smp.peak_rss_mb, peak_pss_mb=smp.peak_pss_mb,
               peak_swap_mb=smp.peak_swap_mb, peak_procs=smp.peak_procs,
               min_avail_mb=round(smp.min_avail, 1),
               top=[f"{c}:{b // 1048576}MB" for c, b in smp.peak_detail])
    txt = raw.decode("utf-8", "replace")
    try:
        obj = json.loads(txt)
    except Exception:
        out["html"] = txt
        out["note"] = "JSON 解析失败，按裸 stdout 处理"
        e = err.decode("utf-8", "replace")
        if e.strip():
            out["stderr"] = e.strip()[-400:]
        return
    if isinstance(obj, dict) and "results" in obj:
        obj = (obj["results"] or [{}])[0]
    out["status"] = obj.get("http_status")
    for k in ("content", "dump", "html", "body", "data"):
        if isinstance(obj.get(k), str) and len(obj[k]) > 200:
            out["html"] = obj[k]
            break
    else:
        out["html"] = ""
        out["note"] = "JSON 里找不到 dump 字段: " + ",".join(list(obj)[:12])
    e = err.decode("utf-8", "replace")
    if e.strip():
        out["stderr"] = "\n".join(e.strip().splitlines()[-6:])[-500:]


# ------------------------------------------------------- lightpanda serve + CDP
def run_lp_cdp(scheme: str, url: str, out: dict) -> None:
    from playwright.sync_api import sync_playwright

    port = 9333
    lp = subprocess.Popen([LP, "serve", "--host", "127.0.0.1", "--port", str(port)],
                          stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    smp = Sampler(lambda: [lp.pid] + child_pids(("lightpanda",)))
    smp.start()
    t0 = time.time()
    try:
        for _ in range(60):                       # 等 CDP 端口起来
            time.sleep(0.2)
            try:
                import urllib.request
                urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=1)
                break
            except Exception:
                if lp.poll() is not None:
                    raise RuntimeError("lightpanda serve 立刻退出: " +
                                       lp.stderr.read().decode()[-300:])
        out["launch_s"] = round(time.time() - t0, 2)
        with sync_playwright() as pw:
            browser = pw.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
            ctx = browser.new_context(user_agent=UA) if hasattr(browser, "new_context") \
                else browser.contexts[0]
            page = ctx.new_page()
            t1 = time.time()
            resp = page.goto(url, wait_until="load", timeout=30000)
            try:
                page.wait_for_load_state("networkidle", timeout=6000)
            except Exception:
                out["note"] = "networkidle 超时"
            page.wait_for_timeout(500)
            out["html"] = page.content()
            out["page_s"] = round(time.time() - t1, 2)
            out["status"] = getattr(resp, "status", None) or 200
            try:
                ctx.close()
            except Exception:
                pass
    finally:
        lp.terminate()
        try:
            lp.wait(timeout=5)
        except Exception:
            lp.kill()
        smp.stop()
        out["wall_s"] = round(time.time() - t0, 2)
        out.update(peak_rss_mb=smp.peak_rss_mb, peak_pss_mb=smp.peak_pss_mb,
                   peak_swap_mb=smp.peak_swap_mb, peak_procs=smp.peak_procs,
                   min_avail_mb=round(smp.min_avail, 1))


# ------------------------------------------------------------------ node jsdom
def run_node(scheme: str, url: str, out: dict) -> None:
    script = os.path.join(BENCH, "node_render.mjs")
    env = dict(os.environ, NODE_PATH=os.path.expanduser("~/bench/node_modules"))
    t0 = time.time()
    proc = subprocess.Popen(["node", script, scheme, url], stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, cwd=os.path.expanduser("~/bench"), env=env)
    smp = Sampler([proc.pid], markers=("node_render.mjs",))
    smp.start()
    raw, err = proc.communicate(timeout=180)
    out["wall_s"] = round(time.time() - t0, 2)
    out["rc"] = proc.returncode
    smp.stop()
    out.update(peak_rss_mb=smp.peak_rss_mb, peak_pss_mb=smp.peak_pss_mb,
               peak_swap_mb=smp.peak_swap_mb, peak_procs=smp.peak_procs,
               min_avail_mb=round(smp.min_avail, 1),
               top=[f"{c}:{b // 1048576}MB" for c, b in smp.peak_detail])
    txt = raw.decode("utf-8", "replace")
    try:
        obj = json.loads(txt[txt.index("{"):])
        out["html"] = obj.get("html", "")
        out["note"] = obj.get("note", "")
        out["status"] = obj.get("status")
    except Exception:
        out["html"] = ""
        out["note"] = "node 输出无法解析: " + txt[-200:]
    e = err.decode("utf-8", "replace")
    if e.strip():
        out["stderr"] = e.strip()[-500:]


# ------------------------------------------------------------------ obscura
OBSCURA = os.path.expanduser("~/bench/obscura/obscura")


def run_obscura(scheme: str, url: str, out: dict) -> None:
    """2025 年的 Rust 无头浏览器（V8 + CDP），官方二进制 43 MB。"""
    args = [OBSCURA, "fetch", "--dump", "html", "--wait", "8", "--timeout", "30", url]
    out["cmd"] = "obscura fetch --dump html --wait 8"
    t0 = time.time()
    proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    smp = Sampler([proc.pid], markers=("obscura",))
    smp.start()
    raw, err = proc.communicate(timeout=120)
    out["wall_s"] = round(time.time() - t0, 2)
    out["rc"] = proc.returncode
    smp.stop()
    out.update(peak_rss_mb=smp.peak_rss_mb, peak_pss_mb=smp.peak_pss_mb,
               peak_swap_mb=smp.peak_swap_mb, peak_procs=smp.peak_procs,
               min_avail_mb=round(smp.min_avail, 1),
               top=[f"{c}:{b // 1048576}MB" for c, b in smp.peak_detail])
    out["html"] = raw.decode("utf-8", "replace")
    e = err.decode("utf-8", "replace").strip()
    if e:
        out["stderr"] = "\n".join(e.splitlines()[-6:])[-500:]


RUNNERS = {"pw": run_pw, "lp-cli": run_lp_cli, "lp-cdp": run_lp_cdp, "node": run_node,
           "obscura": run_obscura}


def runner_for(scheme: str):
    if scheme in PW_SCHEMES:
        return RUNNERS["pw"]
    if scheme.startswith("lp-cli") or scheme == "lp-rec":
        return RUNNERS["lp-cli"]
    if scheme.startswith("lp-cdp"):
        return RUNNERS["lp-cdp"]
    if scheme.startswith("node-"):
        return RUNNERS["node"]
    if scheme.startswith("obscura"):
        return RUNNERS["obscura"]
    raise SystemExit(f"未知方案: {scheme}")


# ------------------------------------------------------------------------- 单跑
def one(scheme: str, target: str) -> dict:
    url = TARGETS[target]
    out: dict = dict(scheme=scheme, target=target, url=url, ok=False, html="")
    t0 = time.time()
    try:
        runner_for(scheme)(scheme, url, out)
        out["ok"] = True
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"[:300]
    out.setdefault("wall_s", round(time.time() - t0, 2))
    out.update(judge(out.pop("html", ""), url))
    return out


def run_cli(argv: list[str]) -> int:
    scheme, target = argv[0], argv[1]
    res = one(scheme, target)
    print(json.dumps(res, ensure_ascii=False))
    return 0 if res.get("ok") else 1


# ------------------------------------------------------------------------ 矩阵
def matrix(schemes: list[str], targets: list[str], out_path: str, timeout: int) -> None:
    print(f"# 目标: {', '.join(targets)}", flush=True)
    for scheme in schemes:
        for target in targets:
            t0 = time.time()
            # 独立 session 跑子进程：超时时能 killpg 把 chromium/lightpanda 一起带走，
            # 不然超时的浏览器会赖在内存里，后面的测量全被污染
            p = subprocess.Popen([sys.executable, os.path.abspath(__file__), "run", scheme, target],
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                 start_new_session=True)
            try:
                raw, err = p.communicate(timeout=timeout)
                line = raw.decode("utf-8", "replace").strip().splitlines()
                res = json.loads(line[-1]) if line else dict(
                    scheme=scheme, target=target, ok=False,
                    error="无输出: " + err[-300:].decode("utf-8", "replace"))
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(os.getpgid(p.pid), signal.SIGKILL)
                except Exception:
                    pass
                p.wait(timeout=10)
                res = dict(scheme=scheme, target=target, ok=False,
                           error=f"外层超时 {timeout}s", wall_s=timeout, peak_rss_mb=None)
            with open(out_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(res, ensure_ascii=False) + "\n")
            print(f"{scheme:16s} {target:9s} ok={int(bool(res.get('ok')))} "
                  f"text={res.get('text_len')!s:>6} policy={int(bool(res.get('is_policy')))} "
                  f"rss={res.get('peak_rss_mb')!s:>7}MB pss={res.get('peak_pss_mb')!s:>7} "
                  f"procs={res.get('peak_procs')!s:>3} wall={res.get('wall_s')!s:>6}s "
                  f"{res.get('error') or res.get('note') or ''}", flush=True)
            time.sleep(2)      # 让内存回到基线再测下一个
    print(f"# 结果写入 {out_path}")


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="跑一个组合")
    r.add_argument("scheme")
    r.add_argument("target")
    m = sub.add_parser("matrix", help="跑一组组合")
    m.add_argument("--schemes", required=True)
    m.add_argument("--targets", default="doulor,lobehub,blizzard")
    m.add_argument("--out", default=os.path.expanduser("~/bench/results.jsonl"))
    m.add_argument("--timeout", type=int, default=180)
    a = ap.parse_args()
    if a.cmd == "run":
        return run_cli([a.scheme, a.target])
    matrix([s.strip() for s in a.schemes.split(",") if s.strip()],
           [t.strip() for t in a.targets.split(",") if t.strip()], a.out, a.timeout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
