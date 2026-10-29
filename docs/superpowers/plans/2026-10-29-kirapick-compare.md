# KiraPick UI part 2: Compare mode — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Compare 2–4 marked photos side by side; the active photo follows the mouse and receives every culling action.

**Architecture:** A pure arrangement/state module, a `CompareTile` wrapping one part 1 `ImageViewer`, and a `CompareView` page
(centre page 3) that `MainWindow` routes every action through (`_action_records()` / `view_record()`). The tiles share
two independent single-thread pools (previews; full-resolution decodes) with an exact 200 000 000-pixel full-frame
budget, and join the part 1 shutdown contract.

**Tech Stack:** Python 3.12/3.13, PySide6 6.12 (Qt Widgets), SQLite (no schema change), pytest + pytest-qt (offscreen;
real `windows` platform in CI).

**Spec:** `docs/superpowers/specs/2026-10-29-kirapick-compare-design.md` (revision 3). Plan revision 2 (review CR-P2-V2-01/02, RV-P2-01/02). Part 1 spec and plan:
`docs/superpowers/specs/2026-10-28-kirapick-ui-layout-design.md`, `docs/superpowers/plans/2026-10-28-kirapick-ui-layout.md`.

## Global Constraints

- 2–4 marked photos only; fewer: status "Đánh dấu 2–4 ảnh (Ctrl+click) rồi bấm C để so sánh."; more: "Chỉ so sánh được tối đa 4 ảnh — đang đánh dấu N, hãy bỏ bớt dấu." — never picks photos itself.
- Every culling action in Compare applies to the active photo only; the active ID changes on `enterEvent` immediately; 150 ms debounce is for the detail panel only, flushed when the pointer leaves the tiles.
- Keys 1–5 stay stars. ← →, Space / Enter, auto-advance: no-ops in Compare. Enter with C or ⧉ So sánh; leave with Esc, G or "◀ Về lưới ảnh".
- Current photo, marking, scroll and filter unchanged by Compare; photos never leave Compare until it closes.
- 100 % = one photo pixel per physical screen pixel (`zoom / devicePixelRatio / pixmap_scale`).
- Compare pools: previews 1 thread + full decodes 1 thread (2 in all, ≤ 1 full decode at a time); ≤ 1 full frame per tile; budget `FULL_BUDGET_PIXELS = 200_000_000` exact pixels, reserved before decoding; a frame larger than the budget is never decoded in Compare.
- Settings only: `compare/arrangement` ∈ {"auto", "row", "grid"} (default "auto"), `compare/show_ai` (default false). No schema change.
- No change to AI scoring/ranking/learning, decisions beyond user actions, export, source photos. No auto-Reject. No tag / publish / release without the owner's command (beta 3.0.0b1).
- Wording rename only: 🎓 "So sánh ảnh…" → "🎓 Dạy gu…".
- After each task: review package (diff, targeted + full suite, screenshots if visual, regression risks); wait for the external reviewer's approval before the next task.

## Review Focus

- Pointer over the detail panel or bottom bar when a key is pressed → the last hovered tile is the target (Task 5 test `test_keys_after_leaving_tiles_hit_last_hovered`).
- Compare entered with the pointer outside the tiles (keyboard user) → active = grid current photo if compared, else tile 1 (Task 3 test `test_initial_active_without_hover`).
- The session reloads while comparing (analysis finishes → `reload_preserving_view`, filter refresh) → tiles keep their photos by ID and refresh chips/scores; a compared ID gone from the model → Compare closes with status "Một ảnh đang so sánh không còn trong danh sách — đã về lưới." (Task 4 test `test_reload_while_comparing`).
- A compared file deleted / unreadable on disk → that tile shows the loupe error text; decisions on it still work; other tiles unaffected (Task 2 test `test_tile_unreadable_file`).
- Xoay xem of the active photo while others are zoomed → re-arrangement keeps every other tile's zoom and centre point (Task 3 test `test_rotation_rearranges_keeping_zoom`).

---

### Task 1: Arrangement and state model

