"""Error hierarchy shared by all layers.

Messages are user-facing (shown in diagnostics), so they never include EXIF
contents or other photo metadata.
"""

from __future__ import annotations

from pathlib import Path


class KiraPickError(Exception):
    """Base class for all expected, user-reportable failures."""


class ImageReadError(KiraPickError):
    """A source image could not be read. Carries the path for the UI only."""

    reason: str = "read_error"

    def __init__(self, path: Path, detail: str = "") -> None:
        self.path = path
        self.detail = detail
        super().__init__(f"{self.reason}: {path.name}" + (f" ({detail})" if detail else ""))


class UnsupportedFormatError(ImageReadError):
    """Extension unknown, or the decoder does not recognise the file contents."""

    reason = "unsupported_format"


class CorruptImageError(ImageReadError):
    """The file is recognised but truncated/damaged or holds no image data."""

    reason = "corrupt_or_incomplete"


class NoPreviewError(ImageReadError):
    """No usable embedded preview and decoding the sensor data also failed."""

    reason = "no_preview"


class UnsafePathError(KiraPickError):
    """Path rejected for safety (symlink, traversal outside the import root...)."""
