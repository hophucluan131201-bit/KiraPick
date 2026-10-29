# KiraPick UI redesign part 1 (adaptive layout) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reorganise the main window into top bar / sidebar / grid / detail panel / bottom bar that adapts to the window size (WIDE, MEDIUM, NARROW, SHORT, TINY) without changing any AI formula.

**Architecture:** Pure, Qt-free modules decide everything testable (score display, chip rule, layout mode, step states, counts/size, histogram, burst). Thin Qt widgets render them. A `LayoutController` applies a mode without reparenting (splitter orientation, layout direction, show/hide, raised overlays). `MainWindow` keeps orchestration and wires parts with signals.

**Tech Stack:** Python 3.12/3.13, PySide6, SQLite, numpy, pytest + pytest-qt (offscreen).

**Spec:** `docs/superpowers/specs/2026-10-28-kirapick-ui-layout-design.md` (revision 2, decisions D1–D8 approved 2026-10-28).

## Global Constraints

- No release and no release markers (`[release…]`) in commit messages; push to `beta` only.
- Never write, move or rename source photos; export stays byte-identical copies.
- No change to `app/quality/score.py` formulas, `app/quality/rank.py`, taste or focus learning.
- Bands: good ≥ 75, fair 45–74, poor < 45 (reuse `GOOD`, `POOR` from `app/quality/score.py`).
- Colours: good `#3FB950`, fair `#D29922`, poor `#F85149`, neutral `#8B949E`, accent `#2F81F7`, suggestion `#E3B341`.
- Mode thresholds (CLIENT area = `QMainWindow.size()`, logical px; spec revision 3): TINY w < 600 or h < 300; SHORT h < 560 or (w ≥ 3 × h and h < 760); NARROW w < 1100; MEDIUM w < 1440; else WIDE. Hysteresis 40 px, debounce 120 ms. Minimum window 560 × 300.
- NARROW: detail docked when content width ≥ 900 (else overlay sheet), ≤ 40 % width, grid ≥ 2 columns.
- Wording (D1): culling = "Chọn / Loại / Bỏ chọn"; batch marking = "đánh dấu".
- Size (D2) follows the export option "Kèm JPEG" (setting `export/include_pairs`, default true).
- Step "Chọn ảnh" (D5): ✓ when ≥ 1 photo Chọn; ◐ when only an AI pick run exists.
- Xoay xem (D6): button only, no key; ignored by AI and export.
- `export_runs` (D8): time and counts only.
- UI text Vietnamese; code, comments and docs English; logs without file names or photo metadata.
- Nothing slow on the Qt thread: histogram and HD thumbnails in the existing thread pool.

## Review Focus

1. A photo without a score (not analysed, or no person) — badge "—", no chip except the user's, no crash in ring/bars. → Task 1 test `test_unscored_photo_shows_dash_and_no_ai_chip`.
2. Keys typed in the search box (P, X, Tab, digits) must type text, not cull or toggle panels. → Task 13 test `test_keys_in_search_box_do_not_cull`.
3. Moving the window to a screen with another scale (4K ↔ laptop) re-evaluates the mode and re-requests sharper thumbnails. → Task 12 test `test_dpr_change_reevaluates_mode`.
4. Shift+tick when the anchor photo is no longer in the current list (filter/sort/search changed) — acts on the single clicked card only. → Task 7 test `test_shift_tick_without_anchor_ticks_one`.
5. A JPEG-only shoot and a broken pair (JPEG whose RAW was deleted) — counted once each, size = own file. → Task 3 test `test_broken_pair_and_jpeg_only`.

---

### Task 1: Score display and chip rule (pure)

**Files:**
- Create: `app/ui/score_style.py`
- Test: `tests/unit/test_score_style.py`

**Interfaces:**
- Consumes: `Score` (`app/quality/score.py`), `Ranked` (`app/quality/rank.py`), `EYES_CLOSED`, `FOCUS_DEFECT`.
- Produces:
  - `display_value(ranked: Ranked | None) -> int | None` — `Ranked.value` rounded half-up.
  - `band(value: float | None) -> Literal["good", "fair", "poor", "none"]`
  - `COLORS: dict[str, str]` keys `good fair poor none accent suggestion`.
  - `hard_defect(score: Score | None, ranked: Ranked | None) -> bool` — eyes ≤ 15 or focus < 30 on `score.parts`, False when `ranked.artistic`.
  - `Chip(kind: Literal["keep","reject","suggested","review"], text: str, color: str)`
  - `chip_for(flag: str | None, pick_rank: int | None, score: Score | None, ranked: Ranked | None, uncertain: bool) -> Chip | None`
  - `REVIEW_WARNINGS = ("lệch nét / rung", "người không nét", "mắt nhắm hoặc nhìn xuống (nếu cố ý thì bỏ qua)", "mặt bị cháy sáng", "đầu chạm mép ảnh")` (exact strings from `score.py`).

- [ ] **Step 1: Write the failing tests**

