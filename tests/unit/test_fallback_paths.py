"""C7 (LIC-1 S4): every fallback goes through the allow-list and is logged.

- GPU -> CPU at run time: the CPU session is opened on the file the registry handed out (not flagged as a bypass);
- YOLOX-M -> S: a YOLOX-M file whose hash is not pinned (the dev folder has the fp32 original) is never opened;
- each verified weight missing in turn: the analysis does what it can, opens nothing else, and says what is missing;
- --self-test with no weights at all fails honestly.
"""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pytest

from app.ai.models import ModelRegistry, ModelState, ModelUnavailableError
from app.ai.policy import LOAD_LOG

REG = ModelRegistry()
VERIFIED_PRESENT = [i for i in REG.policy.ids("verified") if REG.status(i).state is ModelState.READY]
needs_models = pytest.mark.skipif(not REG.can_detect(), reason="verified detection weights not present")


@pytest.fixture(autouse=True)
def _fresh_log() -> None:
    LOAD_LOG.clear()
    yield
    LOAD_LOG.clear()


@needs_models
def test_gpu_failure_at_run_time_reopens_the_same_handed_out_file_on_cpu(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.ai import runtime

    path = REG.require("person_detector_s")
    session = runtime.create_session(path, prefer_gpu=False)
    real = session.session

    class FailingGpu:
        def run(self, *_a):  # noqa: ANN002, ANN202
            raise RuntimeError("DML: operator not supported")

        def get_inputs(self):  # noqa: ANN202
            return real.get_inputs()

    session.session, session.device = FailingGpu(), "directml"
    inp = real.get_inputs()[0]
    session.run(None, {inp.name: np.zeros([d if isinstance(d, int) else 1 for d in inp.shape], np.float32)})
    report = LOAD_LOG.report()
    assert session.device == "cpu"
    assert report["opened"]["person_detector_s"]["providers"] == ["CPUExecutionProvider"]
    assert not any(k.startswith("?") for k in report["skipped"])  # not a bypass


@needs_models
def test_yolox_m_not_pinned_falls_back_to_s_without_opening_it() -> None:
    from app.ai.detect import PersonDetector

    if REG.status("person_detector_m").state is ModelState.READY:
        pytest.skip("the dev folder has the pinned YOLOX-M: nothing to fall back from")
    PersonDetector.load(REG, prefer_gpu=True)
    report = LOAD_LOG.report()
    assert "person_detector_m" not in report["opened"] and "person_detector_s" in report["opened"]


def _folder_without(tmp_path: Path, missing: str) -> Path:
    """Links to every weight file of the dev folder except ``missing``'s."""
    folder = tmp_path / "models"
    folder.mkdir()
    skip = REG.specs[missing].file
    for f in REG.models_dir.iterdir():
        if f.is_file() and f.name != skip:
            os.symlink(f, folder / f.name)
    return folder


@needs_models
@pytest.mark.parametrize("missing", VERIFIED_PRESENT)
def test_each_verified_weight_missing_in_turn(tmp_path: Path, missing: str) -> None:
    from app.selftest import _synthetic_photo
    from app.storage.project import Project
    from app.workers.analyze_job import AnalyzeJob
    from app.workers.import_job import ImportJob

    reg = ModelRegistry(_folder_without(tmp_path, missing))
    assert reg.status(missing).state is ModelState.MISSING
    with pytest.raises(ModelUnavailableError, match="chưa có"):
        reg.require(missing)
    shoot = tmp_path / "shoot"
    shoot.mkdir()
    _synthetic_photo(shoot / "T.jpg", 0)
    with Project.create(tmp_path / "session", "t") as project:
        ImportJob(project, shoot).run()
        if not reg.can_detect():  # YOLOX-S or YuNet missing: the people analysis is unavailable, nothing else opens
            assert missing in ("person_detector_s", "face_detector")
            return
        AnalyzeJob(project, reg, prefer_gpu=False).run(mode="people")
        quality = AnalyzeJob(project, reg, prefer_gpu=False).run(mode="quality")
        assert quality.measure_failed == 0
    opened = set(LOAD_LOG.report()["opened"])
    assert missing not in opened and all(reg.policy.verified(i) for i in opened)


def test_self_test_without_any_weight_fails_honestly(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import json
    import socket

    from app import selftest

    for name in ("connect", "connect_ex"):  # the self-test blocks the network for good: restore it afterwards
        monkeypatch.setattr(socket.socket, name, getattr(socket.socket, name))
    monkeypatch.setattr(socket, "create_connection", socket.create_connection)
    monkeypatch.setattr(socket, "getaddrinfo", socket.getaddrinfo)
    monkeypatch.setenv("KIRAPICK_MODELS_DIR", str(tmp_path / "empty"))
    (tmp_path / "empty").mkdir()
    report = tmp_path / "r.json"
    assert selftest.run(report) == 1
    data = json.loads(report.read_text(encoding="utf-8"))
    assert not data["ok"] and "models not ready" in data["error"]
    assert LOAD_LOG.report()["opened"] == {}
