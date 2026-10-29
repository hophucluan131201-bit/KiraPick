"""Compare mode, part 2 task 1: arrangement of 2–4 photos and the start rules (pure functions, no Qt).
Expected values: the worked-examples table of the spec (revision 3), computed by a prototype of the same rules."""

from __future__ import annotations

import pytest

from app.ui.compare_layout import Cell, arrange, displayed_sizes, initial_active, start_error, turned_size

L, P = (6000, 4000), (4000, 6000)


@pytest.mark.parametrize("sizes,area,mode,shape,fallback", [
    ([L] * 4, (1920, 484), "auto", (1, 4), False),     # SHORT
    ([L] * 2, (960, 1000), "auto", (2, 1), False),     # NARROW
    ([L] * 4, (580, 400), "auto", (2, 2), False),      # TINY
    ([L] * 4, (580, 400), "row", (2, 2), True),        # 1 × 4 long side 140.5 < 160 → auto
    ([L] * 4, (1600, 900), "row", (1, 4), False),      # long side 395.5
    ([P] * 2, (1200, 800), "auto", (1, 2), False),
    ([L] * 3, (1600, 900), "auto", (2, 2), False),     # 2 + 1
    ([P, P, L], (1600, 900), "auto", (1, 3), False),   # mixed
    ([L, L, P], (1600, 900), "auto", (1, 3), False),   # mixed, other order
    ([L] * 3, (960, 1000), "auto", (2, 2), False),     # 2 + 1 beats 3 × 1 (151 686 vs 141 681)
    ([L] * 3, (1600, 900), "grid", (2, 2), False),
    ([L] * 2, (1600, 900), "grid", (1, 2), False),
    ([L] * 4, (1600, 900), "grid", (2, 2), False),
    ([L] * 2, (1600, 900), "row", (1, 2), False),
    ([L] * 3, (1600, 900), "row", (1, 3), False),
])
def test_worked_examples(sizes, area, mode, shape, fallback) -> None:  # noqa: ANN001
    a = arrange(sizes, area, mode)
    assert (a.rows, a.cols) == shape and a.fallback is fallback
    assert len(a.cells) == len(sizes)


@pytest.mark.parametrize("sizes,area,scores", [  # smallest displayed area (px²) per candidate, from the spec table
    ([L] * 4, (1920, 484), {(1, 4): 150734, (2, 2): 70634, (4, 1): 13395}),
    ([L] * 2, (960, 1000), {(2, 1): 338438, (1, 2): 151686}),
    ([L] * 3, (1600, 900), {(2, 2): 270938, (1, 3): 186796, (3, 1): 112614}),
    ([P, P, L], (1600, 900), {(1, 3): 186796, (2, 2): 120417, (3, 1): 50051}),
    ([L] * 3, (960, 1000), {(2, 2): 151686, (3, 1): 141681, (1, 3): 66571}),
])
def test_candidate_scores_match_the_spec(sizes, area, scores) -> None:  # noqa: ANN001
    from app.ui.compare_layout import candidates

    got = {(c.rows, c.cols): round(min(w * h for w, h in displayed_sizes(sizes, area, c.rows, c.cols, c.cells)))
           for c in candidates(len(sizes))}
    assert got == scores


def test_cells_in_tile_order() -> None:
    assert arrange([L] * 4, (1600, 900), "grid").cells == (Cell(0, 0), Cell(0, 1), Cell(1, 0), Cell(1, 1))
    assert arrange([L] * 3, (1600, 900), "row").cells == (Cell(0, 0), Cell(0, 1), Cell(0, 2))
    assert arrange([L] * 2, (960, 1000), "auto").cells == (Cell(0, 0), Cell(1, 0))


