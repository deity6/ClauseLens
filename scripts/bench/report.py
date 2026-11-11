#!/usr/bin/env python3
"""把 bench.py 产出的 jsonl 汇总成 markdown 表（报告里直接用）。

用法：python report.py ~/bench/results_*.jsonl
"""
from __future__ import annotations

import json
import sys


def main(paths: list[str]) -> None:
    rows: list[dict] = []
    for p in paths:
        try:
            with open(p, encoding="utf-8") as f:
                rows += [json.loads(line) for line in f if line.strip()]
        except FileNotFoundError:
            print(f"# 缺文件 {p}")
    order = ["doulor", "lobehub", "blizzard"]
    rows.sort(key=lambda r: (r.get("scheme", ""), order.index(r["target"])
                             if r.get("target") in order else 9))
    print("| 方案 | 站 | 渲染后正文 | 像条款 | 进程树 RSS 峰值 | PSS | 峰值 swap | 当时可用内存 | 进程数 | 单页耗时 | 备注 |")
    print("|---|---|---|---|---|---|---|---|---|---|---|")
    for r in rows:
        err = r.get("error") or ""
        note = (err or r.get("note") or r.get("stderr") or "").replace("\n", " ")[:60]
        rss = r.get("peak_rss_mb")
        print(f"| `{r.get('scheme')}` | {r.get('target')} | {r.get('text_len')} 字 | "
              f"{'是' if r.get('is_policy') else '否'} | "
              f"{rss if rss is not None else '—'} MB | {r.get('peak_pss_mb')} MB | "
              f"{r.get('peak_swap_mb')} MB | {r.get('min_avail_mb')} MB | "
              f"{r.get('peak_procs')} | {r.get('wall_s')} s | {note} |")
    print()
    print("## 链接面（找条款页用）")
    for r in rows:
        print(f"- `{r.get('scheme')}` @ {r.get('target')}: links={r.get('n_links')} "
              f"policy={r.get('policy_links')}")


if __name__ == "__main__":
    main(sys.argv[1:])
