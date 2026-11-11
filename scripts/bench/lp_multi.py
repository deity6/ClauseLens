#!/usr/bin/env python3
"""「一次分析渲染 3 页」的两种接入方式对比（对齐 render.Renderer 的实际用法）。

  A. 每页一个 lightpanda fetch 子进程（无服务、无状态，进程退出即归还内存）
  B. 一个 lightpanda serve + Playwright connect_over_cdp，三页复用

输出每页耗时、总耗时、进程树 RSS 峰值、正文长度。
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time

BENCH = os.path.dirname(os.path.abspath(__file__))
PROJ = os.environ.get("CLAUSELENS_HOME", os.path.expanduser("~/clauselens"))
sys.path.insert(0, os.path.join(PROJ, "backend"))
sys.path.insert(0, BENCH)

from clauselens import discover                     # noqa: E402
from proc_rss import Sampler, child_pids            # noqa: E402

LP = os.path.expanduser("~/bench/lp/lightpanda")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36")

PAGES = ["https://cloud.doulor.cn/privacy",
         "https://cloud.doulor.cn/terms",
         "https://ow.blizzard.cn/"]

WAIT = ["--wait-until", "networkidle", "--wait-ms", "8000", "--terminate-ms", "25000",
        "--load-resources", "stylesheet"]


def text_of(html: str) -> tuple[int, bool]:
    try:
        _t, text = discover.extract_text(html)
        return len(text), bool(discover.looks_like_policy(text))
    except Exception:
        return 0, False


def mode_a() -> dict:
    smp = Sampler([], markers=("lightpanda",))
    smp.start()
    pages = []
    t_all = time.time()
    for url in PAGES:
        t0 = time.time()
        p = subprocess.run([LP, "fetch", "--json", "--dump", "html", url,
                            "--user-agent", UA] + WAIT,
                           capture_output=True, timeout=120)
        try:
            obj = json.loads(p.stdout.decode("utf-8", "replace"))
            html = obj.get("content") or obj.get("html") or ""
            status = obj.get("http_status")
        except Exception:
            html, status = "", None
        n, ok = text_of(html)
        pages.append(dict(url=url, sec=round(time.time() - t0, 2), chars=n, policy=ok, status=status))
    smp.stop()
    return dict(mode="A: 3× lightpanda fetch", pages=pages,
                total_s=round(time.time() - t_all, 2), peak_rss_mb=smp.peak_rss_mb,
                peak_pss_mb=smp.peak_pss_mb, peak_procs=smp.peak_procs)


def mode_b() -> dict:
    from playwright.sync_api import sync_playwright

    port = 9444
    lp = subprocess.Popen([LP, "serve", "--host", "127.0.0.1", "--port", str(port)],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    smp = Sampler(lambda: [lp.pid] + child_pids(("lightpanda", "playwright/driver")))
    smp.start()
    pages = []
    t_all = time.time()
    try:
        import urllib.request
        for _ in range(50):
            time.sleep(0.2)
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=1)
                break
            except Exception:
                pass
        with sync_playwright() as pw:
            browser = pw.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
            ctx = browser.new_context(user_agent=UA)
            for url in PAGES:
                t0 = time.time()
                page = ctx.new_page()
                try:
                    r = page.goto(url, wait_until="load", timeout=30000)
                    try:
                        page.wait_for_load_state("networkidle", timeout=8000)
                    except Exception:
                        pass
                    page.wait_for_timeout(500)
                    html = page.content()
                    status = getattr(r, "status", None)
                except Exception as e:
                    html, status = "", f"ERR {type(e).__name__}"
                n, ok = text_of(html)
                pages.append(dict(url=url, sec=round(time.time() - t0, 2), chars=n,
                                  policy=ok, status=status))
                try:
                    page.close()
                except Exception:
                    pass
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
    return dict(mode="B: lightpanda serve + CDP 复用", pages=pages,
                total_s=round(time.time() - t_all, 2), peak_rss_mb=smp.peak_rss_mb,
                peak_pss_mb=smp.peak_pss_mb, peak_procs=smp.peak_procs)


if __name__ == "__main__":
    print(json.dumps(mode_a(), ensure_ascii=False))
    time.sleep(2)
    print(json.dumps(mode_b(), ensure_ascii=False))
