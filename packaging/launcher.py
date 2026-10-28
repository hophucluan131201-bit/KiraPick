"""Entry point of the packaged app (PyInstaller)."""

import multiprocessing
import sys

if __name__ == "__main__":
    multiprocessing.freeze_support()  # the AI runs in a child process of this exe (app.workers.analyze_process)
    try:
        from app.main import main

        code = main()
    except BaseException:  # noqa: BLE001 - a windowed exe has no console: leave the reason in a file
        if isinstance(sys.exc_info()[1], SystemExit):
            raise
        import traceback
        from pathlib import Path

        text = traceback.format_exc()
        for target in (Path(sys.executable).with_name("startup-error.txt"),):
            try:
                target.write_text(text, encoding="utf-8")
            except OSError:
                pass
        raise
    sys.exit(code)
