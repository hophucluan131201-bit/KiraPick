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
