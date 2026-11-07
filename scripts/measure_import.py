"""Import timing, the same way for KiraPick 3.0.0, a tested Beta and the current Beta (REG-1; development tool).

    python scripts/measure_import.py make-data <dir> [--raw <file.NEF> ...]
        <dir>/jpeg300: 300 synthetic 2400×1600 JPEGs with EXIF date, 2 s apart (no real photos)
        <dir>/raw60:   60 copies of the given RAW files (each made unique by a trailing byte, because the import
                       skips identical files) + 20 same-name JPEGs, so 20 RAW+JPEG pairs
    python scripts/measure_import.py run <repo root> <photos> <personal|media> <out.json> [--reopen] [--analysis]

``run`` opens the window of the checkout at <repo root> (offscreen is fine) and records, separately: the first photo
in the grid, whether the grid can be used while importing (select, P, scroll: round trip in ms), all photos listed,
import done, the first time each import phase is reported, then (``--reopen``) the same folder again (nothing new to
decode) and (``--analysis``) the AI analysis on the CPU. Counts only: no file name or photo data is written.
"""

from __future__ import annotations

import json
import multiprocessing as mp
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path


def make_data(out: Path, raws: list[Path]) -> None:
    from datetime import datetime, timedelta

    import numpy as np
    from PIL import Image

    jpegs = out / "jpeg300"
    jpegs.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(7)
    start = datetime(2026, 6, 19, 8, 0, 0)
    base = (rng.random((200, 300, 3)) * 255).astype("uint8")
    for i in range(300):
        img = Image.fromarray(np.roll(base, i * 3, axis=1)).resize((2400, 1600))
        exif = Image.Exif()
        exif[0x010F], exif[0x0110] = "KiraPick", "Synthetic"
        exif.get_ifd(0x8769)[0x9003] = (start + timedelta(seconds=2 * i)).strftime("%Y:%m:%d %H:%M:%S")
        img.save(jpegs / f"EVT_{i:04d}.jpg", quality=88, exif=exif)
    if raws:
        raw_dir = out / "raw60"
        raw_dir.mkdir(parents=True, exist_ok=True)
        for i in range(60):
            src = raws[i % len(raws)]
            dst = raw_dir / f"DSC_{i:04d}{src.suffix.upper()}"
            shutil.copyfile(src, dst)
            with dst.open("ab") as f:  # a unique tail: the import dedupes identical files by size + first/last 64 KiB
                f.write(i.to_bytes(4, "little"))
            if i < 20:
                shutil.copyfile(jpegs / f"EVT_{i:04d}.jpg", raw_dir / f"DSC_{i:04d}.JPG")
    print(json.dumps({"jpeg": 300, "raw": 60 if raws else 0, "pairs": 20 if raws else 0}))


