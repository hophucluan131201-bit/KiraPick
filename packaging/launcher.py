"""Entry point of the packaged app (PyInstaller)."""

import multiprocessing
import sys

if __name__ == "__main__":
    multiprocessing.freeze_support()  # the AI runs in a child process of this exe (app.workers.analyze_process)
    from app.main import main

    sys.exit(main())
