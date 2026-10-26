from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from app.selection.client_list import (
    NamePattern,
    delete_collection,
    detect_pattern,
    list_collections,
    match_assets,
    parse_client_text,
    save_collection,
)
from app.storage import db, decisions
from app.storage.project import Project

DSC = NamePattern.parse("DSC_####")


@pytest.mark.parametrize(
    ("text", "stems"),
    [
        ("9645, 9646", ["DSC_9645", "DSC_9646"]),
        ("9657-9660", ["DSC_9657", "DSC_9658", "DSC_9659", "DSC_9660"]),
        ("9657 đến 9659", ["DSC_9657", "DSC_9658", "DSC_9659"]),
        ("9657–9658", ["DSC_9657", "DSC_9658"]),
        ("9648-50", ["DSC_9648", "DSC_9649", "DSC_9650"]),
        ("DSC_9665.jpg\nDSC_9666.JPG", ["DSC_9665", "DSC_9666"]),
        ("DSC_9645-DSC_9647", ["DSC_9645", "DSC_9646", "DSC_9647"]),
        ("em chọn 9645 với 9645 nha", ["DSC_9645"]),  # duplicates collapse
        ("IMG_0012.jpg", ["IMG_0012"]),  # other camera naming is kept as written
        ("0012", ["DSC_0012"]),
        ("Golden hour 9645", ["DSC_9645"]),
    ],
)
def test_parse_client_text(text: str, stems: list[str]) -> None:
    assert parse_client_text(text, DSC).stems == stems


def test_parse_ignores_noise_and_bad_ranges() -> None:
    parsed = parse_client_text("chọn 5 tấm: 9645, 1-3 tấm, 9650-9640, 1000-5000", DSC)
    assert parsed.stems == ["DSC_9645"]
    assert parsed.ignored == ["5 (số quá ngắn)", "1-3 (số quá ngắn)", "9650-9640 (khoảng không hợp lệ)",
                              "1000-5000 (khoảng không hợp lệ)"]


def test_patterns() -> None:
    assert NamePattern.parse("Aki_###_edit").stem_for("7") == "Aki_007_edit"
    assert NamePattern.parse("DSC_####").stem_for("123456") == "DSC_123456"
    assert str(NamePattern.parse("DSC_####")) == "DSC_####"
    assert detect_pattern(["DSC_0001", "DSC_9645", "IMG_1234", "notes"]) == "DSC_####"
    assert detect_pattern([]) == "DSC_####"


@pytest.fixture
def project(tmp_path: Path) -> Project:
    p = Project.create(tmp_path / "proj", "Client")
    conn = p.conn
    conn.execute("INSERT INTO sources (root_path, added_at) VALUES ('/a', 'n'), ('/b', 'n')")
    conn.execute("INSERT INTO pair_groups (status) VALUES ('confirmed')")
    rows = [
        (1, "DSC_9645.NEF", "raw", "ok", 1), (1, "DSC_9645.JPG", "raster", "ok", 1),  # a pair
        (1, "DSC_9646.NEF", "raw", "ok", None), (1, "DSC_9647.NEF", "raw", "missing", None),
        (2, "DSC_9646.NEF", "raw", "ok", None),  # counter restarted: same name, other folder
    ]
    for src, rel, kind, status, pair in rows:
        conn.execute(
            """INSERT INTO assets (source_id, relative_path, extension, media_kind, support_level, size, mtime_ns,
               quick_hash, status, pair_group_id, added_at, updated_at) VALUES (?,?,?,?,'verified',1,1,?,?,?,'n','n')""",
            (src, rel, "." + rel.split(".")[1].lower(), kind, rel + str(src), status, pair),
        )
    yield p
    p.close()


def test_match_reports_unmatched_and_ambiguous(project: Project) -> None:
    parsed = parse_client_text("9645, 9646, 9647, 9999", DSC)
    r = match_assets(project.conn, parsed)
    assert r.matched == {"DSC_9645": [1], "DSC_9646": [3, 5]}  # JPEG of the pair is not listed separately
    assert r.unmatched == ["DSC_9647", "DSC_9999"]  # 9647 is missing on disk
    assert r.ambiguous == {"DSC_9646": [3, 5]}
    only_b = match_assets(project.conn, parsed, source_id=2)
    assert only_b.matched == {"DSC_9646": [5]}


def test_save_list_and_delete_keep_photos_and_decisions(project: Project) -> None:
    decisions.set_flag(project.conn, 3, "reject")
    r = match_assets(project.conn, parse_client_text("9645 9646 9999", DSC))
    cid = save_collection(project.conn, "Aki", r, source_text="9645 9646 9999", pattern=DSC)
    [row] = list_collections(project.conn)
    assert (row["id"], row["name"], row["n"]) == (cid, "Aki", 3)
    stored = project.conn.execute("SELECT unmatched_json, pattern FROM collections").fetchone()
    assert stored["unmatched_json"] == '["DSC_9999"]' and stored["pattern"] == "DSC_####"
    delete_collection(project.conn, cid)
    assert list_collections(project.conn) == []
    assert project.conn.execute("SELECT COUNT(*) FROM assets").fetchone()[0] == 5
    assert decisions.get(project.conn, 3).flag == "reject"


def test_v1_project_upgrades_to_v2_keeping_data(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "old.db"
    monkeypatch.setattr(db, "MIGRATIONS", db.MIGRATIONS[:1])
    monkeypatch.setattr(db, "SCHEMA_VERSION", 1)
    conn = db.connect(path)
    conn.execute("INSERT INTO project (id, name, created_at) VALUES (1, 'Aki', 'n')")
    conn.close()
    monkeypatch.undo()
    conn = db.connect(path)
    assert db.current_version(conn) == 2
    assert conn.execute("SELECT name FROM project").fetchone()[0] == "Aki"
    conn.execute("INSERT INTO collections (name, created_at) VALUES ('x', 'n')")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO collection_items (collection_id, asset_id) VALUES (1, 999)")  # FK enforced
