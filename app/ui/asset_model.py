"""List model of photos for the grid/filmstrip, with asynchronous thumbnails.

Rows come from SQLite on the UI thread (a single indexed query); thumbnail
JPEGs from the project cache are decoded to QImage on a thread pool and turned
into QPixmaps on the UI thread.
"""

from __future__ import annotations

import json
import threading
import re
from collections import OrderedDict
from dataclasses import dataclass, field, replace
from enum import Enum
from pathlib import Path, PurePosixPath
from collections.abc import Callable
from typing import Any

from PySide6.QtCore import (
    QAbstractListModel,
    QModelIndex,
    QObject,
    QPersistentModelIndex,
    QRunnable,
    QSize,
    Qt,
    QThreadPool,
    Signal,
)
from PySide6.QtGui import QImage, QPixmap, QTransform

from app.identity.actions import UNIDENTIFIED_ASSETS
from app.quality.rank import Ranked, rank
from app.quality.score import Score, photo_scores
from app.storage import view
from app.storage.stats import SHOWN_PHOTO_SQL
from app.storage.project import Project
from app.ui.score_style import chip_for, display_value
from app.ui.shutdown import Gate

THUMB_DISPLAY = 240  # long side of cached pixmaps at 100 % and the default card size
THUMB_FILE = 400  # long side of the thumbnail written at import (app.workers.import_job.THUMB_LONG_SIDE)
HD_LONG_SIDE = 800  # larger cards / high-DPI screens: a sharper thumbnail made once from the photo, cached
HD_DIR = "thumb_hd"  # in the session's cache folder; the file name carries the photo's size and mtime
_PIXMAP_CACHE_SIZE = 600  # at most this many thumbnails …
_PIXMAP_BUDGET = 256 * 1024 * 1024  # … and at most this many bytes (large cards at 200 %: ~1.2 MB each)

ROLE_RECORD = Qt.ItemDataRole.UserRole + 1


class Filter(str, Enum):
    ALL = "all"
    UNFLAGGED = "unflagged"
    KEEP = "keep"
    REJECT = "reject"
    FAVORITE = "favorite"
    RATED = "rated"  # rating >= min_rating
    ERRORS = "errors"
    COLLECTION = "collection"  # photos of one client list
    SUBJECT = "subject"  # photos where one person was recognised
    UNIDENTIFIED = "unidentified"  # photos with a main person not yet assigned


class Sort(str, Enum):
    TIME = "time"  # capture order
    SCORE = "score"  # technical score, best first
    TASTE = "taste"  # "Hợp gu bạn", best first (photos without it last)
    RANK = "rank"  # ranking value (technical blended with taste), best first
    PICKS_FIRST = "picks"  # photos the AI chose (in pick order), then the rest by score


def sort_records(rows: list["AssetRecord"], sort: Sort) -> list["AssetRecord"]:
    """Stable sort (equal values keep capture order); photos without the value go last."""
    def key_of(value: float | None) -> float:
        return -(value if value is not None else -1.0)

    def tech(rec: "AssetRecord") -> float | None:
        if rec.ranked is not None:
            return rec.ranked.tech
        return rec.score.total if rec.score is not None else None

    if sort is Sort.SCORE:
        return sorted(rows, key=lambda r: key_of(tech(r)))
    if sort is Sort.TASTE:
        return sorted(rows, key=lambda r: key_of(r.ranked.taste if r.ranked else None))
    if sort is Sort.RANK:
        return sorted(rows, key=lambda r: key_of(r.ranked.value if r.ranked else tech(r)))
    if sort is Sort.PICKS_FIRST:
        return sorted(rows, key=lambda r: (r.pick_rank is None, r.pick_rank or 0,
                                           key_of(r.ranked.value if r.ranked else tech(r))))
    return rows


