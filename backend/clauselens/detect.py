"""分句/分段 + 标签识别（规则层 + 可选模型层融合）。"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from .taxonomy import TAGS, TAG_BY_ID, Tag

MODEL_DIR = Path(__file__).resolve().parents[2] / "data" / "models"
MODEL_PATH = MODEL_DIR / "clause_model.pkl"
MODEL_PATH_ZH = MODEL_DIR / "clause_model_zh.pkl"

_SENT_SPLIT = re.compile(r"(?<=[。！？；;!?])\s*|(?<=[.])\s+(?=[A-Z(“\"])|\n+")


@dataclass
class Sentence:
    doc: str
    text: str
    start: int
    end: int


def is_zh(text: str) -> bool:
    sample = text[:3000]
    if not sample:
        return False
    cjk = sum(1 for ch in sample if "一" <= ch <= "鿿")
    return cjk / max(1, len(sample)) > 0.15


def split_sentences(doc_id: str, text: str) -> list[Sentence]:
    out, pos = [], 0
    for piece in _SENT_SPLIT.split(text):
        if piece is None:
            continue
        idx = text.find(piece, pos)
        if idx < 0:
            idx = pos
        s = piece.strip()
        if 8 <= len(s) <= 1200:
            out.append(Sentence(doc_id, s, idx, idx + len(piece)))
        pos = idx + len(piece)
    return out


@dataclass
class Hit:
    tag: str
    confidence: float
    source: str
    evidence: list[dict] = field(default_factory=list)
    provisional: bool = False   # 只有模型命中、没有规则字面锚点：结论待确认


class _Compiled:
    def __init__(self, tag: Tag):
        f = re.I
        self.tag = tag
        self.zh = [re.compile(p, f) for p in tag.zh]
        self.en = [re.compile(p, f) for p in tag.en]
        self.neg_zh = [re.compile(p, f) for p in tag.neg_zh]
        self.neg_en = [re.compile(p, f) for p in tag.neg_en]


_COMPILED = [_Compiled(t) for t in TAGS]
_BY_ID = {c.tag.id: c for c in _COMPILED}


def rule_spans(sent: str, zh: bool, tag_id: str) -> list[list[int]]:
    """该标签的规则在句内命中的位置（供前端精确高亮）。"""
    c = _BY_ID.get(tag_id)
    if not c:
        return []
    out = []
    for p in (c.zh if zh else c.en):
        for m in p.finditer(sent):
            if m.end() > m.start():
                out.append([m.start(), m.end()])
    return sorted(out)[:6]


def rule_scores(sent: str, zh: bool) -> dict[str, float]:
    """返回该句命中的标签及规则强度（命中正则条数）。"""
    out = {}
    for c in _COMPILED:
        pats, negs = (c.zh, c.neg_zh) if zh else (c.en, c.neg_en)
        n = sum(1 for p in pats if p.search(sent))
        if n and not any(p.search(sent) for p in negs):
            out[c.tag.id] = n
    return out


class Model:
    """TF-IDF + 线性分类器（由 scripts/train_model.py 训练）。"""

    def __init__(self, path: Path = MODEL_PATH):
        import pickle
        with open(path, "rb") as f:
            blob = pickle.load(f)
        self.vec = blob["vectorizer"]
        self.clf = blob["classifier"]
        self.labels: list[str] = blob["labels"]
        self.thresholds: dict[str, float] = blob.get("thresholds", {})

    def predict(self, sents: list[str]):
        if not sents:
            return []
        X = self.vec.transform(sents)
        P = self.clf.predict_proba(X)
        return [{lab: float(P[i, j]) for j, lab in enumerate(self.labels)} for i in range(len(sents))]


_models: dict[str, Model | None] = {}


def get_model(zh: bool = False) -> Model | None:
    key = "zh" if zh else "en"
    if key not in _models:
        path = MODEL_PATH_ZH if zh else MODEL_PATH
        try:
            _models[key] = Model(path) if path.exists() else None
        except Exception:
            _models[key] = None
    return _models[key]


# 模型认识该标签、且概率低于 阈值×比例 时，否决规则命中（评测与线上共用）
RULE_VETO_RATIO = {"en": 0.6, "zh": 0.5}


_LATIN_EXT = re.compile(r"[\u00c0-\u024f]")
_HAN = re.compile(r"[\u4e00-\u9fff]")


def _model_worthy(s: str, zh: bool) -> bool:
    """模型单独命中的句子，要长得像一条条款，而不是标题、导航、菜单项或别的语言。

    规则层是正则精确命中，不受这道门槛影响；这里只拦"模型说像、但其实是一行菜单"的情况
    （例如 reddit 文档里的越南语/他加禄语导航「Thông báo về cookie」）。
    """
    t = (s or "").strip()
    if not t:
        return False
    if zh:
        if len(_HAN.findall(t)) < 12:
            return False
        # 中文文档里混着的整句英文，中文模型打分没有意义
        letters = sum(1 for ch in t if ch.isascii() and ch.isalpha())
        if letters > len(t) * 0.5:
            return False
        return True
    words = t.split()
    if len(words) < 8:
        return False
    if len(_LATIN_EXT.findall(t)) > len(t) * 0.02:   # 越南语/法语/德语等
        return False
    caps = sum(1 for w in words if w[:1].isupper())
    if len(words) < 12 and caps >= len(words) * 0.7:  # "Third-Party Content, Advertisements, and Promotions"
        return False
    return True


def fuse(rs: dict[str, int], pr: dict[str, float] | None, thresholds: dict[str, float], ratio: float) -> dict[str, tuple[float, str]]:
    """单句融合：rs=规则命中{tag:条数}，pr=模型概率{tag:p}。返回 {tag: (置信度, 来源)}。"""
    cand: dict[str, tuple[float, str]] = {}
    for tid, n in rs.items():
        if pr is not None and tid in pr and pr[tid] < thresholds.get(tid, 0.5) * ratio:
            continue
        cand[tid] = (min(0.55 + 0.15 * n, 0.85), "rule")
    if pr:
        for tid, p in pr.items():
            th = thresholds.get(tid, 0.5)
            if tid in cand and p >= th * ratio:
                cand[tid] = (min(0.97, cand[tid][0] + 0.25 * p), "rule+model")
            elif tid not in cand and p >= max(th, 0.6):
                cand[tid] = (0.45 + 0.4 * p, "model")
    return cand


def detect(sentences: list[Sentence], use_model: bool = True, max_evidence: int = 3) -> list[Hit]:
    """按句判语言，再分语言融合：规则命中给基础置信度，模型概率高时加成或独立命中。

    以前是拿前 200 句判一次语言，整批都按一种语言处理——一个站点同时抓到中英文文档时
    （github 就有 zh/en 两版），中文句子会走英文正则和英文模型，结果里就混进看不懂的证据。
    """
    if not sentences:
        return []
    groups: dict[bool, list[Sentence]] = {True: [], False: []}
    for s in sentences:
        groups[is_zh(s.text)].append(s)

    merged: dict[str, dict] = {}
    for zh, group in groups.items():
        if not group:
            continue
        for h in _detect_lang(group, zh, use_model, max_evidence):
            m = merged.setdefault(h.tag, {"conf": 0.0, "src": set(), "ev": [], "prov": True})
            m["conf"] = max(m["conf"], h.confidence)
            m["src"].add(h.source)
            m["ev"] += h.evidence
            m["prov"] = m["prov"] and h.provisional

    hits = []
    for tid, m in merged.items():
        src = "rule+model" if ("rule+model" in m["src"] or len(m["src"]) > 1) else next(iter(m["src"]))
        hits.append(Hit(tid, round(m["conf"], 3), src, m["ev"][:max_evidence], m["prov"]))
    hits.sort(key=lambda h: (-TAG_BY_ID[h.tag].weight * h.confidence))
    return hits


def _detect_lang(sentences: list[Sentence], zh: bool, use_model: bool, max_evidence: int) -> list[Hit]:
    """单一语言的一批句子。"""
    # 英文：ToS;DR 标注训练；中文：人工标注的中文句子训练
    model = get_model(zh) if use_model else None
    probs = model.predict([s.text for s in sentences]) if model else [None] * len(sentences)

    agg: dict[str, dict] = {}
    for s, pr in zip(sentences, probs):
        rs = rule_scores(s.text, zh)
        cand = fuse(rs, pr, model.thresholds if model else {}, RULE_VETO_RATIO["zh" if zh else "en"])
        for tid, (conf, src) in cand.items():
            if src == "model" and not _model_worthy(s.text, zh):
                continue   # 只有模型命中、句子又不像条款：不进候选
            a = agg.setdefault(tid, {"conf": 0.0, "src": set(), "ev": [], "n": 0})
            a["n"] += 1
            a["src"].add(src)
            a["ev"].append((conf, s))
            a["conf"] = max(a["conf"], conf)

    hits = []
    for tid, a in agg.items():
        # 多句支持略增置信度
        conf = min(0.99, a["conf"] + 0.03 * min(a["n"] - 1, 5))
        ev = sorted(a["ev"], key=lambda x: (-x[0], len(x[1].text)))[:max_evidence]
        src = "rule+model" if ("rule+model" in a["src"] or len(a["src"]) > 1) else next(iter(a["src"]))
        tag = TAG_BY_ID[tid]
        # 没有任何规则字面锚点、只靠模型判断的负面标签，降级为「待确认」：
        # 不主导评分、不进 TL;DR，但仍展示给用户看（AGENTS §5：宁可未发现，也不乱贴负面标签）
        prov = a["src"] == {"model"} and tag.polarity in ("bad", "blocker")
        hits.append(Hit(tid, round(conf, 3), src,
                        [{"doc": s.doc, "quote": s.text[:400], "start": s.start, "end": s.end,
                          "spans": [sp for sp in rule_spans(s.text[:400], zh, tid)]} for _, s in ev],
                        prov))
    return hits
