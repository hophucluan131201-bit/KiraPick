"""Product name and where the app keeps its own data (never the user's photos).

The app was called "Snorlu AI Culling" until 0.2.0b1; ``migrate_legacy_data`` moves
that data (remembered folders, learning examples, logs) and the window settings to
the new name once, so an upgrade loses nothing.
"""

from __future__ import annotations

import logging
import os
import shutil
from pathlib import Path

APP_NAME = "KiraPick"
APP_TAGLINE = "lọc ảnh cosplay & chân dung bằng AI, chạy offline"
SETTINGS_IDS = ("KiraPick", "KiraPick")  # QSettings(organization, application)
LEGACY_SETTINGS_IDS = ("Snorlu", "AI Culling")
_LEGACY_DIR_PARTS = ("Snorlu", "Snorlu AI Culling")

log = logging.getLogger(__name__)


PROFILE_ENV = "KIRAPICK_PROFILE_DIR"


def profile_dir() -> Path | None:
    """A separate test profile (owner tests, REG-3): every folder and setting of the app goes under it instead of
    %LOCALAPPDATA% and the registry, so a test never touches the user's real data. Unset in normal use."""
    value = os.environ.get(PROFILE_ENV, "").strip().strip('"')
    return Path(value) if value else None


def app_settings():  # noqa: ANN201 - QSettings
    """The app's settings: the registry (HKCU\\Software\\KiraPick) normally, an .ini file in a test profile."""
    from PySide6.QtCore import QSettings

    profile = profile_dir()
    if profile is not None:
        return QSettings(str(profile / APP_NAME / "settings.ini"), QSettings.Format.IniFormat)
    return QSettings(*SETTINGS_IDS)


def _local_base() -> Path:
    """%LOCALAPPDATA% on Windows, ~/.local/share on Linux (no Qt application needed); a test profile if set."""
    profile = profile_dir()
    if profile is not None:
        return profile
    from PySide6.QtCore import QStandardPaths

    base = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.GenericDataLocation)
    return Path(base) if base else Path.home() / ".kirapick-data"


def icon_path() -> Path | None:
    """The app icon, from the source tree or from a packaged build."""
    import sys

    here = Path(__file__).resolve().parents[1]
    for candidate in (Path(getattr(sys, "_MEIPASS", here)) / "assets" / "kirapick.png",
                      here / "packaging" / "kirapick.png"):
        if candidate.is_file():
            return candidate
    return None


def mode_image_path(name: str) -> Path | None:
    """The mode picker's photo ``name`` ("personal" / "event"; the owner's own photos), from the source tree or a
    packaged build."""
    import sys

    here = Path(__file__).resolve().parents[1]
    for candidate in (Path(getattr(sys, "_MEIPASS", here)) / "assets" / "modes" / f"{name}.jpg",
                      here / "packaging" / "modes" / f"{name}.jpg"):
        if candidate.is_file():
            return candidate
    return None


def data_dir() -> Path:
    """Folder with sessions/, learning/ and logs/ of this app."""
    return _local_base() / APP_NAME


def legacy_data_dir() -> Path:
    return _local_base().joinpath(*_LEGACY_DIR_PARTS)


def migrate_legacy_data(new: Path | None = None, old: Path | None = None) -> bool:
    """Move the pre-rename data folder to the new one, once. Returns True if something moved."""
    new = new or data_dir()
    old = old or legacy_data_dir()
    if new.exists() or not old.is_dir() or old.is_symlink():
        return False
    new.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.replace(old, new)  # same disk: instant
    except OSError:
        shutil.copytree(old, new, symlinks=True)
        shutil.rmtree(old, ignore_errors=True)
    try:
        old.parent.rmdir()  # the empty "Snorlu" folder
    except OSError:
        pass
    log.info("moved app data from the old name to %s", new)
    return True


def migrate_legacy_settings() -> None:
    """Copy window settings (size, shortcuts panel, auto-advance) from the old name, once."""
    from PySide6.QtCore import QSettings

    if profile_dir() is not None:
        return  # a test profile starts empty
    new = QSettings(*SETTINGS_IDS)
    if new.allKeys():
        return
    old = QSettings(*LEGACY_SETTINGS_IDS)
    for key in old.allKeys():
        new.setValue(key, old.value(key))
    new.sync()