def test_two_plus_one_third_spans_both_columns_and_is_fitted_wider() -> None:
    a = arrange([L] * 3, (1000, 800), "grid")
    assert a.cells[2] == Cell(1, 0, 1, 2)
    fitted = displayed_sizes([L] * 3, (1000, 800), a.rows, a.cols, a.cells)
    assert fitted[0] == pytest.approx((497.0, 331.3), abs=0.1)
    assert fitted[2] == pytest.approx((562.5, 375.0), abs=0.1)  # wider than one column: the span counts


def test_auto_score_uses_spans() -> None:
    a = arrange([L] * 3, (1600, 900), "auto")
    fitted = displayed_sizes([L] * 3, (1600, 900), a.rows, a.cols, a.cells)
    assert round(min(w * h for w, h in fitted)) == 270938


def test_minimum_is_measured_on_the_displayed_photo() -> None:
    # 1 × 4 at 580 × 400: box 140.5 × 378 (larger than 120 × 90) but the photo shown is 140.5 × 93.7 → too small
    fitted = displayed_sizes([L] * 4, (580, 400), 1, 4, (Cell(0, 0), Cell(0, 1), Cell(0, 2), Cell(0, 3)))
    assert fitted[0] == pytest.approx((140.5, 93.7), abs=0.1)
    assert arrange([L] * 4, (580, 400), "row").fallback
    assert not arrange([L] * 4, (580, 400), "auto").fallback  # auto never reports a fallback


def test_auto_used_even_when_everything_is_small() -> None:
    a = arrange([L] * 4, (300, 200), "row")  # nothing reaches 160 px: auto's best, flagged as a fallback
    best = arrange([L] * 4, (300, 200), "auto")
    assert a.fallback and (a.rows, a.cols, a.cells) == (best.rows, best.cols, best.cells)
    assert not arrange([L] * 4, (300, 200), "auto").fallback


def test_turned_size_for_90_180_270_and_unknown() -> None:
    assert turned_size(6000, 4000, 0) == (6000, 4000)
    assert turned_size(6000, 4000, 1) == (4000, 6000)
    assert turned_size(6000, 4000, 2) == (6000, 4000)
    assert turned_size(6000, 4000, 3) == (4000, 6000)
    assert turned_size(None, 4000, 1) is None and turned_size(6000, 0, 0) is None


def test_rotation_changes_the_choice() -> None:
    # three landscape photos at 1600 × 900 → 2 + 1; turned to portrait by Xoay xem → one row
    a = arrange([L] * 3, (1600, 900), "auto")
    assert (a.rows, a.cols) == (2, 2)
    turned = arrange([turned_size(6000, 4000, 1)] * 3, (1600, 900), "auto")
    assert (turned.rows, turned.cols) == (1, 3)


def test_unknown_size_counts_as_3_2() -> None:
    assert arrange([None, L], (1600, 900), "auto") == arrange([(3, 2), L], (1600, 900), "auto")


def test_bad_input_is_refused() -> None:
    for n in (0, 1, 5):
        with pytest.raises(ValueError):
            arrange([L] * n, (1600, 900), "auto")
    with pytest.raises(ValueError):
        arrange([L] * 2, (1600, 900), "spiral")  # type: ignore[arg-type]


def test_zero_area_does_not_crash() -> None:
    a = arrange([L] * 3, (0, 0), "grid")  # a page not laid out yet: everything is "too small" → auto, no error
    assert a.fallback and len(a.cells) == 3


def test_start_error_texts() -> None:
    assert start_error(0) == "Đánh dấu 2–4 ảnh (Ctrl+click) rồi bấm C để so sánh."
    assert start_error(1) == "Đánh dấu 2–4 ảnh (Ctrl+click) rồi bấm C để so sánh."
    assert start_error(6) == "Chỉ so sánh được tối đa 4 ảnh — đang đánh dấu 6, hãy bỏ bớt dấu."
    assert start_error(2) is None and start_error(4) is None


def test_initial_active() -> None:
    assert initial_active([5, 7, 9], 7) == 7
    assert initial_active([5, 7, 9], 2) == 5
    assert initial_active([5, 7, 9], None) == 5
