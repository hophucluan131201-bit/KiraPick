from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PHOTOS = ROOT / "test_photos"
MANIFEST = ROOT / "tests" / "fixtures" / "raw_samples.json"


def load_samples() -> list[dict]:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))["samples"]


def sample_path(sample: dict) -> Path:
    path = PHOTOS / sample["file"]
    if not path.exists():
        pytest.skip(f"sample not present: {sample['file']} (run scripts/raw_samples.py fetch)")
    return path


@pytest.fixture
def public_nef() -> Path:
    """A real, publicly redistributable NEF (NASA ISS photo, public domain)."""
    path = PHOTOS / "public" / "iss030e122639.NEF"
    if not path.exists():
        pytest.skip("public NEF sample absent (run scripts/raw_samples.py fetch)")
    return path


def pytest_unconfigure(config: pytest.Config) -> None:
    """KIRAPICK_EXIT_WATCHDOG=<seconds> (CI): if the test process has not exited that long after the last test, print
    every thread's stack and exit — a hang at interpreter exit (thread pools, Qt teardown) then shows where it is."""
    import faulthandler
    import os
    import sys

    seconds = os.environ.get("KIRAPICK_EXIT_WATCHDOG")
    if seconds:
        print("\n[exit watchdog armed]", file=sys.stderr, flush=True)
        faulthandler.dump_traceback_later(int(seconds), exit=True)


TEST_RUN = "(SELECT id FROM analysis_runs WHERE stage = 'test')"  # run_id of rows written by tests (known source)


@pytest.fixture(autouse=True)
def _test_analysis_run(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every schema-v8 database a test opens has one 'test' analysis run, so rows the tests write by hand can carry a
    known source (TEST_RUN). Rows from before v8 keep run_id NULL (tests/unit/test_provenance.py builds those)."""
    from app.storage import db

    real_connect = db.connect

    def connect(path):  # noqa: ANN001, ANN202
        conn = real_connect(path)
        if db.current_version(conn) >= 8:
            conn.execute("""INSERT OR IGNORE INTO analysis_runs (id, started_at, app_version, mode, stage)
                            VALUES (1, 't', 'test', 'personal', 'test')""")
        return conn

    monkeypatch.setattr(db, "connect", connect)
