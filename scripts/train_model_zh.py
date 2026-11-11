"""训练中文句子级分类器（字符 n-gram TF-IDF + LR）。

训练数据：data/processed/zh_train_*.jsonl（2000 句，仅来自 zh_split dev 站点）+ zh_gold_dev.jsonl（阈值调参用）
测试：zh_gold_test.jsonl（30 个从未参与训练/调参的站点）
输出：data/models/clause_model_zh.pkl、eval/reports/zh_model_eval.{json,md}
"""
from __future__ import annotations

import glob
import json
import pickle
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.multiclass import OneVsRestClassifier

from clauselens.detect import RULE_VETO_RATIO, fuse, rule_scores

PROC = ROOT / "data" / "processed"
MODELS = ROOT / "data" / "models"
REPORTS = ROOT / "eval" / "reports"


def load(pattern):
    rows = []
    for p in sorted(glob.glob(str(PROC / pattern))):
        rows += [json.loads(l) for l in open(p, encoding="utf-8")]
    return rows


def prf(tp, fp, fn):
    p = tp / (tp + fp) if tp + fp else 0
    r = tp / (tp + fn) if tp + fn else 0
    return round(p, 3), round(r, 3), round(2 * p * r / (p + r), 3) if p + r else 0


def score_sets(gold, pred):
    T = [0, 0, 0]
    labs = sorted({l for g in gold for l in g} | {l for p in pred for l in p})
    per = {}
    for l in labs:
        tp = sum(1 for g, p in zip(gold, pred) if l in g and l in p)
        fp = sum(1 for g, p in zip(gold, pred) if l not in g and l in p)
        fn = sum(1 for g, p in zip(gold, pred) if l in g and l not in p)
        T[0] += tp; T[1] += fp; T[2] += fn
        per[l] = dict(zip(("precision", "recall", "f1"), prf(tp, fp, fn))) | {"support": tp + fn, "fp": fp}
    return dict(zip(("precision", "recall", "f1"), prf(*T))), per


def main():
    train = load("zh_train_[0-9].jsonl")
    dev = load("zh_gold_dev.jsonl")
    test = load("zh_gold_test.jsonl")
    split = json.loads((PROC / "zh_split.json").read_text("utf-8"))
    test_dom = set(split["test"])
    assert not ({r["domain"] for r in train + dev} & test_dom), "泄漏：训练/开发集含测试站点"
    # 去泄漏：①与训练/开发句完全相同的测试句 ②测试站点与训练站点共用同一份文档（同集团共享条款）
    seen = {r["text"] for r in train + dev}
    shared = set()
    by_sha: dict[str, set] = {}
    for line in open(PROC / "cn_docs.jsonl", encoding="utf-8"):
        d = json.loads(line)
        by_sha.setdefault(d["sha1"], set()).add(d["domain"])
    tr_dom = {r["domain"] for r in train + dev}
    for doms in by_sha.values():
        if doms & test_dom and doms & tr_dom:
            shared |= doms & test_dom
    n0 = len(test)
    test = [r for r in test if r["text"] not in seen and r["domain"] not in shared]
    print(f"test 去泄漏：{n0} → {len(test)}（剔除共享文档站点 {sorted(shared)}）")
    cnt = Counter(l for r in train for l in r["labels"])
    labels = sorted(l for l, c in cnt.items() if c >= 6)
    print("train", len(train), "dev", len(dev), "test", len(test), "labels", len(labels))

    vec = TfidfVectorizer(analyzer="char", ngram_range=(1, 3), min_df=2, max_features=80000, sublinear_tf=True)
    X = vec.fit_transform([r["text"] for r in train])
    Y = np.array([[1 if l in r["labels"] else 0 for l in labels] for r in train])
    clf = OneVsRestClassifier(LogisticRegression(C=6.0, max_iter=3000, class_weight="balanced"))
    clf.fit(X, Y)

    Pd = clf.predict_proba(vec.transform([r["text"] for r in dev]))
    th = {}
    for j, l in enumerate(labels):
        y = np.array([1 if l in r["labels"] else 0 for r in dev])
        best, bt = -1, 0.6
        for t in np.arange(0.3, 0.96, 0.05):
            p = Pd[:, j] >= t
            tp = int((p & (y == 1)).sum()); fp = int((p & (y == 0)).sum()); fn = int((~p & (y == 1)).sum())
            pr = tp / (tp + fp) if tp + fp else 0; rc = tp / (tp + fn) if tp + fn else 0
            f05 = 1.25 * pr * rc / (0.25 * pr + rc) if pr + rc else 0
            if f05 > best:
                best, bt = f05, float(t)
        th[l] = round(max(bt, 0.45), 3)

    MODELS.mkdir(parents=True, exist_ok=True)
    with open(MODELS / "clause_model_zh.pkl", "wb") as f:
        pickle.dump({"vectorizer": vec, "classifier": clf, "labels": labels, "thresholds": th}, f)

    Pt = clf.predict_proba(vec.transform([r["text"] for r in test]))
    gold = [set(r["labels"]) for r in test]
    rule = [rule_scores(r["text"], True) for r in test]
    model = [{l for j, l in enumerate(labels) if Pt[i, j] >= th[l]} for i in range(len(test))]
    fused = []
    for i, r in enumerate(test):
        pr = {l: float(Pt[i, j]) for j, l in enumerate(labels)}
        fused.append(set(fuse(rule[i], pr, th, RULE_VETO_RATIO["zh"])))
    rep = {}
    for name, pred in (("rule", [set(x) for x in rule]), ("model", model), ("fused", fused)):
        m, per = score_sets(gold, pred)
        rep[name] = {"micro": m, "per_label": per}
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "zh_model_eval.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1), "utf-8")
    md = [f"# 中文细标签评测（test：{len({r['domain'] for r in test})} 个独立站点、{len(test)} 句人工标注，已去泄漏）", "",
          f"训练 {len(train)} 句 / 阈值调参 {len(dev)} 句（均来自 dev 站点）", "",
          "| 方法 | P | R | F1 |", "|---|---|---|---|"]
    for k in ("rule", "model", "fused"):
        m = rep[k]["micro"]
        md.append(f"| {k} | {m['precision']} | {m['recall']} | {m['f1']} |")
    md += ["", "## fused 每标签", "", "| 标签 | P | R | F1 | 支持 | 误报 |", "|---|---|---|---|---|---|"]
    for l, v in sorted(rep["fused"]["per_label"].items(), key=lambda x: -x[1]["support"]):
        md.append(f"| {l} | {v['precision']} | {v['recall']} | {v['f1']} | {v['support']} | {v['fp']} |")
    (REPORTS / "zh_model_eval.md").write_text("\n".join(md) + "\n", "utf-8")
    print("\n".join(md[:9]))


if __name__ == "__main__":
    main()
