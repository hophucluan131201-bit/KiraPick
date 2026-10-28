"""⚙ Cập nhật mô hình AI: asks first, never automatic unless switched on, nothing active on failure."""

from __future__ import annotations

import hashlib
from pathlib import Path

from PySide6.QtWidgets import QMessageBox

import app.ui.main_window as mw
import app.ui.update_dialog as ud
from tests.gui.test_main_window import _window, env  # noqa: F401 - fixture


def test_auto_check_is_off_by_default(qtbot, env: dict, monkeypatch) -> None:  # noqa: F811
    calls = []
    monkeypatch.setattr(ud, "download_catalog", lambda: calls.append(1) or {"schema": 1, "models": []})
    w = _window(qtbot, env)
    assert not w.act_auto_update.isChecked()
    w._maybe_auto_check()
    qtbot.wait(200)
    assert calls == []


def test_user_started_update_installs_after_confirmation(qtbot, env: dict, monkeypatch, tmp_path: Path) -> None:  # noqa: F811
    w = _window(qtbot, env)
    spec = next(iter(w._registry_or_default().specs.values()))
    data = b"new weights"
    catalog = {"schema": 1, "models": [{"id": spec.id, "version": "9", "file": spec.file, "url": "https://x/y",
                                        "size": len(data), "sha256": hashlib.sha256(data).hexdigest(),
                                        "license": "MIT", "min_app": "0", "embedding_compatible": True}]}
    asked = []
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: asked.append(a[2]) or QMessageBox.StandardButton.Yes)
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)
    updater = w.start_model_update(get_catalog=lambda: catalog,
                                   fetch=lambda url, dest, progress: dest.write_bytes(data), root=tmp_path / "upd")
    qtbot.waitUntil(lambda: updater.result is not None, timeout=10000)
    assert "Không gửi ảnh" in asked[0]  # privacy notice first
    assert updater.result.startswith("Đã cập nhật")
    assert (tmp_path / "upd" / "active" / spec.file).read_bytes() == data


def test_failed_check_changes_nothing(qtbot, env: dict, monkeypatch, tmp_path: Path) -> None:  # noqa: F811
    w = _window(qtbot, env)
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: None)

    def offline() -> dict:
        raise ud.CatalogError("không kết nối được (URLError)")

    updater = w.start_model_update(get_catalog=offline, root=tmp_path / "upd")
    qtbot.waitUntil(lambda: updater.result is not None, timeout=10000)
    assert "Không cập nhật được" in updater.result
    assert not (tmp_path / "upd" / "active").exists() or not any((tmp_path / "upd" / "active").iterdir())
    assert mw  # module imported for the fixture
