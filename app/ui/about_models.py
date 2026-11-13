"""Tuỳ chọn → Giới thiệu → Mô hình và giấy phép: the only screen that names models, files and licences.

Two tabs built from app.ai.features: what each function runs on and what the user gets without it; every weight with
its file, SHA-256, source, licence and status in this build. The installer still carries the full notices
(docs\\THIRD_PARTY_NOTICES.md, docs\\licenses\\).
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app import __version__
from app.ai import features as ft
from app.ai.models import ModelRegistry
from app.branding import APP_NAME


def _table(headers: list[str], rows: list[list[str]]) -> QTableWidget:
    t = QTableWidget(len(rows), len(headers))
    t.setHorizontalHeaderLabels(headers)
    t.verticalHeader().setVisible(False)
    t.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    t.setWordWrap(True)
    for r, row in enumerate(rows):
        for c, text in enumerate(row):
            item = QTableWidgetItem(text)
            item.setToolTip(text)
            t.setItem(r, c, item)
    t.horizontalHeader().setStretchLastSection(True)
    t.resizeColumnsToContents()
    t.resizeRowsToContents()
    return t


class ModelsDialog(QDialog):
    def __init__(self, parent: QWidget | None = None, registry: ModelRegistry | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Giới thiệu {APP_NAME} — Mô hình và giấy phép")
        self.resize(1100, 620)
        rows = ft.model_rows(registry)
        by_id = {r.model_id: r for r in rows}
        names = {r.model_id: r.name for r in rows}
        self.features = _table(
            ["Chức năng", "Chế độ", "Chạy bằng", "Trong bản này", "Khi tắt hoặc thiếu"],
            [[f.name, f.modes, ", ".join(names.get(m, m) for m in f.models) or f.rule,
              ft.feature_status(f, by_id), f.without or "—"] for f in ft.FEATURES])
        self.models = _table(
            ["Mô hình", "File", "SHA-256", "Nguồn", "Giấy phép", "Trong bản này", "Căn cứ",
             "Đo nội bộ (máy phát triển)"],
            [[r.name, r.file, r.sha256 or "—", r.source, r.licence, r.status, r.terms, r.benchmark] for r in rows])
        tabs = QTabWidget()
        tabs.addTab(self.features, "Chức năng")
        tabs.addTab(self.models, "Mô hình và giấy phép")
        note = QLabel(f"{APP_NAME} {__version__}. Chỉ những file đã kiểm mã SHA-256 và có căn cứ sử dụng mới được mở; "
                      "file \"chờ xác minh\" không bao giờ được mở, dù có trên máy. Toàn văn giấy phép và thông báo của "
                      "từng thành phần: thư mục cài đặt → docs\\THIRD_PARTY_NOTICES.md và docs\\licenses\\.")
        note.setWordWrap(True)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        box = QVBoxLayout(self)
        box.addWidget(note)
        box.addWidget(tabs, 1)
        box.addWidget(buttons)
