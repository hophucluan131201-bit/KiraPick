# KiraPick UI redesign, part 2: Compare mode — design

Date: 2026-10-29, revision 2 (external design review: CR-P2-01 action targets, CR-P2-02 arrangement, CR-P2-03 true
100 % zoom, CR-P2-04 viewer resources). Owner-approved in chat, one question at a time:
- how to start: marked photos only (Q1 = A);
- zoom: each photo on its own (Q2 = C);
- deciding: per photo, photos stay on screen (Q3 = A);
- info: minimal, the AI line on I (Q4 = C);
- arrangement: automatic plus a manual switch (Q5 = C);
- approach: one existing viewer per tile (approach 1);
- the active photo follows the mouse pointer; keys 1–5 keep giving stars.

Builds on part 1 (`2026-10-28-kirapick-ui-layout-design.md`). After part 2 the one beta, **3.0.0b1**, is released, and
only on the owner's release command (`docs/beta-release-checklist.md`).

## Goal

Pick the best of 2–4 near-identical photos (a burst of one pose) faster than stepping through them in the loupe:
the photos side by side, each judged at full resolution, decided with the usual keys.

## Non-goals

- Automatic choice of the photos to compare (burst / "Ảnh tương tự" groups): the user marks them.
- Synchronised zoom or pan across tiles.
- A photo leaving the screen when it is rejected ("survey" mode); a "keep this, reject the others" action.
- More than 4 photos.
- Any change to:
  - AI scoring, ranking or learning;
  - decisions other than the user's own key or button presses;
  - the schema;
  - export;
  - source photos (invariant).
- Undo.

## Terms (part 1 terms unchanged)

| Term | Meaning in Compare |
|---|---|
| Current photo | the grid's current photo; **not changed** while comparing |
| UI selection (marking) | the 2–4 photos being compared; **not changed** while comparing |
| **Active photo** | the tile under the mouse pointer (the last one hovered when the pointer is elsewhere); every action applies to it |
| Culling state | as in part 1; changed only by the user's actions on the active photo |

## What the user sees and does

**Start.** Mark 2–4 photos (Ctrl / Shift + click in the grid or filmstrip), then press **C** or the bottom bar's
**⧉ So sánh** button.
- Fewer than 2 marked: status "Đánh dấu 2–4 ảnh (Ctrl+click) rồi bấm C để so sánh."; nothing else changes.
- More than 4 marked: status "Chỉ so sánh được tối đa 4 ảnh — đang đánh dấu N, hãy bỏ bớt dấu."; never picks 4 by
  itself.

Compare takes the centre area (like the loupe). The top bar, bottom bar, sidebar and detail panel follow the part 1
layout modes.

**Tiles.**
- Order: the photos in the grid's current sort order; number 1–4 in a corner.
- Each tile shows:
  - the photo, fitted to its tile, with Xoay xem applied;
  - file name;
  - Chọn / Loại chip, stars and ❤ (updated at once).
- Pressing **I** shows or hides on every tile:
  - K · G scores;
  - ⚠ hard-defect flags;
  - the main weakness line.

  These come from the same values as the detail panel. A photo without analysis says "chưa phân tích"; nothing is
  estimated. Hidden by default; the choice is kept in the settings.
- Arrangement button with three choices, kept in the settings:
  - **Tự động** (default): the rows × columns that give the largest photo for this tile area;
  - **Một hàng**;
  - **Lưới 2×2**: 2 photos side by side, 3 photos as 2 + 1.

**Active photo.**
- Starts as the grid's current photo if it is compared, else tile 1.
- Becomes the tile under the mouse pointer when the pointer enters it; no click needed.
- Stays the last hovered tile when the pointer leaves all tiles (e.g. to press a detail-panel button).
- Bright frame.
- The detail panel shows the active photo after the pointer has rested 150 ms.

**Keys and buttons.** Every one of these acts on the active photo only, never on all marked photos:
- P / K, X, U;
- 1–5 stars;
- F / ❤;
- Q / W / R;
- Xoay xem;
- the detail panel's buttons.

There is no auto-advance. Photos never leave the screen; a photo that no longer matches the filter stays until
Compare closes (part 1 rule).

**Zoom.** Per tile, independent:
- mouse wheel or + / − on the tile under the pointer;
- drag to pan;
- **Z** toggles fit ↔ 100 % for the active photo;
- **E** zooms the active photo to its eyes (part 1 rule; no face → status message, no zoom).

