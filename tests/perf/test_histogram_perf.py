"""Histogram of a full-size image stays fast (marker `perf`)."""

from __future__ import annotations

import time

import numpy as np
import pytest

from app.quality.histogram import histogram

pytestmark = pytest.mark.perf


def test_histogram_of_a_4000x3000_image_under_200_ms() -> None:
    big = np.random.default_rng(0).integers(0, 256, (3000, 4000, 3), np.uint8)
    histogram(big)  # warm-up
    t = time.perf_counter()
    histogram(big)
    assert time.perf_counter() - t < 0.2


def test_burst_lookup_on_10000_photos_under_20_ms(tmp_path) -> None:  # noqa: ANN001
    from app.quality.burst import neighbours
    from app.storage.project import Project

    with Project.create(tmp_path / "s", "t") as project:
        conn = project.conn
        conn.execute("INSERT INTO sources (root_path, added_at) VALUES ('/x', 't')")
        conn.executemany(
            "INSERT INTO assets (source_id, relative_path, extension, media_kind, support_level, size, mtime_ns, "
            "quick_hash, status, added_at, updated_at, capture_time, subsec) "
            "VALUES (1, ?, 'jpg', 'raster', 'full', 1, 1, ?, 'ok', 't', 't', ?, '00')",
            [(f"{i}.jpg", f"h{i}", f"2026-10-25T{10 + i // 3600:02d}:{i // 60 % 60:02d}:{i % 60:02d}")
             for i in range(10_000)])
        t = time.perf_counter()
        for aid in range(1, 101):
            neighbours(conn, aid * 97)
        assert (time.perf_counter() - t) / 100 < 0.02
