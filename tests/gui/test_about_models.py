"""REG-1 (4): work screens name functions; models, files, SHA-256 and licences are only in ⚙ → ℹ Giới thiệu."""

from __future__ import annotations

import ast
import re
from pathlib import Path

from app.ai import features as ft
from app.ai.models import ModelRegistry
from app.ui.about_models import ModelsDialog

ROOT = Path(__file__).resolve().parents[2]
MODEL_WORDS = re.compile(r"\b(CLIP|TOPIQ|LAION|ArcFace|InsightFace|ReID|YoutuReID|SFace|YOLOX|YuNet|eDifFIQA|MediaPipe)\b"
                         r"|\.onnx\b")
# where model names belong: the about screen and its table, and messages written to the local log / self-test files
ALLOWED = {"app/ui/about_models.py", "app/ai/features.py"}


def _ui_strings(path: Path) -> list[tuple[int, str]]:
    """String literals a work screen can show (docstrings and logging calls left out)."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    skip: set[int] = set()
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if isinstance(body, list) and body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
            skip.add(id(body[0].value))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name) \
                and node.func.value.id in ("log", "logging") or (
                isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr in ("debug", "info", "warning", "exception", "error")):
            for sub in ast.walk(node):
                skip.add(id(sub))
    return [(n.lineno, n.value) for n in ast.walk(tree)
            if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in skip]


def test_work_screens_name_functions_not_models() -> None:
    files = sorted(ROOT.glob("app/ui/*.py")) + [ROOT / "app/quality/score.py",
                                                  ROOT / "app/workers/analyze_process.py"]
    found = []
    for f in files:
        rel = f.relative_to(ROOT).as_posix()
        if rel in ALLOWED:
            continue
        found += [f"{rel}:{line}: {text[:80]}" for line, text in _ui_strings(f) if MODEL_WORDS.search(text)]
    assert not found, "\n".join(found)


def test_every_weight_and_function_is_on_the_about_screen(qtbot) -> None:  # noqa: ANN001
    registry = ModelRegistry()
    d = ModelsDialog(None, registry)
    qtbot.addWidget(d)
    assert d.models.rowCount() == len(registry.specs)
    assert d.features.rowCount() == len(ft.FEATURES)
    rows = {r.model_id: r for r in ft.model_rows(registry)}
    assert all(m in rows for f in ft.FEATURES for m in f.models)  # no function names an unknown weight
    for model_id in registry.policy.ids("never"):
        assert rows[model_id].status == ft.STATUS_TEXT["never"]
    for model_id in registry.policy.ids("pending"):
        assert rows[model_id].status == ft.STATUS_TEXT["pending"]
    texts = [d.models.item(r, 0).text() for r in range(d.models.rowCount())]
    assert len(texts) == len(set(texts))


def test_a_function_without_its_weights_says_what_the_user_gets() -> None:
    rows = {r.model_id: r for r in ft.model_rows()}
    grouping = next(f for f in ft.FEATURES if f.models == ("face_embedder",))
    assert ft.feature_status(grouping, rows) == ft.STATUS_TEXT["pending"]
    assert "Gom tay" in grouping.without
    assert all(f.without or f.rule for f in ft.FEATURES)


def test_the_about_screen_is_in_the_options_menu(qtbot, tmp_path) -> None:  # noqa: ANN001
    from PySide6.QtCore import QSettings

    from app.ui.main_window import MainWindow

    w = MainWindow(settings=QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat))
    qtbot.addWidget(w)
    assert w.act_about_models in w.options_button.menu().actions()


def test_every_weight_has_its_own_benchmark_basis() -> None:
    """REG-2 (4): internal benchmarking is decided per weight from its own terms; a 'never' weight is never
    benchmarked, and the field can never make the app open a weight."""
    policy = ModelRegistry().policy
    for e in policy.entries.values():
        assert e.benchmark and e.benchmark["allowed"] in ("yes", "pending", "no") and e.benchmark["basis"], e.id
        if e.status == "never":
            assert e.benchmark["allowed"] == "no", e.id
        if e.status == "pending":
            assert e.benchmark["allowed"] != "yes", e.id  # no use basis yet: no benchmark basis either
    rows = {r.model_id: r for r in ft.model_rows()}
    assert rows["face_embedder_arcface"].benchmark.startswith("Không")
    assert rows["person_detector_s"].benchmark.startswith("Được")
