"""Windows PowerShell 5.1 reads a script without a BOM as ANSI and one with two BOMs as a parse error (REG-3):
every PowerShell script with non-ASCII text starts with exactly one UTF-8 BOM."""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
BOM = b"\xef\xbb\xbf"


@pytest.mark.parametrize("script", sorted(ROOT.glob("scripts/*.ps1")), ids=lambda p: p.name)
def test_one_bom_when_not_ascii(script: Path) -> None:
    data = script.read_bytes()
    assert not data[len(BOM):].startswith(BOM), "two BOMs"
    if any(b > 127 for b in data.removeprefix(BOM)):
        assert data.startswith(BOM), "non-ASCII text without a UTF-8 BOM"
