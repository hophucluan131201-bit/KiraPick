"""DEV-ONLY helper for the RAW sample corpus in test_photos/ (git-ignored).

    python scripts/raw_samples.py fetch     # download public samples, verify SHA-256
    python scripts/raw_samples.py rebuild   # re-derive expectations in the manifest

This script uses the network and is never part of the application runtime.
Samples with ``url: null`` are the photographer's private files: copy them
into test_photos/ by hand; they are never downloaded or committed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

MANIFEST = ROOT / "tests" / "fixtures" / "raw_samples.json"
PHOTOS = ROOT / "test_photos"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        while chunk := fh.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def fetch() -> int:
    samples = json.loads(MANIFEST.read_text(encoding="utf-8"))["samples"]
    failures = 0
    for s in samples:
        target = PHOTOS / s["file"]
        if target.exists() and _sha256(target) == s["sha256"]:
            continue
        if not s.get("url"):
            print(f"missing private sample (copy manually): {s['file']}")
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        url = urllib.request.quote(s["url"], safe=":/")
        print(f"downloading {s['file']} ...")
        tmp = target.with_suffix(target.suffix + ".part")
        with urllib.request.urlopen(url, timeout=120) as resp, open(tmp, "wb") as out:  # noqa: S310 - fixed https URLs
            while chunk := resp.read(1 << 20):
                out.write(chunk)
        if _sha256(tmp) != s["sha256"]:
            tmp.unlink()
            print(f"  SHA-256 mismatch, discarded: {s['file']}")
            failures += 1
            continue
        tmp.replace(target)
    return 1 if failures else 0


def rebuild() -> int:
    from app.core.errors import ImageReadError
    from app.ingest import raw_decode
    from app.ingest.metadata import read_metadata
    from app.ingest.preview import load_full_resolution, load_image

    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    for s in data["samples"]:
        path = PHOTOS / s["file"]
        if not path.exists():
            print(f"skip (absent): {s['file']}")
            continue
        for key in ("orientation", "preview_source", "expect", "make", "model"):
            s.pop(key, None)
        meta = read_metadata(path)
        try:
            info, _ = raw_decode.read_raw(path)
            s["orientation"] = info.orientation
            s["preview_source"] = load_image(path, max_long_side=320, min_long_side=320).source.value
            try:
                load_full_resolution(path)
                s["expect"] = "ok"
            except ImageReadError as exc:
                s["expect"] = f"preview_only:{type(exc).__name__}"
        except ImageReadError as exc:
            s["expect"] = type(exc).__name__
        if meta.make:
            s["make"] = meta.make
        if meta.model:
            s["model"] = meta.model
        print(f"{s['file']}: {s['expect']}")
    MANIFEST.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=["fetch", "rebuild"])
    sys.exit({"fetch": fetch, "rebuild": rebuild}[parser.parse_args().command]())
