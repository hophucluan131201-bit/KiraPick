"""The packaged app's self-test: full pipeline with the network blocked."""

from __future__ import annotations

import json
import socket
from pathlib import Path

import pytest

from app.ai.models import ModelRegistry

HAVE = ModelRegistry().can_detect()  # detection weights verified (face recognition is optional, LIC-1)


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
    media = data["media"]  # M10: the Media step, through MediaRegistry only
    assert any(s.startswith("media: ") for s in data["steps"]) and media["failed"] == 0
    assert media["personal_has_media_tables"] is False
    assert {m["model_id"] for m in media["models"]} <= {"person_detector_s", "person_detector_m", "face_detector"}
    assert set(data["report_a"]["media"]["loaded"]) <= {"person_detector_s", "person_detector_m", "face_detector"}
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


def test_photo_folder_argument_is_cleaned() -> None:
    """Owner, 2.2.0a: 'G:\\DCIM\\125NCZ_5 ' (a trailing space / quote from PowerShell) was not found."""
    from app.main import _folder_arg

    assert str(_folder_arg('G:\\DCIM\\125NCZ_5 ')) == str(Path('G:\\DCIM\\125NCZ_5'))
    assert str(_folder_arg('G:\\DCIM\\125NCZ_5"')) == str(Path('G:\\DCIM\\125NCZ_5'))
    assert _folder_arg("  ") is None


def test_self_test_leaves_the_user_data_folder_untouched(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """BUILD-1 run 42376018586: the installed self-test changed %LOCALAPPDATA%\\KiraPick (the analysis children write
    their logs there). The self-test now sends child logs to a temporary folder."""
    from app import selftest

    for name in ("connect", "connect_ex"):
        monkeypatch.setattr(socket.socket, name, getattr(socket.socket, name))
    monkeypatch.setattr(socket, "create_connection", socket.create_connection)
    monkeypatch.setattr(socket, "getaddrinfo", socket.getaddrinfo)
    data_home = tmp_path / "data-home"
    monkeypatch.setenv("XDG_DATA_HOME", str(data_home))  # children (spawned) resolve %LOCALAPPDATA% from this
    monkeypatch.delenv("KIRAPICK_LOG_DIR", raising=False)
    assert selftest.run(tmp_path / "r.json") == 0
    written = [p for p in data_home.rglob("*") if p.is_file()] if data_home.exists() else []
    assert written == [], written
    import os

    assert "KIRAPICK_LOG_DIR" not in os.environ