At 100 % or closer a tile loads the full-resolution image, like the loupe, so judged sharpness is real.

**Inactive keys.** ← → and Space / Enter do nothing in Compare; the key hints say "Esc: về lưới".

**Leave.** Esc, G or the "◀ Về lưới ảnh" button returns to the grid. The current photo, the marking, the scroll
position and the filter are as before. A folder switch or closing the window first leaves Compare and stops its
loads (part 1 shutdown contract).

**Wording.** The taste dialog's "So sánh ảnh…" (🎓) is renamed "🎓 Dạy gu…" so the two cannot be confused. Its
behaviour is unchanged.

## Architecture

- `app/ui/compare_view.py` (new):
  - `arrange(...)`: a pure function, contract and rules in "Arrangement" below.
  - `CompareTile(QWidget)`: one part 1 `ImageViewer` plus a header and overlay labels and the active frame. It emits
    `hovered(asset_id)` from `enterEvent` (immediately). Its viewer shares the window's gate and Compare's decode
    pool; its full-resolution cache holds 1 frame (see "Viewer resources").
  - `CompareView(QWidget)`:
    - holds up to 4 tiles in a `QGridLayout`;
    - methods `show_records(records, active_id)`, `set_arrangement(mode)`, `set_ai_visible(on)`,
      `refresh(asset_id)` (chips after a decision), `active_id`, `stop_pending()`, `wait_idle(ms)`;
    - signals `active_changed(int)` (immediate: the action target), `panel_photo_changed(int)` (debounced 150 ms,
      flushed when the pointer leaves the tiles), `back_requested()`.
- `MainWindow` (`app/ui/main_window.py`):
  - centre page 3 = Compare;
  - `show_compare()` / `leave_compare()`, key C, bottom bar button, G and Esc;
  - `_action_records()` / `view_record()` route every action (see "Action targets");
  - `step()` / auto-advance and ← → / Space / Enter do nothing in Compare;
  - `_session_work()` adds the Compare pool (see "Viewer resources");
  - `_close_session()` leaves Compare first.
- `app/ui/bottom_bar.py`: the ⧉ So sánh button (with a tooltip on C and the 2–4 rule); compact width follows part 1.
- Settings: `compare/arrangement` (auto | row | grid), `compare/show_ai` (bool). No schema change, no new table.

## Action targets (CR-P2-01)

One routing point decides which photo an action changes. Every culling action goes through it; no handler reads the
marking or the current photo on its own while Compare is shown.

- `MainWindow._action_records()` replaces the direct uses in `_targets()`:
  - outside Compare: part 1 behaviour (the marked photos when more than one, else the current photo);
  - in Compare: `[active photo]`, always exactly one record.
- **The active ID changes at once** when the pointer enters a tile (`enterEvent`). Keys pressed right after
  moving the mouse act on the new tile. The 150 ms debounce delays only the detail panel's refresh, never the
  target.
- **Detail-panel buttons and the panel's people menu act on the photo the panel shows.** When the pointer leaves the
  tiles, the pending panel refresh is flushed at once. By the time a panel button can be clicked, panel photo ==
  active photo. A click while they differ (a race inside one event-loop turn) is refused with a status message,
  never applied to another photo.
- `MainWindow.view_record()` gives the photo shown for E / Z / zoom / Xoay xem / the people menu / the inspector:
  the active photo in Compare, the current photo otherwise. `current_record()` keeps meaning the grid's current photo.
- **Audit list.** Each handler is routed through `_action_records()` or `view_record()` and gets a Compare test:
  - keys and window actions:
    - `set_flag` (P, K, X, U);
    - `set_rating` (1–5, 0);
    - `toggle_favorite` (F);
    - `set_focus_label` (Q, W, R);
    - `rotate_view`;
  - detail panel:
    - `detail.keep_clicked`, `reject_clicked`, `clear_clicked`, `rating_clicked`, `favorite_clicked`;
    - `detail.people_menu_requested`;
    - `detail.neighbour_clicked` (in Compare: shows that photo in the panel only, does not change the compared set);
  - bottom bar: the Chọn / Loại / Bỏ chọn buttons, the "⋯" Xoay xem / Bỏ chọn entries, and the size / count refresh
    after a change;
  - view keys:
    - `zoom_to_eyes` (E);
    - `toggle_zoom` (Z);
    - `zoom_step` (+ / −);
  - inactive in Compare (no-ops):
    - `step` / auto-advance / ← →;
    - `toggle_loupe` (Space / Enter);
  - not reachable in Compare (the grid is hidden): tick boxes, `_grid_context_menu`.
  The tests check that the other compared photos' rows (`decisions`, `view_rotation`, `occurrences`) are
  byte-identical before and after each action.