```python
def test_value_rounds_half_up_and_bands():
    assert display_value(Ranked(74.5, None, 74.5)) == 75
    assert band(75) == "good" and band(74.9) == "fair" and band(45) == "fair" and band(44.9) == "poor"
    assert band(None) == "none" and display_value(None) is None

def test_chip_priority_user_first():
    s = _score(focus=10)  # hard problem
    assert chip_for("keep", 1, s, _r(s), True).kind == "keep"
    assert chip_for("reject", None, s, _r(s), False).kind == "reject"
    assert chip_for(None, 1, s, _r(s), False).kind == "suggested"
    assert chip_for(None, None, s, _r(s), False).kind == "review"
    assert chip_for(None, None, _score(focus=90), _r(_score(focus=90)), True).kind == "review"  # uncertain person
    assert chip_for(None, None, _score(focus=90), _r(_score(focus=90)), False) is None

def test_hard_defect_follows_rank_thresholds_and_artistic_exception():
    assert hard_defect(_score(eyes=15), None) and not hard_defect(_score(eyes=16), None)
    assert hard_defect(_score(focus=29.9), None) and not hard_defect(_score(focus=30), None)
    assert not hard_defect(_score(focus=10), Ranked(10, 90, 50, artistic=True))

def test_unscored_photo_shows_dash_and_no_ai_chip():
    assert display_value(None) is None and chip_for(None, None, None, None, False) is None
    assert chip_for("keep", None, None, None, False).kind == "keep"
```

(`_score(**parts)` builds a `Score` with those parts and the matching warnings via `app.quality.score.score` on a values dict, or directly; `_r(s)` = `rank(s, None, [])`.)

- [ ] **Step 2:** `.venv/bin/python -m pytest tests/unit/test_score_style.py -q` → FAIL (module missing).
- [ ] **Step 3: Implement** in `app/ui/score_style.py` (no QtWidgets import). "review" when `hard_defect` or any `score.warnings` item in `REVIEW_WARNINGS`, or `uncertain`.
- [ ] **Step 4:** run → PASS.
- [ ] **Step 5: Commit** `git commit -m "UI part 1: score display and status chip rule"`

### Task 2: Migration 7, view rotation and export runs

**Files:**
- Modify: `app/storage/db.py` (append migration 7)
- Create: `app/storage/view.py`, `app/storage/exports.py`
- Modify: `app/ui/export_dialog.py` (record a run after a finished export; remember "Kèm JPEG" in settings `export/include_pairs`)
- Test: `tests/unit/test_view_and_exports.py`

**Interfaces:**
- Produces:
  - SQL: `CREATE TABLE view_rotation (asset_id INTEGER PRIMARY KEY REFERENCES assets(id) ON DELETE CASCADE, quarter_turns INTEGER NOT NULL CHECK (quarter_turns IN (1, 2, 3)));` `CREATE TABLE export_runs (id INTEGER PRIMARY KEY, finished_at TEXT NOT NULL, photos INTEGER NOT NULL, files INTEGER NOT NULL);`
  - `view.rotation(conn, asset_id: int) -> int` (0–3), `view.rotate(conn, asset_id: int) -> int` (+1 mod 4; deletes the row at 0), `view.rotations(conn) -> dict[int, int]`.
  - `exports.record(conn, photos: int, files: int) -> None`, `exports.count(conn) -> int`.

