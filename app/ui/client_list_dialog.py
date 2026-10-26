"""Dialog: paste a client's pick list, check what matched, save it as a list."""

from __future__ import annotations

from datetime import datetime
from html import escape
from pathlib import PurePosixPath

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.selection.client_list import (
    MatchResult,
    NamePattern,
    detect_pattern,
    match_assets,
    parse_client_text,
    save_collection,
)
from app.storage import decisions
from app.storage.project import Project
from app.ui import theme


class ClientListDialog(QDialog):
    def __init__(self, project: Project, parent: QWidget | None = None, *, source_id: int | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Danh sách ảnh khách chọn")
        self.resize(720, 640)
        self.project = project
        self.result: MatchResult | None = None
        self.collection_id: int | None = None

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            "Dán nguyên tin nhắn của khách vào ô dưới. Ví dụ: <i>9645, 9646, 9657-9660, DSC_9665.jpg</i><br>"
            "Hiểu được: số lẻ, khoảng (9657-9660, 9657 đến 9660, 9645-50), tên đầy đủ có/không đuôi file."
        ))
        self.text = QPlainTextEdit()
        self.text.setPlaceholderText("Dán danh sách khách gửi vào đây…")
        layout.addWidget(self.text, 1)

        form = QFormLayout()
        self.name = QLineEdit(f"Khách chọn {datetime.now():%d/%m %H:%M}")
        form.addRow("Tên danh sách", self.name)
        stems = [PurePosixPath(r[0]).stem for r in project.conn.execute(
            "SELECT relative_path FROM assets WHERE status NOT IN ('missing','duplicate')")]
        self.pattern = QLineEdit(detect_pattern(stems))
        self.pattern.setToolTip("Mỗi dấu # là một chữ số. Ví dụ DSC_#### : 9645 → DSC_9645, 12 → DSC_0012")
        self.example = QLabel()
        form.addRow("Cấu trúc tên file", self.pattern)
        form.addRow("", self.example)
        self.scope = QComboBox()
        self.scope.addItem("Tất cả thư mục trong dự án", None)
        for r in project.conn.execute("SELECT id, root_path FROM sources ORDER BY id"):
            self.scope.addItem(PurePosixPath(r["root_path"].replace("\\", "/")).name, r["id"])
        if source_id is not None:
            self.scope.setCurrentIndex(max(0, self.scope.findData(source_id)))
        form.addRow("Tìm trong", self.scope)
        self.mark_keep = QCheckBox("Đồng thời đánh dấu Giữ (K) cho các ảnh này")
        form.addRow("", self.mark_keep)
        layout.addLayout(form)

        self.report = QLabel()
        self.report.setWordWrap(True)
        layout.addWidget(self.report)

        buttons = QDialogButtonBox()
        self.create_button = buttons.addButton("Tạo danh sách", QDialogButtonBox.ButtonRole.AcceptRole)
        buttons.addButton("Huỷ", QDialogButtonBox.ButtonRole.RejectRole)
        self.create_button.clicked.connect(self.create)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._debounce = QTimer(self, singleShot=True, interval=250)
        self._debounce.timeout.connect(self.refresh)
        self.text.textChanged.connect(self._debounce.start)
        self.pattern.textChanged.connect(self._debounce.start)
        self.scope.currentIndexChanged.connect(self.refresh)
        self.refresh()

    def done(self, result: int) -> None:  # noqa: D401 - Qt override
        self._debounce.stop()  # never touch the database after the dialog is closed
        super().done(result)

    def refresh(self) -> None:
        pattern = NamePattern.parse(self.pattern.text())
        self.example.setText(f"<span style='color:{theme.MUTED}'>Ví dụ: 9645 → {escape(pattern.stem_for('9645'))}</span>")
        parsed = parse_client_text(self.text.toPlainText(), pattern)
        self.result = match_assets(self.project.conn, parsed, source_id=self.scope.currentData())
        r = self.result
        found = len(r.matched)
        total = len(parsed.stems)
        lines = []
        if not total:
            lines.append("Chưa đọc được số/tên ảnh nào.")
        else:
            lines.append(f"<b>Tìm thấy {found}/{total} ảnh khách chọn.</b>")
        if r.unmatched:
            shown = ", ".join(escape(s) for s in r.unmatched[:40]) + (" …" if len(r.unmatched) > 40 else "")
            lines.append(f"<span style='color:{theme.REJECT}'>Không có ảnh nào tên: {shown}</span> "
                         "— kiểm tra lại với khách hoặc sửa cấu trúc tên.")
        if r.ambiguous:
            amb = ", ".join(f"{escape(s)} ({len(ids)} ảnh)" for s, ids in list(r.ambiguous.items())[:20])
            lines.append(f"<span style='color:{theme.ERROR}'>Trùng tên ở nhiều thư mục, đã chọn tất cả: {amb}</span> "
                         "— chọn một thư mục ở mục “Tìm trong” nếu cần.")
        if parsed.ignored:
            lines.append(f"<span style='color:{theme.MUTED}'>Bỏ qua: {escape(', '.join(parsed.ignored[:20]))}</span>")
        self.report.setText("<br>".join(lines))
        self.create_button.setEnabled(found > 0)
        self.create_button.setText(f"Tạo danh sách ({len(r.asset_ids)} ảnh)" if found else "Tạo danh sách")

    def create(self) -> None:
        self._debounce.stop()
        self.refresh()
        if self.result is None or not self.result.matched:
            return
        with self.project.transaction() as conn:
            self.collection_id = save_collection(
                conn, self.name.text(), self.result, source_text=self.text.toPlainText(),
                pattern=NamePattern.parse(self.pattern.text()),
            )
            if self.mark_keep.isChecked():
                for asset_id in self.result.asset_ids:
                    decisions.set_flag(conn, asset_id, "keep")
        self.accept()
