"""评分标定（只用 train 站点）。

1. 对每个站点跑识别，缓存 {domain: [(tag, conf)]} 到 data/cache/site_hits_{split}.json
2. 用岭回归在 train 站点上拟合 每个标签的权重（目标：ToS;DR 等级 A=0..E=4），系数做收缩并与人工先验权重混合
3. 在 train 上搜索原始分的 4 个切点，使等级完全一致率最高；再给出原始分 → 0–100 展示分的分段线性映射，
   使切点对应 85/70/55/40
输出 data/models/score_params.json（score.py 读取）

用法：python scripts/calibrate_score.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))

import numpy as np
from sklearn.linear_model import Ridge

from clauselens.score import PARAMS_PATH
from clauselens.taxonomy import TAGS, TAG_BY_ID

CACHE = ROOT / "data" / "cache"
G2N = {"A": 0, "B": 1, "C": 2, "D": 3, "E": 4}


def site_hits(split: str):
    p = CACHE / f"site_hits_{split}.json"
    if p.exists():
        return json.loads(p.read_text("utf-8"))
    from eval_sites import load, site_hits as sh
    out = {}
    for r, docs in load(split):
        out[r.get("domain") or str(r["service_id"])] = {"rating": r["rating"], "hits": sh(docs)}
    CACHE.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out), "utf-8")
    return out


def features(hits):
    x = np.zeros(len(TAGS))
    idx = {t.id: i for i, t in enumerate(TAGS)}
    for tid, conf in hits:
        if tid in idx:
            x[idx[tid]] = max(x[idx[tid]], conf)
    return x


def main():
    tr = site_hits("train")
    X = np.array([features(v["hits"]) for v in tr.values()])
    y = np.array([G2N[v["rating"]] for v in tr.values()], dtype=float)

    # 先验：好标签 -w，坏标签 +w（正值 = 更差）
    prior = np.array([(-t.weight if t.polarity == "good" else (t.weight if t.polarity in ("bad", "blocker") else t.weight * 0.2)) for t in TAGS])
    reg = Ridge(alpha=8.0).fit(X, y)
    coef = reg.coef_
    # 方向约束：学习到的方向与先验相反时置 0（不让数据把"好"学成"坏"）；再与先验混合
    scale = np.abs(coef).sum() / max(1e-9, np.abs(prior).sum())
    learned = np.where(np.sign(coef) == np.sign(prior), coef, 0.0)
    mix = 0.6 * learned + 0.4 * prior * scale
    penalty = {t.id: round(float(mix[i]), 4) for i, t in enumerate(TAGS)}

    raw = X @ mix  # 越大越差
    # 切点搜索：在分位点上枚举
    qs = np.quantile(raw, np.linspace(0.01, 0.99, 99))
    best = (-1, None)
    cands = sorted(set(np.round(qs, 4)))
    for i, c1 in enumerate(cands):
        for c2 in cands[i + 1::2]:
            for c3 in [c for c in cands if c > c2][::2]:
                for c4 in [c for c in cands if c > c3][::3]:
                    pred = np.digitize(raw, [c1, c2, c3, c4])
                    acc = float((pred == y).mean()) + 0.25 * float((np.abs(pred - y) <= 1).mean())
                    if acc > best[0]:
                        best = (acc, [float(c1), float(c2), float(c3), float(c4)])
    cuts = best[1]
    pred = np.digitize(raw, cuts)
    print("train exact", round(float((pred == y).mean()), 3), "within1", round(float((np.abs(pred - y) <= 1).mean()), 3))

    # 展示分映射：raw 越小越好。锚点 raw_min→100, cut1→85, cut2→70, cut3→55, cut4→40, raw_max→5
    lo, hi = float(np.quantile(raw, 0.005)), float(np.quantile(raw, 0.995))
    anchors_raw = [min(lo, cuts[0] - 1e-3)] + cuts + [max(hi, cuts[3] + 1e-3)]
    anchors_disp = [100, 85, 70, 55, 40, 5]
    params = {"mode": "learned", "penalty": penalty, "intercept": 0.0,
              "anchors_raw": anchors_raw, "anchors_disp": anchors_disp,
              "fit": {"n_train_sites": int(len(y)), "train_exact": round(float((pred == y).mean()), 3)}}
    PARAMS_PATH.parent.mkdir(parents=True, exist_ok=True)
    PARAMS_PATH.write_text(json.dumps(params, indent=1), "utf-8")
    top = sorted(penalty.items(), key=lambda x: -abs(x[1]))[:12]
    print("top penalties:", top)


if __name__ == "__main__":
    main()
