"""The export's ③ Thư mục đích option (Part 3 spec §3.4)."""

from __future__ import annotations

from enum import Enum


class Layout(str, Enum):
    SINGLE = "single"  # every file into the destination folder
    SUBJECTS = "subjects"  # one folder per subject
