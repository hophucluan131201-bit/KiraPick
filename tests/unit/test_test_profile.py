"""REG-3: a separate test profile (KIRAPICK_PROFILE_DIR): data, logs, events and settings go under it."""

from __future__ import annotations

from pathlib import Path

from app import branding


def test_profile_moves_every_folder_and_the_settings(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setenv(branding.PROFILE_ENV, f'"{tmp_path / "profile"}" ')  # quotes / spaces from PowerShell
    assert branding.data_dir() == tmp_path / "profile" / branding.APP_NAME
    from app.media import event as ev

    assert ev.media_root() == tmp_path / "profile" / branding.APP_NAME / "media"
    s = branding.app_settings()
    s.setValue("probe", 1)
    s.sync()
    assert Path(s.fileName()) == tmp_path / "profile" / branding.APP_NAME / "settings.ini"
    assert Path(s.fileName()).is_file()


def test_without_the_variable_nothing_changes(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.delenv(branding.PROFILE_ENV, raising=False)
    assert branding.profile_dir() is None
    assert branding.app_settings().organizationName() == branding.SETTINGS_IDS[0]
