"""Compare mode: how 2–4 photos share the Compare page, and the rules for starting it. Pure functions (no Qt), so the
arrangement can be tested on numbers alone (spec: docs/superpowers/specs/2026-10-29-kirapick-compare-design.md,
"Arrangement")."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

Mode = Literal["auto", "row", "grid"]
MODES: tuple[Mode, ...] = ("auto", "row", "grid")
MIN_PHOTOS, MAX_PHOTOS = 2, 4
UNKNOWN_SIZE = (3, 2)  # a photo whose size is not recorded counts as 3:2


@dataclass(frozen=True)
class Cell:
    row: int
    col: int
    row_span: int = 1
    col_span: int = 1


@dataclass(frozen=True)
class Arrangement:
    rows: int
    cols: int
    cells: tuple[Cell, ...]  # one per photo, in tile order
    fallback: bool = False  # Row / Grid was too small here: Auto's result is used instead


def _row(n: int) -> Arrangement:
    return Arrangement(1, n, tuple(Cell(0, c) for c in range(n)))


def _column(n: int) -> Arrangement:
    return Arrangement(n, 1, tuple(Cell(r, 0) for r in range(n)))


def _grid(n: int) -> Arrangement:
    if n == 2:
        return _row(2)
    if n == 3:  # "2 + 1": the third photo below, across both columns
        return Arrangement(2, 2, (Cell(0, 0), Cell(0, 1), Cell(1, 0, 1, 2)))
    return Arrangement(2, 2, (Cell(0, 0), Cell(0, 1), Cell(1, 0), Cell(1, 1)))


def candidates(n: int) -> tuple[Arrangement, ...]:
    """Auto's choices for n photos, in tie-break order."""
    _check_count(n)
    return (_row(n), _column(n)) if n == 2 else (_row(n), _column(n), _grid(n))


def displayed_sizes(sizes: Sequence[tuple[int, int] | None], area: tuple[int, int], rows: int, cols: int,
                    cells: Sequence[Cell], *, gap: int = 6, header: int = 22) -> list[tuple[float, float]]:
    """Each photo fitted into its cell's box (spans included), in logical pixels."""
    col_w = max(0.0, (area[0] - gap * (cols - 1)) / cols)
    row_h = max(0.0, (area[1] - gap * (rows - 1)) / rows)
    out = []
    for size, cell in zip(sizes, cells, strict=True):
        w, h = size if size and size[0] > 0 and size[1] > 0 else UNKNOWN_SIZE
        box_w = col_w * cell.col_span + gap * (cell.col_span - 1)
        box_h = max(0.0, row_h * cell.row_span + gap * (cell.row_span - 1) - header)
        k = min(box_w / w, box_h / h)
        out.append((w * k, h * k))
    return out


def arrange(sizes: Sequence[tuple[int, int] | None], area: tuple[int, int], mode: Mode, *, gap: int = 6,
            header: int = 22, min_long: int = 160) -> Arrangement:
    """Rows, columns and each photo's cell for the Compare page of ``area`` (its own size, not the window's).
    ``sizes``: each photo's size after Xoay xem (``turned_size``); None = unknown (3:2)."""
    if mode not in MODES:
        raise ValueError(f"unknown arrangement {mode!r}")
    n = len(sizes)

    def fitted(a: Arrangement) -> list[tuple[float, float]]:
        return displayed_sizes(sizes, area, a.rows, a.cols, a.cells, gap=gap, header=header)

    options = candidates(n)
    best = max(options, key=lambda a: (round(min(w * h for w, h in fitted(a))), -a.rows, -options.index(a)))
    if mode == "auto":
        return best
    chosen = _row(n) if mode == "row" else _grid(n)
    if min(max(w, h) for w, h in fitted(chosen)) < min_long:
        return Arrangement(best.rows, best.cols, best.cells, fallback=True)
    return chosen


def turned_size(width: int | None, height: int | None, rotation: int) -> tuple[int, int] | None:
    """The photo's size as shown after ``rotation`` quarter turns (Xoay xem); None when unknown."""
    if not width or not height or width <= 0 or height <= 0:
        return None
    return (height, width) if rotation % 2 else (width, height)


def start_error(count: int) -> str | None:
    """Why Compare cannot start with ``count`` marked photos (None: it can)."""
    if count < MIN_PHOTOS:
        return "Đánh dấu 2–4 ảnh (Ctrl+click) rồi bấm C để so sánh."
    if count > MAX_PHOTOS:
        return f"Chỉ so sánh được tối đa 4 ảnh — đang đánh dấu {count}, hãy bỏ bớt dấu."
    return None


def initial_active(compared: Sequence[int], current: int | None) -> int:
    """The active photo when Compare opens: the grid's current photo if compared, else the first tile."""
    return current if current in compared else compared[0]


def _check_count(n: int) -> None:
    if not MIN_PHOTOS <= n <= MAX_PHOTOS:
        raise ValueError(f"Compare shows 2–4 photos, not {n}")