@dataclass(slots=True)
class AssetRecord:
    id: int
    source_id: int
    path: Path
    relative_path: str
    extension: str
    status: str
    error: str | None
    thumb_file: Path | None
    capture_time: str | None
    width: int | None
    height: int | None
    camera: str | None
    lens: str | None
    exif: dict[str, Any] = field(default_factory=dict)
    paired_with: list[str] = field(default_factory=list)
    preview_source: str | None = None
    flag: str | None = None
    rating: int = 0
    favorite: bool = False
    focus: str | None = None  # the user's Q / W / R sharpness label
    uncertain: bool = False  # in a person view: only suggested (no clear face), needs a look
    score: Score | None = None  # of the person shown (person view) or of the main person
    pick_rank: int | None = None  # chosen by "⭐ Chọn ảnh": 1 = first choice
    ranked: Ranked | None = None  # technical score blended with the taste score (None = not scored)
    rotation: int = 0  # "Xoay xem": quarter turns clockwise, display only (app.storage.view)

    @property
    def name(self) -> str:
        return Path(self.relative_path).name


_QUERY = """
SELECT a.id, a.source_id, a.relative_path, a.extension, a.status, a.error, a.capture_time, a.width, a.height,
       a.make, a.model, a.lens, a.exif_json, a.pair_group_id, s.root_path,
       p.file_name AS thumb, p.source AS preview_source,
       d.flag, COALESCE(d.rating, 0) AS rating, COALESCE(d.favorite, 0) AS favorite, d.focus
FROM assets a
JOIN sources s ON s.id = a.source_id
LEFT JOIN previews p ON p.asset_id = a.id AND p.kind = 'thumb'
LEFT JOIN decisions d ON d.asset_id = a.id AND d.subject_id IS NULL
WHERE """ + SHOWN_PHOTO_SQL + "\n"

_FILTER_SQL = {
    Filter.ALL: "",
    Filter.UNFLAGGED: " AND d.flag IS NULL AND a.status = 'ok'",
    Filter.KEEP: " AND d.flag = 'keep'",
    Filter.REJECT: " AND d.flag = 'reject'",
    Filter.FAVORITE: " AND d.favorite = 1",
    Filter.RATED: " AND COALESCE(d.rating, 0) >= :min_rating",
    Filter.ERRORS: " AND a.status = 'error'",
    Filter.COLLECTION: " AND a.id IN (SELECT asset_id FROM collection_items WHERE collection_id = :target_id)",
    Filter.SUBJECT: " AND a.id IN (SELECT asset_id FROM occurrences WHERE subject_id = :target_id)",
    Filter.UNIDENTIFIED: f" AND a.id IN ({UNIDENTIFIED_ASSETS})",
}


def search_tokens(text: str) -> list[str]:
    """'9645 9650' or '9645, DSC_97' -> case-insensitive substrings, any of which may match."""
    return [t for t in re.split(r"[\s,;]+", text.casefold()) if t]


def _camera(make: str | None, model: str | None) -> str | None:
    if not model:
        return make
    if make and not model.lower().startswith(make.split()[0].lower()):
        return f"{make.split()[0].title()} {model}"
    return model


def _pixmap_bytes(pm: QPixmap) -> int:
    return pm.width() * pm.height() * 4


def turned(pm: QPixmap, turns: int) -> QPixmap:
    """The pixmap turned ``turns`` quarter turns clockwise (display only)."""
    return pm.transformed(QTransform().rotate(90 * (turns % 4))) if turns % 4 and not pm.isNull() else pm


class _ThumbSignals(QObject):
    loaded = Signal(int, QImage, int)  # asset id, image, generation


def hd_thumbnail(source: Path, hd_dir: Path, asset_id: int) -> Path | None:
    """An 800 px thumbnail of the photo, made once (RAW: its embedded preview) and cached in the session folder.
    The photo is only read. None when it cannot be made (the 400 px import thumbnail is used then)."""
    try:
        st = source.stat()
        target = hd_dir / f"{asset_id}_{st.st_size}_{st.st_mtime_ns}.jpg"
        if target.is_file():
            return target
        from app.ingest.preview import load_image

        loaded = load_image(source, max_long_side=HD_LONG_SIDE, min_long_side=HD_LONG_SIDE)
        hd_dir.mkdir(parents=True, exist_ok=True)
        tmp = target.with_name(f"{target.stem}.{threading.get_ident()}.part")  # one per worker thread
        try:
            loaded.image.save(tmp, "JPEG", quality=88)
            tmp.replace(target)  # complete files only, even if two decodes of the same photo race
        except BaseException:
            tmp.unlink(missing_ok=True)  # e.g. disk full: no half-written file left taking space
            raise
        return target
    except Exception:  # noqa: BLE001 - only the sharper thumbnail is lost
        return None


