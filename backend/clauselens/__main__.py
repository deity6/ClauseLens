"""命令行入口：查一个网站的条款。

    python -m clauselens baidu.com
    python -m clauselens https://www.baidu.com/duty/yinsiquan-policy.html
    python -m clauselens github.com --json > out.json

在 backend 目录下直接跑，或者从项目根跑 scripts/query.py（会自己加 sys.path）。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

from .pipeline import analyze
from .taxonomy import TAG_BY_ID

# ── 终端颜色（管道输出 / NO_COLOR 时自动关掉） ──────────────────────
_C = {"bad": "\033[31m", "blocker": "\033[1;31m", "good": "\033[32m",
      "neutral": "\033[90m", "dim": "\033[90m", "bold": "\033[1m",
      "warn": "\033[33m", "cyan": "\033[36m", "reset": "\033[0m"}


class _Paint:
    def __init__(self):
        self.on = sys.stdout.isatty() and not os.environ.get("NO_COLOR")

    def __call__(self, key: str, s: str) -> str:
        return f"{_C[key]}{s}{_C['reset']}" if self.on else s


paint = _Paint()

POLARITY_ZH = {"bad": "需要注意", "blocker": "需要注意", "good": "还不错", "neutral": "一般说明"}
POLARITY_MARK = {"bad": "✗", "blocker": "✗", "good": "✓", "neutral": "·"}
SOURCE_ZH = {"rule": "规则匹配", "model": "模型判断", "rule+model": "规则+模型", "tosdr": "社区标注"}


def _clip(s: str, n: int) -> str:
    s = " ".join((s or "").split())
    return s if len(s) <= n else s[: n - 1] + "…"


def _width(s: str) -> int:
    """按东亚宽度算显示长度（终端对齐用）。"""
    return sum(2 if "\u4e00" <= ch <= "\u9fff" or "\u3000" <= ch <= "\u303f" else 1 for ch in s)


def _pad(s: str, n: int) -> str:
    w = _width(s)
    return s if w >= n else s + " " * (n - w)


def render(res: dict) -> str:
    out: list[str] = []
    site, sc, stats = res["site"], res["score"], res["stats"]
    jur = res["jurisdiction"]
    out.append("")
    out.append(paint("bold", f"  {site.get('name') or site['domain']}") + paint("dim", f"   {site['domain']}"))
    out.append(f"  {jur['name_zh']} · {sc['grade']} 级 · {sc['value']} / 100   "
               + paint("dim", f"{len(res['documents'])} 份文档 · {stats['total_chars']:,} 字 · "
                              f"约 {stats['read_minutes']} 分钟读完"))
    if res.get("tosdr", {}).get("rating") if res.get("tosdr") else False:
        out.append(paint("dim", f"  ToS;DR 社区评级 {res['tosdr']['rating']}"))
    out.append("")

    out.append(paint("dim", "  文档"))
    for d in res["documents"]:
        out.append(f"    {d['id']:<4}{paint('cyan', '[' + {'privacy': '隐私政策', 'terms': '用户协议'}.get(d['type'], d['type']) + ']')}"
                   f" {_pad(_clip(d['title'], 30), 30)} {d['chars']:>7,} 字  {paint('dim', d.get('host', ''))}")

    if res["warnings"]:
        out.append("")
        for w in res["warnings"]:
            out.append(paint("warn", f"  ! {w['message_zh']}"))

    if res["tldr"]:
        out.append("")
        out.append(paint("bold", "  一句话总结"))
        for x in res["tldr"]:
            out.append(f"    {paint(x['polarity'], POLARITY_MARK[x['polarity']])} {x['text']}")

    groups: dict[str, list] = {}
    for t in res["tags"]:
        meta = TAG_BY_ID.get(t["id"])
        key = "待确认" if t.get("provisional") else POLARITY_ZH.get(meta.polarity if meta else "neutral", "一般说明")
        groups.setdefault(key, []).append(t)

    if tags := res["tags"]:
        out.append("")
        out.append(paint("bold", f"  标签 {len(tags)} 个")
                   + paint("dim", f"  其中 {sum(1 for t in tags if t.get('provisional'))} 个待确认" if any(t.get('provisional') for t in tags) else ""))
    for gname in ("需要注意", "待确认", "还不错", "一般说明"):
        items = groups.get(gname)
        if not items:
            continue
        out.append("")
        out.append(paint("dim", f"  {gname}（{len(items)}）"))
        for t in items:
            meta = TAG_BY_ID.get(t["id"])
            name = meta.name_zh if meta else t["id"]
            mark = "?" if t.get("provisional") else POLARITY_MARK.get(meta.polarity if meta else "neutral", "·")
            cls = "neutral" if t.get("provisional") else (meta.polarity if meta else "neutral")
            ev = (t["evidence"][0]["quote"] if t.get("evidence") else "")
            out.append(f"    {paint(cls, mark)} {_pad(_clip(name, 22), 22)} "
                       f"{paint('dim', f'{t['confidence'] * 100:>3.0f}%  ' + SOURCE_ZH.get(t['source'], t['source']))}"
                       f"  {paint('dim', _clip(ev, 52))}")

    out.append("")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    try:  # Windows 终端默认 GBK，中文会崩
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    ap = argparse.ArgumentParser(
        prog="clauselens", description="查一个网站的服务条款、隐私政策，给出等级、标签和原文证据。")
    ap.add_argument("target", help="域名或条款页面网址，例如 baidu.com")
    ap.add_argument("--json", action="store_true", help="输出完整 JSON（含原文全文），不再排版")
    ap.add_argument("--no-cache", action="store_true", help="绕过 24 小时缓存")
    ap.add_argument("-v", "--verbose", action="store_true", help="显示抓取过程中的每个阶段")
    args = ap.parse_args(argv)

    t0 = time.monotonic()
    res = None
    cached = False
    for ev, data in analyze(args.target, use_cache=not args.no_cache):
        if ev == "error":
            msg = data.get("message_zh") or data.get("code")
            print(paint("bad", f"\n  ✗ {msg}\n"), file=sys.stderr)
            return 2
        if data.get("cached") if isinstance(data, dict) else False:
            cached = True
        if ev == "result":
            res = data
        elif args.verbose and not args.json:
            if ev == "stage":
                info = " ".join(f"{k}={v}" for k, v in data.items() if k != "stage")
                print(paint("dim", f"  · {data.get('stage')}  {info}"), file=sys.stderr)
            elif ev == "document":
                print(paint("dim", f"  ✓ {data['title'][:34]}  {data['chars']} 字"), file=sys.stderr)
            elif ev == "tag":
                pass

    if not res:
        print("没有拿到结果", file=sys.stderr)
        return 1
    if args.json:
        json.dump(res, sys.stdout, ensure_ascii=False, indent=1)
        sys.stdout.write("\n")
    else:
        print(render(res))
        note = "（24 小时内的缓存结果，加 --no-cache 可重抓）" if cached else ""
        print(paint("dim", f"  用时 {time.monotonic() - t0:.1f}s{note}"))
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
