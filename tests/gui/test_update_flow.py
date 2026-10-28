"""⚙ Cập nhật KiraPick: asks first, never automatic unless switched on, nothing installed on failure."""

from __future__ import annotations

import hashlib
from pathlib import Path

from PySide6.QtWidgets import QMessageBox

import app.ui.update_dialog as ud
from tests.gui.test_main_window import _window, env  # noqa: F401 - fixture


def _releases(data: bytes) -> list[dict]:
    return [{"tag_name": "v9.9.9", "prerelease": False, "draft": False,
             "assets": [{"name": "KiraPick-Setup-9.9.9.exe", "size": len(data), "browser_download_url": "https://x/s",
                         "digest": "sha256:" + hashlib.sha256(data).hexdigest()}]}]


def test_auto_check_is_off_by_default(qtbot, env: dict, monkeypatch) -> None:  # noqa: F811
    calls = []
    monkeypatch.setattr(ud, "list_releases", lambda: calls.append(1) or [])  # noqa: E501
    w = _window(qtbot, env)
    assert not w.act_auto_update.isChecked()
    w._maybe_auto_check()
    qtbot.wait(200)
    assert calls == []


def test_user_started_update_downloads_checks_and_starts_the_installer(qtbot, env: dict, monkeypatch,
                                                                      tmp_path: Path) -> None:  # noqa: F811
    w = _window(qtbot, env)
    data = b"installer"
    asked, started = [], []
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: asked.append(a[2]) or QMessageBox.StandardButton.Yes)
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)
    monkeypatch.setattr(w, "close", lambda: True)
    updater = w.start_app_update(get_releases=lambda: _releases(data),
                                 fetch=lambda url, dest, progress: dest.write_bytes(data),
                                 folder=tmp_path / "dl", start=started.append)
    qtbot.waitUntil(lambda: updater.result is not None, timeout=10000)
    assert "Không gửi ảnh" in asked[0]  # privacy notice before any connection
    assert updater.result.startswith("Đang mở bộ cài") and started and started[0].name == "KiraPick-Setup-9.9.9.exe"


def test_offline_changes_nothing(qtbot, env: dict, monkeypatch, tmp_path: Path) -> None:  # noqa: F811
    w = _window(qtbot, env)
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: None)

    def offline() -> list[dict]:
        raise ud.UpdateError("không kết nối được GitHub (URLError)")

    updater = w.start_app_update(get_releases=offline, folder=tmp_path / "dl", start=lambda p: None)
    qtbot.waitUntil(lambda: updater.result is not None, timeout=10000)
    assert "Không cập nhật được" in updater.result and not (tmp_path / "dl").exists()
