"""Render the main window at the reference sizes of the adaptive layout (offscreen) and save PNGs.

    python scripts/ui_screenshots.py --out <folder>            # all sizes at 100 %
    python scripts/ui_screenshots.py --out <folder> --scale 2   # e.g. 2560×1387 physical = 1280×693 logical
    python scripts/ui_screenshots.py --out <folder> --compare   # Compare (part 2) with 2, 3 and 4 photos
    python scripts/ui_screenshots.py --out <folder> --export    # Export dialog (part 3) at the five layout modes

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
COMPARE_SIZES = [(1920, 1000), (1280, 667), (960, 1000), (1920, 484), (580, 400)]  # WIDE MEDIUM NARROW SHORT TINY


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


def _compare_shots(w, out: Path, suffix: str, settle) -> None:  # noqa: ANN001
    """Compare with 2 / 3 / 4 marked photos at the five layout modes (AI line on, one tile zoomed to 100 %)."""
    from PySide6.QtCore import QItemSelectionModel
    from PySide6.QtWidgets import QApplication

    def ready() -> None:
        tiles = [w.compare.tile(r.id) for r in w.compare.records()]
        for _ in range(500):
            QApplication.processEvents()
            if all(t.viewer.source_label for t in tiles):
                break
        w.compare.wait_idle(10_000)
        QApplication.processEvents()

    for count in (2, 3, 4):
        w.leave_compare()
        w.resize(1920, 1000)
        settle()
        sel = w.grid.selectionModel()
        sel.clearSelection()
        for row in range(count):
            sel.select(w.model.index(row), QItemSelectionModel.SelectionFlag.Select)
        assert w.show_compare()
        if not w.compare.ai_visible:
            w.toggle_compare_ai()
        for width, height in COMPARE_SIZES:
            w.resize(width, height)
            settle()
            ready()
            name = f"compare{count}_{width}x{height}{suffix}_{w.layout_controller.mode.value}.png"
            w.grab().save(str(out / name))
            print(name)
    w.resize(1920, 1000)
    settle()
    first = w.compare.tile(w.compare.records()[0].id)
    first.viewer.set_zoom(1.0)
    ready()
    w.grab().save(str(out / f"compare4_1920x1000{suffix}_zoom100.png"))


def _card(tmp: Path) -> Path:
    """Another folder for the export: two kept JPEGs (content matches) and two RAW stand-ins for DSC_0004 within
    2 s of its capture time (an unsure match the user confirms)."""
    import shutil

    from PIL import Image

    card = tmp / "Thẻ nhớ" / "DCIM"
    (card / "100NIKON").mkdir(parents=True)
    for name in ("DSC_0000.jpg", "DSC_0001.jpg"):
        shutil.copy2(tmp / "photos" / name, card / "100NIKON" / name)
    for folder, second in (("100NIKON", "09"), ("101NIKON", "07")):
        (card / folder).mkdir(exist_ok=True)
        exif = Image.Exif()
        exif.get_ifd(0x8769)[0x9003] = f"2026:10:25 16:00:{second}"
        Image.new("RGB", (16, 16), (9, 9, 9)).save(card / folder / "DSC_0004.NEF", "TIFF", exif=exif.tobytes())
    return card.parent


def _export_shots(w, tmp: Path, out: Path, suffix: str, settle) -> None:  # noqa: ANN001
    """The export dialog over the window at WIDE / MEDIUM / NARROW / SHORT / TINY: imported preview, another folder
    with an unsure match to confirm, and the names tab."""
    from PySide6.QtWidgets import QApplication, QMessageBox

    QMessageBox.information = lambda *a, **k: None  # type: ignore[method-assign]
    card = _card(tmp)
    names = ["wide", "medium", "narrow", "short", "tiny"]
    for (width, height), mode in zip(COMPARE_SIZES, names):
        w.resize(width, height)
        settle()
        dialog = w.open_export_dialog()
        dialog.resize(min(880, width - 20), min(700, height - 20))
        dialog.dest.setText(str(tmp / "Xuất"))
        dialog.source_imported.setChecked(True)
        dialog.refresh()
        for _ in range(5):
            QApplication.processEvents()
        dialog.grab().save(str(out / f"export_{mode}_{width}x{height}{suffix}_imported.png"))
        dialog.external_path.setText(str(card))
        dialog.source_external.setChecked(True)
        for _ in range(2000):
            QApplication.processEvents()
            if dialog.plan is not None and not dialog.scanning:
                break
        dialog.preview_tabs.setCurrentIndex(1)
        dialog.scroll.verticalScrollBar().setValue(dialog.scroll.verticalScrollBar().maximum())
        QApplication.processEvents()
        dialog.grab().save(str(out / f"export_{mode}_{width}x{height}{suffix}_external_review.png"))
        dialog.tabs.setCurrentWidget(dialog.names_tab)
        QApplication.processEvents()
        dialog.grab().save(str(out / f"export_{mode}_{width}x{height}{suffix}_names.png"))
        print(mode, dialog.size().width(), dialog.size().height())
        dialog._cancel_plans()
        for t in dialog._plan_threads:
            t.wait()
        dialog.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--scale", type=float, default=1.0)
    parser.add_argument("--compare", action="store_true", help="Compare screenshots instead of the grid ones")
    parser.add_argument("--export", action="store_true", help="Export dialog screenshots instead of the grid ones")
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

    if args.compare:
        _compare_shots(w, args.out, suffix, settle)
        w.close()
        return 0
    if args.export:
        _export_shots(w, tmp, args.out, suffix, settle)
        w.close()
        return 0
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
