"""站点级评测：ClauseLens 等级 vs ToS;DR 社区人工等级。

- 输入 data/processed/tosdr_site_docs.jsonl（每站的条款全文）+ split.json
- calibrate：在 train 站点上网格搜索评分参数（base/k_bad/k_good），使等级与 ToS;DR 等级的平均绝对差最小，
  写入 data/models/score_params.json
- eval：在 test 站点上报告 等级完全一致率、±1 级一致率、Spearman 相关、混淆矩阵

用法：python scripts/eval_sites.py calibrate|eval|all
"""
from __future__ import annotations

import itertools
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from clauselens.detect import detect, split_sentences
from clauselens.score import DEFAULT, PARAMS_PATH, score

PROC = ROOT / "data" / "processed"
REPORTS = ROOT / "eval" / "reports"
G2N = {"A": 0, "B": 1, "C": 2, "D": 3, "E": 4}


def load(split_name: str):
    split = json.loads((PROC / "split.json").read_text("utf-8"))
    keep = set(split[split_name])
    out = []
    with open(PROC / "tosdr_site_docs.jsonl", encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            if r.get("rating") not in G2N:
                continue
            key = r.get("domain") or str(r.get("service_id"))
            if key not in keep:
                continue
            text_docs = [d for d in r.get("docs", []) if len(d.get("text", "")) > 500]
            if not text_docs:
                continue
            out.append((r, text_docs))
    return out


def site_hits(docs):
    sents = []
    for i, d in enumerate(docs):
        sents += split_sentences(f"d{i}", d["text"][:300000])
    return [(h.tag, h.confidence) for h in detect(sents)]


def spearman(a, b):
    def rank(x):
        order = sorted(range(len(x)), key=lambda i: x[i])
        r = [0.0] * len(x)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and x[order[j + 1]] == x[order[i]]:
                j += 1
            for k in range(i, j + 1):
                r[order[k]] = (i + j) / 2
            i = j + 1
        return r
    ra, rb = rank(a), rank(b)
    n = len(a)
    ma, mb = sum(ra) / n, sum(rb) / n
    cov = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    va = sum((x - ma) ** 2 for x in ra) ** .5
    vb = sum((y - mb) ** 2 for y in rb) ** .5
    return round(cov / (va * vb), 3) if va and vb else 0.0


def calibrate():
    sites = load("train")
    print("train sites with docs:", len(sites))
    cached = [(G2N[r["rating"]], site_hits(docs)) for r, docs in sites]
    best = None
    for base, kb, kg in itertools.product([60, 66, 72, 78, 84], [1.6, 2.4, 3.2, 4.0, 5.0], [0.8, 1.6, 2.4, 3.2]):
        p = {**DEFAULT, "base": base, "k_bad": kb, "k_good": kg}
        err = sum(abs(G2N[score(h, p)["grade"]] - g) for g, h in cached) / len(cached)
        if best is None or err < best[0]:
            best = (err, p)
    PARAMS_PATH.parent.mkdir(parents=True, exist_ok=True)
    PARAMS_PATH.write_text(json.dumps(best[1], indent=1), "utf-8")
    print("best MAE", round(best[0], 3), best[1])
    return best


def evaluate():
    sites = load("test")
    gold, pred, scores, rows = [], [], [], []
    for r, docs in sites:
        h = site_hits(docs)
        s = score(h)
        gold.append(G2N[r["rating"]]); pred.append(G2N[s["grade"]]); scores.append(-s["value"])
        rows.append({"domain": r.get("domain"), "tosdr": r["rating"], "ours": s["grade"], "score": s["value"], "n_tags": len(h)})
    n = len(gold)
    exact = sum(g == p for g, p in zip(gold, pred)) / n
    within1 = sum(abs(g - p) <= 1 for g, p in zip(gold, pred)) / n
    conf = Counter((g, p) for g, p in zip(gold, pred))
    rep = {"n_test_sites": n, "exact": round(exact, 3), "within_1": round(within1, 3),
           "spearman_score_vs_grade": spearman(scores, gold),
           "baseline_majority_exact": round(max(Counter(gold).values()) / n, 3),
           "confusion": {f"{'ABCDE'[g]}->{'ABCDE'[p]}": c for (g, p), c in sorted(conf.items())},
           "sites": rows}
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "site_eval.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1), "utf-8")
    md = ["# 站点级评测（我们的等级 vs ToS;DR 社区等级，test 站点）", "",
          f"- 站点数：{n}", f"- 等级完全一致：{rep['exact']}（多数类基线 {rep['baseline_majority_exact']}）",
          f"- 相差 ≤1 级：{rep['within_1']}", f"- Spearman（分数 vs 人工等级）：{rep['spearman_score_vs_grade']}", "",
          "## 混淆矩阵（行=ToS;DR，列=ClauseLens）", "", "| | A | B | C | D | E |", "|---|---|---|---|---|---|"]
    for g in range(5):
        md.append(f"| {'ABCDE'[g]} | " + " | ".join(str(conf.get((g, p), 0)) for p in range(5)) + " |")
    (REPORTS / "site_eval.md").write_text("\n".join(md) + "\n", "utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "eval"
    if cmd == "calibrate-legacy":
        calibrate()
    if cmd in ("eval", "all"):
        evaluate()
