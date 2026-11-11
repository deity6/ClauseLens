#!/usr/bin/env python3
"""`pip install lightpanda` 的 Python SDK 实测（最省事的接入方式）。

用 venv-lp 跑：~/bench/venv-lp/bin/python lp_sdk_test.py
"""
from __future__ import annotations

import json
import os
import sys
import time

sys.path.insert(0, os.path.expanduser("~/bench/bench"))
sys.path.insert(0, os.path.expanduser("~/clauselens/backend"))

from clauselens import discover     # noqa: E402
from proc_rss import Sampler        # noqa: E402

from lightpanda import Browser      # noqa: E402

URLS = ["https://cloud.doulor.cn/privacy", "https://lobehub.com/privacy",
        "https://ow.blizzard.cn/"]

ARGS = ["--locale", "zh-CN", "--load-resources", "stylesheet"]


def main() -> None:
    smp = Sampler([], markers=("lightpanda",))
    smp.start()
    t0 = time.time()
    browser = Browser(args=ARGS)
    boot = time.time() - t0
    rows = [dict(boot_s=round(boot, 2))]
    for url in URLS:
        t = time.time()
        s = browser.new_session()
        try:
            r = s.goto(url=url, wait_until="networkidle", timeout=25000)
            html = s.html()
        except Exception as e:
            rows.append(dict(url=url, error=f"{type(e).__name__}: {e}"[:200]))
            continue
        finally:
            try:
                s.close()
            except Exception:
                pass
        title, text = discover.extract_text(html or "")
        rows.append(dict(url=url, sec=round(time.time() - t, 2), status=getattr(r, "http_status", None),
                         html_bytes=len(html or ""), chars=len(text),
                         policy=bool(discover.looks_like_policy(text)), title=title[:50]))
    browser.close()
    smp.stop()
    rows.append(dict(peak_rss_mb=smp.peak_rss_mb, peak_pss_mb=smp.peak_pss_mb,
                     procs=smp.peak_procs,
                     top=[f"{c}:{b // 1048576}MB" for c, b in smp.peak_detail]))
    for r in rows:
        print(json.dumps(r, ensure_ascii=False))


if __name__ == "__main__":
    main()