- [ ] **Step 1: Failing tests**: `test_migration_7_on_a_v6_session` (open a DB at user_version 6 with a decision row; after `migrate` version is 7 and the row is intact), `test_rotate_cycles_and_clears` (rotate ×4 → 1,2,3,0 and no row left), `test_export_run_recorded_without_path` (`record(conn, 3, 5)`; table columns are exactly `id, finished_at, photos, files`), `test_export_dialog_records_a_run` (GUI: run the existing export flow from `tests/gui/test_main_window.py::test_export_dialog_previews_then_copies` setup; `exports.count == 1`; source files' bytes unchanged).
- [ ] **Step 2:** run → FAIL.
- [ ] **Step 3: Implement** migration, the two modules, the export-dialog hook (after a successful run only; cancelled/failed records nothing).
- [ ] **Step 4:** run these tests and `tests/unit/test_storage*.py tests/integration/test_export.py` → PASS.
- [ ] **Step 5: Commit** `"UI part 1: view rotation and export runs (schema v7)"`

### Task 3: Counts and export size (pure query)

**Files:**
- Create: `app/storage/stats.py`
- Test: `tests/unit/test_stats.py`

**Interfaces:**
- Produces: `Counts(total: int, keep: int, reject: int, undecided: int, errors: int, keep_bytes: int)`; `counts(conn, include_pairs: bool) -> Counts`. Photos counted as the grid shows them (JPEG half of a pair hidden — reuse the condition in `MainWindow._update_counts`); `keep_bytes` = sum of `assets.size` of kept photos, plus their paired JPEG when `include_pairs`.

- [ ] **Step 1: Failing tests**: `test_pair_counts_once_and_size_follows_option` (RAW 30 MB + JPEG 10 MB kept → keep 1, bytes 40 MB with pairs, 30 MB without), `test_broken_pair_and_jpeg_only` (JPEG with pair_group whose RAW row is gone counts 1 with its own size; plain JPEG counts 1), `test_undecided_excludes_errors`.
- [ ] **Step 2:** FAIL. **Step 3:** implement one SQL query. **Step 4:** PASS.
- [ ] **Step 5: Commit** `"UI part 1: counts and export size"`

### Task 4: Workflow step states (pure query)

**Files:**
- Create: `app/storage/workflow.py`
- Test: `tests/unit/test_workflow_steps.py`

**Interfaces:**
- Produces: `StepState(done: bool, partial: str | None)`; `STEPS = ("import", "people", "quality", "pick", "export")`; `steps(conn, *, importing: tuple[int, int] | None) -> dict[str, StepState]`. Rules exactly as the spec table: people = every ok photo has `detect` and `embed` in state done/failed; quality = every photo with `detect` done has `quality` done/failed; pick = ≥ 1 keep (partial "có đề xuất" when a `pick_runs` row exists); export = `exports.count > 0`; partial texts "a/b" with Vietnamese thousands dots via the existing number formatting if any, else `f"{a:,}".replace(",", ".")`.

- [ ] **Step 1: Failing tests**, one per table row: empty session; importing (340, 1082) → import partial "340/1.082"; half detected → people partial; all detected+embedded → done; failed photos count as processed; pick partial with pick run only; done with one keep; export done after `exports.record`.
- [ ] **Steps 2–4** FAIL → implement → PASS.
- [ ] **Step 5: Commit** `"UI part 1: workflow step states"`

### Task 5: Histogram and burst neighbours (pure)

**Files:**
- Create: `app/quality/histogram.py`, `app/quality/burst.py`
- Test: `tests/unit/test_histogram_burst.py`

**Interfaces:**
- Produces:
  - `Histogram(bins: np.ndarray, shadows: float, highlights: float)`; `histogram(rgb: np.ndarray) -> Histogram` — downscale to ≤ 1024 px long side, Y = 0.2126 R + 0.7152 G + 0.0722 B on 8-bit, 64 bins normalised to max 1, `shadows` share of Y ≤ 2, `highlights` share of Y ≥ 253.
  - `neighbours(conn, asset_id: int, window_s: float = 3.0) -> list[int]` — same subject as the photo's main occurrence (any photo when it has none or people are not recognised), capture time within ±window, excluding itself, ordered by time; photos without capture time → `[]`.

- [ ] **Step 1: Failing tests**: half black / half white image → shadows ≈ 0.5, highlights ≈ 0.5, bins[0] and bins[63] = 1.0; grey 128 → one bin; 4000×3000 input finishes < 0.2 s; burst at t = 0, 2, 3, 5 s same subject → neighbours(t=2) = [0, 3] (and 5 excluded); other subject at t = 1 excluded; no time → [].
- [ ] **Steps 2–4** FAIL → implement → PASS.
- [ ] **Step 5: Commit** `"UI part 1: histogram and burst neighbours"`

### Task 6: Layout mode decision (pure)

**Files:**
- Create: `app/ui/layout_modes.py` (pure part only in this task)
- Test: `tests/unit/test_layout_modes.py`

**Interfaces:**
- Produces: `class Mode(str, Enum): WIDE, MEDIUM, NARROW, SHORT, TINY`; `mode_for(width: int, height: int, previous: Mode | None = None) -> Mode`; constants `TINY_W = 600, TINY_H = 300, SHORT_H = 560, STRIP_RATIO = 3.0, STRIP_MAX_H = 760, NARROW_W = 1100, MEDIUM_W = 1440, HYSTERESIS = 40, DEBOUNCE_MS = 120, NARROW_DOCK_W = 900, MIN_WINDOW = (560, 300)`; `detail_docked(mode: Mode, width: int, previously_docked: bool | None = None) -> bool`; `detail_visible_default(mode: Mode, width: int) -> bool`; `client_size(window) -> tuple[int, int]` (review CR6-01/02). Hysteresis: a threshold already crossed by `previous` moves by 40 px in its favour (leaving a smaller mode needs `threshold + 40`).

- [ ] **Step 1: Failing tests**: table of (w, h) → mode for 1920×1080 WIDE, 1536×864 WIDE, 1280×720 MEDIUM, 960×1080 NARROW, 1920×540 SHORT, 700×400 TINY, 0×0 WIDE; hysteresis: previous NARROW at 1120 stays NARROW, at 1141 → MEDIUM; previous MEDIUM at 1090 → NARROW; `detail_docked(NARROW, 950)` True, `(NARROW, 880)` False, `(TINY, 2000)` False.
- [ ] **Steps 2–4** FAIL → implement → PASS.
- [ ] **Step 5: Commit** `"UI part 1: layout mode decision"`

### Task 7: Grid card (tick box, badge, chip) and model fields

**Files:**
- Modify: `app/ui/grid.py` (new card painting; `badge_text` removed), `app/ui/asset_model.py` (`AssetRecord.rotation: int`, chip computed lazily via `score_style.chip_for`; `rotations` loaded in `reload`), `app/ui/main_window.py` (handle `tick_clicked`)
- Test: `tests/gui/test_grid_cards.py`; update `tests/gui/test_grid_scores.py`

**Interfaces:**
- Consumes: Task 1, Task 2 (`view.rotations`).
- Produces: `ThumbnailDelegate.tick_rect(cell: QRect) -> QRect`; grid view signal `tick_clicked = Signal(int, bool)` (asset id, shift) emitted from an event filter on the viewport that swallows the press (so selection/current do not change); `MainWindow.toggle_keep(asset_ids: list[int])` (keep ↔ none, through `_apply` so learning still runs), anchor stored as `self._tick_anchor: int | None`, reset in `_after_filter`, `_on_sort_changed`, `_apply_search`.
- Card: tick box 20 px top-left (filled `COLORS["good"]` with ✓ when keep, empty otherwise), badge bottom-right of the picture with `display_value` on `band` colour and "⚠ " prefix when `hard_defect`, chip under the badge, stars + ❤ row, file name; current photo 3 px `accent` frame; UI selection light-blue tint (`accent` at 25 % alpha) + 1 px outline; rejected picture at 45 % opacity.

- [ ] **Step 1: Failing GUI tests**: `test_tick_toggles_keep_without_touching_selection` (select rows 0–1, current row 2; click tick of row 4 → row 4 keep, selection and current unchanged); `test_shift_tick_ticks_range` (tick row 1, shift-tick row 4 → rows 1–4 keep); `test_shift_tick_without_anchor_ticks_one` (tick row 1, change filter, shift-tick row 3 → only row 3 changes); `test_badge_shows_ranking_value` (record with Ranked value 74.5 → painted text "75"; use `score_style.display_value` through a delegate helper `card_texts(rec) -> tuple[str, str | None]`).
- [ ] **Steps 2–4** FAIL → implement → PASS (plus `tests/gui` all green).
- [ ] **Step 5: Commit** `"UI part 1: grid cards with tick box, score badge and chip"`

### Task 8: View rotation in grid, preview and loupe

**Files:**
- Modify: `app/ui/asset_model.py` (rotate pixmap by `rec.rotation` when caching), `app/ui/viewer.py` (`ImageViewer.set_rotation(quarter_turns: int)` rotating the pixmap item about its centre; `map_to_view(point: QPointF) -> QPointF` for the eye zoom), `app/ui/main_window.py` (`rotate_view()` action → `view.rotate`, refresh record/viewer; `zoom_to_eyes` maps the face centre through the rotation)
- Test: `tests/gui/test_view_rotation.py`

- [ ] **Step 1: Failing tests**: `test_rotation_changes_display_not_file` (rotate once: thumbnail pixmap width/height swapped, viewer shows rotated, source file SHA-256 unchanged, `view.rotation == 1`, survives session reopen); `test_eye_zoom_follows_rotation` (synthetic face box at top-left; after one rotation the zoom centre lands top-right); `test_export_ignores_rotation` (exported copy bytes == original).
- [ ] **Steps 2–4** FAIL → implement → PASS.
- [ ] **Step 5: Commit** `"UI part 1: view-only rotation"`

### Task 9: Detail panel (preview, buttons, four tabs)

**Files:**
- Create: `app/ui/detail_panel.py` (`DetailPanel(QWidget)`), `app/ui/score_card.py` (`ScoreCard`, `HistogramWidget`)
- Modify: `app/ui/inspector.py` (becomes the Thông tin tab content; EXIF in a `CollapsibleSection` "Thông số EXIF", collapsed by default, not persisted), `app/ui/main_window.py` (replace the inspector scroll area by `DetailPanel`)
- Test: `tests/gui/test_detail_panel.py`

**Interfaces:**
- Consumes: Tasks 1, 5, `explain_html`'s per-criterion reasons (`Score.reasons`).
- Produces: `DetailPanel.show_record(rec: AssetRecord | None, *, taste: TasteStatus, people: str | None, neighbours: list[AssetRecord])`; signals `keep_clicked, reject_clicked, clear_clicked, rating_clicked(int), favorite_clicked, neighbour_clicked(int), open_loupe`; `DetailPanel.open_exif()` (switch to Thông tin tab and expand EXIF); `DetailPanel.set_horizontal(on: bool)` (preview beside tabs via `QBoxLayout.setDirection`); tab names exactly "Phân tích AI", "Thông tin ảnh", "Ảnh tương tự", "Chủ thể". Histogram is computed by a `QRunnable` in the existing pool and cached in an `OrderedDict` LRU of 512 keyed by asset id + rotation-independent; label "theo ảnh xem trước".
- Score card: ring with `display_value`; "Kỹ thuật X · Hợp gu Y" only when `ranked.taste` is not None; suggestion text "Đề xuất giữ" when chip kind is "suggested", "Xem lại" when "review", else none; one bar per criterion in `WEIGHTS` order, unmeasured criteria as "— chưa đo được" text (no bar); Hợp gu row; "Bạn chấm nét" row.
- Chủ thể tab: moves today's grid context-menu person actions into buttons (reuse the existing methods in MainWindow via signals `person_action(str, int)`).

- Task 5 review notes: RV5-01 verify the importer's `capture_time`/`subsec` contract on real imported files (fractional seconds, missing/odd values; timezone only if the importer can store one) and add tests — no change to EXIF storage without a verified cause; RV5-02 the Ảnh tương tự tab header says "Ảnh chụp liền nhau (±3 giây, cùng chủ thể)" — not a pose/visual similarity; RV5-03 histogram off the UI thread with a request token so a late result for a previous photo is dropped (test `test_late_histogram_of_previous_photo_is_ignored`).
- [ ] **Step 1: Failing tests**: `test_ring_equals_grid_badge` (same record → `ScoreCard.value_text == card_texts(rec)[0]`); `test_unmeasured_criterion_is_not_a_zero_bar`; `test_exif_hidden_until_opened` (EXIF section collapsed; `open_exif()` → Thông tin tab current and expanded); `test_neighbour_click_changes_current_photo`; `test_histogram_arrives_off_thread` (panel shows empty frame, then bins after `wait_for_done`).
- [ ] **Steps 2–4** FAIL → implement → PASS; update `tests/gui/test_inspector_scores.py` to the new widgets.
- [ ] **Step 5: Commit** `"UI part 1: detail panel with score card, histogram and tabs"`

### Task 10: Top bar, ⚙ menu and sidebar additions

**Files:**
- Create: `app/ui/top_bar.py` (`TopBar(QWidget)`)
- Modify: `app/ui/main_window.py` (remove the QToolBar; move Làm lại, 🎓 AI đã học, Phím tắt into ⚙; Gộp button in the Chủ thể section header; "📋 Khách chọn…" item at the end of Bộ lọc nhanh; people name filter `QLineEdit`)
- Test: `tests/gui/test_top_bar.py`; update `tests/gui/test_main_window.py`, `test_left_panel.py`

**Interfaces:**
- Consumes: Task 4 `steps`.
- Produces: `TopBar.step_clicked = Signal(str)` (keys of `STEPS`); `TopBar.set_states(states: dict[str, StepState], busy: bool)`; `TopBar.set_compact(on: bool)` (icons only, height 36 vs 48); exposes `search: QLineEdit`, `size_slider: QSlider`, `options_button: QToolButton`. `MainWindow.refresh_steps()` calls `steps(...)` after import/analysis/decision/export; for export it is connected to `ExportDialog.run_recorded` (added in Task 2 review), so ✓ Xuất ảnh appears as soon as a run is recorded. Test: `test_export_step_turns_done_when_run_recorded`. The suggested next step is the first not-done step and gets the accent style; running steps are disabled while busy.

- Task 4 review notes: the Nhập ảnh tooltip says the state is that of the most recent import ("lần nhập gần nhất"); UI regression tests `test_steps_when_every_detection_failed` (quality ✓, people ✓, no ◐ stuck) and `test_steps_after_stage_version_change` (◐ shown, next step = that step).
- [ ] **Step 1: Failing tests**: `test_steps_show_done_partial_and_next` (after import: ✓ Nhập ảnh, next = people); `test_options_menu_has_moved_actions` (menu texts include "↺ Làm lại", "🎓 AI đã học", "⌨ Phím tắt"); `test_people_filter_and_merge_button` (typing "2" shows only "Chủ thể 2…"; Gộp enabled after ticking two).
- [ ] **Steps 2–4** FAIL → implement → PASS (all GUI tests updated for the removed toolbar: use `w.top_bar` / menu actions).
- [ ] **Step 5: Commit** `"UI part 1: workflow top bar and options menu"`

### Task 11: Bottom bar

**Files:**
- Create: `app/ui/bottom_bar.py` (`BottomBar(QWidget)`)
- Modify: `app/ui/main_window.py` (replace the status bar and `_update_counts`; status messages via `BottomBar.message(text)`; progress + pause moved here)
- Test: `tests/gui/test_bottom_bar.py`

**Interfaces:**
- Consumes: Task 3 `counts`.
- Produces: `BottomBar.set_counts(c: Counts, include_pairs: bool, marked: int)`; text "Đã chọn N ảnh (x,y GB)" + " (gồm JPEG kèm)" when include_pairs; "Đang đánh dấu M ảnh" when marked ≥ 2; `set_compact(on: bool)` → "✓N ✗M ·K" and a "⋯" menu holding ★, Xoay xem, Xem EXIF; signals `keep, reject, clear, rating(int), rotate, exif, export, export_client`; `message(text: str)`; `progress(done: int, total: int, pausable: bool)` / `progress_done()`; attribute `status: QLabel` (tests read `w.status.text()` today — keep `MainWindow.status` pointing at it).

- Size refresh (Task 3 review CR3-05): the bar recomputes `counts` when a decision changes, when a session opens, after import/analysis, and when `export/include_pairs` changes (`ExportDialog.include_pairs.toggled` → `MainWindow.refresh_counts`); repeated triggers within 100 ms are coalesced (counts take ~23 ms at 10,000 photos). Test: `test_size_follows_include_pairs_toggle`.
- RV3-01 (review): the bar's tooltip explains photos (a pair = 1) vs files vs the estimated size (from import, may differ from the export: deleted files, files already at the destination, a hidden pair member kept on its own before pairing is copied too). Test: `test_size_tooltip_explains_estimate`.
- [ ] **Step 1: Failing tests**: `test_counts_and_size_text` (2 kept RAW+JPEG → "Đã chọn 2 ảnh (… GB) (gồm JPEG kèm)"); `test_marking_text_only_for_two_or_more`; `test_compact_keeps_keep_reject_export_visible`; `test_buttons_act_like_keys` (bottom Chọn on current photo == pressing P).
- [ ] **Steps 2–4** FAIL → implement → PASS.
- [ ] **Step 5: Commit** `"UI part 1: bottom bar with counts, size and actions"`

### Task 12: LayoutController, overlays and state preservation

**Files:**
- Modify: `app/ui/layout_modes.py` (add `LayoutController`), `app/ui/main_window.py` (build the body as: top bar; central container holding sidebar + icon rail + `QSplitter[grid area, detail]`; bottom bar; remove `fit_panels`)
- Create: `app/ui/overlay.py` (`Overlay(QWidget)`: scrim + slide-in host for a widget that keeps its parent)
- Test: `tests/gui/test_layout_modes.py`; screenshots script `scripts/ui_screenshots.py`

**Interfaces:**
- Consumes: Tasks 6, 9, 10, 11.
- Produces: `LayoutController(window, *, sidebar, rail, splitter, grid_area, detail, top_bar, bottom_bar, settings)`; `apply(mode: Mode)`; `mode: Mode`; `toggle_detail()` (Tab: SHORT switches Grid Focus ↔ Detail Focus, setting `short_focus` in {"grid","detail"}; NARROW/TINY show/hide, setting `narrow_detail_visible`); `open_drawer(section: str)` / `close_drawer()`; splitter sizes saved to `splitter/<mode>`. Evaluation on `resizeEvent` of the central widget with a 120 ms single-shot timer, and on `screenChanged` / `devicePixelRatio` change (also asks the model to re-request thumbnails at the new DPR).
- Rules (no reparenting): detail panel shown as a right-side `Overlay` sheet in TINY and in NARROW below 900 px (`detail_docked` False), docked in the splitter otherwise; splitter `setOrientation`; detail `set_horizontal(mode is SHORT)`; sidebar hidden from layout and shown raised over the grid by `Overlay` in TINY/SHORT/NARROW; SHORT Grid Focus = detail hidden + one-line strip (`QLabel` in grid area) visible; Detail Focus = grid as one row (`grid.setFlow(LeftToRight)`, `setWrapping(False)`, fixed height max(72, 25 % of area)) + detail visible.

- [ ] **Step 1: Failing tests** (`w.resize(...)` then `qtbot.wait(150)`): `test_modes_at_reference_sizes` (client sizes via `client_size(window)`: 1920×1000 WIDE, 1536×800 WIDE, 1280×667 MEDIUM, 960×1000 NARROW, 768×800 NARROW, 1920×484 SHORT, 1280×323 SHORT, 2560×683 SHORT, 580×400 TINY); initial panel visibility from `detail_visible_default`, Tab toggles a per-mode user choice that a resize within the same mode never overwrites (`test_resize_keeps_tab_choice`); `test_state_survives_a_full_mode_cycle` (set current row 5, mark rows 2–3, filter Keep, sort score, search "DSC", scroll, loupe zoom 200 %, detail tab "Thông tin ảnh" with EXIF open, a fake running job progress; cycle WIDE→NARROW→SHORT→TINY→WIDE; all equal after); `test_widget_parents_never_change`; `test_short_tab_switches_focus` and `test_narrow_tab_hides_detail_and_grid_keeps_two_columns`; `test_drawer_closes_on_escape_and_returns_focus`; `test_detail_sheet_in_tiny_and_narrow_below_900`; `test_dpr_change_reevaluates_mode` (emit `screenChanged` with a fake screen of DPR 2: mode recomputed, thumbnail requests made at 2× cell size); `test_minimum_window_size` (`minimumSize() == QSize(560, 300)`).
- [ ] **Steps 2–4** FAIL → implement → PASS; whole suite green.
- Task 6 review notes: RV6-03 test `test_3840x1024_wide_shows_grid_and_detail` (WIDE, grid ≥ 4 columns, detail column visible with preview and tabs not clipped); RV6-05 keep `test_resize_keeps_tab_choice`.
- Task 10 review note RV10-02: `test_top_bar_while_a_job_runs` (during import / analysis the step buttons mirror their QActions, no second job can start); use or remove the unused `busy` argument of `TopBar.set_states`.
- Task 9 review UX notes: detail tab titles must fit without scroll arrows in every mode where the panel is docked (shorter titles or icon+tooltip below 280 px; test `test_detail_tabs_fit`); the preview and buttons never cover the tab area (preview height capped by the panel height); burst rows have one fixed height with a placeholder icon until the thumbnail arrives; the current tab survives refreshes and mode changes (`test_detail_tab_kept_on_refresh_and_mode_change`).
- Task 11 review (approval notes, Task 12 focus): Windows Snap horizontal/vertical sizes behave as the approved modes; nothing lost on resize (current photo, marking, Chọn/Loại, filter, sort, search, scroll, detail tab, Grid/Detail Focus choice); detail panel never clipped and tabs never scroll in supported modes; top/bottom bar compact switch with the mode; reference sizes include 2560×683, 2560×664, 3840×1024; resize/mode change while workers run must not touch the Gate/shutdown path (`test_mode_change_while_workers_run`).
- [ ] **Step 5:** `scripts/ui_screenshots.py --out <scratchpad>` renders 1920×1000, 960×1000, 1920×484, 1280×323, 580×400, 2560×683, 2560×664, 3840×1024 (RV6-04) and 2560×1387@2 with synthetic photos; send the PNGs to the owner.
- [ ] **Step 6: Commit** `"UI part 1: adaptive layout controller and overlays"`

### Task 13: HD thumbnails, keys and help

**Files:**
- Modify: `app/ui/asset_model.py` (pixmap request size = cell × DPR; when > 400 px make/cache an 800 px thumbnail `thumb_hd` in the preview cache from the embedded preview in the existing thumb pool), `app/ui/main_window.py` (`P` = keep alongside `K`; `Tab` = `LayoutController.toggle_detail` via an application-level shortcut that is ignored while a `QLineEdit`/`QTextEdit` has focus; key-hint lists, F1 text), `README.md` (keys table, new layout paragraph)
- Test: `tests/gui/test_keys_and_thumbs.py`

- Task 7 review notes: RV7-01 the marking tint is painted under the picture (card background only; the photo itself is never tinted) — test `test_marking_tint_never_covers_the_photo` (pixel under the picture unchanged when marked); RV7-02 tests `test_tick_and_shift_tick_with_keep_filter` and `test_shift_tick_follows_sorted_order` (anchor, current photo and marking stay right); RV7-03 filmstrip cards without a chip carry the chip text in their tooltip (`test_filmstrip_tooltip_has_status`).
- Task 8 review notes: RV8-01 `test_fast_rotations_while_loading_keep_the_latest` (several Xoay xem presses while the preview/full image loads: the last rotation wins, no stale callback); RV8-02 `test_user_pan_after_eye_zoom_is_not_overridden` (a pan/zoom by the user while the full image loads clears the pending E point); RV8-03 `test_four_turns_back_to_zero` (UI at 0°, no view_rotation row); RV8-04 document and test what a rotation does to a zoomed loupe (`test_rotation_while_zoomed_keeps_the_same_spot`).
- Task 9 review notes: RV9-01 `test_exif_folds_when_switching_to_another_session_with_the_same_asset_id` (reset the panel's shown id on session close if it fails).
- Task 10 review note RV10-01: `test_size_slider_140_to_340` (visualRect size, number of grid columns, tick-box hit box still on the box, QSettings `grid_cell` saved and restored, thumbnails drawn after dragging).
- CR12-03 (review): thumbnail decodes carry a generation/token; a decode started for an older device pixel ratio (or before a cache clear) must never overwrite the newer cache entry. Test with callbacks delivered out of order (old-DPR result after new-DPR result).
- Task 12 review note: the SHORT Detail Focus row and the drawer/sheet must keep working with the Tab key binding (key path = `LayoutController.toggle_detail`, Escape = `close_floating`).
- [ ] **Step 1: Failing tests**: `test_p_keeps_like_k`; `test_keys_in_search_box_do_not_cull` (focus search, type "pX1\t" → text "pX1", no decision changed, layout unchanged); `test_hd_thumbnail_for_large_cells` (cell 300 at DPR 2 → cached pixmap long side ≥ 600 after `wait_for_thumbnails`; source untouched).
- [ ] **Steps 2–4** FAIL → implement → PASS.
- [ ] **Step 5: Commit** `"UI part 1: HD thumbnails, P and Tab keys, help"`

### Task 14: Grid performance at 1,000 / 5,000 / 10,000 photos

**Files:**
- Create: `tests/perf/test_grid_perf.py` (marker `perf`, registered in `pyproject.toml`/`pytest.ini`), `tests/perf/synthetic_session.py` (builds a session with N assets, one shared 400 px thumbnail file per 50 photos, measurements/occurrences for half, decisions for 10 %)
- Modify (only if a target is missed): `app/ui/asset_model.py` — build records in a `QRunnable`, swap in with `beginResetModel/endResetModel` on the Qt thread
- Modify: `.github/workflows/build-windows.yml` (run `pytest -m perf` non-blocking after the build, print a `::notice` with the numbers), `docs/IMPLEMENTATION_STATUS.md` (results table with machine)

**Interfaces:**
- Targets from the spec: open → first paint ≤ 0.5 / 1.5 / 3 s; filter/sort ≤ 0.2 / 0.6 / 1.2 s; scroll paint median ≤ 16 ms, worst ≤ 50 ms; tick/P/X repaint ≤ 50 ms; mode change ≤ 100 / 100 / 150 ms; pixmap cache ≤ 300 MB at DPR 2.

- RV5-03 (review): also run the histogram and burst perf tests on Windows.
- RV7-04 (review) — DONE early in Task 8 (the flake made full runs unreliable); keep it green here: rewrite `test_empty_state_then_import_without_freezing` so it does not depend on how long the import runs (e.g. import enough synthetic files, or assert the event loop processed a queued call while the import thread was alive).
- CR9-03 (review): measure `_show_inspector` (detail refresh incl. burst lookup) after Chọn/sao/♥ on a 10,000-photo session; target ≤ 30 ms median.
- RV9-02 (review): time closing/switching a session while the thread pool still runs a learning job (histogram.wait + taste/focus jobs); target ≤ 1 s added.
- RV10-03 (review): the sustained P/X measure includes `_show_inspector`, `_update_counts`/bottom-bar counts, `refresh_steps` and the repaint — end-to-end per key press, not SQL alone.
- RV3-03 (review): add a sustained-culling measure: 200 alternating P/X presses on a 10,000-photo session, worst and median time from key to repainted card and updated counts (target ≤ 50 ms median, ≤ 100 ms worst); run in CI on Windows and report.
- Task 11 review (V2/V3): measure GC pauses (the GUI-thread timer's `gc.collect` duration, worst and median) and process memory after a long session (e.g. 2,000 P/X + browsing on 10,000 photos), with `app.ui.gc_guard` on.
- Task 11 review: run `-m stress` (`tests/gui/test_worker_lifecycle.py`, `tests/gui/test_shutdown_timeout.py`) on Windows / Python 3.12 in CI; close and switch session while analysis, thumbnails and histograms run (real models where available). A run without a crash is not proof that the crash is gone; report it as "not reproduced in N runs".
- RV11-V4-01 (review): verify queued callbacks / `MetaCall` counting in `shutdown.settle` on Windows / Python 3.12 (CI run of `tests/gui/test_shutdown_*.py`).
- RV11-V4-02 (review): measure settle time and window responsiveness on close and folder switch; `settle(msecs)` must be ONE deadline for all rounds, not `msecs` per round (fixed early in Task 12, keep the test green).
- RV11-V4-03 (review): stress with real RAW files, the AI/GPU workload, a large export and the GC guard (close/switch during each).
- [ ] **Step 1: Write the perf tests** parametrised over (1000, 5000, 10000), each measuring with `time.perf_counter` and asserting the targets; print the numbers.
- [ ] **Step 2:** run `.venv/bin/python -m pytest -m perf -q -s` here; record numbers. If any target fails, implement the off-thread reload and rerun.
- [ ] **Step 3:** default test run excludes `perf` (`addopts = -m "not perf"`); CI step added.
- [ ] **Step 4: Commit** `"UI part 1: grid performance tests and results"`

### Task 15: Finish

- [ ] RV9-03: integration test on a real session DB: the panel's people action changes only the current photo's occurrences/subject rows; marked photos' rows are byte-identical before/after.
- [ ] RV2-04: integration test with a real RAW+JPEG pair (public NEF fixture + its JPEG) through import → grid → Chọn → size == export plan → export copies both.
- [ ] RV2-05: open a v6 session copy with this build (migrates to v7, data intact) and confirm 2.2.1 refuses v7 with its "update the app" message; write it in the beta release notes.
- [ ] Task 11 review: on the owner's Windows PC, close KiraPick during an analysis and during a large import; it must close within a few seconds or show the "Đang đợi … dừng hẳn" status, never crash.
- [ ] Full suite `.venv/bin/python -m pytest -q` green; perf numbers in `docs/IMPLEMENTATION_STATUS.md` with status "tested offscreen" (no real Windows GUI run here); screenshots sent; push to `beta` with no release marker; report to the owner in Vietnamese and start the part 2 discussion.
