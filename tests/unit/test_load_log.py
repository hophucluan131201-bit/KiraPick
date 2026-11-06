"""U14: every opened weight is logged with the SHA-256 of the file itself and the provider really used; a file
opened without the allow-list check is flagged."""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

import pytest

from app.ai.models import ModelRegistry, ModelState
from app.ai.policy import LOAD_LOG

REG = ModelRegistry()
HAVE_MESH = REG.status("face_mesh").state is ModelState.READY
HAVE_YUNET = REG.status("face_detector").state is ModelState.READY


@pytest.fixture(autouse=True)
def _fresh_log() -> None:
    LOAD_LOG.clear()
    yield
    LOAD_LOG.clear()


@pytest.mark.skipif(not HAVE_MESH, reason="MediaPipe weights not present")
def test_onnxruntime_session_records_id_hash_and_provider() -> None:
    from app.ai.runtime import create_session

    path = REG.require("face_mesh")
    create_session(path, prefer_gpu=False)
    opened = LOAD_LOG.report()["opened"]["face_mesh"]
    assert opened["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()  # computed from the file
    assert opened["providers"] == ["CPUExecutionProvider"]


@pytest.mark.skipif(not HAVE_YUNET, reason="YuNet weights not present")
def test_opencv_load_records_the_provider() -> None:
    import numpy as np

    from app.ai.detect import FaceDetector

    FaceDetector(REG).detect(np.zeros((64, 64, 3), np.uint8))
    assert LOAD_LOG.report()["opened"]["face_detector"]["providers"] == ["opencv"]


@pytest.mark.skipif(not HAVE_MESH, reason="MediaPipe weights not present")
def test_a_file_opened_without_the_check_is_flagged(tmp_path: Path) -> None:
    from app.ai.runtime import create_session

    copy = tmp_path / "copied.onnx"
    shutil.copy(REG.status("face_mesh").path, copy)
    create_session(copy, prefer_gpu=False)  # never handed out by the registry
    report = LOAD_LOG.report()
    assert "face_mesh" not in report["opened"]
    assert report["skipped"]["?copied.onnx"]["reason"] == "mở không qua danh sách cho phép"


def test_log_lines_hold_ids_files_and_hashes_only(caplog: pytest.LogCaptureFixture, tmp_path: Path) -> None:
    import logging

    caplog.set_level(logging.INFO, logger="app.ai.policy")
    photo_folder = tmp_path / "Khách hàng Nguyễn" / "models"
    photo_folder.mkdir(parents=True)
    LOAD_LOG.refuse("face_embedder_arcface", photo_folder / "w600k_r50.onnx", "test")
    assert "w600k_r50.onnx" in caplog.text and "Khách hàng" not in caplog.text  # file name only, no folder
