"""Errors of the export (their messages are shown in the export dialog, in Vietnamese)."""

from __future__ import annotations

from app.core.errors import KiraPickError


class ExportError(KiraPickError):
    pass
