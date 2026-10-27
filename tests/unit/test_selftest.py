"""The packaged app's self-test: full pipeline with the network blocked."""

from __future__ import annotations

import json
import socket
from pathlib import Path

import pytest

from app.ai.models import ModelRegistry

HAVE = ModelRegistry().ready("identity") and ModelRegistry().ready("quality")


@pytest.mark.skipif(not HAVE, reason="AI models not fetched")
def test_self_test_passes_offline(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from app import selftest

    for name in ("connect", "connect_ex"):  # restore the real socket after the test
        monkeypatch.setattr(socket.socket, name, getattr(socket.socket, name))
    monkeypatch.setattr(socket, "create_connection", socket.create_connection)
    monkeypatch.setattr(socket, "getaddrinfo", socket.getaddrinfo)
    report = tmp_path / "r.json"
    assert selftest.run(report) == 0
    data = json.loads(report.read_text(encoding="utf-8"))
    assert data["ok"] and data["network_attempts"] == [] and "selection ran" in data["steps"]
    with pytest.raises(OSError):  # the block is real: any connection attempt fails and is recorded
        socket.create_connection(("example.com", 443), timeout=1)


def test_report_in_a_missing_folder_is_not_lost(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Owner, 2.1.0b2: "%USERPROFILE%\\Desktop" did not exist (Desktop moved to OneDrive), the report
    write crashed the exe with FileNotFoundError and the whole self-test result was lost."""
    from app import selftest

    monkeypatch.setattr(selftest, "_fallback_report_dir", lambda: tmp_path / "logs")
    target = tmp_path / "no-such-desktop" / "r.json"
    written = selftest._write_report(target, {"ok": True})
    assert written == tmp_path / "logs" / "r.json" and json.loads(written.read_text(encoding="utf-8"))["ok"]
    assert not target.parent.exists()  # no stray "Desktop" folder is created
    assert selftest._write_report(tmp_path / "r2.json", {"ok": False}) == tmp_path / "r2.json"
