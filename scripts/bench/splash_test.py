#!/usr/bin/env python3
"""Splash（scrapy 生态的渲染服务）实测：render.html 直接返回执行完 JS 的 HTML。

容器常驻，所以内存读 cgroup v2 的 memory.peak（容器生命周期内的高水位）。
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.expanduser("~/clauselens/backend"))
from clauselens import discover      # noqa: E402

IMG = "scrapinghub/splash"
NAME = "splash-bench"
PORT = 8050
URLS = ["https://cloud.doulor.cn/privacy", "https://lobehub.com/privacy",
        "https://ow.blizzard.cn/"]


def sh(*args: str, **kw) -> subprocess.CompletedProcess:
    return subprocess.run(["sudo", "docker", *args], capture_output=True, text=True, **kw)


def peak_mb(pid: int) -> float:
    try:
        with open(f"/proc/{pid}/cgroup") as f:
            scope = [p for p in f.read().split(":")[-1].strip().split("\n") if p][0]
        with open(f"/sys/fs/cgroup{scope}/memory.peak") as f:
            return round(int(f.read()) / 1048576, 1)
    except Exception:
        return -1.0


def main() -> None:
    sh("rm", "-f", NAME)
    start = sh("run", "-d", "--name", NAME, "-p", f"127.0.0.1:{PORT}:8050",
               "--memory", "600m", IMG, "--max-timeout", "60")
    if start.returncode != 0:
        print("启动失败:", start.stderr[-300:])
        return
    pid = int(sh("inspect", "-f", "{{.State.Pid}}", NAME).stdout.strip())
    t0 = time.time()
    for _ in range(120):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{PORT}/_ping", timeout=1).read()
            break
        except Exception:
            time.sleep(0.5)
    print(f"# 启动耗时 {time.time() - t0:.1f}s")
    rows = []
    for url in URLS:
        q = urllib.parse.urlencode({"url": url, "wait": "6.0", "timeout": "45"})
        t = time.time()
        try:
            html = urllib.request.urlopen(
                f"http://127.0.0.1:{PORT}/render.html?{q}", timeout=90).read().decode("utf-8", "replace")
        except Exception as e:
            rows.append(dict(url=url, error=f"{type(e).__name__}: {e}"))
            continue
        title, text = discover.extract_text(html)
        rows.append(dict(url=url, sec=round(time.time() - t, 1), html_bytes=len(html),
                         chars=len(text), policy=bool(discover.looks_like_policy(text)),
                         title=title[:60], peak_mb=peak_mb(pid)))
        print(json.dumps(rows[-1], ensure_ascii=False))
    print("PEAK_MB=", peak_mb(pid))
    sh("rm", "-f", NAME)


if __name__ == "__main__":
    main()
