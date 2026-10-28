"""Personal taste: learns from the owner's Keep/Reject/stars which photos they like.

Features: the photo's CLIP embedding (content, light, style) and the technical score
parts. Model: weighted, L2-regularised logistic regression (numpy, trained in well under a
second). It is shown only when cross-validation — folds split by shoot day, so frames of one
burst never sit on both sides — says it predicts clearly better than chance; otherwise the UI
says why it is not ready. Never a guess presented as a score.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

VERSION = "taste-v1"
PARTS = ("focus", "eyes", "face", "exposure", "framing", "aesthetic")
MIN_EXAMPLES = 60
MIN_EACH = 20
MIN_AUC = 0.65
FOLDS = 5
L2 = 1.0
MAX_ITER = 300


@dataclass(slots=True)
class TasteExample:
    label: int  # +1 liked, -1 not liked
    weight: float
    day: str  # shoot day (ISO), for the cross-validation folds
    clip: np.ndarray | None
    parts: dict[str, float | None]


@dataclass(slots=True)
class TasteModel:
    w: np.ndarray
    b: float
    mean: np.ndarray
    std: np.ndarray
    n: int
    n_pos: int
    n_neg: int
    auc: float
    version: str = VERSION

    def _raw(self, clip: np.ndarray, parts: dict[str, float | None]) -> float:
        x = (_features(clip, parts) - self.mean) / self.std
        return float(x @ self.w + self.b)

    def predict(self, clip: np.ndarray, parts: dict[str, float | None]) -> float:
        """0..100: how much this photo looks like the ones the owner keeps."""
        return round(100.0 / (1.0 + np.exp(-self._raw(clip, parts))), 1)

    def _clip_direction(self) -> np.ndarray:
        dim = len(self.w) - 2 * len(PARTS)
        return self.w[:dim] / self.std[:dim]

    def concepts(self, prompts: dict[str, np.ndarray], k: int = 3) -> list[tuple[str, float]]:
        """The k prompt concepts the taste leans to most, then the k it leans away from most."""
        d = self._clip_direction()
        dim = len(d)
        scored = sorted(((name, float(d @ (np.asarray(v, float) - self.mean[:dim]))) for name, v in prompts.items()),
                        key=lambda t: -t[1])
        picked = scored[:k] + [s for s in scored[-k:] if s not in scored[:k]]
        return picked

    def part_effects(self) -> list[tuple[str, float]]:
        """Effect of +1 point of each technical part on the log-odds, strongest first."""
        dim = len(self.w) - 2 * len(PARTS)
        effects = [(name, float(self.w[dim + 2 * i] / self.std[dim + 2 * i])) for i, name in enumerate(PARTS)]
        return sorted(effects, key=lambda t: -abs(t[1]))


@dataclass(slots=True)
class TasteStatus:
    ready: bool
    reason: str
    model: TasteModel | None = None


def _features(clip: np.ndarray, parts: dict[str, float | None]) -> np.ndarray:
    tech = []
    for name in PARTS:
        v = parts.get(name)
        tech += [0.0, 1.0] if v is None else [float(v), 0.0]  # value, missing flag
    return np.concatenate([np.asarray(clip, float), tech])


def _fit(x: np.ndarray, y: np.ndarray, sw: np.ndarray) -> tuple[np.ndarray, float]:
    """Weighted L2 logistic regression by Newton steps (y in {0, 1}); the bias is not penalised."""
    n, d = x.shape
    xb = np.hstack([x, np.ones((n, 1))])
    beta = np.zeros(d + 1)
    reg = np.full(d + 1, L2)
    reg[-1] = 0.0
    for _ in range(MAX_ITER):
        p = 1.0 / (1.0 + np.exp(-(xb @ beta)))
        grad = xb.T @ (sw * (p - y)) + reg * beta
        h = (xb * (sw * p * (1 - p))[:, None]).T @ xb + np.diag(reg)
        step = np.linalg.solve(h, grad)
        beta -= step
        if np.max(np.abs(step)) < 1e-6:
            break
    return beta[:-1], float(beta[-1])


def weighted_auc(scores: np.ndarray, y: np.ndarray, sw: np.ndarray) -> float:
    """Probability that a liked photo outranks a not-liked one (weighted; ties count half)."""
    order = np.argsort(scores, kind="mergesort")
    s, yy, ww = scores[order], y[order], sw[order]
    total_pos, total_neg = ww[yy == 1].sum(), ww[yy == 0].sum()
    if total_pos == 0 or total_neg == 0:
        return 0.5
    win = 0.0
    neg_below = 0.0
    i = 0
    while i < len(s):
        j = i
        while j < len(s) and s[j] == s[i]:
            j += 1
        pos_here = ww[i:j][yy[i:j] == 1].sum()
        neg_here = ww[i:j][yy[i:j] == 0].sum()
        win += pos_here * (neg_below + neg_here / 2)
        neg_below += neg_here
        i = j
    return float(win / (total_pos * total_neg))


def _folds(days: list[str]) -> np.ndarray:
    unique = sorted(set(days))
    if len(unique) >= 2:
        k = min(FOLDS, len(unique))
        fold_of = {d: i % k for i, d in enumerate(unique)}
        return np.array([fold_of[d] for d in days])
    return np.arange(len(days)) * FOLDS // max(1, len(days))  # one day: contiguous blocks (shooting order)


def _standardise(x: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Centre everything. The CLIP block shares one scale (its geometry carries the meaning; scaling
    each of its 768 dimensions to unit variance would blow tiny noise dimensions up to the size of
    real ones); each technical part gets its own."""
    mean = x.mean(axis=0)
    std = x.std(axis=0)
    dim = x.shape[1] - 2 * len(PARTS)
    std[:dim] = max(float(np.sqrt(np.mean((x[:, :dim] - mean[:dim]) ** 2))), 1e-6)
    std[std < 1e-6] = 1.0
    return mean, std


