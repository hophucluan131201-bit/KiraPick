"""Grid: K (technical) · G (taste) badge and the new sort orders."""

from __future__ import annotations

from pathlib import Path

from app.quality.rank import Ranked
from app.quality.score import score
from app.ui.asset_model import AssetRecord, Sort, sort_records
from app.ui.grid import badge_text


def _rec(i: int, tech: float | None, taste: float | None, value: float | None, capped: bool = False) -> AssetRecord:
    r = AssetRecord(i, 1, Path(f"/x/{i}.jpg"), f"{i}.jpg", "jpg", "ok", None, None, f"2026-10-28T10:00:0{i}", 1, 1,
                    None, None)
    if tech is not None:
        r.score = score({"eye_sharp": 0.5})
        r.ranked = Ranked(tech, taste, value, capped=capped)
    return r


def test_badge_text() -> None:
    assert badge_text(_rec(1, 78.4, 85.0, 81.7)) == "K 78 · G 85"
    assert badge_text(_rec(2, 78.4, None, 78.4)) == "K 78"
    assert badge_text(_rec(3, 40.0, 90.0, 40.0, capped=True)) == "⚠ K 40 · G 90"
    assert badge_text(_rec(4, None, None, None)) == ""


def test_sort_orders() -> None:
    recs = [_rec(1, 60, 90, 75), _rec(2, 80, 40, 60), _rec(3, None, None, None), _rec(4, 70, None, 70)]
    assert [r.id for r in sort_records(recs, Sort.SCORE)] == [2, 4, 1, 3]
    assert [r.id for r in sort_records(recs, Sort.TASTE)] == [1, 2, 3, 4]  # no taste: last, in capture order
    assert [r.id for r in sort_records(recs, Sort.RANK)] == [1, 4, 2, 3]
