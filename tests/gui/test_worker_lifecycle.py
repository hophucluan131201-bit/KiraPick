"""Worker threads and Qt objects: every signal object is owned by a GUI-thread object that outlives its workers,
and closing a window or switching sessions waits for running workers (review CR11-02)."""

from __future__ import annotations

import gc
from pathlib import Path

import pytest

from tests.gui.test_main_window import _import, _photo, _window, env  # noqa: F401 - fixture


def test_learning_jobs_use_window_owned_signals(qtbot, env: dict) -> None:  # noqa: F811
    from app.ui import main_window as mw

    w = _window(qtbot, env)
    taste, focus = mw._TasteJob([], w._taste_signals), mw._FocusJob([], w._focus_signals)
    assert taste.signals is w._taste_signals and focus.signals is w._focus_signals
    assert w._taste_signals.parent() is w and w._focus_signals.parent() is w  # never deleted by a worker


def test_closing_waits_for_every_worker_pool(qtbot, env: dict, monkeypatch) -> None:  # noqa: F811
    w = _window(qtbot, env)
    _import(qtbot, w, env["photos"])
    waited = []
    for name, obj in (("thumbs", w.model), ("hist", w.detail.score_card.histogram), ("viewer", w.viewer)):
        real = obj.wait_for_thumbnails if name == "thumbs" else (obj.wait if name == "hist" else obj.wait_idle)
        monkeypatch.setattr(obj, real.__name__, lambda *a, n=name, r=real, **k: (waited.append(n), r(*a, **k))[1])
    real_pool = w._taste_pool.waitForDone
    monkeypatch.setattr(w._taste_pool, "waitForDone", lambda *a: (waited.append("learning"), real_pool(*a))[1])
    w.close()
    assert {"thumbs", "hist", "viewer", "learning"} <= set(waited)


def _churn(qtbot, w, rounds: int) -> None:  # noqa: ANN001
    for i in range(rounds):
        for row in range(w.model.rowCount()):  # every change starts thumbnail + histogram + burst work
            w.select_row(row)
            qtbot.wait(1)
        w.set_flag("keep" if i % 2 else "reject")
        w.show_loupe(i % 2 == 0)


@pytest.mark.parametrize("cycles", [3])
def test_open_switch_close_while_workers_run(qtbot, env: dict, tmp_path: Path, cycles: int) -> None:  # noqa: F811
    """Stress: import, browse fast (workers queued), switch session, close — repeatedly; then collect garbage."""
    other = tmp_path / "Buổi khác"
    for i in range(4):
        _photo(other / f"IMG_{i:04d}.jpg", 50 + i)
    for _ in range(cycles):
        w = _window(qtbot, env)
        _import(qtbot, w, env["photos"])
        _churn(qtbot, w, 2)
        _import(qtbot, w, other)  # session switch with work in flight
        _churn(qtbot, w, 1)
        w.close()
        w.deleteLater()
        qtbot.wait(20)
        gc.collect()  # on the GUI thread, after the window is gone


@pytest.mark.stress
def test_open_switch_close_while_workers_run_many_times(qtbot, env: dict, tmp_path: Path) -> None:  # noqa: F811
    test_open_switch_close_while_workers_run(qtbot, env, tmp_path, 25)


def test_gc_guard_gives_gc_back_when_the_app_quits(qtbot) -> None:  # noqa: ANN001
    from app.ui import gc_guard

    guard = gc_guard.installed()
    if guard is None:
        from PySide6.QtWidgets import QApplication

        guard = gc_guard.install(QApplication.instance())
    assert not gc.isenabled()
    gc_guard.uninstall()
    assert gc.isenabled() and gc_guard.installed() is None
    from PySide6.QtWidgets import QApplication

    gc_guard.install(QApplication.instance())  # other tests expect it installed again
    assert not gc.isenabled()


def test_gc_guard_needs_an_application(monkeypatch) -> None:
    from app.ui import gc_guard

    assert gc_guard.install(None) is None and gc_guard.installed() is not None  # nothing changed
