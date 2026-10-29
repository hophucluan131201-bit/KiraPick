"""Print what Qt sees on this machine (platform, screens, default font, text widths) as one line: used by the
Windows CI job to tell real-platform results from offscreen ones. Development tool, not shipped."""

from __future__ import annotations

import json
import sys


def main() -> int:
    from PySide6.QtGui import QFontMetrics
    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv[:1])
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from app.ui.theme import apply_dark_theme

    apply_dark_theme(app)
    font = app.font()
    fm = QFontMetrics(font)
    samples = ["⚙ Tuỳ chọn", "✓ Chọn", "🧠 Nhận diện chủ thể", "Phân tích AI", "Thông tin ảnh"]
    report = {
        "platform": app.platformName(),
        "screens": [{"size": s.size().toTuple(), "available": s.availableGeometry().size().toTuple(),
                     "dpr": s.devicePixelRatio(), "logical_dpi": round(s.logicalDotsPerInch(), 1)}
                    for s in app.screens()],
        "font": f"{font.family()} {font.pointSizeF()} pt / {fm.height()} px high",
        "advance_px": {t: fm.horizontalAdvance(t) for t in samples},
    }
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
