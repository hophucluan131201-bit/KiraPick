"""Signed AI-model updates: catalogue signature, staged download, atomic activation, rollback."""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from app.ai.models import ModelRegistry, ModelSpec, ModelState
from app.updates.catalog import CatalogError, Entry, pending_updates, verify_catalog
from app.updates.installer import UpdateError, install, rollback

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def keys() -> tuple[Ed25519PrivateKey, bytes]:
    priv = Ed25519PrivateKey.generate()
    return priv, priv.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)


def _catalog(entries: list[dict]) -> bytes:
    return json.dumps({"schema": 1, "models": entries}).encode()


def _entry(data: bytes, version: str = "2", **kw: object) -> dict:
    return {"id": "m", "version": version, "file": "m.onnx", "url": "https://example.invalid/m.onnx",
            "size": len(data), "sha256": hashlib.sha256(data).hexdigest(), "license": "MIT", "min_app": "2.2.0",
            "embedding_compatible": True, "notes": "test"} | kw


def test_signature_must_match(keys) -> None:  # noqa: ANN001
    priv, pub = keys
    data = _catalog([_entry(b"x")])
    assert verify_catalog(data, priv.sign(data), pub)["models"][0]["id"] == "m"
    with pytest.raises(CatalogError):
        verify_catalog(data + b" ", priv.sign(data), pub)  # tampered
    with pytest.raises(CatalogError):
        verify_catalog(data, Ed25519PrivateKey.generate().sign(data), pub)  # someone else's key
    with pytest.raises(CatalogError):
        verify_catalog(data, priv.sign(data)[:10], pub)  # truncated


def _registry(tmp_path: Path) -> ModelRegistry:
    bundled = tmp_path / "bundled"
    bundled.mkdir()
    (bundled / "m.onnx").write_bytes(b"old")
    spec = ModelSpec("m", "M", "m.onnx", hashlib.sha256(b"old").hexdigest(), 3, "MIT", "https://x", "t", "onnxruntime")
    return ModelRegistry(bundled, {"m": spec}, override_dir=tmp_path / "updates" / "active")


def _fetch(content: bytes):  # noqa: ANN202
    def fetch(url: str, dest: Path, progress) -> None:  # noqa: ANN001
        dest.write_bytes(content)
    return fetch


def test_install_activates_verified_file_and_rollback_restores(tmp_path: Path) -> None:
    reg = _registry(tmp_path)
    root = tmp_path / "updates"
    e = Entry.from_dict(_entry(b"new model"))
    assert [p.id for p in pending_updates({"models": [_entry(b"new model")]}, reg, "2.2.0")] == ["m"]
    install(e, _fetch(b"new model"), lambda *_: None, root)
    reg2 = ModelRegistry(reg.models_dir, reg.specs, override_dir=root / "active")
    st = reg2.status("m")
    assert st.state is ModelState.READY and st.path == root / "active" / "m.onnx"
    assert pending_updates({"models": [_entry(b"new model")]}, reg2, "2.2.0") == []
    rollback("m", "m.onnx", root)
    reg3 = ModelRegistry(reg.models_dir, reg.specs, override_dir=root / "active")
    assert reg3.status("m").path == reg.models_dir / "m.onnx"  # back to the bundled model


def test_bad_download_never_becomes_active(tmp_path: Path) -> None:
    root = tmp_path / "updates"
    e = Entry.from_dict(_entry(b"new model"))
    with pytest.raises(UpdateError):
        install(e, _fetch(b"tampered!"), lambda *_: None, root)
    assert not (root / "active" / "m.onnx").exists()

    def broken(url: str, dest: Path, progress) -> None:  # noqa: ANN001
        dest.write_bytes(b"half")
        raise OSError("connection reset")

    with pytest.raises(UpdateError):
        install(e, broken, lambda *_: None, root)
    assert not (root / "active" / "m.onnx").exists()
    assert not any((root / "staged").rglob("*.onnx"))  # nothing half-written left behind


def test_entries_for_a_newer_app_are_not_offered(tmp_path: Path) -> None:
    reg = _registry(tmp_path)
    assert pending_updates({"models": [_entry(b"x", min_app="9.0.0")]}, reg, "2.2.0") == []
    assert pending_updates({"models": [_entry(b"x", id="unknown")]}, reg, "2.2.0") == []


def test_only_the_updater_may_use_the_network() -> None:
    allowed = {ROOT / "app" / "updates", ROOT / "app" / "selftest.py"}  # selftest only blocks sockets
    bad = []
    for path in (ROOT / "app").rglob("*.py"):
        if any(path == a or a in path.parents for a in allowed):
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            names = [a.name for a in node.names] if isinstance(node, ast.Import) else (
                [node.module or ""] if isinstance(node, ast.ImportFrom) else [])
            if any(n.split(".")[0] in {"urllib", "http", "socket", "ssl", "requests", "httpx"} for n in names):
                bad.append(f"{path.relative_to(ROOT)}: {names}")
    assert bad == []


def test_auto_check_is_off_by_default_and_daily() -> None:
    from app.updates.catalog import should_auto_check

    assert not should_auto_check(enabled=False, last_check=None, today="2026-10-28")
    assert should_auto_check(enabled=True, last_check=None, today="2026-10-28")
    assert not should_auto_check(enabled=True, last_check="2026-10-28", today="2026-10-28")
    assert should_auto_check(enabled=True, last_check="2026-10-27", today="2026-10-28")


def test_public_key_is_shipped() -> None:
    from app.updates.catalog import public_key

    assert len(public_key()) == 32