**Files:**
- Create: `app/ui/compare_layout.py` (pure: no widgets)
- Test: `tests/unit/test_compare_layout.py`

**Interfaces:**
- Produces:
  - `Mode = Literal["auto", "row", "grid"]`
  - `@dataclass(frozen=True) class Cell: row: int; col: int; row_span: int = 1; col_span: int = 1`
  - `@dataclass(frozen=True) class Arrangement: rows: int; cols: int; cells: tuple[Cell, ...]; fallback: bool` (fallback = Row/Grid replaced by auto because a displayed photo's long side < `min_long`)
  - `arrange(sizes: Sequence[tuple[int, int] | None], area: tuple[int, int], mode: Mode, *, gap: int = 6, header: int = 22, min_long: int = 160) -> Arrangement`
  - `displayed_sizes(sizes, area, rows: int, cols: int, cells: Sequence[Cell], *, gap: int = 6, header: int = 22) -> list[tuple[float, float]]` (each photo fitted into its cell's box, spans included)
  - `turned_size(width: int | None, height: int | None, rotation: int) -> tuple[int, int] | None` (odd quarter turns swap; None when unknown)
  - `start_error(count: int) -> str | None` (the two exact status texts; None for 2–4)
  - `initial_active(compared: Sequence[int], current: int | None) -> int`

- [ ] **Step 1: Write the failing tests** (expected values = the spec's worked-examples table, revision 3)

```python
L, P = (6000, 4000), (4000, 6000)

@pytest.mark.parametrize("sizes,area,mode,shape,fallback", [
    ([L] * 4, (1920, 484), "auto", (1, 4), False),     # SHORT
    ([L] * 2, (960, 1000), "auto", (2, 1), False),     # NARROW
    ([L] * 4, (580, 400), "auto", (2, 2), False),      # TINY
    ([L] * 4, (580, 400), "row", (2, 2), True),        # 1 × 4 long side 140.5 < 160 → auto
    ([L] * 4, (1600, 900), "row", (1, 4), False),      # long side 395.5
    ([P] * 2, (1200, 800), "auto", (1, 2), False),
    ([L] * 3, (1600, 900), "auto", (2, 2), False),     # 2 + 1
    ([P, P, L], (1600, 900), "auto", (1, 3), False),   # mixed
    ([L, L, P], (1600, 900), "auto", (1, 3), False),   # mixed, other order
    ([L] * 3, (960, 1000), "auto", (2, 2), False),     # 2 + 1 beats 3 × 1 (151 686 vs 141 681)
    ([L] * 3, (1600, 900), "grid", (2, 2), False),
    ([L] * 2, (1600, 900), "grid", (1, 2), False),
    ([L] * 4, (1600, 900), "grid", (2, 2), False),
])
def test_worked_examples(sizes, area, mode, shape, fallback):
    a = arrange(sizes, area, mode)
    assert (a.rows, a.cols) == shape and a.fallback is fallback

def test_two_plus_one_third_spans_both_columns_and_is_fitted_wider():
    a = arrange([L] * 3, (1000, 800), "grid")
    assert a.cells[2] == Cell(1, 0, 1, 2)
    fitted = displayed_sizes([L] * 3, (1000, 800), a.rows, a.cols, a.cells)
    assert fitted[0] == pytest.approx((497.0, 331.3), abs=0.1)
    assert fitted[2] == pytest.approx((562.5, 375.0), abs=0.1)  # wider than one column: the span counts

def test_auto_score_uses_spans():
    # the 2 + 1 score at 1600 × 900 is the smallest displayed area with photo 3 in its spanning box
    a = arrange([L] * 3, (1600, 900), "auto")
    fitted = displayed_sizes([L] * 3, (1600, 900), a.rows, a.cols, a.cells)
    assert round(min(w * h for w, h in fitted)) == 270938

def test_minimum_is_measured_on_the_displayed_photo():
    # 1 × 4 at 580 × 400: box 140.5 × 378 (larger than 120 × 90) but the photo shown is 140.5 × 93.7 → too small
    assert arrange([L] * 4, (580, 400), "row").fallback
    assert not arrange([L] * 4, (580, 400), "auto").fallback  # auto never reports a fallback

def test_turned_sizes_change_the_choice():
    assert turned_size(6000, 4000, 1) == (4000, 6000) and turned_size(6000, 4000, 2) == (6000, 4000)
    assert turned_size(None, 4000, 1) is None

def test_unknown_size_counts_as_3_2():
    assert arrange([None, L], (1600, 900), "auto") == arrange([(3, 2), L], (1600, 900), "auto")

def test_start_error_texts():
    assert start_error(1) == "Đánh dấu 2–4 ảnh (Ctrl+click) rồi bấm C để so sánh."
    assert start_error(6) == "Chỉ so sánh được tối đa 4 ảnh — đang đánh dấu 6, hãy bỏ bớt dấu."
    assert start_error(2) is None and start_error(4) is None

def test_initial_active():
    assert initial_active([5, 7, 9], 7) == 7 and initial_active([5, 7, 9], 2) == 5
```

- [ ] **Step 2: Run** `.venv/bin/python -m pytest -q tests/unit/test_compare_layout.py` — Expected: FAIL (module missing).
- [ ] **Step 3: Implement `app/ui/compare_layout.py`.** Candidates per n exactly as the spec table (cells in tile order); `displayed_sizes` fits each photo into its cell box `cw·col_span + gap·(col_span−1)` × `rh·row_span + gap·(row_span−1) − header`; auto = max of `round(min(area))`, ties fewer rows then listed order; Row/Grid with any displayed long side < `min_long` → the auto result with `fallback=True`.
- [ ] **Step 4: Run** the same command — Expected: all pass.
- [ ] **Step 5: Commit** `"Compare: arrangement and state model (part 2 task 1)"`.

### Task 2: CompareTile and independent ImageViewer

**Files:**
- Modify: `app/ui/viewer.py` (`ImageViewer.__init__`)
- Create: `app/ui/compare_view.py` (`CompareTile` in this task)
- Test: `tests/gui/test_compare_tile.py`

**Interfaces:**
- Consumes: part 1 `ImageViewer.show_photo(path, placeholder, full_long_side, rotation)`, `set_zoom`, `set_rotation`, `toggle_zoom`, `zoom`, `is_full_resolution_shown()`, `_apply_zoom` scale rule; `card_texts(rec)` from `app/ui/grid.py`.
- Produces:
  - `ImageViewer(parent=None, *, pool: QThreadPool | None = None, full_pool: QThreadPool | None = None, full_cache: int = 2)` — given pools are used and never owned (`full_pool` defaults to `pool`; FULL loads go to `full_pool`); `full_cache` replaces the module constant per instance.
  - `class CompareTile(QWidget)`: `hovered = Signal(int)` (emitted from `enterEvent`), `viewer: ImageViewer`, `asset_id: int | None`, `show_record(rec: AssetRecord, pixmap: QPixmap | None) -> None`, `update_record(rec: AssetRecord) -> None` (header: number, name, chip, ★, ♥ — no reload), `set_number(n: int)`, `set_active(on: bool)` (frame), `set_ai_text(text: str | None)` (overlay; content from Task 6), `set_note(text: str)` (header note, e.g. "đang tải ảnh gốc…").

- [ ] **Step 1: Write the failing tests**
  - `test_viewer_uses_given_pools`: `ImageViewer(pool=p, full_pool=f)`: a preview load is started on `p`, a FULL load on `f`; default viewer still owns one 2-thread pool used for both.
  - `test_true_100_percent_at_dpr` (CR-P2-03), parametrised dpr 1 / 1.5 / 2 (monkeypatch `devicePixelRatioF`): after full image shown and `set_zoom(1.0)`, `viewer.transform().m11() == pytest.approx(1 / dpr)`.
  - `test_preview_to_full_keeps_centre_point`: zoom 1.0 at focus (0.3, 0.6) on a preview; deliver the full image; the scene point at the viewport centre maps to (0.3, 0.6) ± 0.01 of the pixmap.
  - `test_rotation_while_zoomed_keeps_point` and `test_eye_point_with_turned_photo` (face box at (0.2, 0.1, 0.1, 0.1), rotation 1 → centre at `rotate_point(0.25, 0.142, 1)`).
  - `test_tile_header_follows_record`: `update_record` with flag keep / rating 3 / favorite → header text contains "Chọn", "★★★", "♥"; no new load requested (pool activeThreadCount unchanged, token unchanged).
  - `test_tile_hover_emits_id`: `QTest.mouseMove` / `QEnterEvent` → `hovered` emitted once with the asset id.
  - `test_tile_unreadable_file` (Review Focus): a garbage `.jpg` → viewer message text "Không đọc được ảnh này"; `update_record` still updates the chip.
- [ ] **Step 2: Run** `.venv/bin/python -m pytest -q tests/gui/test_compare_tile.py` — Expected: FAIL.
- [ ] **Step 3: Implement** the `ImageViewer` parameters (no behaviour change for the loupe: existing `tests/gui/test_viewer*.py` stay green) and `CompareTile` (header `QLabel` above the viewer, `objectName "compareTile"`, active frame via a dynamic property + theme rule `QWidget#compareTile[active="true"] { border: 2px solid <accent> }`).
- [ ] **Step 4: Run** the task tests plus `tests/gui -k viewer` — Expected: pass.
- [ ] **Step 5: Commit** `"Compare: tile with its own viewer; viewer takes a shared pool (part 2 task 2)"`.

### Task 3: CompareView and active hover

**Files:**
- Modify: `app/ui/compare_view.py` (`CompareView`)
- Test: `tests/gui/test_compare_view.py`

**Interfaces:**
- Consumes: Task 1 `arrange`, `turned_size`, `initial_active`; Task 2 `CompareTile`.
- Produces: `class CompareView(QWidget)`:
  - `active_changed = Signal(int)` (immediate), `panel_photo_changed = Signal(int)` (150 ms after the last change; flushed on leaving the tiles), `back_requested = Signal()`
  - `PANEL_DELAY_MS = 150`
  - `show_records(records: list[AssetRecord], pixmaps: dict[int, QPixmap], active_id: int) -> None`
  - `clear() -> None` (every tile `show_photo(None)`, hidden)
  - `active_id: int | None`, `tile(asset_id: int) -> CompareTile | None`, `records() -> list[AssetRecord]`
  - `update_record(rec: AssetRecord) -> None` (chips / rotation; re-arranges when the turned size changes)
  - `set_arrangement(mode: Mode) -> None`, `arrangement: Arrangement`
  - `preview_pool: QThreadPool` (1 thread) and `full_pool: QThreadPool` (1 thread), created once; four tiles created once in `__init__`

- [ ] **Step 1: Write the failing tests**
  - `test_active_changes_immediately_on_enter`: hover tile 2 → `active_id == id2` and `active_changed` emitted before any event-loop wait; `panel_photo_changed` not yet emitted; after 150 ms it is emitted once with id2.
  - `test_quick_hover_emits_panel_once`: hover 1 → 2 → 3 within 50 ms → `panel_photo_changed` emitted once, with id3.
  - `test_leave_keeps_last_and_flushes_panel`: hover tile 3 then `leaveEvent` on the view → `active_id == id3`, `panel_photo_changed(id3)` emitted at once.
  - `test_initial_active_without_hover` (Review Focus): `show_records(..., active_id=id2)` with the pointer outside → `active_id == id2`, tile 2 frame on.
  - `test_layout_matches_arrange`: 3 records with the Compare page resized to 1600×900 in "grid" → tile geometries in a 2×2 grid, third tile spanning both columns.
  - `test_arrange_uses_the_page_size` (RV-P2-V3-03): the size passed to `arrange` is `CompareView.contentsRect().size()` (the page as laid out by Qt, without the arrangement toolbar), never the window size: a window of 1600×1000 with sidebar and detail panel docked gives `arrange` an area smaller than the window and equal to the page.
  - `test_resize_keeps_each_tile_zoom`: tiles 1 and 2 zoomed to 1.0 at different points; resize 1600×900 → 960×1000 (arrangement changes) → each tile's `zoom` and centre point unchanged (± 0.01).
  - `test_rotation_rearranges_keeping_zoom` (Review Focus): two landscape photos 1×2 at 1200×800; `update_record` with rotation 1 for one → arrangement recomputed; the other tile's zoom and centre point unchanged.
  - `test_tiles_and_pools_created_once`: `show_records` / `clear` repeated 5× → same 4 tile objects, same two pools, each `maxThreadCount() == 1`.
- [ ] **Step 2: Run** `.venv/bin/python -m pytest -q tests/gui/test_compare_view.py` — Expected: FAIL.
- [ ] **Step 3: Implement** `CompareView` (QGridLayout rebuilt from `arrange` on show / resize — part 1 `DEBOUNCE_MS` 120 ms — / rotation; panel timer single-shot 150 ms restarted by each change; `leaveEvent` of the tiles' container flushes).
- [ ] **Step 4: Run** the task tests — Expected: pass.
- [ ] **Step 5: Commit** `"Compare: view with active hover and arrangement (part 2 task 3)"`.

### Task 4: MainWindow integration

**Files:**
- Modify: `app/ui/main_window.py` (centre page 3, shortcuts, `show_compare`, `leave_compare`, `view_record`, reload hook, "Dạy gu" wording at the 🎓 dialog), `app/ui/bottom_bar.py` (⧉ So sánh button + `compare = Signal()`), README keys table
- Test: `tests/gui/test_compare_window.py`

**Interfaces:**
- Consumes: Task 1 `start_error`, `initial_active`; Task 3 `CompareView`.
- Produces on `MainWindow`:
  - `self.compare: CompareView` (centre index `COMPARE_PAGE = 3`), `in_compare() -> bool`
  - `show_compare() -> bool` (False + status text when `start_error` says so)
  - `leave_compare() -> None` (back to page 1, grid scrolled to the current photo, focus on grid)
  - `view_record() -> AssetRecord | None` (Compare: active photo; else `current_record()`); `_show_inspector` callers in Compare use it via `compare.panel_photo_changed`
  - shortcuts: `C` → `show_compare`, `G` → `leave_compare` (grid view; outside Compare it equals `show_loupe(False)`), Escape → `close_floating() or leave_compare() or show_loupe(False)`

- [ ] **Step 1: Write the failing tests**
  - `test_c_with_wrong_counts`: 0, 1 and 5 marked → page unchanged, status equals `start_error(n)`.
  - `test_c_with_two_and_four`: page == 3, tiles show the marked photos in grid order, active = current photo when compared.
  - `test_leave_restores_everything`: record current id, marked ids, scroll value, filter; C, hover, Esc → all identical; same with G and with the back button.
  - `test_arrows_space_enter_noop_in_compare`: ← → Space Enter → page 3, current photo and active photo unchanged.
  - `test_detail_panel_follows_panel_photo`: hover tile 2, wait 200 ms → detail panel shows id2; the grid's current photo unchanged.
  - `test_reload_while_comparing` (Review Focus): `reload_preserving_view()` → tiles keep their IDs and show refreshed chips; a compared asset removed from the model (filter that excludes it via `model.set_filter`) → still shown (spec rule), but an asset deleted from the session (`DELETE FROM assets` + reload) → page 1 and the exact status text.
  - `test_teach_taste_wording`: the 🎓 dialog button text is "🎓 Dạy gu…"; no visible text "So sánh ảnh…" remains in `app/ui`.
  - `test_compare_button_in_bottom_bar`: the ⧉ So sánh button triggers `show_compare`; its tooltip mentions C and 2–4.
- [ ] **Step 2: Run** `.venv/bin/python -m pytest -q tests/gui/test_compare_window.py` — Expected: FAIL.
- [ ] **Step 3: Implement** the integration (Compare records looked up by ID from the model after each reload; `step`, `toggle_loupe` return early in Compare; key hints text for Compare: "Rê chuột: chọn ảnh · P/X chọn/loại · 1–5 sao · I thông tin AI · E mắt · Z 100% · Esc về lưới").
- [ ] **Step 4: Run** the task tests and `tests/gui/test_main_window.py tests/gui/test_adaptive_layout.py` — Expected: pass.
- [ ] **Step 5: Commit** `"Compare: window integration, C / G / Esc, Dạy gu wording (part 2 task 4)"`.

### Task 5: Active-photo culling commands (CR-P2-01)

**Files:**
- Modify: `app/ui/main_window.py` (`_targets` → `_action_records`, handlers below), `app/ui/detail_panel.py` (`shown_id` property)
- Test: `tests/gui/test_compare_actions.py`

**Interfaces:**
- Consumes: Task 4 `in_compare`, `view_record`; Task 3 `active_id`, `update_record`.
- Produces:
  - `MainWindow._action_records() -> list[AssetRecord]` — the only target source for: `set_flag`, `set_rating`, `toggle_favorite`, `set_focus_label`, `rotate_view`, bottom-bar Chọn / Loại / Bỏ chọn and "⋯" Xoay xem / Bỏ chọn
  - `DetailPanel.shown_id: int | None`; panel buttons / people menu act on `shown_id`; in Compare, `shown_id != compare.active_id` → refused, status "Bảng chi tiết chưa kịp đổi sang ảnh đang chọn — bấm lại."
  - `zoom_to_eyes`, `toggle_zoom`, `zoom_step` act on the active tile's viewer in Compare
  - after each action in Compare: `compare.update_record(rec)`, counts / steps refreshed, no auto-advance

- [ ] **Step 1: Write the failing tests** — parametrised over every audited action (`P`, `K`, `X`, `U`, `1`…`5`, `0`, `F`, `Q`, `W`, `R`, Xoay xem action, detail keep / reject / clear / rating / favorite, bottom-bar Chọn / Loại / Bỏ chọn, ⋯ Xoay xem / Bỏ chọn):
  - `test_action_hits_active_only[...]`: 3 compared photos, hover tile 2 → act → tile 2's row changed as expected; tiles 1 and 3 rows in `decisions`, `view_rotation` and `occurrences` byte-identical before / after; current photo and marking unchanged; page still 3.
  - `test_keys_after_leaving_tiles_hit_last_hovered` (Review Focus): hover tile 3, move the pointer onto the detail panel, press X → tile 3 rejected.
  - `test_key_right_after_hover_uses_new_tile`: hover tile 1, then tile 2 and press P within the same event-loop turn (no wait) → tile 2 kept.
  - `test_panel_button_refused_while_panel_lags`: hover tile 1, wait 200 ms, hover tile 2 (no wait), click the panel's ✓ Chọn → nothing changed, exact status text.
  - `test_people_menu_acts_on_panel_photo`: as RV9-03 (part 1) inside Compare.
  - `test_e_z_plus_act_on_active_tile`: other tiles' `zoom` unchanged.
  - `test_neighbour_click_in_compare`: the panel's Ảnh tương tự click shows that photo in the panel only; compared set, active photo, current photo unchanged.
  - `test_outside_compare_unchanged`: part 1 multi-mark behaviour (`_targets` semantics) still applies on the grid.
- [ ] **Step 2: Run** `.venv/bin/python -m pytest -q tests/gui/test_compare_actions.py` — Expected: FAIL.
- [ ] **Step 3: Implement** the routing; grep `app/ui/main_window.py` for `_targets(` and `current_record()` in action handlers: every one is replaced or listed in the commit message as intentionally grid-only.
- [ ] **Step 4: Run** the task tests and the full GUI suite `.venv/bin/python -m pytest -q tests/gui` — Expected: pass.
- [ ] **Step 5: Commit** `"Compare: every action targets the active photo (part 2 task 5, CR-P2-01)"`.

### Task 6: AI overlay and settings

**Files:**
- Modify: `app/ui/compare_view.py` (arrangement button + AI overlay), `app/ui/main_window.py` (I key, settings)
- Create: `compare_ai_text(rec: AssetRecord) -> str` in `app/ui/compare_view.py`
- Test: `tests/gui/test_compare_overlay.py`

**Interfaces:**
- Consumes: `card_texts`, `Score.weaknesses`, `Ranked.tech` / `.taste` (as the score card does).
- Produces: `compare_ai_text(rec) -> str`: `"K 78 · G 85"` (G omitted when taste not ready), `"⚠ "` prefix on hard defect, then `" · " + weaknesses[0]`; no score → `"chưa phân tích"`. `CompareView.set_ai_visible(on: bool)`; arrangement button (QToolButton menu: "Tự động", "Một hàng", "Lưới 2×2"; label "Tự động (cửa sổ nhỏ)" when `arrangement.fallback`).

- [ ] **Step 1: Write the failing tests**
  - `test_ai_text_values`: a scored record → exactly the K/G numbers `card_texts` / score card show; hard defect → starts with "⚠"; unscored → "chưa phân tích"; no digits in that text.
  - `test_i_toggles_all_tiles_and_persists`: I → every visible tile overlay shown; I → hidden; `settings.value("compare/show_ai")` follows; a new window restores it.
  - `test_arrangement_menu_persists`: choose "Một hàng" → `compare/arrangement == "row"`, layout 1 × n; new window restores it; TINY size shows "Tự động (cửa sổ nhỏ)" and the saved value stays "row".
- [ ] **Step 2: Run** `.venv/bin/python -m pytest -q tests/gui/test_compare_overlay.py` — Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** — Expected: pass.
- [ ] **Step 5: Commit** `"Compare: AI line on I, arrangement choice, settings (part 2 task 6)"`.

### Task 7: Worker lifecycle and memory (CR-P2-04)

**Files:**
- Modify: `app/ui/compare_view.py` (full-frame budget), `app/ui/viewer.py` (`full_frame_loaded = Signal(object)` carrying `(width, height)` of the decoded image, `full_load_failed = Signal()`, `drop_full() -> None`, `request_full_allowed: Callable[[], bool] | None` hook asked before a FULL load is queued), `app/ui/main_window.py` (`_session_work`, `_close_session`, `closeEvent` leave Compare first), `.github/workflows/build-windows.yml` (stress step adds the new test file)
- Test: `tests/gui/test_compare_lifecycle.py` (stress-marked loop variant `@pytest.mark.stress`)

**Interfaces:**
- Consumes: Task 3 `preview_pool`, `full_pool`, tiles; part 1 `shutdown.Work`, `settle`, gate.
- Produces: `FULL_BUDGET_PIXELS = 200_000_000`; `CompareView.full_pixels() -> int` (held + reserved, exact); `CompareView.wait_idle(msecs: int) -> bool` and `stop_pending()` over both pools; `Work("đọc ảnh để so sánh", compare.wait_idle, compare.stop_pending)` in `_session_work()`; header texts "đã trả về vừa khung để đủ bộ nhớ" and "Ảnh quá lớn để mở độ phân giải đầy đủ khi so sánh — mở ở Xem lớn để soi 100 %".

- [ ] **Step 1: Write the failing tests**
  - `test_budget_counts_exact_pixels`: frames of 6000 × 4000 and 6001 × 4001 → `full_pixels() == 24_000_000 + 24_010_001` (no rounding).
  - `test_budget_drops_least_recently_active`: assets recorded 9504 × 6336 (60 217 344 px); zoom tiles 1, 2, 3 (180 652 032), activate 4 and zoom → before tile 4's decode is queued, tile 1 (least recently active) is back to fit with the exact header text, `full_pixels() <= 200_000_000`.
  - `test_reservation_before_decode`: two tiles zoomed within one event-loop turn whose expected sizes together pass the budget → the second reservation drops the first tile before any decode starts (held decode via threading.Event; only one FULL task ever queued at a time).
  - `test_reservation_released_on_failure_and_drop`: a FULL load that fails, and one dropped by leaving Compare → `full_pixels() == 0`.
  - `test_double_reservation_same_tile`: Z twice / wheel zoom repeated on one tile before its decode arrives → one reservation, `full_pixels()` counts it once; one FULL task queued (RV-P2-V3-02).
  - `test_decoded_larger_than_expected`: recorded 6000 × 4000 but the decode returns 8256 × 5504 → reservation corrected to 45 441 024 on arrival; if that passes the budget, least recently active tiles are dropped until `full_pixels() <= 200_000_000` (RV-P2-V3-02).
  - `test_oversized_single_frame_not_decoded`: an asset recorded 20000 × 12000 (240 MP) zoomed → no FULL task queued, tile stays on the preview, exact oversized header text.
  - `test_late_result_after_leaving_is_ignored`: hold a decode (threading.Event), Esc, release → no tile pixmap change, no exception.
  - `test_close_with_full_loads_running` and `test_switch_with_full_loads_running`: 4 held full decodes; close / folder switch waits (part 1 status "Đang đợi đọc ảnh để so sánh …"), DB closed only after the pool is idle (part 1 `_watch_db` order check).
  - `test_one_full_decode_at_a_time`: 4 zoomed tiles with held decodes → `full_pool.activeThreadCount() <= 1` and the two pools together `<= 2`, sampled during the loads.
  - `test_compare_stress` (`@pytest.mark.stress`): 30 × (enter, zoom all, Esc / switch / close) without crash.
- [ ] **Step 2: Run** `.venv/bin/python -m pytest -q tests/gui/test_compare_lifecycle.py -m "not stress"` — Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** task tests, `-m stress tests/gui/test_compare_lifecycle.py`, and part 1 `tests/gui/test_shutdown_*.py` — Expected: pass.
- [ ] **Step 5: Commit** `"Compare: shared pool, 200 MP budget, shutdown contract (part 2 task 7, CR-P2-04)"`.

### Task 8: Regression, performance and Windows CI

**Files:**
- Create: `tests/perf/test_compare_perf.py` (marker `perf`)
- Modify: `tests/gui/test_snap_sizes.py` (Compare variant), `scripts/ui_screenshots.py` (Compare shots), `.github/workflows/build-windows.yml` (GUI smoke list adds the Compare test files), `docs/IMPLEMENTATION_STATUS.md`, `docs/beta-release-checklist.md` (section 3 gets Compare steps), README
- Test: as listed

**Interfaces:**
- Consumes: everything above.

- [ ] **Step 1: Write the tests**
  - perf: enter Compare with 4 photos (synthetic 10,000-photo session) first paint ≤ 100 ms; real NEF previews ≤ 1 s (skips without samples); P/X in Compare median ≤ 50 ms, worst ≤ 100 ms (200 presses); hover change worst Qt-thread block ≤ 50 ms (10 ms probe, part 1 method).
  - RV-P2-02 memory: zoom all 4 tiles and record process peak RSS (sampled every 20 ms) and each decode's transient peak, for 24 MP NEF (owner samples, skip without), synthetic 45 MP (8256 × 5504) and 61 MP (9504 × 6336) JPEGs; assert held full pixels ≤ `FULL_BUDGET_PIXELS` throughout and no more than one full decode in flight; the 61 MP set shows the budget drop (four do not fit).
  - Snap: Compare at the 13 part 1 Snap sizes (layout from the Compare page's real Qt size, RV-P2-V3-03) → no cut-off button (`clipped_buttons`), every displayed photo's long side ≥ 160 px or the auto fallback.
- [ ] **Step 2: Run** `.venv/bin/python -m pytest -q -m perf tests/perf/test_compare_perf.py -s` and `.venv/bin/python -m pytest -q tests/gui/test_snap_sizes.py` — Expected: pass; numbers recorded.
- [ ] **Step 3: Full suite** `.venv/bin/python -m pytest -q` three times — Expected: all pass each time.
- [ ] **Step 4: Windows CI** — push with `[perf]` (never a release marker); read each notice (`suite`, `gui-windows`, `snap-dpi`, `perf`, `stress`), record them in `docs/beta-release-checklist.md` B2; screenshots WIDE / NARROW / SHORT / TINY.
- [ ] **Step 5: Commit** `"Compare: performance, Windows CI and docs (part 2 task 8)"`; report to the owner in Vietnamese; release-candidate validation follows only after approval and the owner's command.
