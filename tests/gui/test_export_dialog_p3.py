"""Part 3 Task 10 — the export dialog: three independent groups, preview tabs, confirming unsure matches, copy,
retry, and the "Tên ảnh đã Chọn" tab (spec §4, RV-P3-C02, RV-P3-C05)."""

from __future__ import annotations

import itertools
import os
import shutil
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QSettings
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication, QMessageBox, QPushButton

from app.export import copy_export
from app.export.copy_export import Selection
from app.export.formats import ExportFormat
from app.export.layout import Layout
from app.storage import decisions
from app.ui import export_dialog as ed
from app.ui.export_dialog import MIGRATION_NOTICE, MIGRATION_NOTICE_KEY, ExportDialog
from tests.fixtures_export import add_asset
from tests.gui.test_export_plan_thread import SlowScan, external_dialog, fx, settle_threads, wait_plan  # noqa: F401
from tests.unit.test_export_match import exif_file


@pytest.fixture(autouse=True)
def _quiet_boxes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)


def imported_dialog(qtbot, fx, ids: list[int] | None = None) -> ExportDialog:  # noqa: ANN001
    dialog = ExportDialog(fx.project, ids or [], settings=fx.settings)
    qtbot.addWidget(dialog)
    dialog.dest.setText(str(fx.dest))
    if ids:
        dialog.radios[Selection.IDS].setChecked(True)
    dialog.refresh()
    return dialog


def copy_and_wait(qtbot, dialog: ExportDialog):  # noqa: ANN001, ANN202
    dialog.result = None
    dialog.start_copy()
    qtbot.waitUntil(lambda: dialog.result is not None, timeout=20000)
    dialog.copy_thread.wait()
    return dialog.result


def test_defaults_on_first_run(qtbot, fx) -> None:  # noqa: ANN001
    dialog = imported_dialog(qtbot, fx)
    assert dialog.source_imported.isChecked() and dialog.export_format is ExportFormat.RAW_JPEG
    assert dialog.export_layout is Layout.SINGLE and not dialog.notice.isVisibleTo(dialog)
    assert not hasattr(dialog, "keep_folders")  # "Giữ cấu trúc thư mục con" is gone (spec §4)
    texts = [w.text() for w in dialog.findChildren(QPushButton)] + [w.text() for w in
                                                                     dialog.findChildren(ed.QCheckBox)]
    assert not any("cấu trúc" in t for t in texts)


@pytest.mark.parametrize("old", [True, False])
def test_defaults_and_migration(qtbot, fx, old: bool) -> None:  # noqa: ANN001
    fx.settings.setValue("export/include_pairs", old)
    dialog = imported_dialog(qtbot, fx)
    assert dialog.export_format is ExportFormat.RAW_JPEG and not fx.settings.contains("export/include_pairs")
    assert dialog.notice.isVisibleTo(dialog) is (not old)
    if not old:
        assert dialog.notice_label.text() == MIGRATION_NOTICE
        dialog.format_buttons[ExportFormat.RAW].setChecked(True)  # any change of ② dismisses it for good
        assert not dialog.notice.isVisibleTo(dialog) and not fx.settings.contains(MIGRATION_NOTICE_KEY)
    again = imported_dialog(qtbot, fx)
    assert not again.notice.isVisibleTo(again)  # never shown on the next opening


def test_migration_notice_closed_by_closing_the_dialog(qtbot, fx) -> None:  # noqa: ANN001
    fx.settings.setValue("export/include_pairs", False)
    dialog = imported_dialog(qtbot, fx)
    assert dialog.notice.isVisibleTo(dialog)
    dialog.close()
    assert not fx.settings.contains(MIGRATION_NOTICE_KEY)
    assert not imported_dialog(qtbot, fx).notice.isVisibleTo(dialog)


