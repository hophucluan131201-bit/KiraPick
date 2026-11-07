"""Checklist G1-G4: the inventory of what a build hands to testers (synthetic package, no real build)."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

from tests.unit.test_packaging import ROOT, _package

spec = importlib.util.spec_from_file_location("package_inventory", ROOT / "scripts" / "package_inventory.py")
inv_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(inv_mod)


def _dist(tmp_path: Path, edition: str):  # noqa: ANN202
    folder, policy = _package(tmp_path, edition)
    dist = tmp_path / "dist"
    dist.mkdir()
    folder.rename(dist / "KiraPick")
    (dist / "installer").mkdir()
    (dist / "installer" / "KiraPick-Setup-x.exe").write_bytes(b"setup")
    (dist / "installer" / "KiraPick-Setup-x-1.bin").write_bytes(b"data" * 10)
    return dist, policy


def test_inventory_lists_every_package_with_its_sha256_and_checks_the_program_folder(tmp_path: Path) -> None:
    dist, policy = _dist(tmp_path, "directml")
    inv = inv_mod.inventory(dist, "directml", "abc1234", "42", policy=policy)
    assert inv["ok"] and inv["commit"] == "abc1234" and inv["version"]
    assert [p["file"] for p in inv["packages"]] == ["KiraPick-Setup-x-1.bin", "KiraPick-Setup-x.exe"]
    assert inv["packages"][1]["sha256"] == hashlib.sha256(b"setup").hexdigest()
    md = inv_mod.markdown(inv)
    assert "abc1234" in md and hashlib.sha256(b"setup").hexdigest() in md and "đạt" in md
    json.dumps(inv)  # serialisable as written by main()


def test_a_bad_program_folder_fails_the_inventory(tmp_path: Path) -> None:
    dist, policy = _dist(tmp_path, "directml")
    (dist / "KiraPick" / "models" / "w600k_r50.onnx").write_bytes(b"arcface")
    inv = inv_mod.inventory(dist, "directml", "abc1234", policy=policy)
    assert not inv["ok"] and inv["program_folder"]["failures"]


def test_cudnn_left_by_an_upgrade_from_3_0_0a_is_reported_not_failed(tmp_path: Path) -> None:
    """CLEAN-2 is an open owner decision: the upgrade check lists the leftover DLLs; a fresh install must have none."""
    dist, policy = _dist(tmp_path, "cuda")
    lic = dist / "KiraPick" / "docs" / "licenses"
    (lic / "NVIDIA-nvidia-cublas-cu12-12.9-License.txt").write_text("x", encoding="utf-8")
    for name in ("onnxruntime-LICENSE.txt", "onnxruntime-ThirdPartyNotices.txt"):
        if not (lic / name).is_file():
            (lic / name).write_text("x", encoding="utf-8")
    (dist / "KiraPick" / "docs" / "HUONG_DAN_CUDNN.txt").write_text("cuDNN", encoding="utf-8")
    import shutil

    installed = tmp_path / "Programs" / "KiraPick"
    shutil.copytree(dist / "KiraPick", installed)
    (installed / "_internal").mkdir(exist_ok=True)
    (installed / "_internal" / "cudnn64_9.dll").write_bytes(b"x")
    upgraded = inv_mod.inventory(dist, "cuda", "abc", installed=installed, upgrade_from="3.0.0a", policy=policy)
    assert upgraded["ok"] and upgraded["installed"]["clean2_leftover"] == ["cudnn64_9.dll"]
    assert "CLEAN-2" in inv_mod.markdown(upgraded)
    fresh = inv_mod.inventory(dist, "cuda", "abc", installed=installed, policy=policy)
    assert not fresh["ok"]  # a fresh install never has cuDNN
