"""M11 (MED-EXP): P photos copied by moment / shot size; originals never change; nothing is overwritten.

Cases asked by the review: P photos without a moment, two cameras with the same file name, SHA-256 of the originals.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta
from pathlib import Path

from app.media import cameras as cam
from app.media import event as ev
from app.media import export as mx
from app.media import labels as lb
from app.media import moments as mo
from app.storage import decisions
from tests.media.fixtures import hashes, photo

DAY = datetime(2026, 6, 19, 9, 0, 0)


def _at(s: int) -> str:
    return (DAY + timedelta(seconds=s)).strftime("%Y:%m:%d %H:%M:%S")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _two_cameras(tmp_path: Path):  # noqa: ANN202
    a, b = tmp_path / "MayA", tmp_path / "MayB"
    photo(a / "DSC_0001.jpg", 1, taken=_at(0), make="NIKON", model="Z 6")
    photo(a / "DSC_0002.jpg", 2, taken=_at(1800), make="NIKON", model="Z 6")
    photo(b / "DSC_0001.jpg", 3, taken=_at(30), make="NIKON", model="Z 6")  # same name, same model, other body
    photo(b / "DSC_0003.jpg", 4, taken=_at(60), make="NIKON", model="Z 6")
    e = ev.create_event("export", tmp_path / "media")
    cam.import_folder(e, a)
    cam.import_folder(e, b)
    rows = e.conn.execute("SELECT a.id, s.root_path, a.relative_path FROM assets a JOIN sources s ON s.id = a.source_id")
    ids = {f"{Path(r[1]).name}/{Path(r[2]).stem}": r[0] for r in rows}
    return e, ids, (a, b)


def _files(out: Path) -> dict[str, str]:
    return {str(p.relative_to(out)).replace("\\", "/"): _sha(p) for p in sorted(out.rglob("*.jpg"))}


def test_p_photos_without_a_moment_and_same_names_from_two_cameras(tmp_path: Path) -> None:
    e, ids, folders = _two_cameras(tmp_path)
    before = [hashes(f) for f in folders]
    for key in ("MayA/DSC_0001", "MayB/DSC_0001", "MayB/DSC_0003"):
        decisions.set_flag(e.conn, ids[key], "keep")
    decisions.set_flag(e.conn, ids["MayA/DSC_0002"], "reject")
    out = tmp_path / "out1"
    p = mx.plan(e, out, mx.BY_MOMENT)  # not analysed: no moments yet
    result = mx.run(e, p)
    files = _files(out)
    assert len(files) == 3 and all(k.startswith(mx.NO_MOMENT + "/") for k in files), files
    assert f"{mx.NO_MOMENT}/DSC_0001.jpg" in files and f"{mx.NO_MOMENT}/DSC_0003.jpg" in files
    # the two DSC_0001 are two different files with each camera's own content
    assert sorted(files.values()) == sorted([_sha(folders[0] / "DSC_0001.jpg"), _sha(folders[1] / "DSC_0001.jpg"),
                                             _sha(folders[1] / "DSC_0003.jpg")])
    assert not result.failed and len(result.copied) == 3
    assert [hashes(f) for f in folders] == before  # originals: same bytes, still there (copies, not moves)
    assert (e.folder / mx.RECORD_DIR).is_dir() and any((e.folder / mx.RECORD_DIR).iterdir())
    e.close()


def test_by_moment_by_shot_and_never_overwrite(tmp_path: Path) -> None:
    e, ids, folders = _two_cameras(tmp_path)
    before = [hashes(f) for f in folders]
    mo.analyse(e)
    mo.rename(e, mo.moment_of(e.conn, ids["MayA/DSC_0001"]), "Khai mạc / Opening")  # '/' made safe
    for key in ids:
        decisions.set_flag(e.conn, ids[key], "keep")
    out = tmp_path / "out2"
    first_moment = "01 Khai mạc _ Opening"
    (out / first_moment).mkdir(parents=True)
    (out / first_moment / "DSC_0003.jpg").write_bytes(b"not a photo: must survive")
    mx.run(e, mx.plan(e, out, mx.BY_MOMENT))
    files = _files(out)
    assert (out / first_moment / "DSC_0003.jpg").read_bytes() == b"not a photo: must survive"
    assert {k.split("/")[0] for k in files} == {first_moment, "02 Khoảnh khắc 09_30"}  # ':' is not allowed in a Windows folder name
    assert sum(1 for k in files if k.startswith(first_moment)) == 4  # 3 copies + the existing file
    lb.confirm(e, [ids["MayA/DSC_0001"]], "shot", "can")
    out3 = tmp_path / "out3"
    mx.run(e, mx.plan(e, out3, mx.BY_SHOT))
    shot_files = _files(out3)
    assert {k.split("/")[0] for k in shot_files} == {"Cận", mx.NO_SHOT}
    assert len(shot_files) == 4
    assert [hashes(f) for f in folders] == before
    e.close()
