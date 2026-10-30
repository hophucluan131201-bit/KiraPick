"""GUI test hygiene shared by every module in tests/gui."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _viewers_idle_before_teardown(qtbot):  # noqa: ANN001, ANN202
    """After each test, before pytest-qt closes and deletes the test's widgets: wait until every image viewer's
    decode pools are idle. Deleting a QThreadPool waits for its running task on the GUI thread while Python's GIL is
    held there, and the task (Python) needs the GIL: a deadlock (known issue K12). The app never deletes a viewer
    with work running (the window, Compare and folder switches wait for the pools first, app.ui.shutdown); a test
    that fails early used to leave decodes running, and the next test froze (Windows CI run 40999914267)."""
    yield
    from PySide6.QtWidgets import QApplication

    from app.ui.compare_view import CompareView
    from app.ui.viewer import ImageViewer

    for widget in QApplication.allWidgets():
        if isinstance(widget, (ImageViewer, CompareView)):
            widget.wait_idle(20000)
