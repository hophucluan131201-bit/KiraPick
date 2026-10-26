"""Turn a client's free-text pick list into photos.

Clients reply with things like ``"9645, 9646, 9657-9660, DSC_9665.jpg"``.
With a file-name pattern such as ``DSC_####`` (each ``#`` = one digit) every
bare number becomes a file stem (``9645`` -> ``DSC_9645``); tokens that already
carry letters are taken as stems as written. Extensions are ignored, so a
client choosing ``DSC_9645.jpg`` selects the RAW ``DSC_9645.NEF`` too.

Nothing is guessed silently: the result lists every token that matched no
photo, and every token that matched more than one photo (camera counters
restart after 9999, so the same name can exist in two folders).
"""

from __future__ import annotations

import json
import re
import sqlite3
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import PurePosixPath

from app.storage.project import utc_now

MAX_RANGE = 1000  # a typo like "9645-19645" must not select ten thousand photos
DEFAULT_MIN_DIGITS = 3  # "chọn 5 tấm" must not select DSC_0005


@dataclass(frozen=True, slots=True)
class NamePattern:
    prefix: str
    width: int  # number of '#'
    suffix: str

    @classmethod
    def parse(cls, text: str) -> NamePattern:
        text = text.strip()
        m = re.search(r"#+", text)
        if not m:
            return cls(text, 0, "")
        return cls(text[: m.start()], len(m.group()), text[m.end():])

    def stem_for(self, digits: str) -> str:
        number = digits.lstrip("0") or "0"
        return f"{self.prefix}{number.zfill(self.width) if self.width else digits}{self.suffix}"

    def __str__(self) -> str:
        return f"{self.prefix}{'#' * self.width}{self.suffix}"


def detect_pattern(stems: Iterable[str]) -> str:
    """Most common 'letters + fixed-width number' shape among file stems."""
    shapes: Counter[tuple[str, int, str]] = Counter()
    for stem in stems:
        m = re.fullmatch(r"(\D*?)(\d+)(\D*)", stem)
        if m:
            shapes[(m.group(1), len(m.group(2)), m.group(3))] += 1
    if not shapes:
        return "DSC_####"
    (prefix, width, suffix), _ = shapes.most_common(1)[0]
    return f"{prefix}{'#' * width}{suffix}"


# letters/underscore/dash prefix (optional) + number + optional extension + optional "- end"
_TOKEN = re.compile(
    r"(?<![A-Za-z0-9])"
    r"(?P<prefix>[A-Za-z][A-Za-z_\-]*?)?(?P<start>\d+)(?:\.[A-Za-z0-9]{2,4})?"
    r"(?:\s*-\s*(?:(?P=prefix))?(?P<end>\d+)(?:\.[A-Za-z0-9]{2,4})?)?"
    r"(?![A-Za-z0-9])"
)


@dataclass(slots=True)
class ParsedList:
    stems: list[str] = field(default_factory=list)  # ordered, unique (casefold)
    ignored: list[str] = field(default_factory=list)  # text fragments not used, with reason


def parse_client_text(text: str, pattern: NamePattern, *, min_digits: int = DEFAULT_MIN_DIGITS) -> ParsedList:
    normalized = re.sub(r"\s*(?:–|—|~|\bđến\b|\bden\b|\bto\b)\s*", "-", text, flags=re.IGNORECASE)
    out = ParsedList()
    seen: set[str] = set()

    def add(stem: str) -> None:
        key = stem.casefold()
        if key not in seen:
            seen.add(key)
            out.stems.append(stem)

    for m in _TOKEN.finditer(normalized):
        prefix, start, end = m.group("prefix"), m.group("start"), m.group("end")
        if prefix is None and len(start) < min_digits:
            out.ignored.append(f"{m.group(0).strip()} (số quá ngắn)")
            continue
        def stem_of(digits: str, width: int) -> str:
            return f"{prefix}{digits.zfill(width)}" if prefix else pattern.stem_for(digits)
        if end is None:
            add(stem_of(start, len(start)))
            continue
        if len(end) < len(start):  # shorthand "9645-50" = 9645..9650
            end = start[: len(start) - len(end)] + end
        a, b = int(start), int(end)
        if b < a or b - a >= MAX_RANGE:
            out.ignored.append(f"{m.group(0).strip()} (khoảng không hợp lệ)")
            continue
        for n in range(a, b + 1):
            add(stem_of(str(n), len(start)))
    return out


@dataclass(slots=True)
class MatchResult:
    matched: dict[str, list[int]] = field(default_factory=dict)  # stem -> asset ids (photo-level)
    unmatched: list[str] = field(default_factory=list)

    @property
    def asset_ids(self) -> list[int]:
        return list(dict.fromkeys(i for ids in self.matched.values() for i in ids))

    @property
    def ambiguous(self) -> dict[str, list[int]]:
        return {stem: ids for stem, ids in self.matched.items() if len(ids) > 1}


def _photo_stems(conn: sqlite3.Connection, source_id: int | None) -> dict[str, list[int]]:
    """stem -> photo ids; a RAW+JPEG pair counts once (as its RAW, like in the grid)."""
    sql = """SELECT a.id, a.relative_path, a.source_id FROM assets a
             WHERE a.status NOT IN ('missing', 'duplicate')
               AND NOT (a.media_kind = 'raster' AND a.pair_group_id IS NOT NULL
                        AND EXISTS (SELECT 1 FROM assets r WHERE r.pair_group_id = a.pair_group_id
                                    AND r.media_kind = 'raw'))"""
    params: tuple = ()
    if source_id is not None:
        sql += " AND a.source_id = ?"
        params = (source_id,)
    stems: dict[str, list[int]] = {}
    for r in conn.execute(sql + " ORDER BY a.id", params):
        stems.setdefault(PurePosixPath(r["relative_path"]).stem.casefold(), []).append(int(r["id"]))
    return stems


def match_assets(conn: sqlite3.Connection, parsed: ParsedList, *, source_id: int | None = None) -> MatchResult:
    index = _photo_stems(conn, source_id)
    result = MatchResult()
    for stem in parsed.stems:
        ids = index.get(stem.casefold())
        if ids:
            result.matched[stem] = ids
        else:
            result.unmatched.append(stem)
    return result


def save_collection(
    conn: sqlite3.Connection, name: str, result: MatchResult, *, source_text: str, pattern: NamePattern
) -> int:
    """Store the client's picks as a named list. Returns the collection id."""
    cid = int(conn.execute(
        """INSERT INTO collections (name, kind, source_text, pattern, unmatched_json, created_at)
           VALUES (?, 'client', ?, ?, ?, ?)""",
        (name.strip() or "Khách chọn", source_text, str(pattern), json.dumps(result.unmatched, ensure_ascii=False),
         utc_now()),
    ).lastrowid)
    conn.executemany(
        "INSERT OR IGNORE INTO collection_items (collection_id, asset_id, token) VALUES (?, ?, ?)",
        [(cid, asset_id, stem) for stem, ids in result.matched.items() for asset_id in ids],
    )
    return cid


def list_collections(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        """SELECT c.id, c.name, c.created_at, COUNT(i.asset_id) AS n FROM collections c
           LEFT JOIN collection_items i ON i.collection_id = c.id GROUP BY c.id ORDER BY c.id"""
    ).fetchall()


def delete_collection(conn: sqlite3.Connection, collection_id: int) -> None:
    """Deletes only the list itself; photos and decisions are untouched."""
    conn.execute("DELETE FROM collections WHERE id = ?", (collection_id,))
