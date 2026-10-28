"""⚙ Tuỳ chọn → Cập nhật KiraPick: the only place KiraPick goes online, and only when asked.

All network work runs in a QThread; the window never waits on it.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import QMessageBox, QProgressDialog, QWidget

from app import __version__
from app.branding import data_dir
from app.edition import EDITION
from app.updates.app_update import (
    HOSTS,
    Release,
    UpdateError,
    download,
    fetch_url,
    list_releases,
    newest_release,
    start_installer,
)

log = logging.getLogger(__name__)

PRIVACY = ("KiraPick sẽ kết nối tới GitHub ({hosts}) để xem có bản mới không, và nếu bạn đồng ý thì tải bộ cài "
           "về (được kiểm tra mã SHA-256). Không gửi ảnh, điểm, tên hay bất kỳ dữ liệu nào của bạn.")


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
        except UpdateError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:  # noqa: BLE001 - never crash the app over an update
            log.exception("app update failed")
            self.failed.emit(f"lỗi không mong đợi ({type(exc).__name__})")


class AppUpdater:
    """Check → confirm → download + SHA-256 → start the installer and close. Network/IO swappable for tests."""

    def __init__(self, parent: QWidget, *, get_releases: Callable[[], list[dict]] | None = None,
                 fetch=fetch_url, folder: Path | None = None,  # noqa: ANN001
                 start: Callable[[Path], None] = start_installer, close: Callable[[], object] | None = None) -> None:
        self.parent = parent
        self.get_releases = get_releases or (lambda: list_releases())
        self.fetch, self.start = fetch, start
        self.folder = folder or data_dir() / "update"
        self.close = close or parent.close
        self.worker: Worker | None = None
        self.result: str | None = None  # last outcome, for the status bar and tests

    def check(self, *, ask: bool = True) -> None:
        if ask:
            sure = QMessageBox.question(self.parent, "Cập nhật KiraPick",
                                        PRIVACY.format(hosts=", ".join(HOSTS)) + "\n\nKiểm tra bản mới?")
            if sure != QMessageBox.StandardButton.Yes:
                return
        self._run(lambda _p: newest_release(self.get_releases(), EDITION, __version__), self._offer)

    def _run(self, fn, on_done) -> Worker:  # noqa: ANN001
        self.worker = Worker(fn, self.parent)
        self.worker.done.connect(on_done)
        self.worker.failed.connect(self._failed)
        self.worker.start()
        return self.worker

    def _failed(self, message: str) -> None:
        self.result = f"Không cập nhật được: {message}"
        QMessageBox.warning(self.parent, "Cập nhật KiraPick", self.result + "\nBản đang dùng không thay đổi.")

    def _offer(self, release: Release | None) -> None:
        if release is None:
            self.result = f"Bạn đang dùng bản mới nhất ({__version__})."
            QMessageBox.information(self.parent, "Cập nhật KiraPick", self.result)
            return
        text = (f"Có bản mới: {release.version} (bạn đang dùng {__version__}).\n"
                f"Dung lượng tải về: {release.size / 1e9:.1f} GB.\n\n"
                "Tải về, kiểm tra rồi mở bộ cài? KiraPick sẽ tự đóng; dữ liệu buổi chụp và phần đã học được giữ nguyên.")
        if QMessageBox.question(self.parent, "Cập nhật KiraPick", text) != QMessageBox.StandardButton.Yes:
            return
        progress = QProgressDialog(f"Đang tải KiraPick {release.version}…", "", 0, 100, self.parent)
        progress.setCancelButton(None)
        progress.show()
        worker = self._run(lambda step: download(release, self.fetch, step, self.folder), self._install)
        worker.step.connect(lambda a, b: progress.setValue(int(a * 100 / b)) if b else None)
        worker.finished.connect(progress.close)

    def _install(self, setup: Path) -> None:
        try:
            self.start(setup)
        except UpdateError as exc:
            self._failed(str(exc))
            return
        self.result = f"Đang mở bộ cài {setup.name}; KiraPick sẽ đóng để cài bản mới."
        QMessageBox.information(self.parent, "Cập nhật KiraPick", self.result)
        self.close()


def auto_check_worker(parent: QWidget) -> Worker:
    """Opt-in daily check: only reads the release list, never downloads."""
    return Worker(lambda _p: newest_release(list_releases(), EDITION, __version__), parent)
