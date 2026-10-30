"""QThread adapters for long jobs. Each thread opens its own SQLite connection."""

from __future__ import annotations

import logging
import threading
from dataclasses import asdict, dataclass, field
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from app.export.copy_export import ExportError, ExportPlan, plan_export, run_export
from app.export.formats import ExportFormat
from app.export.hashing import HashCache, HashCancelled
from app.export.layout import Layout
from app.export.sources import ScanCancelled, SourceSpec, scan_external
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


@dataclass(frozen=True)
class PlanRequest:
    """Everything one preview depends on (spec §5): a new choice is a new request with a new generation."""
    photo_ids: tuple[int, ...]
    destination: Path
    source: SourceSpec
    fmt: ExportFormat
    layout: Layout
    confirmations: dict[tuple[int, str], Path] = field(default_factory=dict)


class ExportPlanThread(QThread):
    """Plans an export from another folder: scans it (when the request has no index yet), reads the candidates' EXIF
    and hashes what must be proven — never on the GUI thread. Results carry their generation: the dialog drops a
    result for an older choice. Cancellable between files and between 1 MiB hash chunks."""

    progress = Signal(int, str, int)  # generation, phase ("scan" | "match"), files seen
    planned = Signal(int, object, object)  # generation, ExportPlan, ExternalIndex used
    failed = Signal(int, str)  # generation, message ("" when cancelled)

    def __init__(self, project_folder: Path, request: PlanRequest, generation: int,
                 hashes: HashCache | None = None) -> None:
        super().__init__()
        self.project_folder, self.request, self.generation = project_folder, request, generation
        self.hashes = hashes if hashes is not None else HashCache()
        self._cancel = threading.Event()

    def cancel(self) -> None:
        self._cancel.set()

    @property
    def cancel_requested(self) -> bool:
        return self._cancel.is_set()

    def run(self) -> None:
        gen, req = self.generation, self.request
        try:
            with Project.open(self.project_folder) as project:
                source = req.source
                if source.mode == "external" and source.index is None:
                    if source.root is None:
                        raise ExportError("chưa chọn thư mục nguồn")
                    index = scan_external(source.root, session_folder=project.folder, destination=req.destination,
                                          progress=lambda n: self.progress.emit(gen, "scan", n),
                                          should_cancel=self._cancel.is_set)
                    source = SourceSpec("external", source.root, index)
                    self.progress.emit(gen, "match", index.files)
                plan = plan_export(project, list(req.photo_ids), req.destination, source=source, fmt=req.fmt,
                                   layout=req.layout, confirmations=dict(req.confirmations), hashes=self.hashes,
                                   should_cancel=self._cancel.is_set)
            self.planned.emit(gen, plan, source.index)
        except (ScanCancelled, HashCancelled):
            self.failed.emit(gen, "")
        except ExportError as exc:
            self.failed.emit(gen, str(exc))
        except Exception as exc:  # noqa: BLE001 - reported to the user, logged without photo data
            log.exception("export planning failed")
            self.failed.emit(gen, f"{type(exc).__name__}: {exc}")


class ExportThread(QThread):
    progress = Signal(int, int)
    succeeded = Signal(object)  # ExportResult
    failed = Signal(str)

    def __init__(self, plan: ExportPlan, options: dict[str, str] | None = None) -> None:
        super().__init__()
        self.plan = plan
        self.options = dict(options or {})
        self._cancel = threading.Event()
        self._stop = threading.Event()

    def cancel(self) -> None:
        """Dừng: stops at once, inside the file being copied (that file is removed)."""
        self._cancel.set()

    def stop_after_file(self) -> None:
        """Closing / switching folder: stops after the photo being copied (export_stop_text)."""
        self._stop.set()

    def run(self) -> None:
        try:
            result = run_export(self.plan, progress=self.progress.emit, should_cancel=self._cancel.is_set,
                                options=self.options, should_stop=self._stop.is_set)
            self.succeeded.emit(result)
        except Exception as exc:  # noqa: BLE001
            log.exception("export failed")
            self.failed.emit(f"{type(exc).__name__}: {exc}")


class AnalyzeThread(QThread):
    """Runs AnalyzeJob ('people': detection + grouping, or 'quality': scoring) in a child process
    (app.workers.analyze_process), so the window stays responsive."""

    progress = Signal(str, int, int)
    succeeded = Signal(dict)
    failed = Signal(str)

    def __init__(self, project_folder: Path, mode: str = "people", learning_dir: Path | None = None,
                 prefer_gpu: bool = True) -> None:
        super().__init__()
        self.project_folder = project_folder
        self.mode = mode
        self.learning_dir = learning_dir
        self.prefer_gpu = prefer_gpu
        self._cancel = threading.Event()

    def cancel(self) -> None:
        self._cancel.set()

    @property
    def cancel_requested(self) -> bool:
        return self._cancel.is_set()

    def run(self) -> None:
        from app.workers.analyze_process import run_in_child

        try:
            summary = run_in_child(self.project_folder, self.mode, self.learning_dir, self.prefer_gpu,
                                   self.progress.emit, self._cancel.is_set)
            self.succeeded.emit(summary | {"mode": self.mode})
        except Exception as exc:  # noqa: BLE001 - the child already logged details
            log.warning("analysis failed: %s", exc)
            self.failed.emit(str(exc))
