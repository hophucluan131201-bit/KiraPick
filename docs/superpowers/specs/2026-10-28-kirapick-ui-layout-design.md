# KiraPick UI redesign, part 1: adaptive layout — design

Date: 2026-10-28, revision 2 (owner's review: 8 additions, see "Changes in revision 2").
Owner-approved in chat: approach A (one adaptive layout), the owner's demo of three window sizes,
answers to questions 1–4, EXIF hidden by default. Part 2 (Compare 2–4 photos) stays a separate
spec and is built after this part. **No release between part 1 and part 2**: one beta after part 2.

## Goal

The app has the features it needs; the problem is how information is organised. The user should look,
compare and pick quickly instead of reading. Photos come first; details appear on demand. One window
has to work on the owner's laptop (1080p, full screen or split in half either way) and on external
monitors up to 4K.

## Non-goals (this part)

- Compare mode (part 2), "Đánh giá AI" filter section, pose-similarity grouping (part 3), user-defined
  shortcuts (part 4).
- No change to any AI formula: scoring rubric, weights, ranking blend, hard-defect cap, taste and focus
  learning stay exactly as they are. This part only changes how their results are displayed.
- No change to export, learning data or existing sessions beyond the additive migration below.
- Nothing that edits, moves or renames source photos (invariant): no "Di chuyển"; "Xoay" is view-only.
- No scores the app does not measure (no "màu sắc", "biểu cảm", "góc chụp"); no account icon.

## Terms: three different things

The redesign keeps these strictly apart in code, wording and tests.

| Term | Meaning | Stored | Changed by |
|---|---|---|---|
| **Current photo** | the one photo shown in the detail panel / loupe | no (restored per session from settings) | click on a picture, ← →, Ảnh tương tự |
| **UI selection** | photos marked for a batch action | no, transient | Ctrl/Shift+click on the picture, Ctrl+A, Esc clears |
| **Culling state** | Chọn (keep) / Loại (reject) / none, plus stars, ❤, Q/W/R | yes, `decisions` | tick box, P/K, X, U, stars, buttons |

Rules:
- The **tick box shows and changes the culling state only**. Clicking it never changes the current
  photo or the UI selection. Shift+click on a tick box sets Chọn on every card between the last tick
  box clicked (anchor) and this one, in the current sort order; the anchor resets when the filter or
  sort changes.
- Keys and bottom-bar buttons act on the UI selection when it has 2+ photos, otherwise on the current
  photo (today's `_targets` rule).
- The UI selection is drawn as a light-blue tint with a thin outline; the current photo as a thick blue
  frame; Chọn as a filled green tick box. Three different visuals, never a shared one.
- Wording: culling state uses **Chọn / Loại / Bỏ chọn**; the UI selection is called **"đánh dấu"**
  ("Đang đánh dấu 12 ảnh — phím tắt áp dụng cho cả 12", shown in the bottom bar only while 2+ are marked).
  *To confirm (D1).*

## Layout modes

### Measuring
The mode is chosen from the size of the window's **content area** (the central widget: window minus
title bar, top bar and bottom bar), in logical pixels (after Windows scaling, so the same thresholds
work at 100–200 % and on 4K), re-evaluated on resize and on moving to a screen with another scale.
A change needs the size to pass the threshold by **40 px** (hysteresis) and is applied after the
resize settles (**120 ms** debounce) so dragging a window edge never flickers.

### Modes (first rule that matches wins)

| Mode | Content area | Grid | Sidebar | Detail panel |
|---|---|---|---|---|
| `TINY` | width < 720 or height < 420 | full area | icon rail hidden; ☰ opens overlay drawer | overlay sheet over the grid (Tab), closed by default |
| `SHORT` (horizontal split) | height < 640 | see Grid Focus / Detail Focus | icon rail + overlay drawer | below the grid, horizontal, only in Detail Focus |
| `NARROW` (vertical split) | width < 1100 | priority, ≥ 2 columns | icon rail + overlay drawer | docked ~280 px column if width ≥ 900, else overlay sheet; hidden/shown with Tab |
| `MEDIUM` | width < 1440 | | sidebar ~210 px | ~300 px column, smaller preview |
| `WIDE` | otherwise | | sidebar ~240 px | ~360 px column (up to 420 when width ≥ 2200), large preview |

Minimum window size: 560 × 380 logical px (below that Windows stops shrinking it).

**SHORT — Grid Focus (default) and Detail Focus.** Grid and details are not forced on screen together.
- *Grid Focus*: the grid fills the content area (as many rows as fit); a one-line strip under it shows
  the current photo's name, score badge, status chip and stars.
- *Detail Focus*: the grid becomes one filmstrip row (thumbnail height ~ 25 % of the area, min 72 px);
  below it the preview on the left and the tabs on the right.
- Tab switches between the two; the choice is remembered (setting `short_focus`). Enter / Space still open
  the loupe as everywhere else.

**NARROW.** The grid keeps priority: the detail column is never wider than 40 % of the area and closes
before the grid would drop under 2 columns. Tab shows/hides it (setting `narrow_detail_visible`,
default visible when width ≥ 900).

**Overlay drawer (TINY, SHORT, NARROW).** The full sidebar slides over the grid from the left with a dark
scrim; it opens from the icon rail (Bộ lọc, Chủ thể, Thư mục, ⚙) at the chosen section. Esc, a click
on the scrim or choosing a filter/person closes it; keyboard focus returns to the grid.

**Overlay sheet (detail panel in TINY / narrow NARROW).** Same mechanism from the right; Tab / Esc close it.

### Keeping the working state across modes
A mode change is a presentation change only. It must keep: current photo, UI selection, filter, sort,
search text, scroll position (current photo kept visible), loupe zoom and pan, open detail tab, EXIF
section open/closed, running/paused job and its progress, and any open dialog. Splitter sizes are
remembered per mode (settings `splitter/<mode>`). The drawer and overlay sheet close on a mode change.

**Technical approach (safest Qt option, no reparenting).** Every widget is created once and keeps its
parent for the window's lifetime:
- grid area and detail panel live in one `QSplitter`; SHORT uses `setOrientation(Vertical)`, other modes
  `Horizontal`; hiding the detail panel uses `setVisible(False)` / splitter sizes, never removal;
- the detail panel switches its inner arrangement (preview above tabs ↔ beside tabs) with
  `QBoxLayout.setDirection`;
- the sidebar stays a child of the central container; in drawer modes it is taken out of the layout's
  space (zero-width splitter slot) and shown as a raised child with geometry set over the grid,
  plus a scrim widget — same parent, so no state or model connection is lost;
- the grid's model and selection model are shared and never recreated.
A GUI test asserts that `parent()` of every major widget is unchanged after cycling through all modes.

## Regions

### Top bar
- Workflow steps: **Nhập ảnh → Nhận diện chủ thể → Phân tích AI → Chọn ảnh → Xuất ảnh**; each runs
  today's action. Step state (see "Workflow step states") shows as ✓ done, ◐ partly done with a count, or
  plain; the first step that is not done is highlighted as the suggested next step. Steps are never locked.
- Right side: search (Ctrl+F), thumbnail-size slider, ⚙ menu.
- ⚙ gains: Làm lại, 🎓 AI đã học, Phím tắt (F1, key-hint strip on/off), plus today's options.
- In NARROW, SHORT and TINY the steps show icons only (names in tooltips) and the bar is 36 px high
  (48 px otherwise).

### Left sidebar (content unchanged)
Thư mục, Bộ lọc nhanh, Chủ thể, collapsible as today; plus a name search box in Chủ thể, a **🔗 Gộp**
button in its header (enabled with ≥ 2 people ticked) and **📋 Khách chọn** in Bộ lọc nhanh.

### Centre: grid
- Header: filter name and count, **Lưới / Xem lớn** switch, sort box, "đang xem a–b / N" (continuous
  scrolling; no pages). In SHORT/TINY the header folds into the top of the grid as one 28 px line.
- Card: tick box (top-left), score badge (bottom-right of the picture), one status chip, stars, ❤, file name.
  Card sizes follow the slider; in TINY the stars/❤ row hides below 140 px card width.

### Right: detail panel
- Preview (click → Xem lớn), stars, ❤, **Chọn (P/K) · Loại (X) · Bỏ chọn (U)**.
- Tabs:
  - **Phân tích AI**: score ring; "Kỹ thuật 88 · Hợp gu 95" under it when taste is ready; suggestion
    (Đề xuất giữ / Xem lại / —) and one summary sentence; histogram; one bar per criterion (Nét, Mắt, Mặt,
    Sáng, Bố cục, Thẩm mỹ) with its existing one-line reason; Hợp gu row; "Bạn chấm nét" (Q/W/R).
  - **Thông tin ảnh**: file name, capture time, camera + lens, RAW+JPEG pair, folder. Full EXIF is
    **hidden** behind "▸ Thông số EXIF" and opens only on click; "Xem EXIF" (bottom bar) opens this tab
    with that section expanded.
  - **Ảnh tương tự**: the burst: photos of the same subject (or, before people are recognised, any photo)
    taken ≤ 3 s before or after this one, with thumbnail, score and chip; click makes it the current photo.
  - **Chủ thể**: people in the photo, assignment state (chắc chắn / cần xem), today's context-menu actions.

### Bottom bar
- Left: "Đã chọn N ảnh (x GB)", Đã loại, Chưa chọn; "Đang đánh dấu M ảnh" while M ≥ 2; AI progress and
  pause while a job runs (status messages replace today's status bar).
- Actions: Chọn · Loại · Bỏ chọn · ★1–5 · **Xoay xem** · Xem EXIF · **Xuất bản sao** ▾ (Xuất theo danh sách khách…).
- NARROW/TINY: counts shorten to "✓150 ✗42 ·862"; less used actions go into a "⋯" menu; Chọn/Loại and
  Xuất bản sao always stay visible.

## Scores and warning colours (display only)

One display module (`app/ui/score_style.py`) is the only place that turns numbers into text and colour.
Formulas are untouched; it reads today's `Score` and `Ranked`.

- **Number shown** on the badge and in the ring: `Ranked.value` (K blended with G by the ⚙ weight when
  taste is ready, K alone otherwise), rounded half-up to an integer, the same function for both places.
  A photo without a score shows "—" (grey), never 0.
- **Bands** (from the existing `GOOD = 75`, `POOR = 45` in `app/quality/score.py`): ≥ 75 good, 45–74 fair,
  < 45 poor. Criterion bars use the same bands on their part score.
- **Colour tokens** (dark theme, contrast ≥ 4.5:1 on the card background for text):
  good `#3FB950`, fair `#D29922`, poor `#F85149`, neutral/unmeasured `#8B949E`, accent (current
  photo, AI suggestion outline) `#2F81F7`, suggestion chip `#E3B341`.
- **Hard defect** (the existing cap condition in `app/quality/rank.py`: eyes part ≤ 15 or focus part < 30,
  not lifted by the artistic exception): badge gets a ⚠ glyph next to the number, whatever its band; the chip is "Xem lại".
- **Status chips**: ✅ Chọn (good green), ❌ Loại (poor red), ⭐ Đề xuất (suggestion yellow), ⚠ Xem lại
  (fair amber). Every chip has an icon and a word, so meaning never depends on colour alone.
- Chip rule, first that applies: user Chọn · user Loại · in the newest "⭐ Chọn ảnh" run and undecided ·
  undecided with a measured hard problem (focus/shake warning, eyes closed, face burnt out, head cut) or
  an uncertain person assignment · none. The AI never rejects.

## Precise behaviour

### RAW+JPEG pairs
The grid already shows a pair once, through its RAW; decisions are stored on the RAW and the export
copies the JPEG too when "Kèm file JPEG của cặp RAW+JPEG" is on (default on).
- Counts (Đã chọn / Đã loại / Chưa chọn) count **photos** (a pair = 1).
- "x GB" is the size of the files the next export would copy: RAW + its JPEG when the export dialog's
  "Kèm JPEG" option (remembered in settings) is on, RAW only when off; the label says
  "(gồm JPEG kèm)" in the first case. Sizes come from `assets.size` (no disk access). *To confirm (D2).*
- A JPEG whose RAW is missing (pair broken) is an ordinary photo.

### View rotation ("Xoay xem")
- Rotates the displayed image 90° clockwise per press; button only in this part (no key, see D6).
- Applied **on top of** the EXIF orientation that previews already respect; stored per photo in a new
  project table `view_rotation(asset_id INTEGER PRIMARY KEY REFERENCES assets(id) ON DELETE CASCADE,
  quarter_turns INTEGER NOT NULL CHECK (quarter_turns IN (1, 2, 3)))` (no row = 0), migration 7.
- Used by grid, detail preview, loupe, Ảnh tương tự. **Not** used by the AI (detection, scores and face
  boxes keep the photo's own orientation; the eye-zoom maps the face box through the rotation) and **not**
  by export: copies stay byte-identical to the originals.

### Histogram
- Computed from the **preview image the app displays** (the embedded camera JPEG of a RAW, or the JPEG
  itself), not from RAW sensor data — the panel says "theo ảnh xem trước". 8-bit, luminance
  Y = 0.2126 R + 0.7152 G + 0.0722 B, 64 bins, drawn as a filled curve; plus the share of pixels at
  0–2 (shadows clipped) and 253–255 (highlights clipped), shown as small red end marks when ≥ 1 %.
- Computed in the existing thread pool from a ≤ 1024 px downscale, cached in memory (LRU, 512 photos),
  never stored; the panel shows an empty frame until it arrives. Rotation does not change it.

### Workflow step states
Read with one query when the session opens and after each job/decision/export; failed photos count as
processed (they are listed in the step's tooltip). `ok` = imported photos with status ok.

| Step | ✓ done when | ◐ partly done when |
|---|---|---|
| Nhập ảnh | ≥ 1 photo and no import job running or paused | an import is running/paused ("đang nhập 340/1.082") |
| Nhận diện chủ thể | every ok photo has the people stages (`detect`, `embed`) done or failed | some have ("620/1.082") |
| Phân tích AI | every photo with `detect` done has `quality` done or failed | some have |
| Chọn ảnh | ≥ 1 photo is Chọn | an AI pick run exists but nothing is Chọn yet ("có đề xuất") |
| Xuất ảnh | an export finished for this session (new table `export_runs(id, finished_at, photos, files)`, migration 7; destination path not stored) | — |

## Code structure
`app/ui/main_window.py` (1,860 lines) is split so each part has one job:
- `layout_modes.py` — pure `mode_for(width, height, previous)` with hysteresis + `LayoutController`
  (applies a mode with the no-reparenting rules above, remembers splitter sizes).
- `overlay.py` — drawer/sheet + scrim (same-parent raised widgets).
- `top_bar.py` — steps, search, slider, ⚙; `app/storage/workflow.py` — step states (pure query).
- `bottom_bar.py` — counts, size, marking, progress, actions (compact variant).
- `detail_panel.py` + `score_card.py` (ring, bars, histogram widget) + today's `inspector.py` content in the
  Thông tin tab; `app/quality/histogram.py` (pure numpy).
- `grid.py` delegate — card painting, tick-box hit testing, anchor for Shift.
- `score_style.py` — numbers, bands, colours, chip rule (pure, no Qt widgets).
- `app/storage/view.py` — view rotation; `app/storage/exports.py` — export runs; migration 7 for both.
MainWindow keeps orchestration (sessions, jobs, learning) and wires the parts with signals.

## Error handling
Layout and painting never touch the database on the Qt thread beyond today's cheap reads; histogram and
HD thumbnails run in the thread pool. Missing preview → placeholder. Unknown or zero size → `WIDE`
until the first real resize. A failed histogram or HD thumbnail is logged (no file names) and skipped.

## HiDPI
Grid thumbnails are drawn at cell size × device pixel ratio. The 400 px import thumbnail is used up to
that; larger cells get an 800 px thumbnail made in the background from the embedded preview / JPEG and
cached next to today's thumbnails; until it exists the 400 px one is shown scaled.

## Testing

**Unit:** `mode_for` incl. hysteresis and TINY edges; chip rule; number rounding and bands; size sum with
and without paired JPEG; burst neighbours; view rotation and export-run storage; migration 7 on a v6
session; histogram on synthetic images (known clipping shares); workflow step states for each row of the table.

**GUI (offscreen):** content sizes 1920×1080, 1536×864, 960×1080, 1920×540, 700×400 and 3840×2160 at
device pixel ratio 2 — no clipped controls, grid ≥ 1 column (≥ 2 in NARROW), detail panel and drawer as
specified; SHORT Grid Focus ↔ Detail Focus with Tab; NARROW Tab hide/show; drawer open/close returns
focus; state kept across a full mode cycle (current photo, UI selection, filter, sort, search, scroll,
loupe zoom, tab, EXIF open, running job); widget parents unchanged; tick box vs UI selection independence;
Shift range; badge number = ring number; Xem EXIF opens the hidden section; existing GUI tests pass
(updated for moved actions).

**Performance (offscreen, synthetic sessions of 1,000 / 5,000 / 10,000 photos with thumbnails and
scores):** measured and recorded in `docs/IMPLEMENTATION_STATUS.md` with the machine they ran on.
Targets on the CI Windows runner (the owner's laptop should be similar or faster):

| Measure | 1,000 | 5,000 | 10,000 |
|---|---|---|---|
| open session → first grid paint | ≤ 0.5 s | ≤ 1.5 s | ≤ 3 s |
| filter / sort change | ≤ 0.2 s | ≤ 0.6 s | ≤ 1.2 s |
| scroll one screen (paint) | ≤ 16 ms median, ≤ 50 ms worst | same | same |
| tick box / P / X on one photo → repainted | ≤ 50 ms | ≤ 50 ms | ≤ 50 ms |
| layout mode change | ≤ 100 ms | ≤ 100 ms | ≤ 150 ms |
| thumbnail memory | bounded by the pixmap cache (≤ 300 MB at DPR 2) | same | same |

If a target is missed, the model reload moves off the Qt thread (worker builds the records, the model
swaps them in) before part 1 is called done. Perf tests are marked `perf`, run in CI as non-blocking with
their numbers printed as annotations.

**Screenshots** of every mode on synthetic photos go to the owner. A real Windows run is not possible
here; the owner checks the beta on the laptop after part 2.

## Changes in revision 2
1. SHORT: Grid Focus (default) and Detail Focus, switched with Tab; grid and details no longer forced together.
2. NARROW: grid priority (≥ 2 columns, detail ≤ 40 %), detail docked or overlay and hideable, sidebar as overlay drawer.
3. New "Terms" section separating current photo, UI selection and culling state; tick box changes culling only.
4. Breakpoints measured on the content area, with hysteresis + debounce, a TINY mode and a minimum window size.
5. "Scores and warning colours": one display module, fixed bands/tokens, AI formulas unchanged.
6. State-preservation list and a no-reparenting Qt approach with a test.
7. Performance tests and targets for 1,000 / 5,000 / 10,000 photos.
8. Precise rules for RAW+JPEG counts and size, view rotation, histogram and workflow step states.

## Decisions still to confirm
- **D1** Wording: culling = "Chọn / Loại / Bỏ chọn"; batch marking = "đánh dấu". (Avoids two meanings of "chọn".)
- **D2** "x GB" follows the export option "Kèm JPEG" (default on), so it predicts the export size.
- **D3** NARROW shows the detail column by default only when the content width is ≥ 900.
- **D4** TINY limits: < 720 wide or < 420 high; minimum window 560 × 380.
- **D5** "Chọn ảnh" step is ✓ once ≥ 1 photo is Chọn (an AI pick run alone is ◐).
- **D6** Xoay xem has no keyboard key in this part (R is "lệch nét"); the AI and export ignore it.
- **D7** Performance targets above; missing one moves the model reload to a worker thread.
- **D8** `export_runs` stores time and counts only, not the destination folder.