def run(root: Path, photos: Path, mode: str, out: Path, reopen: bool, analysis: bool) -> None:
    sys.path.insert(0, str(root))
    os.chdir(root)
    from PySide6.QtCore import QSettings
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    tmp = Path(tempfile.mkdtemp(prefix="kp-timing-"))
    n_files = len([p for p in photos.iterdir() if p.is_file()])
    res: dict = {"mode": mode, "files": n_files}

    def pump(sec: float = 0.0) -> None:
        end = time.perf_counter() + sec
        while True:
            app.processEvents()
            if time.perf_counter() >= end:
                return
            time.sleep(0.01)

    def wait(cond, limit: float = 7200) -> None:  # noqa: ANN001
        t0 = time.perf_counter()
        while not cond() and time.perf_counter() - t0 < limit:
            app.processEvents()
            time.sleep(0.01)

    def run_import(win, start, prefix: str) -> None:  # noqa: ANN001
        phases: dict = {}
        t0 = time.perf_counter()
        start()
        th = win.import_thread
        if th is not None:
            th.progress.connect(lambda ph, d, t: phases.setdefault(ph, round(time.perf_counter() - t0, 2)))
        model, grid = win.model, win.grid
        wait(lambda: model.rowCount() > 0 or win.import_thread is None)
        res[prefix + "grid_first_s"] = round(time.perf_counter() - t0, 2)
        if model.rowCount() and win.import_thread is not None:
            u0 = time.perf_counter()
            sel = grid.selectionModel()
            grid.setCurrentIndex(model.index(0))
            sel.select(model.index(0), sel.SelectionFlag.ClearAndSelect)
            win.set_flag("keep")
            grid.verticalScrollBar().setValue(grid.verticalScrollBar().maximum())
            app.processEvents()
            res[prefix + "usable_during_import"] = True
            res[prefix + "mark_while_importing_ms"] = round((time.perf_counter() - u0) * 1000)
        else:
            res[prefix + "usable_during_import"] = False  # the grid had nothing before the import ended
        wait(lambda: model.rowCount() >= n_files or win.import_thread is None)
        res[prefix + "grid_all_s"] = round(time.perf_counter() - t0, 2)
        wait(lambda: win.import_thread is None)
        res[prefix + "import_done_s"] = round(time.perf_counter() - t0, 2)
        pump(0.3)
        res[prefix + "rows"] = model.rowCount()
        res[prefix + "phases_first_seen_s"] = phases

    def counts(conn) -> None:  # noqa: ANN001
        res["status_counts"] = dict(conn.execute("SELECT status, COUNT(*) FROM assets GROUP BY status").fetchall())
        res["pairs"] = conn.execute("SELECT COUNT(DISTINCT pair_group_id) FROM assets "
                                    "WHERE pair_group_id IS NOT NULL").fetchone()[0]
        res["with_capture_time"] = conn.execute("SELECT COUNT(*) FROM assets WHERE capture_time IS NOT NULL").fetchone()[0]

    if mode == "personal":
        import app.ui.main_window as mw

        mw.sessions_dir = lambda: tmp / "sessions"
        w = mw.MainWindow(settings=QSettings(str(tmp / "s.ini"), QSettings.Format.IniFormat))
        w._maximize_on_show = False
        w.resize(1600, 1000)
        w.show()
        pump(0.3)
        if hasattr(w, "act_gpu"):
            w.act_gpu.setChecked(False)
        run_import(w, lambda: w.start_import(photos), "")
        counts(w.project.conn)
        if reopen:
            run_import(w, lambda: w.start_import(photos), "reopen_")
        if analysis:
            for m in ("people", "quality"):
                t1 = time.perf_counter()
                w.start_analysis(m)
                pump(0.2)
                wait(lambda: w.analyze_thread is None)
                res[f"analysis_{m}_s"] = round(time.perf_counter() - t1, 2)
                pump(0.3)
    else:
        from app.ui.media_home import MediaHome

        h = MediaHome(root=tmp / "media")
        h.resize(1600, 1000)
        h.show()
        pump(0.3)
        h.create("Timing")
        v = h.view
        if hasattr(v, "resize"):
            v.resize(1600, 1000)
        run_import(v, lambda: v.start_import(photos), "")
        counts(v.media_event.conn)
        if reopen:
            run_import(v, lambda: v.start_import(photos), "reopen_")
        if analysis:
            t1 = time.perf_counter()
            if hasattr(v, "act_gpu"):  # the 3.0.0 window (EventWindow)
                v.act_gpu.setChecked(False)
                v.start_analysis("people")
                attr = "analyze_thread"
            else:  # the tested Beta's EventView
                v.start_analysis(prefer_gpu=False)
                attr = "analysis_thread"
            pump(0.2)
            wait(lambda: getattr(v, attr) is None)
            res["analysis_media_s"] = round(time.perf_counter() - t1, 2)
    out.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(res, ensure_ascii=False))
    sys.stdout.flush()
    os._exit(0)


def main(argv: list[str]) -> int:
    if argv[:1] == ["make-data"]:
        raws = [Path(a) for a in argv[argv.index("--raw") + 1:]] if "--raw" in argv else []
        make_data(Path(argv[1]), raws)
        return 0
    if argv[:1] == ["run"] and len(argv) >= 5:
        run(Path(argv[1]).resolve(), Path(argv[2]).resolve(), argv[3], Path(argv[4]).resolve(),
            "--reopen" in argv, "--analysis" in argv)
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    mp.freeze_support()  # the analysis runs in a spawned child process
    raise SystemExit(main(sys.argv[1:]))
