"""Render the main window at the reference sizes of the adaptive layout (offscreen) and save PNGs.

    python scripts/ui_screenshots.py --out <folder>            # all sizes at 100 %
    python scripts/ui_screenshots.py --out <folder> --scale 2   # e.g. 2560×1387 physical = 1280×693 logical

Uses synthetic photos in a temporary folder and a temporary settings file; never touches real photos or the
user's KiraPick data. Sizes are the window's client area in logical pixels (as app.ui.layout_modes expects).
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path

SIZES = [(1920, 1000), (1536, 800), (1280, 667), (960, 1000), (768, 800), (1920, 484), (1280, 323), (580, 400),
         (2560, 683), (2560, 664), (3840, 1024)]
SCALED = [(1280, 693)]  # with --scale 2: 2560×1387 physical


def _photos(folder: Path, n: int = 24) -> None:
    from PIL import Image, ImageDraw

    folder.mkdir(parents=True, exist_ok=True)
    for i in range(n):
        w, h = (1200, 800) if i % 3 else (800, 1200)
        img = Image.new("RGB", (w, h), (40 + (i * 37) % 180, 60 + (i * 53) % 160, 90 + (i * 29) % 140))
        d = ImageDraw.Draw(img)
        d.ellipse((w // 3, h // 4, 2 * w // 3, 3 * h // 4), fill=(220, 190, 170))
        d.rectangle((0, h - 120, w, h), fill=(30, 30, 40))
        exif = Image.Exif()
        exif[0x0132] = f"2026:10:25 16:{i // 6:02d}:{(i * 2) % 60:02d}"
        img.save(folder / f"DSC_{i:04d}.jpg", quality=85, exif=exif)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--scale", type=float, default=1.0)
    args = parser.parse_args()
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    if args.scale != 1.0:
        os.environ["QT_SCALE_FACTOR"] = str(args.scale)
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

    from PySide6.QtCore import QSettings
    from PySide6.QtWidgets import QApplication

    from app.ui import main_window as mw
    from app.ui.theme import apply_dark_theme

    app = QApplication([])
    apply_dark_theme(app)
    tmp = Path(tempfile.mkdtemp(prefix="kirapick-shots-"))
    mw.sessions_dir = lambda: tmp / "sessions"  # never the user's sessions
    _photos(tmp / "photos")
    w = mw.MainWindow(settings=QSettings(str(tmp / "settings.ini"), QSettings.Format.IniFormat))
    w._maximize_on_show = False
    w.resize(1920, 1000)
    w.show()
    w.start_import(tmp / "photos")
    while w.import_thread is not None:
        app.processEvents()
    w.model.wait_for_thumbnails()
    for row, flag in ((0, "keep"), (1, "keep"), (2, "reject"), (4, "keep")):
        w.select_row(row)
        w.set_flag(flag)
    w.select_row(5)
    args.out.mkdir(parents=True, exist_ok=True)
    suffix = f"@{args.scale:g}x" if args.scale != 1.0 else ""

    def settle() -> None:
        for _ in range(3):
            QApplication.processEvents()
            w.layout_controller.evaluate()
            w.model.wait_for_thumbnails()
            QApplication.processEvents()

    for width, height in (SCALED if args.scale != 1.0 else SIZES):
        w.resize(width, height)
        settle()
        name = f"{width}x{height}{suffix}_{w.layout_controller.mode.value}.png"
        w.grab().save(str(args.out / name))
        print(name, w.size().width(), w.size().height())
    # Two states worth seeing: SHORT Detail Focus, NARROW drawer open.
    w.resize(1920, 484)
    settle()
    w.layout_controller.toggle_detail()
    settle()
    w.grab().save(str(args.out / f"1920x484{suffix}_short_detail_focus.png"))
    w.layout_controller.toggle_detail()
    w.resize(960, 1000)
    settle()
    w.layout_controller.open_drawer("people")
    settle()
    w.grab().save(str(args.out / f"960x1000{suffix}_narrow_drawer.png"))
    w.layout_controller.close_drawer()
    w.resize(580, 400)
    settle()
    w.layout_controller.toggle_detail()
    settle()
    w.grab().save(str(args.out / f"580x400{suffix}_tiny_sheet.png"))
    w.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
