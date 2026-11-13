"""UX-2 (owner approval 2026-11-13): one icon set (Lucide, ISC / MIT) instead of mixed emoji, the next step filled in
the accent colour, and one set of marking buttons (the bottom bar) — the detail panel shows the marks only."""

from __future__ import annotations

import re
from pathlib import Path

from PySide6.QtWidgets import QAbstractButton

from app.ui import icons
from app.ui.top_bar import NEXT_STYLE, STEP_LABELS
from tests.gui.test_main_window import _import, _window, env  # noqa: F401 - fixture

ROOT = Path(__file__).resolve().parents[2]
# pictographs Windows draws as colour emoji (the symbols kept in text, ✓ ✕ ★ ♥ → ① …, are plain glyphs)
EMOJI = re.compile("[\U0001F300-\U0001FAFF☀-⛿⭐✅❌⌨ℹ⏰-⏿]")


def test_every_icon_used_in_the_code_is_shipped_with_its_licence() -> None:
    used = set()
    for f in (ROOT / "app").rglob("*.py"):
        used |= set(re.findall(r'icons\.icon\("([a-z0-9-]+)"', f.read_text(encoding="utf-8")))
    used |= {name for name, _label in STEP_LABELS.values()}
    from app.ui.detail_panel import TABS_ICONS

    used |= set(TABS_ICONS) | {"folder", "list-filter", "user"}  # the narrow window's rail
    shipped = {p.stem for p in icons.icons_dir().glob("*.svg")}
    assert used <= shipped, used - shipped
    assert shipped - used == set(), "unused icon files: " + ", ".join(sorted(shipped - used))
    licence = (icons.icons_dir() / "LICENSE.txt").read_text(encoding="utf-8")
    assert "ISC License" in licence and "Cole Bemis" in licence
    assert (ROOT / "packaging" / "licenses" / "Lucide-LICENSE.txt").read_text(encoding="utf-8") == licence
    assert '"app" / "assets" / "icons"' in (ROOT / "packaging" / "kirapick.spec").read_text(encoding="utf-8")


def test_icons_render_and_a_missing_one_is_empty_not_an_error(qtbot) -> None:  # noqa: ANN001
    pm = icons.icon("check").pixmap(36, 36)
    assert not pm.isNull() and not pm.toImage().allGray()
    assert icons.icon("no-such-icon").isNull()


def test_no_colour_emoji_on_buttons_or_menus(qtbot, env: dict) -> None:  # noqa: F811
    w = _window(qtbot, env)
    _import(qtbot, w, env["photos"])
    texts = [b.text() for b in w.findChildren(QAbstractButton)]
    texts += [a.text() for a in w.options_button.menu().actions()] + [w.search.placeholderText()]
    texts += [a.text() for a in w.bottom_bar.more_button.menu().actions()]
    assert [t for t in texts if EMOJI.search(t)] == []
    assert not w.act_import.icon().isNull() and not w.bottom_bar.keep_button.icon().isNull()


def test_next_step_is_filled_and_named(qtbot, env: dict) -> None:  # noqa: F811
    w = _window(qtbot, env)
    nxt = w.top_bar.buttons[w.top_bar.next_step]
    assert nxt.styleSheet() == NEXT_STYLE and "background" in NEXT_STYLE
    assert nxt.text().endswith(STEP_LABELS[w.top_bar.next_step][1]) and not nxt.icon().isNull()
    others = [b for k, b in w.top_bar.buttons.items() if k != w.top_bar.next_step]
    assert all(b.styleSheet() == "" for b in others)


def test_one_set_of_marking_buttons(qtbot, env: dict) -> None:  # noqa: F811
    w = _window(qtbot, env)
    _import(qtbot, w, env["photos"])
    for name in ("keep_button", "reject_button", "clear_button", "star_buttons", "favorite_button"):
        assert not hasattr(w.detail, name), name
        assert hasattr(w.bottom_bar, name), name
    w.select_row(0)
    w.bottom_bar.favorite_button.click()
    assert w.current_record().favorite and "♥" in w.detail.marks.text()
