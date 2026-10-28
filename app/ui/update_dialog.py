"""⚙ Tuỳ chọn → Cập nhật mô hình AI…: the only place KiraPick goes online, and only when asked.

All network work runs in a QThread; the window never waits on it.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import QMessageBox, QProgressDialog, QWidget

from app import __version__
from app.ai.models import ModelRegistry
from app.updates.catalog import HOSTS, CatalogError, Entry, download_catalog, pending_updates
from app.updates.installer import UpdateError, fetch_url, install, rollback, updates_root

log = logging.getLogger(__name__)

PRIVACY = ("KiraPick sẽ kết nối tới GitHub của KiraPick ({hosts}) để tải danh sách mô hình AI đã được "
           "kiểm tra và ký số. Không gửi ảnh, điểm, tên hay bất kỳ dữ liệu nào của bạn.")


class Worker(QThread):
    done = Signal(object)
    failed = Signal(str)
    step = Signal(int, int)

    def __init__(self, fn: Callable[[Callable[[int, int], None]], object], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.fn = fn

    def run(self) -> None:
        try:
            self.done.emit(self.fn(lambda a, b: self.step.emit(a, b)))
        except (CatalogError, UpdateError) as exc:
            self.failed.emit(str(exc))
        except Exception as exc:  # noqa: BLE001 - never crash the app over an update
            log.exception("model update failed")
            self.failed.emit(f"lỗi không mong đợi ({type(exc).__name__})")


class ModelUpdater:
    """Check → confirm → download/verify/activate, with rollback. ``get_catalog``/``fetch`` are swappable for tests."""

    def __init__(self, parent: QWidget, registry: ModelRegistry, *, get_catalog: Callable[[], dict] = download_catalog,
                 fetch=fetch_url, root: Path | None = None) -> None:  # noqa: ANN001
        self.parent, self.registry = parent, registry
        self.get_catalog, self.fetch, self.root = get_catalog, fetch, root or updates_root()
        self.worker: Worker | None = None
        self.result: str | None = None  # last outcome, for the status bar and tests

    def start(self, *, ask: bool = True) -> None:
        if ask:
            sure = QMessageBox.question(self.parent, "Cập nhật mô hình AI",
                                        PRIVACY.format(hosts=", ".join(HOSTS)) + "\n\nKết nối để kiểm tra?")
            if sure != QMessageBox.StandardButton.Yes:
                return
        self._run(lambda _p: pending_updates(self.get_catalog(), self.registry, __version__), self._offer)

    def _run(self, fn, on_done) -> None:  # noqa: ANN001
        self.worker = Worker(fn, self.parent)
        self.worker.done.connect(on_done)
        self.worker.failed.connect(self._failed)
        self.worker.start()

    def _failed(self, message: str) -> None:
        self.result = f"Không cập nhật được: {message}"
        QMessageBox.warning(self.parent, "Cập nhật mô hình AI", self.result + "\nCác mô hình đang dùng không đổi.")

    def _offer(self, pending: list[Entry]) -> None:
        if not pending:
            self.result = "Mô hình AI đã là bản mới nhất."
            box = QMessageBox(QMessageBox.Icon.Information, "Cập nhật mô hình AI", self.result, parent=self.parent)
            back = box.addButton("Quay lại bản trước…", QMessageBox.ButtonRole.ActionRole)
            box.addButton(QMessageBox.StandardButton.Ok)
            back.setEnabled(any((self.root / "active").glob("*.sha256")))
            box.exec()
            if box.clickedButton() is back:
                self.roll_back_all()
            return
        lines = [f"• {e.id} → bản {e.version} ({e.size / 1e6:.0f} MB, giấy phép {e.license})"
                 + (f": {e.notes}" if e.notes else "") for e in pending]
        reanalyse = [e.id for e in pending if not e.embedding_compatible]
        text = "Có bản mới:\n" + "\n".join(lines)
        if reanalyse:
            text += "\n\nSau khi cập nhật cần bấm 📊 Phân tích ảnh lại cho các buổi chụp cũ."
        if QMessageBox.question(self.parent, "Cập nhật mô hình AI", text + "\n\nTải và cài?") \
                != QMessageBox.StandardButton.Yes:
            return
        progress = QProgressDialog("Đang tải mô hình AI…", "", 0, 100, self.parent)
        progress.setCancelButton(None)
        progress.show()

        def work(step: Callable[[int, int], None]) -> list[str]:
            done = []
            for e in pending:
                install(e, self.fetch, step, self.root)
                done.append(f"{e.id} {e.version}")
            return done

        def finished(done: list[str]) -> None:
            progress.close()
            self.result = "Đã cập nhật: " + ", ".join(done) + ". Mở lại buổi chụp để dùng bản mới."
            QMessageBox.information(self.parent, "Cập nhật mô hình AI", self.result)

        self._run(work, finished)
        if self.worker is not None:
            self.worker.step.connect(lambda a, b: progress.setValue(int(a * 100 / b)) if b else None)
            self.worker.failed.connect(lambda _m: progress.close())

    def roll_back_all(self) -> None:
        for sidecar in (self.root / "active").glob("*.sha256"):
            file = sidecar.name[: -len(".sha256")]
            spec = next((s for s in self.registry.specs.values() if s.file == file), None)
            if spec is not None:
                rollback(spec.id, file, self.root)
        self.result = "Đã quay lại bản mô hình trước."
        QMessageBox.information(self.parent, "Cập nhật mô hình AI", self.result)
