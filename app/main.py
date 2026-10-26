"""Application entry point: ``python -m app`` (or the ``snorlu`` script)."""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from PySide6.QtCore import QStandardPaths
from PySide6.QtWidgets import QApplication

from app import __version__


def _setup_logging() -> Path:
    base = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation)
    log_dir = Path(base or Path.home() / ".snorlu") / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(log_dir / "snorlu.log", maxBytes=2_000_000, backupCount=3, encoding="utf-8")
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


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv if argv is None else argv
    app = QApplication(argv)
    app.setApplicationName("Snorlu AI Culling")
    app.setOrganizationName("Snorlu")
    app.setApplicationVersion(__version__)
    log_dir = _setup_logging()
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
