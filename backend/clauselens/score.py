"""评分模型。

每个维度从基线分出发：坏标签扣 weight*confidence*k_bad，好标签加 weight*confidence*k_good。
总分 = 各维度平均（权重见 DIM_WEIGHTS）。参数可由 scripts/calibrate_score.py 依据 train 集上的
ToS;DR 人工等级标定后写入 data/models/score_params.json。
"""
from __future__ import annotations

import json
from pathlib import Path

from .taxonomy import DIMENSIONS, TAG_BY_ID, grade_for

PARAMS_PATH = Path(__file__).resolve().parents[2] / "data" / "models" / "score_params.json"

# 2026-11-12 重做（用户反馈「全是低分，六维封顶 72，总分没见过 70 以上」）：
#   base 72 → 82：没找到问题不等于有问题。以前「零标签」直接落到 72，再经 learn 模型
#     插值成 65 分（C 级），一个 ToS;DR 评 A 的站被我们判成「中等偏下」。
#   k_bad 3.2 → 2.0：负面标签的累积效应太强，四份文档命中十几条就掉到 20 分以下。
#   k_good 1.6 → 2.8：正面标签原来只能拉回负面的一半，明明有「可以删除数据」「不卖数据」
#     这类条款也体现不出差距——结果所有站挤在中低分段，失去了「区分」的意义。
DEFAULT = {"base": 82.0, "k_bad": 2.0, "k_good": 2.8, "neutral": 0.4,
           "dim_weights": {"privacy": 1.2, "sharing": 1.2, "rights": 1.0, "control": 1.0, "liability": 0.9, "content": 0.7}}


def load_params() -> dict:
    if PARAMS_PATH.exists():
        try:
            p = json.loads(PARAMS_PATH.read_text("utf-8"))
            return {**DEFAULT, **p}
        except Exception:
            pass
    return dict(DEFAULT)


def _interp(x: float, xs: list[float], ys: list[float]) -> float:
    if x <= xs[0]:
        return ys[0]
    for i in range(1, len(xs)):
        if x <= xs[i]:
            t = (x - xs[i - 1]) / max(1e-9, xs[i] - xs[i - 1])
            return ys[i - 1] + t * (ys[i] - ys[i - 1])
    return ys[-1]


def score(tags: list[tuple[str, float]], params: dict | None = None) -> dict:
    """tags: [(tag_id, confidence)]

    维度分：直观的加减分（供雷达图解释）。
    总分：若存在标定参数（mode=learned），用在 ToS;DR train 站点上学到的标签惩罚 + 分段映射；否则用维度加权平均。
    """
    p = params or load_params()
    base = DEFAULT
    dims = {d: base["base"] for d in DIMENSIONS}
    blocker = False
    best: dict[str, float] = {}
    for tid, conf in tags:
        if tid in TAG_BY_ID:
            best[tid] = max(best.get(tid, 0.0), conf)
    for tid, conf in best.items():
        t = TAG_BY_ID[tid]
        if t.polarity in ("bad", "blocker"):
            dims[t.dimension] -= t.weight * conf * base["k_bad"]
            blocker |= t.polarity == "blocker"
        elif t.polarity == "good":
            dims[t.dimension] += t.weight * conf * base["k_good"]
        else:
            dims[t.dimension] -= t.weight * conf * base["neutral"]
    dims = {d: max(0.0, min(100.0, v)) for d, v in dims.items()}
    w = base["dim_weights"]
    dim_total = sum(dims[d] * w[d] for d in dims) / sum(w[d] for d in dims)
    if p.get("mode") == "learned" and p.get("anchors_raw"):
        # 混合：以我们自己的六维为主（0.7），ToS;DR 学到的惩罚只作参考（0.3）。
        # 原来 100% 用 learned，等于把自己那套「六维」变成纯装饰；而且 Anchors 的零点
        # 落在 64.7 分，任何「没发现明显问题」的站都会被压成 C。
        raw = p.get("intercept", 0.0) + sum(p["penalty"].get(tid, 0.0) * c for tid, c in best.items())
        learned = _interp(raw, p["anchors_raw"], p["anchors_disp"])
        total = 0.7 * dim_total + 0.3 * learned
    else:
        total = dim_total
    total = max(0.0, min(100.0, total))
    g = grade_for(total)
    if blocker and g in "ABC":
        g = "D"
    return {"value": round(total), "grade": g, "dimensions": {d: round(v) for d, v in dims.items()}}
