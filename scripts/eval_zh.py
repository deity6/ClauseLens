"""中文规则层评测。

A) CAPP-130（CC BY 4.0）主题级评测：把我们的细标签聚合到 CAPP 主题，按 App 划分 dev/test（seed=42，50/50）。
   只允许看 dev 集调中文正则；报告给出 test 集结果。
B) 细标签银标集 data/processed/zh_gold.jsonl（若存在）：{text, labels[], domain, split}，按标签报告 P/R/F1。

用法：python scripts/eval_zh.py [dev|test]
"""
from __future__ import annotations

import json
import random
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from clauselens.detect import rule_scores

PROC = ROOT / "data" / "processed"
REPORTS = ROOT / "eval" / "reports"

# CAPP 主题 → 能代表该主题的我们的标签（任一命中即视为该主题命中）
CAPP_MAP = {
    "共享、委托、转让、公开（披露）": {"data-sold-or-shared", "gov-disclosure", "not-sold", "cross-border-transfer"},
    "特殊人群": {"minors-protection"},
    "联系方式": {"contact-dpo"},
    "数据、权限管理": {"can-delete-data", "can-export-data", "easy-account-deletion", "hard-account-deletion"},
    "存储方式": {"indefinite-retention", "clear-retention", "cross-border-transfer"},
    "隐私政策的授权、修改与变更": {"terms-change-no-notice", "terms-change-notice", "default-consent"},
    "权限获取": {"collects-contacts-device", "collects-sensitive"},
}


def prf(tp, fp, fn):
    p = tp / (tp + fp) if tp + fp else 0
    r = tp / (tp + fn) if tp + fn else 0
    return round(p, 3), round(r, 3), round(2 * p * r / (p + r), 3) if p + r else 0


def capp(split_name: str):
    rows = [json.loads(l) for l in open(PROC / "capp130_sentences.jsonl", encoding="utf-8")]
    apps = sorted({r["app"] for r in rows})
    random.Random(42).shuffle(apps)
    dev = set(apps[: len(apps) // 2])
    rows = [r for r in rows if (r["app"] in dev) == (split_name == "dev")]
    out = {}
    for topic, tags in CAPP_MAP.items():
        tp = fp = fn = 0
        for r in rows:
            gold = topic in r["label"]
            pred = bool(set(rule_scores(r["text"], True)) & tags)
            tp += gold and pred; fp += (not gold) and pred; fn += gold and not pred
        p, rc, f = prf(tp, fp, fn)
        out[topic] = {"precision": p, "recall": rc, "f1": f, "support": tp + fn}
    return {"split": split_name, "n_apps": len({r['app'] for r in rows}), "n_sentences": len(rows), "topics": out}


def gold(split_name: str):
    p = PROC / "zh_gold.jsonl"
    if not p.exists():
        return None
    rows = [json.loads(l) for l in open(p, encoding="utf-8")]
    rows = [r for r in rows if r.get("split", "test") == split_name]
    labels = sorted({l for r in rows for l in r["labels"]})
    preds = [set(rule_scores(r["text"], True)) for r in rows]
    per, T = {}, [0, 0, 0]
    allp = sorted(labels | {l for s in preds for l in s} if isinstance(labels, set) else set(labels) | {l for s in preds for l in s})
    for lab in allp:
        tp = sum(1 for r, s in zip(rows, preds) if lab in r["labels"] and lab in s)
        fp = sum(1 for r, s in zip(rows, preds) if lab not in r["labels"] and lab in s)
        fn = sum(1 for r, s in zip(rows, preds) if lab in r["labels"] and lab not in s)
        T[0] += tp; T[1] += fp; T[2] += fn
        pr, rc, f = prf(tp, fp, fn)
        per[lab] = {"precision": pr, "recall": rc, "f1": f, "support": tp + fn, "fp": fp}
    mp, mr, mf = prf(*T)
    return {"split": split_name, "n": len(rows), "micro": {"precision": mp, "recall": mr, "f1": mf}, "per_label": per}


def main():
    sp = sys.argv[1] if len(sys.argv) > 1 else "test"
    rep = {"capp130": capp(sp), "zh_gold": gold(sp)}
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / f"zh_eval_{sp}.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1), "utf-8")
    md = [f"# 中文规则层评测（{sp}）", "", f"## A. CAPP-130 主题级（{rep['capp130']['n_apps']} 个 App，{rep['capp130']['n_sentences']} 句）", "",
          "| 主题 | P | R | F1 | 支持 |", "|---|---|---|---|---|"]
    for t, v in rep["capp130"]["topics"].items():
        md.append(f"| {t} | {v['precision']} | {v['recall']} | {v['f1']} | {v['support']} |")
    g = rep["zh_gold"]
    if g:
        md += ["", f"## B. 细标签银标集（{g['n']} 句）", "", f"micro P {g['micro']['precision']} / R {g['micro']['recall']} / F1 {g['micro']['f1']}", "",
               "| 标签 | P | R | F1 | 支持 | 误报 |", "|---|---|---|---|---|---|"]
        for l, v in sorted(g["per_label"].items(), key=lambda x: -x[1]["support"]):
            md.append(f"| {l} | {v['precision']} | {v['recall']} | {v['f1']} | {v['support']} | {v['fp']} |")
    (REPORTS / f"zh_eval_{sp}.md").write_text("\n".join(md) + "\n", "utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    main()
