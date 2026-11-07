"""Focus warnings Out nét / Trật nét (Media spec v6 §6, plan Mốc 1 M7). Warnings only: never an X, never a rejection.

Measured on the full-resolution photo (app.ingest.preview.load_full_resolution: a full-size embedded JPEG or a full
demosaic), with app.quality.measure's edge measure (~1.0 = an edge in one pixel, 0.25 = spread over ~4 px).

- Region of the subject: the face (a close-up is measured at portrait scale, as in Chụp cá nhân), else the upper
  middle of the person box. No subject, or a face too small to measure (wide shots): the whole photo, as tiles.
- Directional: the edge measure is taken across x and across y; the softer one counts. Camera shake and motion blur
  smear one direction only, so they read as soft (UX-4: they are Out nét, there is no separate warning).
- ISO: above ISO 1600 each measured region is denoised (non-local means, as strong as the noise measured in it)
  before measuring, so sensor grain does not pass for detail.
- Out nét: the subject region is soft; without a subject, every tile of the photo is soft.
- Trật nét: the subject is soft AND a region next to it is clearly sharp AND that region is not an LED screen or a
  light. Screens and lights are only left out of that comparison; the subject itself is always measured, even if it
  is bright white (FC-07). A screen is found as a large bright flat-lit rectangle with straight edges, whether or not
  it is saturated (FC-06); a light as a mostly clipped area.

The thresholds are starting values (personal mode: sharp eyes measured 0.5-0.8 on the owner's NEFs, a defocused face
0.08); they are checked only on synthetic photos in CI. On real event photos: [Ảnh mẫu], scored in M9.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np

from app.media.shot import Box, Subject
from app.quality.measure import EDGE_PERCENTILE, MIN_CONTRAST, at_portrait_scale

FOCUS_VERSION = "f1"


@dataclass(frozen=True, slots=True)
class FocusRules:
    soft: float = 0.25  # subject region below this is soft
    sharp: float = 0.40  # a neighbour region at least this sharp ...
    ratio: float = 1.8  # ... and this many times sharper than the subject points at a missed focus
    min_face_px: int = 48  # smaller faces: wide shot, judged on the whole photo
    high_iso: int = 1600
    light_clip: float = 0.30  # fraction of clipped pixels (>= 250) that makes a region a light
    screen_min_area: float = 0.02  # a screen covers at least this fraction of the photo
    screen_fill: float = 0.85  # its bright area fills this much of its rotated rectangle
    screen_lift: float = 35.0  # and is this much brighter (grey levels, smoothed) than the photo's median
    tiles: int = 4  # whole-photo check: tiles per side


@dataclass(slots=True)
class FocusResult:
    warnings: dict[str, float | None]
    unmeasurable: bool
    measures: dict = field(default_factory=dict)


# ------------------------------------------------------------------------------------------------ measures
def directional_sharpness(gray: np.ndarray) -> float | None:
    """The softer of the edge measures across x and across y (each: steepest edges / local contrast)."""
    if gray.ndim != 2 or min(gray.shape) < 16:
        return None
    g = gray.astype(np.float32)
    lo, hi = np.percentile(g, [2, 98])
    contrast = float(hi - lo)
    if contrast < MIN_CONTRAST:
        return None
    out = [min(1.5, float(np.percentile(np.abs(cv2.Sobel(g, cv2.CV_32F, dx, dy, ksize=3)), EDGE_PERCENTILE))
               / (4.0 * contrast)) for dx, dy in ((1, 0), (0, 1))]
    return round(min(out), 4)  # a subject with edges in one direction only reads soft: a known limit


def noise_sigma(gray: np.ndarray) -> float:
    """Sensor noise (grey levels) from the median absolute Laplacian (Immerkær's estimate)."""
    lap = cv2.Laplacian(gray.astype(np.float32), cv2.CV_32F, ksize=1)
    return float(np.median(np.abs(lap))) * 1.4826 / np.sqrt(20.0)


def _denoise(region: np.ndarray, iso: int | None, rules: FocusRules) -> np.ndarray:
    """Above ISO ``high_iso``: non-local means, as strong as the noise measured in the region, so grain does not pass
    for detail and real edges keep their steepness."""
    if iso is None or iso <= rules.high_iso:
        return region
    sigma = noise_sigma(region)
    if sigma < 1.0:
        return region
    return cv2.fastNlMeansDenoising(np.ascontiguousarray(region), None, h=1.3 * sigma, templateWindowSize=7,
                                    searchWindowSize=15)


def _clip(box: Box, w: int, h: int) -> tuple[int, int, int, int] | None:
    x0, y0 = max(0, int(box[0])), max(0, int(box[1]))
    x1, y1 = min(w, int(round(box[0] + box[2]))), min(h, int(round(box[1] + box[3])))
    return (x0, y0, x1, y1) if x1 - x0 >= 16 and y1 - y0 >= 16 else None


def screens(gray: np.ndarray, rules: FocusRules = FocusRules()) -> list[tuple[int, int, int, int]]:  # noqa: B008
    """Bounding boxes of LED screens / projections: large, bright, evenly lit, straight-edged rectangles."""
    h, w = gray.shape
    k = max(3, (min(h, w) // 60) | 1)
    smooth = cv2.blur(gray, (k, k))  # text and pictures on the screen average out
    level = float(np.median(smooth)) + rules.screen_lift
    mask = (smooth >= level).astype(np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((k, k), np.uint8))
    found = []
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for c in contours:
        area = cv2.contourArea(c)
        if area < rules.screen_min_area * h * w:
            continue
        (_, _), (rw, rh), _ = cv2.minAreaRect(c)
        if rw * rh <= 0 or area / (rw * rh) < rules.screen_fill:
            continue
        x, y, bw, bh = cv2.boundingRect(c)
        found.append((x, y, x + bw, y + bh))
    return found


def is_light(region: np.ndarray, rules: FocusRules = FocusRules()) -> bool:  # noqa: B008
    return float(np.mean(region >= 250)) >= rules.light_clip


def _overlap(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> float:
    iw = max(0, min(a[2], b[2]) - max(a[0], b[0]))
    ih = max(0, min(a[3], b[3]) - max(a[1], b[1]))
    area = (a[2] - a[0]) * (a[3] - a[1])
    return iw * ih / area if area else 0.0


# ------------------------------------------------------------------------------------------------ the rule
def _subject_region(subject: Subject | None, scale: float, w: int, h: int,
                    rules: FocusRules) -> tuple[tuple[int, int, int, int] | None, str]:
    if subject is None:
        return None, "none"
    if subject.face is not None:
        fx, fy, fw, fh = (v * scale for v in subject.face)
        if min(fw, fh) >= rules.min_face_px:
            return _clip((fx, fy, fw, fh), w, h), "face"
        return None, "face_too_small"
    if subject.person is not None:
        px, py, pw, ph = (v * scale for v in subject.person)
        return _clip((px + pw * 0.2, py, pw * 0.6, ph * 0.5), w, h), "body"
    return None, "none"


def _neighbours(box: tuple[int, int, int, int], w: int, h: int) -> list[tuple[int, int, int, int]]:
    """Tiles of the subject's size around it (left, right, above, below and the corners)."""
    x0, y0, x1, y1 = box
    bw, bh = x1 - x0, y1 - y0
    out = []
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            if dx == dy == 0:
                continue
            t = _clip((x0 + dx * bw, y0 + dy * bh, bw, bh), w, h)
            if t is not None and _overlap(t, box) < 0.25:
                out.append(t)
    return out


def judge(gray: np.ndarray, subject: Subject | None, scale: float = 1.0, iso: int | None = None,
          rules: FocusRules = FocusRules()) -> FocusResult:  # noqa: B008
    """The warnings for one full-resolution grey photo; ``scale`` maps the detection boxes onto it."""
    h, w = gray.shape

    def sharpness(region: np.ndarray) -> float | None:
        return directional_sharpness(_denoise(region, iso, rules))

    box, where = _subject_region(subject, scale, w, h, rules)
    m: dict = {"region": where, "iso": iso}
    if box is None:  # whole photo: soft only when every measurable tile is soft
        th, tw = h // rules.tiles, w // rules.tiles
        values = [sharpness(gray[j * th:(j + 1) * th, i * tw:(i + 1) * tw])
                  for j in range(rules.tiles) for i in range(rules.tiles)]
        values = [v for v in values if v is not None]
        m["tiles_max"] = max(values) if values else None
        if not values:
            return FocusResult({}, True, m)
        best = max(values)
        return FocusResult({"out_net": round(1 - best / rules.soft, 3)} if best < rules.soft else {}, False, m)
    x0, y0, x1, y1 = box
    region = gray[y0:y1, x0:x1]
    if where == "face":
        region = at_portrait_scale(region, (x1 - x0) * 0.42)  # eyes ~0.42 of the face width apart
    subj = sharpness(region)
    m["subject"] = subj
    if subj is None:
        return FocusResult({}, True, m)
    if subj >= rules.soft:
        return FocusResult({}, False, m)
    lit = screens(gray, rules)
    best, excluded = None, 0
    for t in _neighbours(box, w, h):
        tile = gray[t[1]:t[3], t[0]:t[2]]
        if is_light(tile, rules) or any(_overlap(t, s) > 0.3 for s in lit):
            excluded += 1
            continue
        v = sharpness(tile)
        if v is not None and (best is None or v > best):
            best = v
    m.update(neighbour_best=best, neighbours_excluded=excluded, screens=len(lit))
    confidence = round(1 - subj / rules.soft, 3)
    if best is not None and best >= rules.sharp and best >= rules.ratio * subj:
        return FocusResult({"trat_net": confidence}, False, m)
    return FocusResult({"out_net": confidence}, False, m)


def analyse(path: Path, subject: Subject | None, detect_size: tuple[int, int], *, iso: int | None = None,
            load_full: Callable[[Path], np.ndarray] | None = None, rules: FocusRules = FocusRules()) -> FocusResult:  # noqa: B008
    """Load the full-resolution photo (grey) and judge it; ``detect_size`` is (w, h) of the detection image."""
    if load_full is None:
        from app.ingest.preview import load_full_resolution

        gray = np.asarray(load_full_resolution(path).image.convert("L"))
    else:
        gray = load_full(path)
    scale = gray.shape[1] / detect_size[0] if detect_size[0] else 1.0
    result = judge(gray, subject, scale, iso, rules)
    result.measures["full_px"] = [int(gray.shape[1]), int(gray.shape[0])]
    return result
