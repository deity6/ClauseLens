#!/usr/bin/env python3
"""对比两种渲染方式产出的正文（质量而不只是长度）。

用法：python compare_text.py <url> [--save 前缀]
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

from clauselens import discover           # noqa: E402
from clauselens.net import UA             # noqa: E402

LP = os.path.expanduser("~/bench/lp/lightpanda")


def lp_html(url: str) -> tuple[str, float]:
    """Lightpanda：注意它**拒绝任何含 Mozilla 的 UA**（err=Reserved），默认发 Lightpanda/1.0。"""
    t0 = time.time()
    p = subprocess.run([LP, "fetch", "--json", "--dump", "html", url,
                        "--wait-until", "networkidle", "--wait-ms", "8000",
                        "--load-resources", "stylesheet",
                        "--terminate-ms", "25000"],
                       capture_output=True, timeout=120)
    if p.returncode != 0:
        print("LP STDERR:", p.stderr.decode("utf-8", "replace")[-600:])
    obj = json.loads(p.stdout.decode("utf-8", "replace") or "{}")
    return (obj.get("content") or obj.get("html") or ""), time.time() - t0


def pw_html(url: str) -> tuple[str, float]:
    from playwright.sync_api import sync_playwright
    t0 = time.time()
    with sync_playwright() as pw:
        b = pw.chromium.launch(headless=True, args=["--single-process", "--no-sandbox",
                                                    "--disable-gpu", "--disable-dev-shm-usage"])
        ctx = b.new_context(user_agent=UA, locale="zh-CN",
                            viewport={"width": 1440, "height": 1000})
        page = ctx.new_page()
        page.route("**/*", lambda r: r.abort()
                   if r.request.resource_type in ("image", "media", "font") else r.continue_())
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        try:
            page.wait_for_load_state("networkidle", timeout=4000)
        except Exception:
            pass
        page.wait_for_timeout(300)
        html = page.content()
        b.close()
    return html, time.time() - t0


def show(tag: str, html: str, sec: float, prefix: str) -> None:
    title, text = discover.extract_text(html)
    print(f"\n===== {tag}  {sec:.2f}s  html={len(html)}B  title={title!r}  text={len(text)}字 "
          f"policy={discover.looks_like_policy(text)}")
    lines = text.splitlines()
    print(f"  行数={len(lines)} 唯一行={len(set(lines))}")
    print("  ---- 前 500 字 ----")
    print("  " + text[:500].replace("\n", "\n  "))
    with open(f"{prefix}.{tag}.txt", "w", encoding="utf-8") as f:
        f.write(text)
    with open(f"{prefix}.{tag}.html", "w", encoding="utf-8") as f:
        f.write(html)


if __name__ == "__main__":
    url = sys.argv[1]
    prefix = sys.argv[3] if len(sys.argv) > 3 else "/tmp/cmp"
    h, s = lp_html(url)
    show("lightpanda", h, s, prefix)
    h, s = pw_html(url)
    show("chromium", h, s, prefix)
