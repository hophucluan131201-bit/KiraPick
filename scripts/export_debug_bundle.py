"""Pack the analysis data of one photo folder so grouping can be tuned on real results.

    .\\.venv\\Scripts\\python scripts\\export_debug_bundle.py "D:\\Photos\\Shoot"   # -> .\\snorlu_debug.zip

Contains: the session database (file names, capture times, camera/lens, decisions,
detected boxes, face/outfit vectors, groups), the 400 px thumbnails and the 160 px
face crops. It does NOT contain the RAW/JPEG originals, GPS or serial numbers.
Read-only for the session and the photos. Share the zip only with people you trust.
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
import tempfile
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.storage.project import CACHE_DIR, DB_NAME  # noqa: E402
from app.storage.sessions import session_dir  # noqa: E402


def default_sessions_root() -> Path:
    from PySide6.QtCore import QCoreApplication, QStandardPaths

    QCoreApplication.setOrganizationName("Snorlu")
    QCoreApplication.setApplicationName("Snorlu AI Culling")  # must match app/main.py
    base = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation)
    return Path(base) / "sessions"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("folder", type=Path, help="the photo folder you imported in the app")
    parser.add_argument("--out", type=Path, default=Path.cwd() / "snorlu_debug.zip")
    parser.add_argument("--sessions", type=Path, help="override the sessions directory")
    args = parser.parse_args()

    root = args.sessions or default_sessions_root()
    folder = session_dir(root, args.folder.resolve())
    db_path = folder / DB_NAME
    if not db_path.is_file():
        print(f"Không thấy dữ liệu phiên cho thư mục này.\n  Đã tìm ở: {folder}\n"
              "Hãy nhập thư mục đó trong app và chạy 🧠 Nhận diện người trước.")
        return 1

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        snapshot = Path(tmp) / DB_NAME
        src = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)  # consistent copy, even with WAL
        dst = sqlite3.connect(snapshot)
        src.backup(dst)
        src.close()
        dst.close()
        count = 0
        with zipfile.ZipFile(args.out, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.write(snapshot, DB_NAME)
            for sub in ("thumbs", "crops"):
                for f in sorted((folder / CACHE_DIR / sub).glob("*.jpg")):
                    zf.write(f, f"{sub}/{f.name}")
                    count += 1
    size = args.out.stat().st_size / 1e6
    print(f"Đã tạo {args.out} ({size:.1f} MB, {count} ảnh nhỏ). Không có ảnh gốc trong file này.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
