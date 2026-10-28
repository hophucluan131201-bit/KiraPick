"""Brightness histogram of the image the app displays (embedded camera JPEG of a RAW, or the JPEG itself).

Not RAW sensor data: the panel labels it "theo ảnh xem trước". Pure numpy/OpenCV, no Qt; the window runs it
in its thread pool.
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

BINS = 64
MAX_SIDE = 1024  # downscale before counting: the shape of the histogram does not need more
SHADOW_MAX, HIGHLIGHT_MIN = 2, 253  # 8-bit levels counted as clipped


@dataclass(frozen=True, slots=True)
class Histogram:
    bins: np.ndarray  # BINS values, the tallest = 1.0
    shadows: float  # share of pixels at 0..2
    highlights: float  # share of pixels at 253..255


def histogram(rgb: np.ndarray) -> Histogram:
    """``rgb``: 8-bit RGB (H×W×3) or grey (H×W). Y = 0.2126 R + 0.7152 G + 0.0722 B."""
    if rgb.dtype != np.uint8 or rgb.ndim not in (2, 3) or (rgb.ndim == 3 and rgb.shape[2] != 3) or rgb.size == 0:
        raise ValueError("expected a non-empty 8-bit RGB or grey image")
    h, w = rgb.shape[:2]
    scale = MAX_SIDE / max(h, w)
    if scale < 1:
        rgb = cv2.resize(rgb, (max(1, round(w * scale)), max(1, round(h * scale))), interpolation=cv2.INTER_AREA)
    if rgb.ndim == 3:
        y = rgb.astype(np.float32) @ np.array([0.2126, 0.7152, 0.0722], np.float32)
        y = np.clip(np.rint(y), 0, 255).astype(np.uint8)
    else:
        y = rgb
    counts = np.bincount(y.ravel(), minlength=256)
    total = float(counts.sum())
    bins = counts.reshape(BINS, 256 // BINS).sum(axis=1).astype(np.float64)
    return Histogram(bins / bins.max(), float(counts[:SHADOW_MAX + 1].sum() / total),
                     float(counts[HIGHLIGHT_MIN:].sum() / total))
