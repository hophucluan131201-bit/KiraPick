"""Pick the next "which do you prefer?" question: the two most uncertain near-alternatives.

Only photos of the same subject that look alike (CLIP cosine >= SIMILAR) are compared — the
answer then says something about taste, not about which person or costume the owner prefers —
and among those, the pair whose ranking values are closest (the app is least sure). A pair is
never asked twice.
"""

from __future__ import annotations

import numpy as np

SIMILAR = 0.9


def next_pair(subjects: dict[int, int], clips: dict[int, np.ndarray], ranked: dict[int, float],
              asked: set[frozenset[int]]) -> tuple[int, int] | None:
    by_subject: dict[int, list[int]] = {}
    for asset_id, subject in subjects.items():
        if asset_id in clips and asset_id in ranked:
            by_subject.setdefault(subject, []).append(asset_id)
    best: tuple[float, int, int] | None = None
    for ids in by_subject.values():
        ids.sort()
        if len(ids) < 2:
            continue
        mat = np.stack([clips[i] for i in ids])
        sims = mat @ mat.T
        for a in range(len(ids)):
            for b in range(a + 1, len(ids)):
                if sims[a, b] < SIMILAR or frozenset((ids[a], ids[b])) in asked:
                    continue
                gap = abs(ranked[ids[a]] - ranked[ids[b]])
                if best is None or gap < best[0]:
                    best = (gap, ids[a], ids[b])
    return None if best is None else (best[1], best[2])
