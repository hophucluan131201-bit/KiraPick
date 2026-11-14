"""Import speed on external drives (owner, 2026-11-13: 706 photos, RAW+JPEG on a USB drive, ~2 min). On Windows a
folder name with Vietnamese accents cannot be handed to LibRaw as a path, so the RAW's bytes are given instead.
The whole ~26 MB NEF was read to get a ~2 MB embedded preview for the grid thumbnail; now only the start of the file
is read. The geometry must be exactly what opening the path gives; the preview too, except where the file keeps its
large preview at the end (Pentax): then a smaller embedded preview of the same file, still large enough."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from app.ingest import raw_decode
from app.ingest.formats import MediaKind, format_for
from tests.conftest import load_samples, sample_path

MIN = 400  # the import's thumbnail size
RAWS = [s for s in load_samples() if (f := format_for(Path(s["file"]))) and f.kind is MediaKind.RAW]


def _key(result: tuple[raw_decode.RawInfo, raw_decode.EmbeddedPreview | None]) -> tuple:
    info, emb = result
    preview = None if emb is None else (emb.native_size, emb.is_jpeg,
                                        hashlib.sha256(emb.jpeg_bytes or emb.image.tobytes()).hexdigest())
    return info, preview


class _CountingOpen:
    """Counts the bytes read through open() of one file."""

    def __init__(self, path: Path) -> None:
        self.path, self.read = path, 0

    def __call__(self, file, mode="r", *args, **kwargs):  # noqa: ANN001, ANN002, ANN003, ANN204
        fh = _REAL_OPEN(file, mode, *args, **kwargs)
        if Path(file) == self.path and "b" in mode:
            counter = self
            real_read = fh.read

            def read(n=-1):  # noqa: ANN001, ANN202
                data = real_read(n)
                counter.read += len(data)
                return data

            fh.read = read
        return fh


_REAL_OPEN = open


@pytest.mark.parametrize("sample", RAWS, ids=[s["file"] for s in RAWS])
def test_start_of_file_gives_what_the_path_gives(sample: dict, monkeypatch) -> None:  # noqa: ANN001
    path = sample_path(sample)
    try:
        expected = _key(raw_decode.read_raw(path, draft_size=(400, 400)))
    except Exception as exc:  # noqa: BLE001 - an unreadable sample must fail the same way
        monkeypatch.setattr(raw_decode, "needs_file_object", lambda _p: True)
        with pytest.raises(type(exc)):
            raw_decode.read_raw(path, draft_size=(400, 400), from_start_min=MIN)
        return
    counting = _CountingOpen(path)
    monkeypatch.setattr(raw_decode, "needs_file_object", lambda _p: True)
    monkeypatch.setattr("builtins.open", counting)
    got = _key(raw_decode.read_raw(path, draft_size=(400, 400), from_start_min=MIN))
    assert got[0] == expected[0]  # sizes and orientation
    if got[1] != expected[1]:
        assert path.suffix.lower() == ".pef", (got[1], expected[1])
        assert got[1] is not None and got[1][1] and max(got[1][0]) >= MIN
    size = path.stat().st_size
    assert counting.read <= size
    if path.suffix.lower() == ".nef" and size > 20 << 20:  # the owner's case: a full-size NEF
        assert counting.read <= max(raw_decode.PREFIX_STEPS), (counting.read, size)


def test_only_the_import_thumbnail_reads_from_the_start(monkeypatch, public_nef: Path) -> None:  # noqa: ANN001
    """The large view, 100 % zoom and the AI analysis keep reading as before (the largest preview LibRaw picks)."""
    from app.ingest import preview
    from app.workers import import_job

    calls = []
    real = raw_decode.read_raw
    monkeypatch.setattr(raw_decode, "read_raw", lambda *a, **k: calls.append(k.get("from_start_min")) or real(*a, **k))
    preview.load_image(public_nef, max_long_side=1600, min_long_side=1600)
    assert calls == [None]
    job = import_job.ImportJob.__new__(import_job.ImportJob)
    monkeypatch.setattr(import_job, "load_image", lambda *a, **k: calls.append(("import", k.get("from_start"))) or
                        (_ for _ in ()).throw(RuntimeError("stop")))
    job._ingest_one(1, public_nef)
    assert calls[-1] == ("import", True)
