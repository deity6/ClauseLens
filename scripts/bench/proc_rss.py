"""进程树内存采样器：按 /proc/<pid>/statm 累加**所有相关进程**。

上一轮的教训：只测主进程 RSS 会把 Chromium 低估 3–5 倍（renderer / gpu / zygote 都在外面）。
所以这里做两件事：

1. 从给定的 root pid 出发，沿 /proc/<pid>/stat 的 ppid 做闭包，把整棵树的 RSS 加起来；
2. 额外用 cmdline 子串兜底——父进程先退出时子树会被 reparent 到 1，光靠 ppid 跟丢。

同时记录 PSS（/proc/<pid>/smaps_rollup）和系统 MemAvailable 最低值：RSS 会重复计算共享库，
PSS 更接近真实占用；MemAvailable 说明这台 908 MB 的机器当时还剩多少。
"""
from __future__ import annotations

import os
import threading
import time

PAGE = os.sysconf("SC_PAGE_SIZE")


def _read(path: str) -> bytes:
    try:
        with open(path, "rb") as f:
            return f.read()
    except OSError:
        return b""


def _table() -> dict[int, tuple[int, int]]:
    """{pid: (ppid, rss_bytes)}"""
    out: dict[int, tuple[int, int]] = {}
    for name in os.listdir("/proc"):
        if not name.isdigit():
            continue
        pid = int(name)
        stat = _read(f"/proc/{pid}/stat")
        if not stat:
            continue
        r = stat.rfind(b")")
        if r < 0:
            continue
        tail = stat[r + 2:].split()
        try:
            ppid = int(tail[1])
        except (IndexError, ValueError):
            continue
        statm = _read(f"/proc/{pid}/statm").split()
        rss = 0
        if len(statm) > 1:
            try:
                rss = int(statm[1]) * PAGE
            except ValueError:
                rss = 0
        out[pid] = (ppid, rss)
    return out


def cmdline(pid: int) -> str:
    return _read(f"/proc/{pid}/cmdline").replace(b"\x00", b" ").decode("utf-8", "replace")


def _extra(pid: int) -> tuple[int, int]:
    """(VmSwap bytes, PSS bytes)"""
    swap = 0
    for line in _read(f"/proc/{pid}/status").splitlines():
        if line.startswith(b"VmSwap:"):
            try:
                swap = int(line.split()[1]) * 1024
            except (IndexError, ValueError):
                pass
            break
    pss = 0
    for line in _read(f"/proc/{pid}/smaps_rollup").splitlines():
        if line.startswith(b"Pss:"):
            try:
                pss = int(line.split()[1]) * 1024
            except (IndexError, ValueError):
                pass
            break
    return swap, pss


def mem_available_mb() -> float:
    for line in _read("/proc/meminfo").splitlines():
        if line.startswith(b"MemAvailable:"):
            return int(line.split()[1]) / 1024.0
    return -1.0


def _closure(roots: list[int], table: dict[int, tuple[int, int]]) -> set[int]:
    kids: dict[int, list[int]] = {}
    for pid, (ppid, _) in table.items():
        kids.setdefault(ppid, []).append(pid)
    seen: set[int] = set()
    stack = [p for p in roots if p in table]
    while stack:
        pid = stack.pop()
        if pid in seen:
            continue
        seen.add(pid)
        stack.extend(kids.get(pid, ()))
    return seen


class Sampler(threading.Thread):
    """后台采样：持续记录进程树 RSS 峰值。

    roots: 可调用对象，返回 root pid 列表（进程可能晚一点才出现，所以每次采样都重新问）
    markers: cmdline 子串，兜住被 reparent 的孤儿进程
    """

    def __init__(self, roots, markers=(), interval: float = 0.08):
        super().__init__(daemon=True)
        self._roots = roots if callable(roots) else (lambda: list(roots))
        self.markers = tuple(markers)
        self.interval = interval
        self.peak_rss = 0
        self.peak_procs = 0
        self.peak_swap = 0
        self.peak_pss = 0
        self.min_avail = mem_available_mb()
        self.timeline: list[tuple[float, int, int]] = []   # (t, rss_mb, n)
        self._pids: set[int] = set()
        self._stop = threading.Event()
        self._t0 = time.time()

    # ---- 一次采样 ----
    def _tick(self, deep: bool) -> None:
        table = _table()
        pids = _closure(self._roots(), table)
        if self.markers:
            for pid in table:
                if pid in pids:
                    continue
                cmd = cmdline(pid)
                if cmd and any(m in cmd for m in self.markers):
                    pids.add(pid)
        if not pids:
            return
        self._pids |= pids
        rss = sum(table[p][1] for p in pids if p in table)
        if rss > self.peak_rss:
            self.peak_rss = rss
        if len(pids) > self.peak_procs:
            self.peak_procs = len(pids)
        self.timeline.append((time.time() - self._t0, rss // 1048576, len(pids)))
        self.min_avail = min(self.min_avail, mem_available_mb())
        if deep:                      # smaps_rollup / VmSwap 比较贵，低频做
            swap = pss = 0
            for pid in pids:
                s, p = _extra(pid)
                swap += s
                pss += p
            self.peak_swap = max(self.peak_swap, swap)
            self.peak_pss = max(self.peak_pss, pss)

    def run(self) -> None:
        i = 0
        while not self._stop.is_set():
            try:
                self._tick(deep=(i % 6 == 0))
            except Exception:
                pass
            i += 1
            self._stop.wait(self.interval)

    # ---- 对外 ----
    def stop(self) -> "Sampler":
        self._stop.set()
        self.join(timeout=2)
        return self

    @property
    def peak_rss_mb(self) -> float:
        return round(self.peak_rss / 1048576, 1)

    @property
    def peak_pss_mb(self) -> float:
        return round(self.peak_pss / 1048576, 1)

    @property
    def peak_swap_mb(self) -> float:
        return round(self.peak_swap / 1048576, 1)


def child_pids(markers) -> list[int]:
    """从本进程的子树里挑出 cmdline 命中 marker 的进程（采样 root 用）。"""
    me = os.getpid()
    table = _table()
    pids = _closure([me], table)
    out = []
    for pid in pids:
        if pid == me:
            continue
        cmd = cmdline(pid)
        if cmd and any(m in cmd for m in markers):
            out.append(pid)
    return out
