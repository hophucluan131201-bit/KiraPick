"""Diagnostic (part 2 Task 8 review CR-P2-FINAL-01): what the Compare tiles receive when the pointer moves, on the
platform Qt runs on (CI: the real `windows` platform). Development tool only; the app never runs it.

    python scripts/diag_compare_hover.py --out diag.jsonl

For each scenario it records the Enter / Leave / MouseMove events reaching the Compare page, the tiles and their
viewers' viewports (with time and position), the active_changed / panel_photo_changed signals, active_id, QCursor.pos(),
the widget under the cursor and the tiles' global geometry. Scenarios: QTest.mouseMove (what the tests use) vs moving
the operating-system cursor with QCursor.setPos, a rapid A→B→C sweep, and a pointer resting over a tile when Compare
opens (F1). One JSON object per line. Synthetic photos in a temporary folder; no real photos, no network.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

    from PIL import Image
    from PySide6.QtCore import QEvent, QObject, QPoint
    from PySide6.QtGui import QCursor, QGuiApplication
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QWidget

    from app.ui.compare_view import CompareView
    from tests.gui.test_compare_tile import _record

    app = QApplication.instance() or QApplication([])
    tmp = Path(tempfile.mkdtemp(prefix="kirapick-diag-"))
    photos = []
    for i in range(3):
        p = tmp / f"IMG_{i:04d}.jpg"
        Image.new("RGB", (1200, 800), (40 + 60 * i, 90, 120)).save(p, quality=80)
        photos.append(p)
    clock = time.perf_counter
    t0 = [clock()]
    events: list[str] = []
    signals: list[str] = []
    out = args.out.open("w", encoding="utf-8")

    view = CompareView()
    names: dict[int, str] = {}

    def name_of(obj: QObject) -> str | None:
        return names.get(id(obj))

    class Spy(QObject):
        kinds = {QEvent.Type.Enter: "Enter", QEvent.Type.Leave: "Leave", QEvent.Type.MouseMove: "Move",
                 QEvent.Type.HoverEnter: "HEnter", QEvent.Type.HoverMove: "HMove", QEvent.Type.HoverLeave: "HLeave"}

        def eventFilter(self, obj: QObject, event: QEvent) -> bool:  # noqa: N802 - Qt override
            kind = self.kinds.get(event.type())
            if kind is not None:
                who = name_of(obj)
                if who is not None:
                    pos = ""
                    if hasattr(event, "position"):
                        p = event.position()
                        pos = f"@{int(p.x())},{int(p.y())}"
                    spont = "s" if event.spontaneous() else "n"
                    events.append(f"{(clock() - t0[0]) * 1000:.0f}:{kind}{spont}:{who}{pos}")
            return False

    spy = Spy()
    app.installEventFilter(spy)
    view.active_changed.connect(lambda i: signals.append(f"{(clock() - t0[0]) * 1000:.0f}:active={i}"))
    view.panel_photo_changed.connect(lambda i: signals.append(f"{(clock() - t0[0]) * 1000:.0f}:panel={i}"))

    def label_widgets() -> None:
        names.clear()
        names[id(view.page)] = "page"
        names[id(view.back_button)] = "back"
        for tile in view.tiles:
            if tile.asset_id is not None:
                names[id(tile)] = f"tile{tile.asset_id}"
                names[id(tile.viewer.viewport())] = f"vp{tile.asset_id}"
                names[id(tile.viewer)] = f"viewer{tile.asset_id}"

    def centre(w: QWidget) -> QPoint:
        return w.mapToGlobal(w.rect().center())

    def under() -> str:
        w = QApplication.widgetAt(QCursor.pos())
        return f"{type(w).__name__}:{name_of(w) or (w.objectName() if w else '')}" if w else "None"

    def record(scenario: str, note: str = "") -> None:
        tiles = {f"tile{t.asset_id}": [t.mapToGlobal(QPoint(0, 0)).x(), t.mapToGlobal(QPoint(0, 0)).y(), t.width(),
                                        t.height()] for t in view.tiles if t.asset_id is not None and t.isVisible()}
        screen = QGuiApplication.primaryScreen()
        line = {"scenario": scenario, "note": note, "platform": QGuiApplication.platformName(),
                "active_id": view.active_id, "armed": getattr(view, "_armed", None),
                "cursor": [QCursor.pos().x(), QCursor.pos().y()], "under_cursor": under(),
                "window_active": view.isActiveWindow(), "window": [view.x(), view.y(), view.width(), view.height()],
                "screen": [screen.geometry().width(), screen.geometry().height()] if screen else None,
                "tiles": tiles, "signals": list(signals), "events": list(events)}
        out.write(json.dumps(line, ensure_ascii=False) + "\n")
        out.flush()
        print(scenario, note, "active", view.active_id, "cursor", line["cursor"], "under", line["under_cursor"],
              "events", len(events))

    def reset(active: int = 1) -> None:
        view.clear()
        QApplication.processEvents()
        recs = [_record(p, asset_id=i + 1) for i, p in enumerate(photos)]
        view.show_records(recs, {}, active)
        label_widgets()
        QApplication.processEvents()
        events.clear()
        signals.clear()
        t0[0] = clock()

    def settle(ms: int) -> None:
        QTest.qWait(ms)

    view.resize(1500, 700)
    view.move(40, 40)
    view.show()
    view.raise_()
    view.activateWindow()
    QTest.qWaitForWindowExposed(view)
    QTest.qWaitForWindowActive(view, 2000)
    settle(200)

    # S1: what the tests do (QTest.mouseMove: back button, then tile 2's viewport).
    reset()
    QTest.mouseMove(view.back_button, view.back_button.rect().center())
    vp = view.tile(2).viewer.viewport()
    QTest.mouseMove(vp, vp.rect().center())
    record("S1_qtest_mouseMove", "immediately")
    settle(250)
    record("S1_qtest_mouseMove", "after 250 ms")

    # S2: the operating-system cursor (QCursor.setPos), as a real mouse would move.
    reset()
    QCursor.setPos(centre(view.back_button))
    settle(150)
    QCursor.setPos(centre(view.tile(2).viewer.viewport()))
    record("S2_os_cursor", "immediately")
    settle(250)
    record("S2_os_cursor", "after 250 ms")

    # S3: rapid sweep A→B→C with the OS cursor (30 ms apart), then 250 ms.
    reset()
    QCursor.setPos(centre(view.back_button))
    settle(150)
    for asset_id in (1, 2, 3):
        QCursor.setPos(centre(view.tile(asset_id).viewer.viewport()))
        settle(30)
    record("S3_os_cursor_sweep", "after the sweep")
    settle(250)
    record("S3_os_cursor_sweep", "after 250 ms")

    # S4 (F1): OS cursor resting over tile 3 while Compare opens with tile 1 active; then a 1-px real move.
    view.clear()
    QApplication.processEvents()
    QCursor.setPos(centre(view.page))
    settle(150)
    reset(active=1)
    QCursor.setPos(centre(view.tile(3).viewer.viewport()))
    settle(150)
    view.clear()
    QApplication.processEvents()
    reset(active=1)  # pointer already resting over where tile 3 is shown
    settle(250)
    record("S4_resting_pointer", "opened under a resting pointer (must stay 1)")
    QCursor.setPos(QCursor.pos() + QPoint(1, 1))
    settle(250)
    record("S4_resting_pointer", "after a 1 px real move (expect 3)")

    # S5: QTest.mouseMove after the OS cursor is parked over the back button (does the real cursor interfere?).
    reset()
    QCursor.setPos(centre(view.back_button))
    settle(150)
    events.clear()
    vp = view.tile(2).viewer.viewport()
    QTest.mouseMove(vp, vp.rect().center())
    settle(250)
    record("S5_qtest_with_cursor_parked", "after 250 ms")
    view.close()

    # S6: as the tests do — a new top-level CompareView per test, shown where the platform puts it (no move), 25 times.
    app.removeEventFilter(spy)
    runs = []
    for n in range(25):
        v = CompareView()
        v.resize(1600, 900)
        v.show()
        QTest.qWait(150)  # shown and placed by the platform
        v.show_records([_record(p, asset_id=i + 1) for i, p in enumerate(photos)], {}, 1)
        QApplication.processEvents()
        QTest.mouseMove(v.back_button, v.back_button.rect().center())
        target = v.tile(2).viewer.viewport()
        goal = target.mapToGlobal(target.rect().center())
        QTest.mouseMove(target, target.rect().center())
        QApplication.processEvents()
        frame = v.frameGeometry()
        runs.append(f"{n}:win@{frame.x()},{frame.y()} goal@{goal.x()},{goal.y()} cur@{QCursor.pos().x()},"
                    f"{QCursor.pos().y()} active={v.active_id}")
        v.wait_idle(10000)  # never destroy a view whose pools still decode (the pool waits while Python holds the GIL)
        v.close()
        v.deleteLater()
        QApplication.processEvents()
    avail = QGuiApplication.primaryScreen().availableGeometry() if QGuiApplication.primaryScreen() else None
    out.write(json.dumps({"scenario": "S6_new_window_per_test", "available": [avail.x(), avail.y(), avail.width(),
                          avail.height()] if avail else None, "runs": runs}, ensure_ascii=False) + "\n")
    print("S6", runs[0], runs[-1])
    out.close()
    return 0


if __name__ == "__main__":
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    raise SystemExit(main())
