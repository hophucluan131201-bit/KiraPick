"""Application entry point: ``python -m app`` (or the ``kirapick`` script)."""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from PySide6.QtWidgets import QApplication

from app import __version__
from app.branding import APP_NAME, SETTINGS_IDS, data_dir, icon_path, migrate_legacy_data, migrate_legacy_settings


def _setup_logging() -> Path:
    log_dir = data_dir() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(log_dir / "kirapick.log", maxBytes=2_000_000, backupCount=3, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logging.basicConfig(level=logging.INFO, handlers=[handler])
    return log_dir


def _install_excepthook() -> None:
    """Unexpected errors: log them and tell the user instead of vanishing (pythonw has no console)."""

    def hook(exc_type, exc, tb) -> None:  # type: ignore[no-untyped-def]
        logging.getLogger("app").critical("unhandled error", exc_info=(exc_type, exc, tb))
        from PySide6.QtWidgets import QMessageBox

        QMessageBox.critical(None, "Lỗi không mong muốn",
                             f"{exc_type.__name__}: {exc}\n\nChi tiết đã ghi vào file log của ứng dụng.\n"
                             "Ảnh gốc của bạn không bị ảnh hưởng.")

    sys.excepthook = hook


def _folder_arg(text: str) -> Path | None:
    """A folder typed in PowerShell: drop stray spaces and the quote that "D:\\Ảnh\\" leaves behind."""
    cleaned = text.strip().strip('"').strip()
    return Path(cleaned) if cleaned else None


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv if argv is None else argv
    if "--self-test" in argv:  # packaged app check, no window: KiraPick.exe --self-test report.json
        rest = argv[argv.index("--self-test") + 1:]  # [report.json] [a photo folder to try, read-only]
        report = Path(rest[0]) if rest else Path.cwd() / "kirapick-selftest.json"
        crash = report.with_name(report.stem + ".crash.txt")
        try:  # a native crash (e.g. a DLL that does not load) still leaves a trace next to the report
            import faulthandler

            faulthandler.enable(open(crash, "w", encoding="utf-8"))  # noqa: SIM115
        except OSError:
            pass
        from app.selftest import run

        code = run(report, _folder_arg(rest[1]) if len(rest) > 1 else None)
        try:  # no crash: no empty trace file left on the user's Desktop
            import faulthandler

            faulthandler.disable()
            if crash.exists() and crash.stat().st_size == 0:
                crash.unlink()
        except OSError:
            pass
        return code
    app = QApplication(argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(SETTINGS_IDS[0])
    app.setApplicationVersion(__version__)
    icon = icon_path()
    if icon is not None:
        from PySide6.QtGui import QIcon

        app.setWindowIcon(QIcon(str(icon)))
    moved = migrate_legacy_data()  # before logging opens a file in the new folder
    migrate_legacy_settings()
    log_dir = _setup_logging()
    if moved:
        logging.getLogger(__name__).info("data of the old app name moved to %s", data_dir())
    logging.getLogger(__name__).info("starting %s (logs in %s)", __version__, log_dir)
    _install_excepthook()

    from app.ui.main_window import MainWindow
    from app.ui.theme import apply_dark_theme

    apply_dark_theme(app)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
