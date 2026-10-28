"""Right panel: technical and taste scores, one bar + reason per criterion, honest gaps."""

from __future__ import annotations

from app.learning.taste import TasteStatus
from app.quality.rank import rank
from app.quality.score import score
from app.ui.inspector import explain_html

GOOD = {"eye_sharp": 0.7, "face_quality": 0.7, "face_clip": 0.0, "face_luma": 50, "area": 0.3,
        "aesthetic_mos": 5.0, "laion_mos": 6.1}


def test_both_scores_bars_and_reasons() -> None:
    s = score(GOOD)
    html = explain_html(s, rank(s, 85.0, [], 0.5), TasteStatus(True, "Học từ 214 lựa chọn, độ khớp 0,78"), 2)
    assert f"Kỹ thuật {s.total:.0f}/100" in html and "Hợp gu bạn 85/100" in html
    assert "AI chọn (thứ 2)" in html
    assert "█" in html and "nét ở mắt" in html and "TOPIQ 5,0 · LAION 6,1" in html
    assert "Học từ 214 lựa chọn" in html
    assert "Chưa đánh giá" in html and "mắt nhắm/mở" in html  # blink not measured


def test_taste_not_ready_says_why() -> None:
    s = score(GOOD)
    html = explain_html(s, rank(s, None, [], 0.5), TasteStatus(False, "Chưa đủ dữ liệu: 34/60 lựa chọn"))
    assert "Hợp gu bạn: chưa có" in html and "34/60" in html


def test_artistic_exception_and_main_weakness_are_shown() -> None:
    s = score(GOOD | {"blink": 0.9, "style_tags": [["low_key", 0.05]]})
    html = explain_html(s, rank(s, 80.0, s.tags, 0.5), TasteStatus(True, "ok"))
    assert "ngoại lệ nghệ thuật" in html and "Điểm yếu chính" in html


def test_eye_criterion_cannot_be_read_as_eye_sharpness() -> None:
    """Owner, 2.2.0a: "mắt 100" next to "thiếu nét" read as "the eyes are 100 % sharp". The eyes row is
    open/closed; sharpness (measured at the eyes) is its own row."""
    from app.quality.score import LABELS

    assert LABELS["eyes"] == "mắt mở" and LABELS["focus"] == "độ nét"
    html = explain_html(score(GOOD | {"blink": 0.05}), None, None)
    assert "độ nét" in html and "mắt mở" in html
