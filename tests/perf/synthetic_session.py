"""A big session for the performance tests, written straight into a session database (no import, no photos).

N assets in one source folder: JPEG names, capture times one second apart (bursts of 5 within the same second),
camera / lens / EXIF like a real import; one shared 400 px thumbnail file per 50 photos (decoding is not what the
grid benchmark measures); 10 % Chọn, 3 % Loại, 5 % rated; half the photos have a main person with a quality
measurement (so scores, chips and sorting by score are real work). The photo files do not exist — the grid, the
counts, the detail panel and the workflow steps never read them.
"""

from __future__ import annotations

import json
import random
from pathlib import Path

from PIL import Image

from app.storage.project import Project
from app.storage.sessions import open_session

THUMBS_EVERY = 50


def _thumb(path: Path, seed: int) -> None:
    rng = random.Random(seed)
    img = Image.new("RGB", (400, 267), (rng.randrange(40, 200), rng.randrange(40, 200), rng.randrange(40, 200)))
    img.save(path, "JPEG", quality=85)


def build_session(sessions: Path, root: Path, photos: int, seed: int = 7) -> Project:
    """Create (or reopen) the session of ``root`` and fill it with ``photos`` synthetic assets."""
    root.mkdir(parents=True, exist_ok=True)
    project, _restored = open_session(sessions, root)
    conn = project.conn
    rng = random.Random(seed)
    thumbs = project.cache_dir / "synthetic"
    thumbs.mkdir(exist_ok=True)
    for k in range((photos + THUMBS_EVERY - 1) // THUMBS_EVERY):
        _thumb(thumbs / f"t{k}.jpg", k)
    exif = json.dumps({"ExposureTime": "1/250", "FNumber": 2.8, "ISOSpeedRatings": 400, "FocalLength": 85})
    conn.execute("BEGIN")
    src = conn.execute("INSERT INTO sources (root_path, added_at) VALUES (?, 't')", (str(root),)).lastrowid
    rows = []
    for i in range(photos):
        second = i // 5
        t = f"2026-10-25T{10 + second // 3600:02d}:{second // 60 % 60:02d}:{second % 60:02d}"
        rows.append((i + 1, src, f"IMG_{i:05d}.JPG", t, f"{i % 5:03d}", exif))
    conn.executemany(
        "INSERT INTO assets (id, source_id, relative_path, extension, media_kind, support_level, size, mtime_ns, "
        "quick_hash, status, width, height, orientation, capture_time, subsec, make, model, lens, exif_json, added_at,"
        " updated_at) VALUES (?, ?, ?, '.jpg', 'raster', 'full', 12000000, 1, 'h', 'ok', 6000, 4000, 1, ?, ?, "
        "'NIKON CORPORATION', 'NIKON Z 6_2', 'NIKKOR Z 85mm f/1.8 S', ?, 't', 't')", rows)
    conn.executemany(
        "INSERT INTO previews (asset_id, kind, file_name, width, height, source, render_version) "
        "VALUES (?, 'thumb', ?, 400, 267, 'decoded', 1)",
        [(i + 1, f"synthetic/t{i // THUMBS_EVERY}.jpg") for i in range(photos)])
    decisions = []
    for i in range(photos):
        flag = "keep" if i % 10 == 0 else "reject" if i % 33 == 0 else None
        rating = (i % 5) + 1 if i % 20 == 0 else 0
        if flag or rating:
            decisions.append((i + 1, flag, rating))
    conn.executemany("INSERT INTO decisions (asset_id, flag, rating, favorite, updated_at) VALUES (?, ?, ?, 0, 't')",
                     decisions)
    for i in range(0, photos, 2):  # half: a main person with a quality measurement
        occ = conn.execute("INSERT INTO occurrences (asset_id, prominence, is_main, analysis_version, created_at) "
                           "VALUES (?, 1, 1, 1, 't')", (i + 1,)).lastrowid
        values = {"eye_sharp": rng.uniform(0.2, 1.0), "tech_iqa": rng.uniform(0.3, 0.9),
                  "aesthetic_mos": rng.uniform(3.5, 6.5)}
        conn.execute("INSERT INTO measurements (asset_id, occurrence_id, extractor, extractor_version, input_source, "
                     "values_json, computed_at) VALUES (?, ?, 'quality', '5', 'full', ?, 't')",
                     (i + 1, occ, json.dumps(values)))
    conn.execute("COMMIT")
    return project
