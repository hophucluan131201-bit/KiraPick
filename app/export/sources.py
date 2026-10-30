"""Where the export's files come from: the imported folders or another folder (Part 3 spec §3.3)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal


@dataclass(frozen=True, slots=True)
class SourceSpec:
    mode: Literal["imported", "external"] = "imported"
    root: Path | None = None
