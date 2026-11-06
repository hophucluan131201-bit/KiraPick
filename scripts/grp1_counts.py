"""GRP-1 trial numbers from the source tree; the logic is app/diagnostics/grp1.py (also KiraPick.exe --grp1-counts)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.diagnostics.grp1 import counts, run_cli  # noqa: E402,F401

if __name__ == "__main__":
    sys.exit(run_cli(sys.argv[1:]))