def train(examples: list[TasteExample]) -> TasteStatus:
    used = [e for e in examples if e.clip is not None and e.weight > 0 and e.label in (1, -1)]
    n = len(used)
    n_pos = sum(e.label == 1 for e in used)
    n_neg = n - n_pos
    if n < MIN_EXAMPLES:
        return TasteStatus(False, f"Chưa đủ dữ liệu: {n}/{MIN_EXAMPLES} lựa chọn")
    if n_pos < MIN_EACH or n_neg < MIN_EACH:
        return TasteStatus(False, f"Chưa đủ dữ liệu: cần ít nhất {MIN_EACH} ảnh thích và {MIN_EACH} ảnh không thích "
                                  f"(đang có {n_pos} thích, {n_neg} không thích)")
    x = np.stack([_features(e.clip, e.parts) for e in used])
    y = np.array([1.0 if e.label == 1 else 0.0 for e in used])
    sw = np.array([e.weight for e in used], float)
    folds = _folds([e.day for e in used])
    held = np.zeros(n)
    for f in np.unique(folds):
        tr, te = folds != f, folds == f
        if len(np.unique(y[tr])) < 2:
            held[te] = 0.0
            continue
        mean, std = _standardise(x[tr])
        w, b = _fit((x[tr] - mean) / std, y[tr], sw[tr])
        held[te] = ((x[te] - mean) / std) @ w + b
    auc = weighted_auc(held, y, sw)
    mean, std = _standardise(x)
    w, b = _fit((x - mean) / std, y, sw)
    model = TasteModel(w, b, mean, std, n, n_pos, n_neg, round(auc, 3))
    if auc < MIN_AUC:
        return TasteStatus(False, f"Chưa đoán được gu (độ khớp {auc:.2f})".replace(".", ","), model)
    return TasteStatus(True, f"Học từ {n} lựa chọn, độ khớp {auc:.2f}".replace(".", ","), model)