def test_three_groups_independent(qtbot, fx) -> None:  # noqa: ANN001
    dialog = imported_dialog(qtbot, fx)
    dialog.external_path.setText(str(fx.card))
    calls = []
    real = dialog.refresh
    dialog.refresh = lambda: (calls.append(1), real())[1]  # the connections call it through the instance
    seen = set()
    for src, fmt, lay in itertools.product(("imported", "external"), ExportFormat, Layout):
        for button in (dialog.source_imported if src == "imported" else dialog.source_external,
                       dialog.format_buttons[fmt], dialog.layout_buttons[lay]):
            if not button.isChecked():
                before = len(calls)
                button.setChecked(True)
                assert len(calls) == before + 1  # each change plans once
        wait_plan(qtbot, dialog)
        assert dialog.plan.options == {"source": src, "format": fmt.value, "layout": lay.value,
                                       **({"source_folder": "card"} if src == "external" else {})}
        seen.add((src, fmt, lay))
    assert len(seen) == 12
    assert fx.settings.value(ed.SOURCE_KEY) == "external" and fx.settings.value(ed.LAYOUT_KEY) == "subjects"
    settle_threads(qtbot, dialog)


def test_choices_are_remembered(qtbot, fx) -> None:  # noqa: ANN001
    dialog = external_dialog(qtbot, fx)
    dialog.layout_buttons[Layout.SUBJECTS].setChecked(True)
    dialog.set_external_root(fx.card)
    wait_plan(qtbot, dialog)
    settle_threads(qtbot, dialog)
    again = ExportDialog(fx.project, [], settings=fx.settings)
    qtbot.addWidget(again)
    assert again.source_external.isChecked() and again.export_layout is Layout.SUBJECTS
    assert again.external_path.text() == str(fx.card)  # remembered; scanned again on this opening
    settle_threads(qtbot, again)


def test_preview_counts_and_tabs(qtbot, fx) -> None:  # noqa: ANN001
    dialog = imported_dialog(qtbot, fx)
    plan = dialog.plan
    assert len(plan.operations) == 7 and len(plan.issues) == 1
    assert dialog.preview_tabs.tabText(0) == "Sẽ chép (7)" and dialog.preview_tabs.tabText(1) == "Cần xem lại (1)"
    assert dialog.plan_table.rowCount() == 7 and dialog.issue_table.rowCount() == 1
    assert dialog.issue_table.item(0, 0).text() == "Thiếu"
    text = dialog.summary.text()
    assert "6 ảnh → 7 file sẽ chép" in text and "thiếu 1" in text and "1 thư mục" in text
    assert dialog.copy_button.isEnabled() and dialog.copy_button.text() == "Sao chép 7 file"


def test_subject_layout_hint_without_analysis(qtbot, fx) -> None:  # noqa: ANN001
    dialog = imported_dialog(qtbot, fx)
    dialog.layout_buttons[Layout.SUBJECTS].setChecked(True)
    assert "Chưa nhận diện chủ thể — mọi ảnh sẽ vào Chưa xác định" in dialog.summary.text()
    assert {op.folder for op in dialog.plan.operations} == {"Chưa xác định"}


def _two_candidates(fx) -> tuple[Path, Path]:  # noqa: ANN001
    a = exif_file(fx.card / "A" / "DSC_0004.NEF", "2026:10:25 16:00:01", seed=1)
    b = exif_file(fx.card / "B" / "DSC_0004.NEF", "2026:10:25 15:59:59", seed=2)
    return a, b


def test_ambiguous_confirm_flow(qtbot, fx) -> None:  # noqa: ANN001
    a, _b = _two_candidates(fx)
    dialog = imported_dialog(qtbot, fx, [fx.ids["jpeg_only"]])
    dialog.external_path.setText(str(fx.card))
    dialog.format_buttons[ExportFormat.RAW].setChecked(True)
    dialog.source_external.setChecked(True)
    wait_plan(qtbot, dialog)
    assert dialog.plan.operations == [] and dialog.issue_table.item(0, 0).text() == "Không chắc"
    box = dialog.issue_table.cellWidget(0, 3)
    assert box.count() == 2 and "A/DSC_0004.NEF" in box.itemText(0)
    assert not dialog.copy_button.isEnabled()
    dialog.issue_table.cellWidget(0, 4).click()  # "Dùng file này" on the first candidate
    wait_plan(qtbot, dialog)
    (op,) = dialog.plan.operations
    assert op.source == a.resolve() and op.match == "manual"
    assert "✋ xác nhận tay" in dialog.plan_table.item(0, 1).text()
    assert dialog.copy_button.isEnabled() and dialog.copy_button.text() == "Sao chép 1 file"
    result = copy_and_wait(qtbot, dialog)
    assert result.copied == ["DSC_0004.NEF"] and (fx.dest / "DSC_0004.NEF").read_bytes() == a.read_bytes()
    settle_threads(qtbot, dialog)


