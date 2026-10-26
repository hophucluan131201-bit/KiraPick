"""Dark theme: Fusion style + palette + a small stylesheet."""

from __future__ import annotations

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

BG = "#1e1f22"
PANEL = "#26282c"
RAISED = "#2f3237"
TEXT = "#e3e5e8"
MUTED = "#9aa0a6"
ACCENT = "#4c8dff"
KEEP = "#3fb950"
REJECT = "#f85149"
FAVORITE = "#ff7eb6"
STAR = "#f2c94c"
ERROR = "#ff9f43"


def apply_dark_theme(app: QApplication) -> None:
    app.setStyle("Fusion")
    pal = QPalette()
    for role, color in {
        QPalette.ColorRole.Window: BG,
        QPalette.ColorRole.WindowText: TEXT,
        QPalette.ColorRole.Base: PANEL,
        QPalette.ColorRole.AlternateBase: RAISED,
        QPalette.ColorRole.ToolTipBase: RAISED,
        QPalette.ColorRole.ToolTipText: TEXT,
        QPalette.ColorRole.Text: TEXT,
        QPalette.ColorRole.Button: RAISED,
        QPalette.ColorRole.ButtonText: TEXT,
        QPalette.ColorRole.Highlight: ACCENT,
        QPalette.ColorRole.HighlightedText: "#ffffff",
        QPalette.ColorRole.PlaceholderText: MUTED,
        QPalette.ColorRole.Link: ACCENT,
    }.items():
        pal.setColor(role, QColor(color))
    for role in (QPalette.ColorRole.WindowText, QPalette.ColorRole.Text, QPalette.ColorRole.ButtonText):
        pal.setColor(QPalette.ColorGroup.Disabled, role, QColor(MUTED))
    app.setPalette(pal)
    app.setStyleSheet(
        f"""
        QToolBar {{ background: {PANEL}; border: none; spacing: 6px; padding: 4px; }}
        QToolButton {{ padding: 5px 10px; border-radius: 4px; }}
        QToolButton:hover {{ background: {RAISED}; }}
        QStatusBar {{ background: {PANEL}; }}
        QListView, QListWidget, QTableWidget {{ border: none; }}
        QListWidget::item {{ padding: 5px 6px; border-radius: 4px; }}
        QSplitter::handle {{ background: {BG}; }}
        QLabel#sectionTitle {{ color: {MUTED}; font-weight: 600; padding: 8px 4px 2px 4px; }}
        QLabel#emptyHint {{ color: {MUTED}; font-size: 15px; }}
        """
    )
