"""A small export session built directly in the database (no decoding): real files on disk with known bytes, rows
that describe them as the import would (kind, size, quick hash, capture time, camera, RAW+JPEG pair groups).

Used by the Part 3 export tests. Photos (keys of ``ExportFixture.ids``, each the photo's primary asset):
pair (DSC_0001.NEF + .JPG), pair_missing_jpeg (DSC_0002.NEF + .JPG deleted from disk), raw_only (DSC_0003.NEF),
jpeg_only (DSC_0004.JPG), tiff (DSC_0005.TIF), png (DSC_0006.PNG), rejected (DSC_0007.JPG), undecided (DSC_0008.JPG),
fav (DSC_0009.JPG, favourite, not kept), rated3 (DSC_0010.JPG, 3 stars, not kept), collected (DSC_0011.JPG, in a
client list, not kept). Kept: pair, pair_missing_jpeg, raw_only, jpeg_only, tiff, png.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from app.ingest.fingerprint import quick_fingerprint
from app.storage import decisions
from app.storage.project import Project, utc_now


@dataclass
class ExportFixture:
    project: Project
    root: Path
    dest: Path
    ids: dict[str, int] = field(default_factory=dict)  # photo key -> primary asset id
    files: dict[str, list[int]] = field(default_factory=dict)  # photo key -> all asset ids of the photo
    collection_id: int = 0


def write_file(path: Path, seed: int, size: int = 300_000) -> Path:
    """Deterministic bytes, different for every seed (head, middle and tail differ)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    block = bytes((seed * 31 + i * 7) % 251 for i in range(4096))
    data = (block * (size // len(block) + 1))[:size]
    path.write_bytes(data)
    return path


def add_asset(project: Project, source_id: int, root: Path, rel: str, *, seed: int, kind: str,
              capture_time: str | None = "2026-10-25T16:00:00", camera: tuple[str, str] | None = ("NIKON", "Z 5"),
              pair_group: int | None = None, size: int = 300_000, on_disk: bool = True) -> int:
    path = write_file(root / rel, seed, size)
    fp = quick_fingerprint(path)
    st = path.stat()
    if not on_disk:
        path.unlink()
    now = utc_now()
    return int(project.conn.execute(
        """INSERT INTO assets (source_id, relative_path, extension, media_kind, support_level, size, mtime_ns,
                               quick_hash, status, capture_time, make, model, pair_group_id, added_at, updated_at)
           VALUES (?, ?, ?, ?, 'full', ?, ?, ?, 'ok', ?, ?, ?, ?, ?, ?)""",
        (source_id, rel, Path(rel).suffix.lower(), kind, st.st_size, st.st_mtime_ns, fp.quick_hash, capture_time,
         camera[0] if camera else None, camera[1] if camera else None, pair_group, now, now),
    ).lastrowid)


def make_export_session(tmp_path: Path) -> ExportFixture:
    root = tmp_path / "Ảnh buổi chụp"
    root.mkdir(parents=True)
    project = Project.create(tmp_path / "session", "Export")
    fx = ExportFixture(project, root, tmp_path / "Xuất")
    conn = project.conn
    source_id = int(conn.execute("INSERT INTO sources (root_path, added_at) VALUES (?, ?)",
                                 (str(root), utc_now())).lastrowid)

    def pair(key: str, number: int, seed: int, *, jpeg_on_disk: bool = True) -> None:
        group = int(conn.execute("INSERT INTO pair_groups (status) VALUES ('confirmed')").lastrowid)
        raw = add_asset(project, source_id, root, f"DSC_{number:04d}.NEF", seed=seed, kind="raw", pair_group=group,
                        size=500_000)
        jpg = add_asset(project, source_id, root, f"DSC_{number:04d}.JPG", seed=seed + 1, kind="raster",
                        pair_group=group, on_disk=jpeg_on_disk)
        fx.ids[key], fx.files[key] = raw, [raw, jpg]

    def single(key: str, name: str, seed: int, kind: str = "raster") -> None:
        aid = add_asset(project, source_id, root, name, seed=seed, kind=kind)
        fx.ids[key], fx.files[key] = aid, [aid]

    pair("pair", 1, 10)
    pair("pair_missing_jpeg", 2, 20, jpeg_on_disk=False)
    single("raw_only", "DSC_0003.NEF", 30, "raw")
    single("jpeg_only", "DSC_0004.JPG", 40)
    single("tiff", "DSC_0005.TIF", 50)
    single("png", "DSC_0006.PNG", 60)
    single("rejected", "DSC_0007.JPG", 70)
    single("undecided", "DSC_0008.JPG", 80)
    single("fav", "DSC_0009.JPG", 90)
    single("rated3", "DSC_0010.JPG", 100)
    single("collected", "DSC_0011.JPG", 110)
    for key in ("pair", "pair_missing_jpeg", "raw_only", "jpeg_only", "tiff", "png"):
        decisions.set_flag(conn, fx.ids[key], "keep")
    decisions.set_flag(conn, fx.ids["rejected"], "reject")
    decisions.set_favorite(conn, fx.ids["fav"], True)
    decisions.set_favorite(conn, fx.ids["pair"], True)
    decisions.set_rating(conn, fx.ids["rated3"], 3)
    decisions.set_rating(conn, fx.ids["raw_only"], 4)
    fx.collection_id = int(conn.execute("INSERT INTO collections (name, created_at) VALUES ('Khách A', ?)",
                                        (utc_now(),)).lastrowid)
    for key in ("collected", "jpeg_only"):
        conn.execute("INSERT INTO collection_items (collection_id, asset_id) VALUES (?, ?)",
                     (fx.collection_id, fx.ids[key]))
    conn.commit()
    return fx


def snapshot(plan) -> dict[str, list]:  # noqa: ANN001
    """The comparable content of a plan, in the terms of the export before Part 3: the files it would copy
    (source name, dest_relative), the targets that already hold the file, the missing files.

    Contract note (CR-P3-A02): since Checkpoint A v2 a target that seems to hold the file is still an operation
    (``maybe_present``, verified by full SHA-256 when copying); the old plan left it out of ``items``. ``copies`` is
    therefore the operations that are not ``maybe_present`` (``plan.to_copy``), and ``already_present`` the names of
    the ``maybe_present`` ones — the same two lists the old plan gave."""
    return {
        "copies": sorted((Path(i.source).name, i.dest_relative) for i in plan.to_copy),
        "already_present": sorted(plan.already_present),
        "missing": sorted(plan.missing),
    }


def tree_digest(*roots: Path) -> dict[str, tuple[int, int, str]]:
    """Every file under these roots: (size, mtime_ns, sha256) — to prove sources unchanged."""
    from app.ingest.fingerprint import full_sha256

    out = {}
    for root in roots:
        for dirpath, _dirs, names in os.walk(root):
            for name in names:
                p = Path(dirpath) / name
                st = p.stat()
                out[str(p)] = (st.st_size, st.st_mtime_ns, full_sha256(p))
    return out
