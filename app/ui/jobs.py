"""QThread adapters for long jobs. Each thread opens its own SQLite connection."""

from __future__ import annotations

import logging
import threading
from dataclasses import asdict
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from app.export.copy_export import ExportPlan, run_export
from app.storage.project import Project
from app.workers.import_job import ImportJob, ImportProgress

log = logging.getLogger(__name__)


class ImportThread(QThread):
    progress = Signal(str, int, int)  # phase, done, total
    succeeded = Signal(dict)  # ImportSummary as dict
    failed = Signal(str)

    def __init__(self, project_folder: Path, root: Path, workers: int = 3) -> None:
        super().__init__()
        self.project_folder, self.root, self.workers = project_folder, root, workers
        self._cancel = threading.Event()

    def cancel(self) -> None:
        self._cancel.set()

    @property
    def cancel_requested(self) -> bool:
        return self._cancel.is_set()

    def run(self) -> None:
        try:
            with Project.open(self.project_folder) as project:
                summary = ImportJob(project, self.root, workers=self.workers).run(
                    progress=self._emit, should_cancel=self._cancel.is_set
                )
            self.succeeded.emit(asdict(summary))
        except Exception as exc:  # noqa: BLE001 - reported to the user, logged without photo data
            log.exception("import failed")
            self.failed.emit(f"{type(exc).__name__}: {exc}")

    def _emit(self, p: ImportProgress) -> None:
        self.progress.emit(p.phase, p.done, p.total)


class ExportThread(QThread):
    progress = Signal(int, int)
    succeeded = Signal(object)  # ExportResult
    failed = Signal(str)

    def __init__(self, plan: ExportPlan) -> None:
        super().__init__()
        self.plan = plan
        self._cancel = threading.Event()

    def cancel(self) -> None:
        self._cancel.set()

    def run(self) -> None:
        try:
            result = run_export(self.plan, progress=self.progress.emit, should_cancel=self._cancel.is_set)
            self.succeeded.emit(result)
        except Exception as exc:  # noqa: BLE001
            log.exception("export failed")
            self.failed.emit(f"{type(exc).__name__}: {exc}")
