#!/usr/bin/env python3
"""pyppeteer 实测：本质是「Chromium + WebSocket 驱动」，看它还能不能跑、吃多少内存。

pyppeteer 自带的那份 Chromium 是 2021 年的，这里直接指向 Playwright 已装的 Chromium，
只测「驱动层是否还能驱动新版 Chromium」以及内存是否比 Playwright 低。
"""
from __future__ import annotations

import asyncio
import glob
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.expanduser("~/bench"), "bench"))
from proc_rss import Sampler        # noqa: E402

CHROME = sorted(glob.glob(os.path.expanduser(
    "~/.cache/ms-playwright/chromium-*/chrome-linux64/chrome")))[-1]
URL = sys.argv[1] if len(sys.argv) > 1 else "https://cloud.doulor.cn/privacy"

FLAGS = ["--disable-gpu", "--no-sandbox", "--single-process", "--disable-dev-shm-usage",
         "--js-flags=--max-old-space-size=96 --max-semi-space-size=2"]


async def main() -> None:
    from pyppeteer import launch
    smp = Sampler([], markers=("chrome", "node_render"))
    smp.start()
    browser = await launch(headless=True, executablePath=CHROME, args=FLAGS,
                           handleSIGINT=False, handleSIGTERM=False, handleSIGHUP=False)
    page = await browser.newPage()
    await page.setUserAgent(
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36")
    await page.goto(URL, {"waitUntil": "networkidle0", "timeout": 30000})
    html = await page.content()
    await browser.close()
    smp.stop()
    print(json.dumps({"ok": True, "html_bytes": len(html),
                      "peak_rss_mb": smp.peak_rss_mb, "procs": smp.peak_procs,
                      "top": [f"{c}:{b // 1048576}MB" for c, b in smp.peak_detail]}))


if __name__ == "__main__":
    asyncio.run(main())