def test_source_change_forgets_confirmations_and_hashes(qtbot, fx) -> None:  # noqa: ANN001
    _two_candidates(fx)
    dialog = imported_dialog(qtbot, fx, [fx.ids["jpeg_only"]])
    dialog.external_path.setText(str(fx.card))
    dialog.format_buttons[ExportFormat.RAW].setChecked(True)
    dialog.source_external.setChecked(True)
    wait_plan(qtbot, dialog)
    dialog.use_candidate(0, 0)
    wait_plan(qtbot, dialog)
    hashes = dialog._hashes
    assert dialog.confirmations and len(dialog.plan.operations) == 1
    dialog.set_external_root(fx.card)  # chosen again (RV-P3-C02): a new scan, no old choice, a new hash cache
    assert dialog.confirmations == {} and dialog._hashes is not hashes
    wait_plan(qtbot, dialog)
    assert dialog.plan.operations == [] and dialog.issue_table.item(0, 0).text() == "Không chắc"
    settle_threads(qtbot, dialog)


def test_copy_disabled_while_scanning(qtbot, fx, monkeypatch: pytest.MonkeyPatch) -> None:  # noqa: ANN001
    slow = SlowScan(monkeypatch)
    dialog = external_dialog(qtbot, fx)
    assert slow.started.wait(10)
    assert dialog.scanning and not dialog.copy_button.isEnabled() and dialog.plan is None
    dialog._confirm_and_copy()
    assert dialog.copy_thread is None
    slow.release.set()
    wait_plan(qtbot, dialog)
    assert dialog.copy_button.isEnabled()
    settle_threads(qtbot, dialog)


def test_external_copy_takes_files_from_the_card_only(qtbot, fx) -> None:  # noqa: ANN001
    dialog = external_dialog(qtbot, fx)
    wait_plan(qtbot, dialog)
    assert all(fx.card.resolve() in op.source.parents for op in dialog.plan.operations)
    result = copy_and_wait(qtbot, dialog)
    assert sorted(result.copied) == ["DSC_0001.JPG", "DSC_0001.NEF", "DSC_0003.NEF", "DSC_0004.JPG"]
    assert result.statuses and set(result.statuses.values()) == {"copied"}
    settle_threads(qtbot, dialog)


def test_confirm_text_lists_skipped(qtbot, fx) -> None:  # noqa: ANN001
    dialog = external_dialog(qtbot, fx)
    wait_plan(qtbot, dialog)
    text = dialog.confirm_text()
    assert "Sao chép 4 file" in text and "của 3 ảnh" in text and "cả trên thẻ nhớ" in text
    assert "Sẽ bỏ qua:" in text and "thiếu định dạng" in text and "thiếu" in text
    settle_threads(qtbot, dialog)


def test_retry_button_after_partial_failure(qtbot, fx, monkeypatch: pytest.MonkeyPatch) -> None:  # noqa: ANN001
    dialog = imported_dialog(qtbot, fx)
    real = copy_export._copy_exclusive
    broken = {"DSC_0004.JPG"}

    def flaky(src: Path, root: Path, rel: str, **kw):  # noqa: ANN003, ANN202
        if rel in broken:
            raise OSError(5, "Input/output error")
        return real(src, root, rel, **kw)

    monkeypatch.setattr(copy_export, "_copy_exclusive", flaky)
    result = copy_and_wait(qtbot, dialog)
    assert list(result.failed) == ["DSC_0004.JPG"] and dialog.retry_button.isVisibleTo(dialog)
    broken.clear()
    dialog.result = None
    dialog.retry()  # plans again and asks the usual confirmation (answered Yes here)
    qtbot.waitUntil(lambda: dialog.result is not None, timeout=20000)
    dialog.copy_thread.wait()
    assert dialog.result.copied == ["DSC_0004.JPG"] and not dialog.retry_button.isVisibleTo(dialog)