## Arrangement (CR-P2-02)

`arrange(sizes, area, mode, *, gap=6, header=22, min_tile=(120, 90)) -> Arrangement`

- `sizes`: each compared photo's (width, height) **after Xoay xem** (quarter turns swap them), in tile order.
  Unknown sizes count as 3:2.
- `area`: the Compare page's size in logical pixels.
- Result: `rows`, `cols` and each photo's (row, col, row span, col span).

Each tile's photo box is `(area.w − gaps) / cols × (area.h − gaps) / rows − header`. A photo's displayed size is its
aspect fitted into that box.

| Mode | 2 photos | 3 photos | 4 photos |
|---|---|---|---|
| **Một hàng** (row) | 1 × 2 | 1 × 3 | 1 × 4 |
| **Lưới 2×2** (grid) | 1 × 2 | 2 × 2: two on top, the third centred below (spans both columns) | 2 × 2 |
| **Tự động** (auto) | best of 1 × 2, 2 × 1 | best of 1 × 3, 3 × 1, 2 × 2 (2 + 1) | best of 1 × 4, 4 × 1, 2 × 2 |

- "Best": the candidate whose **smallest displayed photo area** is largest. Ties: fewer rows, then the order
  listed.
- Row or Grid where a tile box would be smaller than `min_tile` (e.g. 1 × 4 in a TINY window): Tự động is used for
  this size; the arrangement button shows "Tự động (cửa sổ nhỏ)". The user's choice stays saved and returns when the
  window is large enough.
- SHORT / TINY get no special case: the rules run on the Compare page's own size, which part 1's layout modes
  already decide. Examples tested:
  - SHORT 1920 × 484 with four 3:2 photos → 1 × 4;
  - NARROW 960 × 1000 with two 3:2 photos → 2 × 1;
  - TINY 580 × 400 with four 3:2 photos → 2 × 2.