class _ThumbTask(QRunnable):
    def __init__(self, asset_id: int, path: Path, signals: _ThumbSignals, target: int = THUMB_DISPLAY,
                 generation: int = 0, source: Path | None = None, hd_dir: Path | None = None) -> None:
        super().__init__()
        self.asset_id, self.path, self.signals, self.target = asset_id, path, signals, target
        self.generation, self.source, self.hd_dir = generation, source, hd_dir

    def run(self) -> None:
        path = self.path
        if self.target > THUMB_FILE and self.source is not None and self.hd_dir is not None:
            path = hd_thumbnail(self.source, self.hd_dir, self.asset_id) or path
        image = QImage(str(path))
        if not image.isNull():
            image = image.scaled(
                self.target, self.target, Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        self.signals.loaded.emit(self.asset_id, image, self.generation)


class AssetListModel(QAbstractListModel):
    thumbnail_ready = Signal(int)  # asset id

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._project: Project | None = None
        self._rows: list[AssetRecord] = []
        self._row_of: dict[int, int] = {}
        self._filter = Filter.ALL
        self._min_rating = 1
        self._source_id: int | None = None
        self._target_id: int | None = None  # collection or subject id, depending on the filter
        self._search: list[str] = []
        self._sort = Sort.TIME
        self._ranker: Callable[[int, Score], Ranked] | None = None
        self._pixmaps: OrderedDict[int, QPixmap] = OrderedDict()
        self._bytes = 0  # memory of the cached pixmaps
        # Decode generations (review CR12-03): a larger card or a sharper screen starts a new generation; a result
        # never replaces a newer one, and an older pixmap stays on screen until the sharper one arrives.
        self._pix_gen: dict[int, int] = {}  # asset id -> generation of the cached pixmap
        self._pending: dict[int, int] = {}  # asset id -> generation being decoded
        self._gen = 0
        self._floor = 0  # oldest generation still accepted (the current session's first)
        self._gen_target = THUMB_DISPLAY  # physical pixels the current generation decodes to
        self._dpr = 1.0  # device pixel ratio of the screen the grid is on: thumbnails are decoded for it
        self._cell = THUMB_DISPLAY  # logical card size the grid shows
        self._pool = QThreadPool(self)
        self._pool.setMaxThreadCount(2)
        self.gate = Gate()  # the window shares its own: closed while a session is being released
        self._signals = _ThumbSignals(self)  # destroyed by the model, on the GUI thread (app.ui.shutdown)
        self._signals.loaded.connect(self._on_thumb_loaded)

    # ---------------------------------------------------------------- data
    def set_project(self, project: Project | None) -> None:
        self._project = project
        self._pixmaps.clear()
        self._bytes = 0
        self._pix_gen.clear()
        self._pending.clear()
        self._gen += 1
        self._floor = self._gen  # results decoded for the previous session (same asset ids!) are dropped
        self.reload()

    def set_filter(
        self, flt: Filter, *, min_rating: int | None = None, source_id: int | None = -1,
        collection_id: int | None = None, subject_id: int | None = None,
    ) -> None:
        self._filter = flt
        target = collection_id if flt is Filter.COLLECTION else subject_id if flt is Filter.SUBJECT else None
        if flt not in (Filter.COLLECTION, Filter.SUBJECT):
            self._target_id = None
        elif target is not None:
            self._target_id = target  # otherwise keep (e.g. only the folder changed)
        if min_rating is not None:
            self._min_rating = min_rating
        if source_id != -1:
            self._source_id = source_id
        self.reload()

    def set_ranker(self, ranker: Callable[[int, Score], Ranked] | None) -> None:
        """How a photo's ranking value is computed (taste model + weight); applied on reload."""
        self._ranker = ranker

    def set_sort(self, sort: Sort) -> None:
        if sort is not self._sort:
            self._sort = sort
            self.reload()

    @property
    def current_sort(self) -> Sort:
        return self._sort

    def set_search(self, text: str) -> None:
        tokens = search_tokens(text)
        if tokens != self._search:
            self._search = tokens
            self.reload()

    @property
    def current_filter(self) -> Filter:
        return self._filter

    @property
    def current_target(self) -> int | None:
        return self._target_id

    @property
    def is_filtered(self) -> bool:
        return self._filter is not Filter.ALL or bool(self._search) or self._source_id is not None

    def reload(self) -> None:
        rows: list[AssetRecord] = []
        if self._project is not None:
            params: dict[str, Any] = {"min_rating": self._min_rating, "target_id": self._target_id}
            extra = _FILTER_SQL[self._filter]
            if self._source_id is not None:
                extra += " AND a.source_id = :source_id"
                params["source_id"] = self._source_id
            rows = sort_records(self._load_rows(extra, params, search=True), self._sort)
        self.beginResetModel()
        self._rows = rows
        self._row_of = {rec.id: i for i, rec in enumerate(rows)}
        self.endResetModel()

    def records_by_id(self, ids: list[int]) -> dict[int, AssetRecord]:
        """Fresh records of these photos whatever the filter, search or folder shown (Compare keeps its photos);
        a photo no longer in the session is missing from the result."""
        if self._project is None or not ids:
            return {}
        marks = ",".join(str(int(i)) for i in ids)
        params: dict[str, Any] = {"min_rating": self._min_rating, "target_id": self._target_id}
        return {rec.id: rec for rec in self._load_rows(f" AND a.id IN ({marks})", params, search=False)}

    def _load_rows(self, extra_sql: str, params: dict[str, Any], *, search: bool) -> list[AssetRecord]:
        assert self._project is not None
        rows: list[AssetRecord] = []
        sql = _QUERY + extra_sql
        uncertain: set[int] = set()
        if self._filter is Filter.SUBJECT:
            uncertain = {r[0] for r in self._project.conn.execute(
                """SELECT asset_id FROM occurrences WHERE subject_id = ? GROUP BY asset_id
                   HAVING SUM(assignment != 'suggested') = 0""", (self._target_id,))}
        sql += " ORDER BY a.capture_time IS NULL, a.capture_time, a.subsec, a.relative_path"
        conn = self._project.conn
        scores = photo_scores(conn, self._target_id if self._filter is Filter.SUBJECT else None)
        picks = {r[0]: r[1] for r in conn.execute("SELECT asset_id, rank FROM picks")}  # newest run only
        turns = view.rotations(conn)
        pairs = self._pair_names(conn)
        cache = self._project.cache_dir
        for r in conn.execute(sql, params):
            if search and self._search:
                name = PurePosixPath(r["relative_path"]).name.casefold()
                if not any(t in name for t in self._search):
                    continue
            rows.append(
                AssetRecord(
                    id=r["id"], source_id=r["source_id"],
                    path=Path(r["root_path"]) / Path(r["relative_path"]),
                    relative_path=r["relative_path"], extension=r["extension"], status=r["status"],
                    error=r["error"], thumb_file=cache / r["thumb"] if r["thumb"] else None,
                    capture_time=r["capture_time"], width=r["width"], height=r["height"],
                    camera=_camera(r["make"], r["model"]), lens=r["lens"],
                    exif=json.loads(r["exif_json"]) if r["exif_json"] else {},
                    paired_with=pairs.get(r["pair_group_id"], {}).get(r["id"], []),
                    preview_source=r["preview_source"],
                    flag=r["flag"], rating=int(r["rating"]), favorite=bool(r["favorite"]), focus=r["focus"],
                    uncertain=r["id"] in uncertain,
                    score=scores[r["id"]][1] if r["id"] in scores else None,
                    pick_rank=picks.get(r["id"]), rotation=turns.get(r["id"], 0),
                )
            )
            rec = rows[-1]
            if rec.score is not None:
                rec.ranked = self._ranker(rec.id, rec.score) if self._ranker else rank(rec.score, None, [], 0.0)
        return rows

    @staticmethod
    def _pair_names(conn: Any) -> dict[int, dict[int, list[str]]]:
        groups: dict[int, list[tuple[int, str]]] = {}
        for r in conn.execute("SELECT id, pair_group_id, relative_path FROM assets WHERE pair_group_id IS NOT NULL"):
            groups.setdefault(r["pair_group_id"], []).append((r["id"], Path(r["relative_path"]).name))
        return {g: {aid: [n for other, n in members if other != aid] for aid, _ in members} for g, members in groups.items()}

    def refresh_record(self, asset_id: int) -> None:
        """Re-read decisions for one row after a keyboard action (cheap, keeps the view stable)."""
        row = self._row_of.get(asset_id)
        if row is None or self._project is None:
            return
        d = self._project.conn.execute(
            "SELECT flag, rating, favorite, focus FROM decisions WHERE asset_id = ? AND subject_id IS NULL", (asset_id,)
        ).fetchone()
        rec = self._rows[row]
        rec.flag, rec.rating, rec.favorite, rec.focus = (
            (d["flag"], d["rating"], bool(d["favorite"]), d["focus"]) if d else (None, 0, False, None))
        idx = self.index(row)
        self.dataChanged.emit(idx, idx)

    def with_decisions(self, rec: AssetRecord) -> AssetRecord | None:
        """A copy of ``rec`` with its decisions and Xoay xem re-read (cheap: no scores; Compare after an action).
        None when the photo is no longer in the session."""
        if self._project is None:
            return None
        conn = self._project.conn
        if conn.execute("SELECT 1 FROM assets WHERE id = ?", (rec.id,)).fetchone() is None:
            return None
        d = conn.execute(
            "SELECT flag, rating, favorite, focus FROM decisions WHERE asset_id = ? AND subject_id IS NULL", (rec.id,)
        ).fetchone()
        flag, rating, favorite, focus = (d["flag"], d["rating"], bool(d["favorite"]), d["focus"]) if d else (None, 0, False, None)
        return replace(rec, flag=flag, rating=rating, favorite=favorite, focus=focus,
                       rotation=view.rotation(conn, rec.id))

    def record(self, index: QModelIndex | QPersistentModelIndex) -> AssetRecord | None:
        return self._rows[index.row()] if index.isValid() and index.row() < len(self._rows) else None

    def index_of(self, asset_id: int) -> QModelIndex:
        row = self._row_of.get(asset_id)
        return self.index(row) if row is not None else QModelIndex()

    def records(self) -> list[AssetRecord]:
        return list(self._rows)

    # --------------------------------------------------------- Qt protocol
    def rowCount(self, parent: QModelIndex | QPersistentModelIndex = QModelIndex()) -> int:  # noqa: B008
        return 0 if parent.isValid() else len(self._rows)

    def data(self, index: QModelIndex | QPersistentModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        rec = self.record(index)
        if rec is None:
            return None
        if role == Qt.ItemDataRole.DisplayRole:
            return rec.name
        if role == Qt.ItemDataRole.ToolTipRole:  # the filmstrip shows no chip or score: they are here
            chip = chip_for(rec.flag, rec.pick_rank is not None, rec.score, rec.ranked, rec.uncertain)
            value = display_value(rec.ranked)
            lines = [rec.relative_path] + ([chip.text] if chip else []) + ([f"Điểm {value}"] if value is not None
                                                                           else [])
            return "\n".join(lines) + (f"\n{rec.error}" if rec.error else "")
        if role == Qt.ItemDataRole.DecorationRole:
            return self.pixmap(rec)
        if role == ROLE_RECORD:
            return rec
        if role == Qt.ItemDataRole.SizeHintRole:
            return QSize(THUMB_DISPLAY + 16, THUMB_DISPLAY + 48)
        return None

    # ------------------------------------------------------------ pixmaps
    def pixmap(self, rec: AssetRecord) -> QPixmap | None:
        pm = self._pixmaps.get(rec.id)
        if pm is not None:
            self._pixmaps.move_to_end(rec.id)
        current = self._pix_gen.get(rec.id, -1) >= self._gen
        if (not current and rec.thumb_file is not None and self._pending.get(rec.id) != self._gen
                and self.gate.open):
            self._pending[rec.id] = self._gen
            hd = self._project.cache_dir / HD_DIR if self._project is not None else None
            self._pool.start(_ThumbTask(rec.id, rec.thumb_file, self._signals, self._gen_target, self._gen,
                                        rec.path, hd))
        return pm  # possibly an older, softer one until the new decode arrives

    def set_display_size(self, cell: int | None = None, ratio: float | None = None) -> None:
        """The card size (logical px) or the screen's pixel ratio changed. New decodes are made at what the cards need
        now (also smaller: a new session after large cards makes no HD thumbnails it does not need — review RV13-01).
        A NEW generation (sharper re-decodes) starts only when they need clearly more pixels than before; cached
        larger pixmaps are reused as they are."""
        if cell is not None:
            self._cell = cell
        if ratio is not None:
            self._dpr = max(1.0, float(ratio))
        need = min(HD_LONG_SIDE, max(THUMB_DISPLAY, round(self._cell * self._dpr)))
        grows = need > self._gen_target * 1.1
        self._gen_target = need
        if grows:
            self._gen += 1
            if self._rows:
                self.dataChanged.emit(self.index(0), self.index(len(self._rows) - 1),
                                      [Qt.ItemDataRole.DecorationRole])

    @property
    def decode_size(self) -> int:
        return self._gen_target

    def _on_thumb_loaded(self, asset_id: int, image: QImage, generation: int = 0) -> None:
        if self._pending.get(asset_id) == generation:
            del self._pending[asset_id]
        if generation < self._floor or generation < self._pix_gen.get(asset_id, -1):
            return  # another session's result, or older than the cached one: never replaces it
        if image.isNull():
            self._pix_gen[asset_id] = generation  # unreadable: not asked again on every repaint
            return
        row = self._row_of.get(asset_id)
        turns = self._rows[row].rotation if row is not None else 0
        old = self._pixmaps.get(asset_id)
        if old is not None:
            self._bytes -= _pixmap_bytes(old)
        self._pixmaps[asset_id] = turned(QPixmap.fromImage(image), turns)
        self._bytes += _pixmap_bytes(self._pixmaps[asset_id])
        self._pixmaps.move_to_end(asset_id)
        self._pix_gen[asset_id] = generation
        while len(self._pixmaps) > 1 and (len(self._pixmaps) > _PIXMAP_CACHE_SIZE or self._bytes > _PIXMAP_BUDGET):
            dropped, pm = self._pixmaps.popitem(last=False)  # least recently shown first
            self._bytes -= _pixmap_bytes(pm)
            self._pix_gen.pop(dropped, None)
        if row is not None:
            idx = self.index(row)
            self.dataChanged.emit(idx, idx, [Qt.ItemDataRole.DecorationRole])
        self.thumbnail_ready.emit(asset_id)

    def set_rotation(self, asset_id: int, turns: int) -> None:
        """Xoay xem changed: turn the cached thumbnail by the difference and repaint that card."""
        row = self._row_of.get(asset_id)
        if row is None:
            return
        rec = self._rows[row]
        delta, rec.rotation = (turns - rec.rotation) % 4, turns
        pm = self._pixmaps.get(asset_id)
        if pm is not None and delta:
            self._pixmaps[asset_id] = turned(pm, delta)
        idx = self.index(row)
        self.dataChanged.emit(idx, idx)

    def wait_for_thumbnails(self, msecs: int = 5000) -> bool:
        """Block at most msecs until thumbnail decodes finish; True when none runs any more."""
        return self._pool.waitForDone(msecs)

    def set_device_pixel_ratio(self, ratio: float) -> None:
        """Another screen or scale: thumbnails for that many physical pixels per logical pixel."""
        self.set_display_size(ratio=ratio)

    @property
    def device_pixel_ratio(self) -> float:
        return self._dpr

    def stop_pending(self) -> None:
        """Drop decodes not started yet (they are asked again when a thumbnail is next painted)."""
        self._pool.clear()
        self._pending.clear()
