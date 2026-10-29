# KiraPick UI redesign, part 2: Compare mode — design

Date: 2026-10-29. Owner-approved in chat, one question at a time:
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
  - `arrange(n, width, height, mode) -> (rows, cols)`: a pure function. **Tự động** picks the grid that maximises the
    smallest displayed photo, using the compared photos' own aspect ratios after Xoay xem.
  - `CompareTile(QWidget)`: one part 1 `ImageViewer` plus a header and overlay labels and the active frame. It emits
    `hovered(asset_id)`. Its viewer shares the window's gate; its full-resolution cache holds 1 frame.
  - `CompareView(QWidget)`:
    - holds up to 4 tiles in a `QGridLayout`;
    - methods `show_records(records, active_id)`, `set_arrangement(mode)`, `set_ai_visible(on)`,
      `refresh(asset_id)` (chips after a decision), `active_id`, `stop_pending()`, `wait_idle(ms)`;
    - signals `active_changed(int)` (debounced 150 ms), `back_requested()`.
- `MainWindow` (`app/ui/main_window.py`):
  - centre page 3 = Compare;
  - `show_compare()` / `leave_compare()`, key C, bottom bar button, G and Esc;
  - `_targets()` returns `[active photo]` while Compare is shown;
  - `step()` / auto-advance and ← → / Space / Enter do nothing in Compare;
  - `_show_inspector()` uses the active photo in Compare;
  - `_session_work()` adds every tile's `wait_idle` / `stop_pending`;
  - `_close_session()` leaves Compare first.
- `app/ui/bottom_bar.py`: the ⧉ So sánh button (with a tooltip on C and the 2–4 rule); compact width follows part 1.
- Settings: `compare/arrangement` (auto | row | grid), `compare/show_ai` (bool). No schema change, no new table.

## Memory and speed

- A tile requests full resolution only when it is zoomed to 100 % or more. Each tile caches 1 full frame: 4 tiles
  at 24 MP is about 400 MB, and only when all four are zoomed.
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

1. `arrange()`:
   - 2 / 3 / 4 photos in landscape, portrait and part 1 Snap sizes;
   - each mode.
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

- Same as part 1: an implementation plan in small tasks; after each task, a review package for the external
  reviewer, then wait for approval.
- No tag / publish / release without the owner's release command; the beta is 3.0.0b1.
- The owner tries the installed build afterwards (release-candidate validation, `docs/beta-release-checklist.md`
  section 3) and may change details then.
