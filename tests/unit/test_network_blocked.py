"""U7 (LIC-1 S11): the analysis, the scoring and Media work with the network blocked, and never try to connect.

In-process block here (every socket connect / name lookup fails and is recorded). The Windows CI job 'lic1-checks'
adds an operating-system firewall rule that blocks every outbound connection of python.exe, which also covers
the analysis child process and native libraries (ONNX Runtime, DirectML).
"""

from __future__ import annotations

import socket
from pathlib import Path

import pytest

from app.ai.models import ModelRegistry

REG = ModelRegistry()


@pytest.fixture
def blocked(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    attempts: list[str] = []

    def refuse(*args, **_kw):  # noqa: ANN002, ANN003, ANN202
        attempts.append(repr(args[1:] if args and isinstance(args[0], socket.socket) else args)[:80])
        raise OSError("network blocked by the test")

    for name in ("connect", "connect_ex"):
        monkeypatch.setattr(socket.socket, name, refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
    monkeypatch.setattr(socket, "getaddrinfo", refuse)
    return attempts


def test_the_block_is_real(blocked: list[str]) -> None:
    with pytest.raises(OSError):
        socket.create_connection(("example.com", 443), timeout=1)
    assert blocked


@pytest.mark.skipif(not REG.can_detect(), reason="verified detection weights not present")
def test_analysis_scoring_and_media_with_the_network_blocked(tmp_path: Path, blocked: list[str]) -> None:
    from app.media.models import MediaRegistry
    from app.quality import select
    from app.selftest import _synthetic_photo
    from app.storage.project import Project
    from app.workers.analyze_job import AnalyzeJob
    from app.workers.import_job import ImportJob

    shoot = tmp_path / "shoot"
    shoot.mkdir()
    for i in range(2):
        _synthetic_photo(shoot / f"T_{i}.jpg", i)
    with Project.create(tmp_path / "session", "t") as project:
        assert ImportJob(project, shoot).run().ingested == 2
        assert AnalyzeJob(project, REG, prefer_gpu=False).run(mode="people").failed == 0
        assert AnalyzeJob(project, REG, prefer_gpu=False).run(mode="quality").measure_failed == 0
        select.select_per_person(project.conn, 3)
    media = MediaRegistry(REG)
    media.report_unavailable()
    assert blocked == []  # nothing tried to connect
