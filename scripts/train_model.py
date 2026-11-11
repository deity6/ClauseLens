"""把 ToS;DR 人工标注映射到 ClauseLens 标签，训练句子级多标签分类器，并在按站点划分的 test 集上评测。

输入：data/processed/tosdr_points.jsonl、data/processed/split.json
输出：data/models/clause_model.pkl、data/processed/labeled_sentences.jsonl、eval/reports/sentence_eval.{json,md}

用法：python scripts/train_model.py
"""
from __future__ import annotations

import json
import pickle
import random
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.multiclass import OneVsRestClassifier
from sklearn.pipeline import FeatureUnion

from clauselens.detect import RULE_VETO_RATIO, fuse, rule_scores
from clauselens.taxonomy import TAGS
from clauselens.tosdr_map import CASE_TAGS

PROC = ROOT / "data" / "processed"
MODELS = ROOT / "data" / "models"
REPORTS = ROOT / "eval" / "reports"
SEED = 42



def map_case(case_id, title: str = "", classification: str = "") -> list[str]:
    """ToS;DR case → 本项目标签（人工审定表 backend/clauselens/tosdr_map.py）。"""
    try:
        return list(CASE_TAGS.get(int(case_id), []))
    except (TypeError, ValueError):
        return []


def load_points():
    rows = []
    with open(PROC / "tosdr_points.jsonl", encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            q = (r.get("quote_text") or "").strip()
            if len(q) < 15:
                continue
            rows.append(r)
    return rows


def prf(tp, fp, fn):
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return round(p, 3), round(r, 3), round(f, 3)


def evaluate(gold: list[set], pred: list[set], labels: list[str]) -> dict:
    per = {}
    TP = FP = FN = 0
    for lab in labels:
        tp = sum(1 for g, p in zip(gold, pred) if lab in g and lab in p)
        fp = sum(1 for g, p in zip(gold, pred) if lab not in g and lab in p)
        fn = sum(1 for g, p in zip(gold, pred) if lab in g and lab not in p)
        TP, FP, FN = TP + tp, FP + fp, FN + fn
        sup = tp + fn
        if sup or fp:
            per[lab] = dict(zip(("precision", "recall", "f1"), prf(tp, fp, fn))) | {"support": sup, "fp": fp}
    micro = dict(zip(("precision", "recall", "f1"), prf(TP, FP, FN)))
    f1s = [v["f1"] for v in per.values() if v["support"] > 0]
    macro = round(sum(f1s) / len(f1s), 3) if f1s else 0.0
    return {"micro": micro, "macro_f1": macro, "per_label": per}


def main():
    rows = load_points()
    split = json.loads((PROC / "split.json").read_text("utf-8"))
    test_dom = set(split["test"])

    data = []
    case_map_counter = Counter()
    for r in rows:
        labs = map_case(r.get("case_id"))
        for l in labs:
            case_map_counter[(r.get("case_id"), r.get("case_title"), l)] += 1
        key = r.get("domain") or str(r.get("service_id"))
        data.append({"text": r["quote_text"][:1500], "labels": labs, "domain": key,
                     "case_id": r.get("case_id"), "split": "test" if key in test_dom else "train"})

    # 去重（同一句同一标签集）
    seen, uniq = set(), []
    for d in data:
        k = (d["text"], d["domain"])
        if k in seen:
            continue
        seen.add(k)
        uniq.append(d)
    data = uniq

    with open(PROC / "labeled_sentences.jsonl", "w", encoding="utf-8", newline="\n") as f:
        for d in data:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")
    (PROC / "case_tag_map.json").write_text(json.dumps(
        [{"case_id": c, "case_title": t, "tag": l, "n": n} for (c, t, l), n in case_map_counter.most_common()],
        ensure_ascii=False, indent=1), "utf-8")

    train = [d for d in data if d["split"] == "train"]
    test = [d for d in data if d["split"] == "test"]
    labels = sorted({l for d in train for l in d["labels"]})
    lab_counts = Counter(l for d in train for l in d["labels"])
    labels = [l for l in labels if lab_counts[l] >= 8]
    print(f"sentences={len(data)} train={len(train)} test={len(test)} labels={len(labels)}")

    vec = FeatureUnion([
        ("w", TfidfVectorizer(ngram_range=(1, 2), min_df=2, max_features=60000, sublinear_tf=True)),
        ("c", TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=3, max_features=80000, sublinear_tf=True)),
    ])
    Xtr = vec.fit_transform([d["text"] for d in train])
    Ytr = np.array([[1 if l in d["labels"] else 0 for l in labels] for d in train])
    clf = OneVsRestClassifier(LogisticRegression(C=4.0, max_iter=2000, class_weight="balanced"), n_jobs=-1)
    clf.fit(Xtr, Ytr)

    # 阈值：在 train 内部用 5 折外的验证集挑，目标 precision 优先（F0.5）
    rng = random.Random(SEED)
    doms = sorted({d["domain"] for d in train})
    rng.shuffle(doms)
    val_dom = set(doms[: len(doms) // 5])
    sub_tr = [d for d in train if d["domain"] not in val_dom]
    sub_va = [d for d in train if d["domain"] in val_dom]
    clf_v = OneVsRestClassifier(LogisticRegression(C=4.0, max_iter=2000, class_weight="balanced"), n_jobs=-1)
    vec_v = vec  # 共享词表，避免重复拟合开销（词表来自 train，不含 test）
    clf_v.fit(vec_v.transform([d["text"] for d in sub_tr]),
              np.array([[1 if l in d["labels"] else 0 for l in labels] for d in sub_tr]))
    Pva = clf_v.predict_proba(vec_v.transform([d["text"] for d in sub_va]))
    thresholds = {}
    for j, l in enumerate(labels):
        y = np.array([1 if l in d["labels"] else 0 for d in sub_va])
        best, bt = -1, 0.5
        for th in np.arange(0.3, 0.96, 0.025):
            p = Pva[:, j] >= th
            tp = int((p & (y == 1)).sum()); fp = int((p & (y == 0)).sum()); fn = int((~p & (y == 1)).sum())
            pr = tp / (tp + fp) if tp + fp else 0; rc = tp / (tp + fn) if tp + fn else 0
            f05 = (1.25 * pr * rc / (0.25 * pr + rc)) if pr + rc else 0
            if f05 > best:
                best, bt = f05, float(th)
        thresholds[l] = round(bt, 3)

    MODELS.mkdir(parents=True, exist_ok=True)
    with open(MODELS / "clause_model.pkl", "wb") as f:
        pickle.dump({"vectorizer": vec, "classifier": clf, "labels": labels, "thresholds": thresholds}, f)

    # ── 评测（test 集站点从未参与训练/调阈值）
    Pte = clf.predict_proba(vec.transform([d["text"] for d in test]))
    gold = [set(d["labels"]) & set(labels) for d in test]
    gold_all = [set(d["labels"]) for d in test]
    pred_model = [{l for j, l in enumerate(labels) if Pte[i, j] >= thresholds[l]} for i in range(len(test))]
    pred_rule = [set(rule_scores(d["text"], False).keys()) for d in test]
    pred_fused = []
    for i, d in enumerate(test):
        pr = {l: float(Pte[i, j]) for j, l in enumerate(labels)}
        pred_fused.append(set(fuse(rule_scores(d["text"], False), pr, thresholds, RULE_VETO_RATIO["en"])) & set(labels))
    all_labels = sorted({l for g in gold_all for l in g} | set(labels))
    report = {
        "n_train": len(train), "n_test": len(test),
        "n_train_sites": len({d["domain"] for d in train}), "n_test_sites": len({d["domain"] for d in test}),
        "leak_check_overlap_sites": len({d["domain"] for d in train} & {d["domain"] for d in test}),
        "labels_trained": labels, "thresholds": thresholds,
        "rule": evaluate(gold_all, pred_rule, all_labels),
        "model": evaluate(gold, pred_model, labels),
        "fused": evaluate(gold, pred_fused, labels),
        "label_support_train": dict(lab_counts),
    }
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "sentence_eval.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), "utf-8")
    lines = ["# 句子级评测（ToS;DR 人工标注，按站点划分）", "",
             f"- train: {report['n_train']} 句 / {report['n_train_sites']} 站；test: {report['n_test']} 句 / {report['n_test_sites']} 站；站点重叠 {report['leak_check_overlap_sites']}",
             "", "| 方法 | micro P | micro R | micro F1 | macro F1 |", "|---|---|---|---|---|"]
    for k in ("rule", "model", "fused"):
        m = report[k]
        lines.append(f"| {k} | {m['micro']['precision']} | {m['micro']['recall']} | {m['micro']['f1']} | {m['macro_f1']} |")
    lines += ["", "## 每标签（fused）", "", "| 标签 | P | R | F1 | test 支持 | 误报 |", "|---|---|---|---|---|---|"]
    for l, v in sorted(report["fused"]["per_label"].items(), key=lambda x: -x[1]["support"]):
        lines.append(f"| {l} | {v['precision']} | {v['recall']} | {v['f1']} | {v['support']} | {v['fp']} |")
    lines += ["", "## 每标签（rule，仅规则层）", "", "| 标签 | P | R | F1 | test 支持 | 误报 |", "|---|---|---|---|---|---|"]
    for l, v in sorted(report["rule"]["per_label"].items(), key=lambda x: -x[1]["support"]):
        lines.append(f"| {l} | {v['precision']} | {v['recall']} | {v['f1']} | {v['support']} | {v['fp']} |")
    (REPORTS / "sentence_eval.md").write_text("\n".join(lines) + "\n", "utf-8")
    print("\n".join(lines[:12]))


if __name__ == "__main__":
    main()