- Re-arranged on resize (debounced with part 1's 120 ms), on Xoay xem of a compared photo and on a mode change. Each
  tile keeps its zoom level and the photo point at its centre (relative coordinates).

## Zoom: true 100 % (CR-P2-03)

Each tile is a part 1 `ImageViewer` and keeps its contract, now written down and tested for tiles:

- **100 % = one photo pixel per physical screen pixel.**
  - The scale is `zoom / devicePixelRatio / (shown pixmap pixels per full-resolution pixel)`.
  - At 150 % Windows scaling, 100 % therefore draws the photo at 1/1.5 logical pixels per photo pixel.
  - The DPR is read from the tile's own screen; moving the window to another monitor re-applies the zoom.
- **Before the full image arrives** (async load), a zoomed tile shows the preview scaled to the same physical size;
  its header says "đang tải ảnh gốc…". When the full image arrives it replaces the preview without moving the photo
  point at the tile centre.
- **Xoay xem:** the loaded image turns in place; the photo point at the centre stays.
- **E:**
  - uses the face box (file coordinates) turned by Xoay xem;
  - 200 % for small faces, 100 % for close-ups (part 1 rule);
  - the point is kept until the full image is shown, unless the user pans first.
- Wheel zoom keeps the photo point under the pointer. Double-click toggles fit ↔ 100 % at that point. Z toggles fit
  ↔ 100 % at the centre.
- Tests: physical pixel scale at DPR 1 / 1.5 / 2, preview → full swap keeps the centre point, rotation while zoomed,
  E with a turned photo, wheel point fixed.

## Viewer resources (CR-P2-04)

- **Workers:** the four tiles share one decode pool owned by `CompareView`, **2 threads** (the loupe keeps its own,
  as today). `ImageViewer` takes an optional `pool` argument.
- **Full-resolution frames:**
  - each tile caches at most 1 full frame;
  - a Compare-wide budget of **200 megapixels** of full frames (≈ 800 MB at 4 bytes per pixel) — four 45 MP photos
    fit, four 61 MP ones do not;
  - when a new full frame would pass the budget, the least recently active zoomed tile drops its full frame and goes
    back to fit (header: "đã trả về vừa khung để đủ bộ nhớ").
  - Previews (≤ 2560 px) are not counted.
- **Lifetime:**
  - the tiles and the shared pool are created once with the window and **never deleted** while the window lives.
    Closing Compare hides them and calls `show_photo(None)`, so their tokens change and late results are dropped.
  - Workers hold only a path and a signal object owned by the tile, on the GUI thread.
- **Leaving Compare:** `stop_pending()` on the shared pool (queued loads dropped; a running decode finishes and its
  result is ignored by token).
- **Folder switch / close:** `_session_work()` contains a `Work("đọc ảnh để so sánh", pool.waitForDone,
  pool.clear)`. The part 1 contract applies: gate closed → settle → the database closes only after the pool is idle;
  the hung-worker question and `os._exit(3)` path unchanged.
- **Tests:**
  - close and switch with 4 full loads running (slowed decode);
  - a late result after leaving Compare is ignored;
  - the budget drop;
  - the shared pool never has more than 2 threads;
  - stress loop added to the CI stress step.

## Memory and speed

- Memory and workers: see "Viewer resources".
- Tiles show the grid's cached thumbnail at once, then the preview (as the loupe does); all loading is off the Qt
  thread.
- Targets:
  - entering Compare with 4 photos: first paint ≤ 100 ms (thumbnails), previews ≤ 1 s for real NEF files;
  - P/X end-to-end in Compare: median ≤ 50 ms, worst ≤ 100 ms;
  - the active-photo change on hover never blocks the Qt thread by more than 50 ms.

## Errors and edge cases

| Case | Behaviour |
|---|---|
| Unreadable photo | that tile shows the reason (loupe text); its chip, stars and decision still work; other tiles unaffected |
| No face for E | status "Ảnh này chưa có khuôn mặt được nhận diện — …"; no zoom |
| Photo filtered out after a decision | stays in Compare until it closes |
| RAW + JPEG pair | one tile (the pair's shown photo), as in the grid |
| Resize / Snap / mode or DPI change | tiles re-arranged; each tile keeps its zoom and position (relative) |
| TINY window | Compare still works (tiles stacked by Tự động) |
| Folder switch / close while full images load | Compare left first, loads stopped through the gate; no crash, no hang |

## Testing

1. `arrange()`: the table above for 2 / 3 / 4 photos in each mode, mixed portrait / landscape after Xoay xem, the
   min-tile fallback, and the SHORT / NARROW / TINY examples.
2. Start / leave:
   - C with 0, 1, 2, 4, 5 marked;
   - after Esc / G the current photo, marking, scroll and filter are unchanged.
3. Active photo:
   - hover each tile;
   - leaving to the detail panel keeps the last one;
   - the panel follows after 150 ms;
   - the initial active photo is chosen as specified.
4. Keys and buttons on the active photo only:
   - P / X / U / 1–5 / F / Q / W / R / Xoay xem;
   - the other compared photos' database rows are identical before and after;
   - no auto-advance; ← → / Space do nothing.
5. Zoom:
   - independent per tile;
   - ≥ 100 % loads the full resolution;
   - E and Z act on the active tile.
6. I:
   - shows / hides on all tiles;
   - "chưa phân tích" without analysis; no invented numbers.
7. Shutdown: close and folder switch with full images loading (part 1 stress tests extended).
8. Performance:
   - real NEF tiles;
   - P/X in Compare;
   - memory with 4 zoomed tiles;
   - Windows CI read per step notice.
9. Snap sizes 100–200 % on the real Windows platform: no cut-off button in Compare.
10. Screenshots: WIDE, NARROW (half screen), SHORT, TINY.

## Process

- The implementation plan follows the reviewer's 8 tasks:
  1. arrangement and state model;
  2. CompareTile and independent ImageViewer;
  3. CompareView and active hover;
  4. MainWindow integration;
  5. active-photo culling commands;
  6. AI overlay and settings;
  7. worker lifecycle and memory;
  8. regression, performance and Windows CI.
- Same as part 1: after each task, a review package (diff, targeted and full suite, screenshots when visual,
  regression risks) for the external reviewer, then wait for approval.
- No tag / publish / release without the owner's release command; the beta is 3.0.0b1.
- The owner tries the installed build afterwards (release-candidate validation, `docs/beta-release-checklist.md`
  section 3) and may change details then.
