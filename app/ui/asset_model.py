"""List model of photos for the grid/filmstrip, with asynchronous thumbnails.

Rows come from SQLite on the UI thread (a single indexed query); thumbnail
JPEGs from the project cache are decoded to QImage on a thread pool and turned
into QPixmaps on the UI thread.
"""

from __future__ import annotations

import json
import re
from collections import OrderedDict
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path, PurePosixPath
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
from PySide6.QtGui import QImage, QPixmap

from app.storage.project import Project

THUMB_DISPLAY = 240  # long side of cached pixmaps
_PIXMAP_CACHE_SIZE = 600

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
    uncertain: bool = False  # in a person view: only suggested (no clear face), needs a look

    @property
    def name(self) -> str:
        return Path(self.relative_path).name


_QUERY = """
SELECT a.id, a.source_id, a.relative_path, a.extension, a.status, a.error, a.capture_time, a.width, a.height,
       a.make, a.model, a.lens, a.exif_json, a.pair_group_id, s.root_path,
       p.file_name AS thumb, p.source AS preview_source,
       d.flag, COALESCE(d.rating, 0) AS rating, COALESCE(d.favorite, 0) AS favorite
FROM assets a
JOIN sources s ON s.id = a.source_id
LEFT JOIN previews p ON p.asset_id = a.id AND p.kind = 'thumb'
LEFT JOIN decisions d ON d.asset_id = a.id AND d.subject_id IS NULL
WHERE a.status NOT IN ('missing', 'duplicate')
  -- a JPEG that is half of a RAW+JPEG pair is shown through its RAW
  AND NOT (a.media_kind = 'raster' AND a.pair_group_id IS NOT NULL
           AND EXISTS (SELECT 1 FROM assets r WHERE r.pair_group_id = a.pair_group_id AND r.media_kind = 'raw'))
"""

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
    Filter.UNIDENTIFIED: " AND a.id IN (SELECT asset_id FROM occurrences WHERE is_main = 1 AND subject_id IS NULL)",
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


class _ThumbSignals(QObject):
    loaded = Signal(int, QImage)


class _ThumbTask(QRunnable):
    def __init__(self, asset_id: int, path: Path, signals: _ThumbSignals) -> None:
        super().__init__()
        self.asset_id, self.path, self.signals = asset_id, path, signals

    def run(self) -> None:
        image = QImage(str(self.path))
        if not image.isNull():
            image = image.scaled(
                THUMB_DISPLAY, THUMB_DISPLAY, Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        self.signals.loaded.emit(self.asset_id, image)


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
        self._pixmaps: OrderedDict[int, QPixmap] = OrderedDict()
        self._pending: set[int] = set()
        self._pool = QThreadPool(self)
        self._pool.setMaxThreadCount(2)
        self._signals = _ThumbSignals()
        self._signals.loaded.connect(self._on_thumb_loaded)

    # ---------------------------------------------------------------- data
    def set_project(self, project: Project | None) -> None:
        self._project = project
        self._pixmaps.clear()
        self._pending.clear()
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
            sql = _QUERY + _FILTER_SQL[self._filter]
            params: dict[str, Any] = {"min_rating": self._min_rating, "target_id": self._target_id}
            uncertain: set[int] = set()
            if self._filter is Filter.SUBJECT:
                uncertain = {r[0] for r in self._project.conn.execute(
                    """SELECT asset_id FROM occurrences WHERE subject_id = ? GROUP BY asset_id
                       HAVING SUM(assignment != 'suggested') = 0""", (self._target_id,))}
            if self._source_id is not None:
                sql += " AND a.source_id = :source_id"
                params["source_id"] = self._source_id
            sql += " ORDER BY a.capture_time IS NULL, a.capture_time, a.subsec, a.relative_path"
            conn = self._project.conn
            pairs = self._pair_names(conn)
            cache = self._project.cache_dir
            for r in conn.execute(sql, params):
                if self._search:
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
                        flag=r["flag"], rating=int(r["rating"]), favorite=bool(r["favorite"]),
                        uncertain=r["id"] in uncertain,
                    )
                )
        self.beginResetModel()
        self._rows = rows
        self._row_of = {rec.id: i for i, rec in enumerate(rows)}
        self.endResetModel()

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
            "SELECT flag, rating, favorite FROM decisions WHERE asset_id = ? AND subject_id IS NULL", (asset_id,)
        ).fetchone()
        rec = self._rows[row]
        rec.flag, rec.rating, rec.favorite = (d["flag"], d["rating"], bool(d["favorite"])) if d else (None, 0, False)
        idx = self.index(row)
        self.dataChanged.emit(idx, idx)

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
        if role == Qt.ItemDataRole.ToolTipRole:
            return rec.relative_path + (f"\n{rec.error}" if rec.error else "")
        if role == Qt.ItemDataRole.DecorationRole:
            return self.pixmap(rec)
        if role == ROLE_RECORD:
            return rec
        if role == Qt.ItemDataRole.SizeHintRole:
            return QSize(THUMB_DISPLAY + 16, THUMB_DISPLAY + 40)
        return None

    # ------------------------------------------------------------ pixmaps
    def pixmap(self, rec: AssetRecord) -> QPixmap | None:
        pm = self._pixmaps.get(rec.id)
        if pm is not None:
            self._pixmaps.move_to_end(rec.id)
            return pm
        if rec.thumb_file is not None and rec.id not in self._pending:
            self._pending.add(rec.id)
            self._pool.start(_ThumbTask(rec.id, rec.thumb_file, self._signals))
        return None

    def _on_thumb_loaded(self, asset_id: int, image: QImage) -> None:
        self._pending.discard(asset_id)
        if image.isNull():
            return
        self._pixmaps[asset_id] = QPixmap.fromImage(image)
        while len(self._pixmaps) > _PIXMAP_CACHE_SIZE:
            self._pixmaps.popitem(last=False)
        row = self._row_of.get(asset_id)
        if row is not None:
            idx = self.index(row)
            self.dataChanged.emit(idx, idx, [Qt.ItemDataRole.DecorationRole])
        self.thumbnail_ready.emit(asset_id)

    def wait_for_thumbnails(self, msecs: int = 5000) -> bool:
        """Test helper: block until queued thumbnail decodes finish."""
        return self._pool.waitForDone(msecs)