# --- 📋 Tên ảnh đã Chọn ---------------------------------------------------------------------------------------------

def test_names_tab_copies_to_clipboard(qtbot, fx) -> None:  # noqa: ANN001
    dialog = imported_dialog(qtbot, fx)
    assert dialog.names_list.toPlainText().splitlines() == ["DSC_0001", "DSC_0002", "DSC_0003", "DSC_0004",
                                                             "DSC_0005", "DSC_0006"]
    assert dialog.names_count.text().startswith("6 ảnh đã Chọn trong phạm vi này")
    dialog.copy_names_button.click()
    assert QGuiApplication.clipboard().text() == "DSC_0001\nDSC_0002\nDSC_0003\nDSC_0004\nDSC_0005\nDSC_0006"
    assert dialog.names_status.text() == "Đã sao chép 6 tên vào bộ nhớ tạm"
    dialog.names_with_ext.setChecked(True)
    dialog.copy_names_button.click()
    assert QGuiApplication.clipboard().text().splitlines()[0] == "DSC_0001.NEF"


def test_names_work_without_the_source(qtbot, fx) -> None:  # noqa: ANN001
    dialog = imported_dialog(qtbot, fx)
    dialog.external_path.setText(str(fx.root.parent / "thẻ đã rút"))
    dialog.source_external.setChecked(True)
    dialog.dest.setText("")
    dialog.refresh()
    shutil.rmtree(fx.root)  # neither the imported folder nor the card exists
    dialog.names_with_ext.setChecked(True)
    dialog.copy_names_button.click()
    assert len(QGuiApplication.clipboard().text().splitlines()) == 6
    settle_threads(qtbot, dialog)


def test_names_warn_duplicates(qtbot, fx) -> None:  # noqa: ANN001
    source_id = fx.project.conn.execute("SELECT id FROM sources").fetchone()[0]
    other = add_asset(fx.project, source_id, fx.root, "Buổi 2/DSC_0001.JPG", seed=900, kind="raster")
    decisions.set_flag(fx.project.conn, other, "keep")
    dialog = imported_dialog(qtbot, fx)
    assert "DSC_0001 (2 ảnh)" in dialog.names_warning.text()
    assert dialog.names_list.toPlainText().splitlines().count("DSC_0001") == 1  # one line per displayed name
    dialog.copy_names_button.click()
    assert QGuiApplication.clipboard().text().splitlines().count("DSC_0001") == 1


# --- fits the small layouts -------------------------------------------------------------------------------------------

@pytest.mark.parametrize("size", [(560, 400), (1280, 323)])
def test_dialog_fits_tiny_and_short(qtbot, fx, size: tuple[int, int]) -> None:  # noqa: ANN001
    dialog = imported_dialog(qtbot, fx)
    dialog.show()
    dialog.resize(*size)
    qtbot.waitUntil(lambda: dialog.width() <= size[0] + 1 and dialog.height() <= size[1] + 1, timeout=3000)
    QApplication.processEvents()
    close = next(b for b in dialog.buttons.buttons() if b.text() == "Đóng")
    for button in (dialog.copy_button, close):
        assert button.isVisible()
        top_left = button.mapTo(dialog, button.rect().topLeft())
        assert dialog.rect().contains(top_left) and top_left.y() + button.height() <= dialog.height()
    assert not dialog.scroll.horizontalScrollBar().isVisible()
    assert dialog.scroll.widget().width() <= dialog.scroll.viewport().width()
