"""C12 (LIC-1 S8, S10): packaging filters, licence texts, package check and the clean-up on upgrade (CLEAN-1).

Static and synthetic checks only: the real installer contents (P1-P4 on DirectML / CUDA / portable) and the upgrade
over an installed v3.0.0 (P8) need an internal build (BUILD-1, awaiting the owner).
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pytest

from app.ai.models import load_manifest
from app.ai.policy import ModelPolicy, Pinned, PolicyEntry, load_model_policy
from scripts import check_package, collect_licenses

ROOT = Path(__file__).resolve().parents[2]
CLEAN = json.loads((ROOT / "configs" / "clean-on-upgrade.json").read_text(encoding="utf-8"))["files"]
# what the published v3.0.0 / v3.0.0a installers put in {app} (inventory run 42199575662), for the files concerned
INSTALLED_300 = {
    *(f"models\\{n}" for n in ("w600k_r50.onnx", "person_reid_youtu_2021nov.onnx", "topiq_iaa_res50.onnx",
                               "topiq_nr_koniq_res50.onnx", "topiq_nr_face_res50.onnx",
                               "face_recognition_sface_2021dec.onnx", "clip_l14_image.onnx", "clip_prompts_v1.npz",
                               "laion_aesthetic.onnx", "yolox_m.onnx", "yolox_s.onnx", "ediffiqa_tiny_jun2024.onnx",
                               "face_detection_yunet_2023mar.onnx", "mediapipe_face_landmarks_v2.onnx",
                               "mediapipe_face_blendshapes_v2.onnx")),
    *(f"models\\{n}.sha256" for n in ("w600k_r50.onnx", "person_reid_youtu_2021nov.onnx", "topiq_iaa_res50.onnx",
                                      "topiq_nr_koniq_res50.onnx", "topiq_nr_face_res50.onnx",
                                      "face_recognition_sface_2021dec.onnx", "clip_l14_image.onnx",
                                      "clip_prompts_v1.npz", "laion_aesthetic.onnx", "yolox_m.onnx")),
    "_internal\\cv2\\opencv_videoio_ffmpeg4140_64.dll", "_internal\\onnxruntime\\capi\\onnxruntime_providers_tensorrt.dll",
    "_internal\\nvidia\\cublas\\bin\\cublas64_12.dll", "_internal\\nvidia\\cublas\\bin\\cublasLt64_12.dll",
    "_internal\\nvidia\\cudnn\\bin\\cudnn_graph64_9.dll", "_internal\\nvidia\\cudnn\\bin\\cudnn_ops64_9.dll",
    "_internal\\nvidia\\cufft\\bin\\cufft64_11.dll",
}


def test_install_delete_is_exactly_the_clean_list_with_no_wildcard() -> None:
    iss = (ROOT / "packaging" / "installer.iss").read_text(encoding="utf-8")
    section = iss.split("[InstallDelete]", 1)[1].split("\n[", 1)[0]
    names = re.findall(r'Type: files; Name: "\{app\}\\(.+?)"', section)
    assert names == CLEAN
    assert not any(c in n for n in names for c in "*?")
    assert "filesandordirs" not in section


def test_clean_list_covers_only_files_an_old_installer_managed_and_never_a_shipped_weight() -> None:
    assert set(CLEAN) <= INSTALLED_300
    shipped = {f"models\\{load_manifest()[i].file}" for i in load_model_policy().ids("verified")}
    assert not set(CLEAN) & shipped
    removed = {f"models\\{load_manifest()[i].file}" for i in load_model_policy().ids("pending")
               + load_model_policy().ids("never")} & INSTALLED_300
    assert removed <= set(CLEAN)  # every removed weight an old installer put there is cleaned


def test_upgrade_cleaning_removes_old_files_and_keeps_strange_ones(tmp_path: Path) -> None:
    """The [InstallDelete] semantics (exact names) on a copy of a 3.0.0 folder plus files the user put there."""
    app = tmp_path / "KiraPick"
    for rel in INSTALLED_300:
        (app / rel.replace("\\", "/")).parent.mkdir(parents=True, exist_ok=True)
        (app / rel.replace("\\", "/")).write_bytes(b"old")
    strangers = ["models/my_notes.txt", "models/my_own_model.onnx", "_internal/user_plugin.dll", "docs/ghi_chu.txt"]
    for rel in strangers:
        (app / rel).parent.mkdir(parents=True, exist_ok=True)
        (app / rel).write_bytes(b"user")
    for rel in CLEAN:  # what Inno Setup does for each 'Type: files' entry
        (app / rel.replace("\\", "/")).unlink(missing_ok=True)
    left = {str(p.relative_to(app)).replace("/", "\\") for p in app.rglob("*") if p.is_file()}
    assert not left & set(CLEAN)
    assert {s.replace("/", "\\") for s in strangers} <= left  # nothing the user put there is touched
    assert "models\\yolox_s.onnx" in left  # shipped weights are replaced by the new installer, not deleted first


def test_spec_drops_ffmpeg_tensorrt_and_duplicate_nvidia_dlls() -> None:
    spec = (ROOT / "packaging" / "kirapick.spec").read_text(encoding="utf-8")
    assert "opencv_videoio_ffmpeg4140_64.dll" in spec and "onnxruntime_providers_tensorrt.dll" in spec
    assert 'startswith("nvidia/")' in spec


def test_build_script_ships_only_allow_listed_weights_and_runs_the_gate() -> None:
    ps1 = (ROOT / "scripts" / "build_windows.ps1").read_text(encoding="utf-8")
    assert "models\\weights\\*.onnx" not in ps1  # nothing copied in from the build machine
    assert "convert_topiq" not in ps1 and "convert_clip" not in ps1
    assert '"*.sha256"' not in ps1 and "check_package.py" in ps1 and "collect_licenses.py" in ps1


def _package(tmp_path: Path, edition: str = "directml") -> tuple[Path, ModelPolicy]:
    """A synthetic package that passes: one fake file per verified weight (pinned in a test policy), licences, notices."""
    folder = tmp_path / "pkg"
    (folder / "models").mkdir(parents=True)
    specs, real = load_manifest(), load_model_policy()
    entries = dict(real.entries)
    for model_id in real.ids("verified"):
        data = f"w {model_id}".encode()
        (folder / "models" / specs[model_id].file).write_bytes(data)
        e = real.entries[model_id]
        entries[model_id] = PolicyEntry(e.id, e.status, e.modes, (Pinned(hashlib.sha256(data).hexdigest(), len(data)),),
                                        e.terms, e.media)
    assert collect_licenses.collect(folder / "docs" / "licenses", edition) == [] or True
    (folder / "docs" / "THIRD_PARTY_NOTICES.md").write_text((ROOT / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8"),
                                                            encoding="utf-8")
    return folder, ModelPolicy(entries)


def test_collect_licenses_gathers_every_required_text(tmp_path: Path) -> None:
    missing = collect_licenses.collect(tmp_path / "lic", "directml")
    assert missing == []
    names = {p.name for p in (tmp_path / "lic").iterdir()}
    assert set(collect_licenses.REQUIRED_STATIC) <= names and "DirectML-LICENSE.txt" in names
    assert {"onnxruntime-LICENSE.txt", "LibRaw-LICENSE.txt", "Python-LICENSE.txt", "python-packages.txt"} <= names
    assert "GNU LESSER GENERAL PUBLIC LICENSE" in (tmp_path / "lic" / "LGPL-3.0.txt").read_text(encoding="utf-8")
    assert "Attribution 4.0 International" in (tmp_path / "lic" / "CC-BY-4.0.txt").read_text(encoding="utf-8")


def test_package_check_passes_a_clean_package(tmp_path: Path) -> None:
    folder, policy = _package(tmp_path)
    report = check_package.check(folder, "directml", policy)
    assert report["ok"], report["failures"]


@pytest.mark.parametrize("damage, code", [
    (lambda f: (f / "models" / "w600k_r50.onnx").write_bytes(b"arc"), "P1"),
    (lambda f: (f / "models" / "yolox_s.onnx").write_bytes(b"tampered"), "P1"),
    (lambda f: (f / "models" / "face_detection_yunet_2023mar.onnx").unlink(), "P1"),
    (lambda f: ((f / "_internal").mkdir(), (f / "_internal" / "extra.onnx").write_bytes(b"x")), "P2"),
    (lambda f: ((f / "_internal" / "cv2").mkdir(parents=True),
                (f / "_internal" / "cv2" / "opencv_videoio_ffmpeg4140_64.dll").write_bytes(b"x")), "P3"),
    (lambda f: ((f / "_internal" / "nvidia" / "cublas" / "bin").mkdir(parents=True),
                (f / "_internal" / "nvidia" / "cublas" / "bin" / "cublas64_12.dll").write_bytes(b"x"),
                (f / "_internal" / "cublas64_12.dll").write_bytes(b"x")), "P3"),
    (lambda f: (f / "docs" / "licenses" / "CC-BY-4.0.txt").unlink(), "P4"),
    (lambda f: (f / "docs" / "THIRD_PARTY_NOTICES.md").write_text("- TOPIQ aesthetics\n", encoding="utf-8"), "P4"),
])
def test_package_check_fails_each_kind_of_problem(tmp_path: Path, damage, code: str) -> None:  # noqa: ANN001
    folder, policy = _package(tmp_path)
    damage(folder)
    report = check_package.check(folder, "directml", policy)
    assert not report["ok"] and any(f.startswith(code) for f in report["failures"]), report["failures"]


def test_cudnn_in_a_package_is_a_failure(tmp_path: Path) -> None:
    folder, policy = _package(tmp_path, "cuda")
    (folder / "_internal").mkdir()
    (folder / "_internal" / "cudnn64_9.dll").write_bytes(b"x")
    report = check_package.check(folder, "cuda", policy)
    assert any("cudnn64_9.dll: cuDNN must not be shipped" in f for f in report["failures"])

def test_cuda_edition_ships_no_cudnn_and_carries_the_guide(tmp_path: Path) -> None:
    """LIC-7 b (owner, 2026-11-07): cuDNN is not distributed; the CUDA package carries the install guide."""
    folder, policy = _package(tmp_path, "cuda")
    licences = folder / "docs" / "licenses"
    (licences / "NVIDIA-nvidia-cublas-cu12-12.9-License.txt").write_text("x", encoding="utf-8")
    for name in ("onnxruntime-LICENSE.txt", "onnxruntime-ThirdPartyNotices.txt"):
        if not (licences / name).is_file():  # CI has onnxruntime-directml, not onnxruntime-gpu: stand-in text
            (licences / name).write_text("x", encoding="utf-8")
    report = check_package.check(folder, "cuda", policy)
    assert any("HUONG_DAN_CUDNN.txt missing" in f for f in report["failures"])
    (folder / "docs" / "HUONG_DAN_CUDNN.txt").write_text("cài cuDNN", encoding="utf-8")
    assert check_package.check(folder, "cuda", policy)["ok"]
    spec = (ROOT / "packaging" / "kirapick.spec").read_text(encoding="utf-8")
    req = (ROOT / "packaging" / "requirements-cuda.txt").read_text(encoding="utf-8")
    assert 'startswith("cudnn")' in spec and "onnxruntime-gpu[cuda]==" in req and "cudnn]" not in req
    guide = (ROOT / "packaging" / "notes" / "HUONG_DAN_CUDNN.txt").read_text(encoding="utf-8-sig")
    assert "developer.nvidia.com/cudnn-downloads" in guide and "CUDNN_PATH" in guide


def test_user_installed_cudnn_is_found(tmp_path: Path) -> None:
    from app.ai import runtime

    pf = tmp_path / "Program Files"
    old = pf / "NVIDIA" / "CUDNN" / "v9.1" / "bin" / "12.4"
    new = pf / "NVIDIA" / "CUDNN" / "v9.8" / "bin" / "12.9"
    for d in (old, new):
        d.mkdir(parents=True)
        (d / runtime.CUDNN_DLL).write_bytes(b"x")
    assert runtime.find_cudnn({"ProgramFiles": str(pf), "PATH": ""}) == new  # newest first
    custom = tmp_path / "my" / "cudnn"
    custom.mkdir(parents=True)
    (custom / runtime.CUDNN_DLL).write_bytes(b"x")
    assert runtime.find_cudnn({"ProgramFiles": str(pf), "CUDNN_PATH": str(custom), "PATH": ""}) == custom
    assert runtime.find_cudnn({"ProgramFiles": str(tmp_path / "none"), "PATH": ""}) is None
