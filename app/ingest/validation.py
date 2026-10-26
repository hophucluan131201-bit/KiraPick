"""Self-checks that compare independent decode paths of the same RAW file.

Used by tests and by ``snorlu-raw-probe --verify`` on the user's own photos to
prove (not assume) that the embedded-preview path is oriented correctly.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image

from app.ingest import raw_decode

_SIDE = 128
_ROTATIONS = {
    0: None,
    90: Image.Transpose.ROTATE_90,
    180: Image.Transpose.ROTATE_180,
    270: Image.Transpose.ROTATE_270,
}


@dataclass(frozen=True, slots=True)
class OrientationCheck:
    correlations: dict[int, float]  # extra rotation applied to the preview -> similarity

    @property
    def best_rotation(self) -> int:
        return max(self.correlations, key=self.correlations.__getitem__)

    @property
    def margin(self) -> float:
        others = [v for k, v in self.correlations.items() if k != 0]
        return round(self.correlations[0] - max(others), 4)

    @property
    def passed(self) -> bool:
        return self.best_rotation == 0 and self.margin > 0.05


# Edge similarity between a correctly decoded RAW and its own embedded preview
# was >= 0.22 on every real sample (lowest: Fujifilm X-Trans); unrelated or
# garbage images score ~0. Heuristic threshold, documented in the matrix doc.
MIN_PREVIEW_CONSISTENCY = 0.10


def _edge_signature(image: Image.Image) -> np.ndarray:
    # Square resize removes aspect differences between rotations; gradient
    # magnitude is robust to tone/WB differences between camera JPEG and LibRaw.
    gray = np.asarray(image.convert("L").resize((_SIDE, _SIDE), Image.Resampling.BOX), dtype=np.float32)
    gy, gx = np.gradient(gray)
    mag = np.hypot(gx, gy)
    mag -= mag.mean()
    norm = float(np.linalg.norm(mag))
    return mag / norm if norm else mag


def edge_similarity(a: Image.Image, b: Image.Image) -> float:
    """Cosine similarity of gradient-magnitude maps (1 = identical structure)."""
    return float((_edge_signature(a) * _edge_signature(b)).sum())


def check_embedded_orientation(path: Path) -> OrientationCheck | None:
    """Return None when the file has no embedded preview to check."""
    _, embedded = raw_decode.read_raw(path, draft_size=(_SIDE * 4, _SIDE * 4))
    if embedded is None:
        return None
    _, reference = raw_decode.demosaic(path, half_size=True)
    correlations = {}
    for degrees, method in _ROTATIONS.items():
        candidate = embedded.image if method is None else embedded.image.transpose(method)
        correlations[degrees] = round(edge_similarity(candidate, reference), 4)
    return OrientationCheck(correlations)
