"""Applies the layout mode (app.ui.layout_modes) to the main window, without ever moving a widget to another parent.

Body: [icon rail][QSplitter: sidebar slot | grid area | detail slot]. The sidebar and the detail panel are children
of the body for their whole life and are placed by ``Placement`` (docked over their slot, or floating as a drawer /
sheet). Per mode:

- WIDE / MEDIUM: sidebar and details docked; Tab (``toggle_detail``) shows/hides the details.
- NARROW: sidebar as a drawer (icon rail + "☰"), details docked from 900 px, a sheet below; Tab shows/hides them
  (remembered: ``layout/narrow_detail_visible``).
- SHORT: splitter vertical (grid above, details below, detail panel laid out horizontally); Grid Focus = details
  hidden + a one-line strip about the current photo; Detail Focus = the grid as one row + details
  (remembered: ``layout/short_focus`` in {"grid", "detail"}).
- TINY: grid only; sidebar drawer and detail sheet on demand.

Splitter sizes are remembered per mode (``splitter/<mode>``). A resize is evaluated 120 ms after it settles; a change
of screen (DPI) is evaluated at once. Layout never touches the worker/shutdown machinery (app.ui.shutdown).
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, QPoint, QSettings, Qt, QTimer
from PySide6.QtWidgets import QAbstractItemView, QLabel, QListView, QSplitter, QWidget

from app.ui.layout_modes import (
    DEBOUNCE_MS,
    MIN_WINDOW,
    NARROW_W,
    Mode,
    client_size,
    detail_docked,
    detail_visible_default,
    mode_for,
)
from app.ui.overlay import Placement, Scrim

FOOTER = 40  # grid card caption (app.ui.grid.FOOTER)
SHORT_KEY, NARROW_KEY = "layout/short_focus", "layout/narrow_detail_visible"
QT_MAX = 16777215


class LayoutController(QObject):
    def __init__(self, window: QWidget, *, body: QWidget, sidebar: QWidget, side_slot: QWidget, rail: QWidget,
                 drawer_button: QWidget, splitter: QSplitter, grid_area: QWidget, grid: QListView,
                 detail: QWidget, detail_slot: QWidget, strip: QLabel, top_bar: QWidget, bottom_bar: QWidget,
                 settings: QSettings, model: QObject | None = None) -> None:
        super().__init__(window)
        self.body, self.sidebar, self.rail = body, sidebar, rail  # the window is our Qt parent (no ref cycle)
        self.drawer_button, self.splitter, self.grid_area, self.grid = drawer_button, splitter, grid_area, grid
        self.detail, self.detail_slot, self.side_slot, self.strip = detail, detail_slot, side_slot, strip
        self.top_bar, self.bottom_bar, self.settings, self.model = top_bar, bottom_bar, settings, model
        self.scrim = Scrim(body)  # one for both: whatever floats is above it, every docked panel below it
        self.side = Placement(body, sidebar, side_slot, side=Qt.Edge.LeftEdge, scrim=self.scrim,
                              sheet_width=lambda w: min(320, w - 40))
        self.sheet = Placement(body, detail, detail_slot, side=Qt.Edge.RightEdge, scrim=self.scrim,
                               sheet_width=lambda w: min(380, max(260, int(w * 0.6))))
        self.scrim.clicked.connect(self.close_floating)  # like Escape
        self.mode: Mode | None = None
        self.docked: bool | None = None
        self._choice: dict[Mode, bool] = {}  # Tab choice per mode, in memory (SHORT / NARROW also in settings)
        short = settings.value(SHORT_KEY, None)
        if short in ("grid", "detail"):
            self._choice[Mode.SHORT] = short == "detail"
        narrow = settings.value(NARROW_KEY, None)
        if narrow is not None:
            self._choice[Mode.NARROW] = str(narrow).lower() in ("true", "1")
        self._cell: int | None = None  # grid cell before SHORT Detail Focus shrank it
        self._timer = QTimer(self, singleShot=True, interval=DEBOUNCE_MS)
        self._timer.timeout.connect(self.evaluate)
        window.setMinimumSize(*MIN_WINDOW)
        window.installEventFilter(self)
        splitter.splitterMoved.connect(lambda *_a: self._save_sizes())

    @property
    def window(self) -> QWidget:
        return self.parent()  # type: ignore[return-value]

    # ------------------------------------------------------------------ API
    def evaluate(self) -> None:
        width, height = client_size(self.window)
        mode = mode_for(width, height, self.mode)
        docked = detail_docked(mode, width, self.docked)
        if mode is not self.mode or docked != self.docked:
            self.apply(mode, docked)

    def apply(self, mode: Mode, docked: bool | None = None) -> None:
        width = client_size(self.window)[0]
        docked = detail_docked(mode, width, self.docked) if docked is None else docked
        top = self._top_index()
        if self.mode is not None:
            self._save_sizes()
        self.mode, self.docked = mode, docked
        self.side.close()
        self.sheet.close()
        self.splitter.setOrientation(Qt.Orientation.Vertical if mode is Mode.SHORT else Qt.Orientation.Horizontal)
        self.detail.set_horizontal(mode is Mode.SHORT)  # type: ignore[attr-defined]
        side_docked = mode in (Mode.WIDE, Mode.MEDIUM)
        self.side_slot.setVisible(side_docked)
        (self.side.dock if side_docked else self.side.float)()
        self.rail.setVisible(mode is Mode.NARROW)
        self.drawer_button.setVisible(not side_docked)
        compact = mode is Mode.TINY or width < NARROW_W  # by width: a wide SHORT strip has room for full bars
        room = getattr(self.window, "set_key_hints_room", None)
        if room is not None:
            room(mode not in (Mode.SHORT, Mode.TINY))
        self.top_bar.set_compact(compact)  # type: ignore[attr-defined]
        self.bottom_bar.set_compact(compact)  # type: ignore[attr-defined]
        self._show_detail(self.detail_visible())
        self._restore_sizes()
        self._restore_top(top)

    def detail_visible(self) -> bool:
        assert self.mode is not None
        return self._choice.get(self.mode, detail_visible_default(self.mode, client_size(self.window)[0]))

    def toggle_detail(self) -> None:
        """Tab: SHORT switches Grid Focus ↔ Detail Focus; elsewhere shows/hides the details (a sheet opens/closes)."""
        if self.mode is None:
            return
        on = not (self.sheet.is_open if not self.docked else self.detail_visible())
        self._choice[self.mode] = on
        if self.mode is Mode.SHORT:
            self.settings.setValue(SHORT_KEY, "detail" if on else "grid")
        elif self.mode is Mode.NARROW:
            self.settings.setValue(NARROW_KEY, on)
        top = self._top_index()
        self._show_detail(on)
        self._restore_top(top)

    def open_drawer(self, section: str | None = None) -> None:
        """The sidebar over the grid (NARROW / SHORT / TINY); ``section`` is opened and scrolled into view."""
        if self.side.docked:
            return
        self.sheet.close()
        self.side.open()
        if section is not None:
            open_section = getattr(self.window, "open_sidebar_section", None)
            if open_section is not None:
                open_section(section)

    def close_drawer(self) -> None:
        self.side.close()

    def close_floating(self) -> bool:
        """Escape: close an open drawer or sheet; False when nothing was open (Escape then does its usual job)."""
        was_open = self.side.is_open or self.sheet.is_open
        self.side.close()
        self.sheet.close()
        if was_open and self.mode is not None and not self.docked:
            self._choice[self.mode] = False  # the sheet stays closed until Tab / ▤ opens it again
        return was_open

    def on_screen_changed(self, screen: object) -> None:
        """New screen or scale: thumbnails at the new pixel ratio, then the mode for the new logical size."""
        ratio = float(screen.devicePixelRatio()) if screen is not None else 1.0  # type: ignore[attr-defined]
        set_ratio = getattr(self.model, "set_device_pixel_ratio", None)
        if set_ratio is not None:
            set_ratio(ratio)
        self.evaluate()

    # ------------------------------------------------------------- helpers
    def _show_detail(self, on: bool) -> None:
        assert self.mode is not None
        short = self.mode is Mode.SHORT
        self.strip.setVisible(short and not on)
        self._one_row(short and on)
        if self.docked:
            self.detail_slot.setVisible(on)
            self.sheet.dock()
        else:
            self.detail_slot.setVisible(False)
            self.sheet.float()
            if on:
                self.side.close()
                self.sheet.open()

    def _one_row(self, on: bool) -> None:
        """SHORT Detail Focus: the grid becomes one row of small cards above the details."""
        delegate = self.grid.itemDelegate()
        if on:
            if self._cell is None:
                self._cell = int(getattr(delegate, "cell", 0))
            # One row of cards readable at a glance (tick box, chip and name need ≥ 96 px), at most ~40 % height.
            cell = max(96, min(self._cell, int(self.body.height() * 0.4) - FOOTER - 8))
            row = cell + FOOTER + 8
            delegate.cell = cell  # type: ignore[attr-defined]
            self.grid.setWrapping(False)
            self.grid.setFlow(QListView.Flow.LeftToRight)
            self.grid_area.setMaximumHeight(row + self._chrome())
        else:
            if self._cell is not None:
                delegate.cell = self._cell  # type: ignore[attr-defined]
                self._cell = None
            self.grid.setWrapping(True)
            self.grid_area.setMaximumHeight(QT_MAX)
        self.grid.doItemsLayout()

    def _chrome(self) -> int:
        """Height of the grid area that is not the grid (header row, key hints)."""
        return max(0, self.grid_area.sizeHint().height() - self.grid.sizeHint().height()) + 8

    def _key(self) -> str:
        assert self.mode is not None
        return f"splitter/{self.mode.value}" + ("" if self.docked else "-sheet")

    def _save_sizes(self) -> None:
        if self.mode is not None:
            self.settings.setValue(self._key(), [int(s) for s in self.splitter.sizes()])

    def _restore_sizes(self) -> None:
        saved = self.settings.value(self._key(), None)
        sizes = [int(s) for s in saved] if isinstance(saved, (list, tuple)) and len(saved) == 3 else None
        if sizes is None or sum(sizes) <= 0:
            sizes = self._default_sizes()
        self.splitter.setSizes(sizes)

    def _default_sizes(self) -> list[int]:
        width, height = client_size(self.window)
        if self.mode is Mode.SHORT:
            return [0, max(1, int(height * 0.3)), max(1, int(height * 0.7))]
        left = max(210, min(280, int(width * 0.2))) if self.side_slot.isVisibleTo(self.body) else 0
        right = max(260, min(380, int(width * 0.24))) if self.detail_slot.isVisibleTo(self.body) else 0
        return [left, max(200, width - left - right), right]

    def _top_index(self) -> object:
        return self.grid.indexAt(QPoint(8, 8))  # the first card at the top-left of the grid

    def _restore_top(self, top: object) -> None:
        """The photo at the top-left before the change stays at the top, and the current photo stays in view.
        The splitter and the grid are laid out first, at once (the grid normally lays out in batches, so a scroll
        right after a change would land on positions that are not computed yet)."""
        self.splitter.refresh()
        layout = self.body.layout()
        if layout is not None:
            layout.activate()
        mode = self.grid.layoutMode()
        self.grid.setLayoutMode(QListView.LayoutMode.SinglePass)
        self.grid.doItemsLayout()
        index = top if getattr(top, "isValid", lambda: False)() else self.grid.currentIndex()
        if index.isValid():  # type: ignore[attr-defined]
            self.grid.scrollTo(index, QAbstractItemView.ScrollHint.PositionAtTop)  # type: ignore[arg-type]
        current = self.grid.currentIndex()
        if current.isValid():
            self.grid.scrollTo(current, QAbstractItemView.ScrollHint.EnsureVisible)
        self.grid.setLayoutMode(mode)

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:  # noqa: N802 - Qt override
        if obj is self.window and event.type() == QEvent.Type.Resize:
            self._timer.start()
        return False
