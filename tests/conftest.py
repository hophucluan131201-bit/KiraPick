from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PHOTOS = ROOT / "test_photos"
MANIFEST = ROOT / "tests" / "fixtures" / "raw_samples.json"


def load_samples() -> list[dict]:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))["samples"]


def sample_path(sample: dict) -> Path:
    path = PHOTOS / sample["file"]
    if not path.exists():
        pytest.skip(f"sample not present: {sample['file']} (run scripts/raw_samples.py fetch)")
    return path


@pytest.fixture
def public_nef() -> Path:
    """A real, publicly redistributable NEF (NASA ISS photo, public domain)."""
    path = PHOTOS / "public" / "iss030e122639.NEF"
    if not path.exists():
        pytest.skip("public NEF sample absent (run scripts/raw_samples.py fetch)")
    return path
