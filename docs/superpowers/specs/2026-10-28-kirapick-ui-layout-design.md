# KiraPick UI redesign, part 1: adaptive layout — design

Date: 2026-10-28. Owner-approved in chat (approach A, the owner's demo of three window sizes,
answers to questions 1–4 and the EXIF note). Part 2 (Compare 2–4 photos) is discussed and built
after this part. **No release between part 1 and part 2**: one beta is published after part 2.

## Goal

The app has the features it needs; the problem is how the information is organised. The user should
look, compare and pick quickly instead of reading. The photos come first; details appear on demand.
The same window has to work on the owner's laptop (1080p, full screen or split in half) and on
external monitors up to 4K.

## Non-goals (this part)

- Compare mode (part 2), "Đánh giá AI" filter section, pose-similarity grouping (part 3), user-defined
  shortcuts (part 4).
- No change to scoring, ranking, learning, export, the database of existing sessions (except one new
  table for view rotation) or the AI pipeline.
- Nothing that edits, moves or renames source photos (invariant). "Di chuyển" from the first mockup is
  not built; "Xoay" is a view-only rotation.
- No scores the app does not measure (no "màu sắc", "biểu cảm", "góc chụp"). No account icon (offline app).

## Layout modes

A `LayoutController` picks a mode from the window's size in logical pixels (after Windows scaling;
a 1080p laptop at 125 % full screen is 1536×864) with 40 px hysteresis so it does not flicker while
the user drags the edge. Switching modes moves existing widgets; it never rebuilds them, so the
current photo, selection, scroll position and open tab are kept.

| Mode | Condition (checked in this order) | Left | Right / detail |
|---|---|---|---|
| `SHORT` (horizontal split) | height < 640 | icon rail | below the grid: preview left, tabs right; grid shows one row |
| `NARROW` (vertical split) | width < 1100 | icon rail; a click opens the full sidebar as an overlay drawer | ~280 px column, preview + tabs; **Tab** hides/shows it |
| `MEDIUM` | width < 1400 | sidebar ~210 px | ~300 px, smaller preview |
| `WIDE` | otherwise | sidebar ~240 px | ~360 px (up to 420 on 2K/4K), large preview + tabs |

The user can still drag the splitters inside a mode; the sizes are remembered per mode.
**Tab** toggles the detail panel in every mode (not while typing in a text field).

HiDPI: grid thumbnails are drawn at cell size × device pixel ratio. The 400 px import thumbnail is
enough up to that size; for larger cells (4K, big zoom) a sharper thumbnail (long side 800) is made in
the background from the embedded RAW preview / JPEG and cached; until it exists the 400 px one is shown.

## Regions

### Top bar
- Workflow steps: **Nhập ảnh → Nhận diện chủ thể → Phân tích AI → Chọn ảnh → Xuất ảnh**. Each is a
  button running today's action. A step shows ✓ when done for this session (photos imported; people
  recognised; quality analysed; an AI selection exists; an export was made). The next useful step is
  highlighted.
- Right side: search (Ctrl+F), thumbnail-size slider, ⚙ menu.
- ⚙ menu gains the actions removed from the toolbar: Làm lại, 🎓 AI đã học, Phím tắt (F1 and the small
  key-hint strip on/off), plus today's options (Tự chuyển ảnh, card đồ hoạ, mức gu, Cập nhật KiraPick, tự kiểm tra).
- In `NARROW`/`SHORT` the steps show icons only (text in tooltips), toolbar height shrinks.

### Left sidebar (unchanged content)
Thư mục, Bộ lọc nhanh, Chủ thể, collapsible as today. Additions: a name search box at the top of
Chủ thể; **🔗 Gộp** button in the Chủ thể header (enabled with ≥ 2 ticked); **📋 Khách chọn** entry in
Bộ lọc nhanh. Icon rail (`NARROW`/`SHORT`): Bộ lọc, Chủ thể, Thư mục, ⚙ — each opens the drawer at that section.

### Centre: grid
- Header: filter name and count, **Lưới / Xem lớn** switch, sort box, "đang xem a–b / N" (continuous
  scrolling stays; no pages).
- Card: tick box (top-left), score badge (bottom-right of the picture), one status chip, stars, ❤, file name.
  - **Tick box = Chọn (keep).** Click toggles Chọn ↔ not chosen (same as P/K and U). Shift+click on a
    tick box sets Chọn for every card between the last tick box clicked and this one (in the current order). A rejected photo has an empty
    box and the red chip. Ctrl/Shift+click on the picture keeps selecting several photos for key actions.
  - **Score badge** = the ranking value shown in the detail panel's ring (technical score K, blended
    with the taste score G by the ⚙ weight once taste is ready; K alone before). Colour: green ≥ 75,
    amber 45–75, red ≤ 45 or a hard defect (the existing cap).
  - **Status chip**, one per card, first that applies: ✅ Chọn (user kept) · ❌ Loại (user rejected) ·
    ⭐ Đề xuất (in the newest "⭐ Chọn ảnh" run, no user decision) · ⚠ Xem lại (no user decision and a
    measured hard problem: focus/shake, eyes closed, face burnt out, head cut — or the person
    assignment is uncertain) · none. The AI never rejects on its own.
- The current photo has a thick blue frame.

### Right: detail panel
- Preview (fits the panel; click → Xem lớn), stars, ❤, **Chọn (P/K) · Loại (X) · Bỏ chọn (U)**.
- Tabs:
  - **Phân tích AI**: score ring with the same number as the badge; under it "Kỹ thuật 88 · Hợp gu 95"
    when taste is ready; suggestion label (Đề xuất giữ / Xem lại / —) and one summary sentence; a
    luminance histogram computed from the preview image; one bar per measured criterion (Nét, Mắt,
    Mặt, Sáng, Bố cục, Thẩm mỹ) with its existing one-line reason; Hợp gu cá nhân row (score or
    today's "chưa đủ dữ liệu" reason); "Bạn chấm nét" (Q/W/R). Unmeasured criteria are listed as such,
    never drawn as 0.
  - **Thông tin ảnh**: file name, capture time, camera + lens, RAW+JPEG pair, folder. **EXIF details are
    hidden** behind "▸ Thông số EXIF" and open only when clicked; the bottom bar's "Xem EXIF" opens this
    tab with that section expanded.
  - **Ảnh tương tự**: photos of the same person (same subject, else same main occurrence) taken ≤ 3 s
    apart from this one (the burst), with thumbnail, score and status; click jumps to the photo.
  - **Chủ thể**: who is in the photo, assignment state (chắc chắn / cần xem), and today's context-menu
    actions (đúng là X, bỏ khỏi chủ thể, gán sang chủ thể khác, tạo chủ thể mới).

### Bottom bar
- Left: "Đã chọn N ảnh (x GB)" (sum of original file sizes of kept photos, RAW+JPEG pairs counted
  once per file), Đã loại, Chưa chọn, and the AI progress/pause while a job runs (replaces the status bar;
  status messages appear here).
- Actions: Chọn · Loại · Bỏ chọn · ★1–5 · **Xoay xem** · Xem EXIF · **Xuất bản sao** ▾ (menu: Xuất theo
  danh sách khách…).
- **Xoay xem** rotates the view by 90° and is remembered per photo in a new project table
  `view_rotation(asset_id PRIMARY KEY, quarter_turns)` (migration 7). The grid, preview and loupe apply
  it; the source file and the exported copies are untouched.

## Keys
P = Chọn (added; K stays), X, U, 0–5, F, Q/W/R, E, Z, Space/Enter, Esc, ← →, **Tab** (detail panel),
Ctrl+F/I/E/L, F1. Help (F1, hint strip, README) updated.

## Code structure
`app/ui/main_window.py` (1,860 lines) is split so each part has one job:
- `layout_modes.py` — mode from size (pure function, hysteresis) + `LayoutController` that moves widgets.
- `top_bar.py` — workflow steps + search + slider + ⚙ button; step states come from one query function.
- `bottom_bar.py` — counts, size, progress, action buttons.
- `detail_panel.py` — preview + buttons + four tabs (`score_card.py` for the ring/bars/histogram;
  today's `inspector.py` content moves into the Thông tin tab).
- `grid.py` delegate — new card painting and tick-box hit testing.
- `app/quality/status.py` — pure function photo → status chip (testable without Qt).
- `app/storage/view.py` — view rotation get/set.
MainWindow keeps orchestration (sessions, jobs, learning) and wires the parts with signals.

## Error handling
Layout and drawing never touch the database on the Qt thread beyond today's cheap reads; histogram and
HD thumbnails are computed in the existing thread pool. A missing preview shows a placeholder, not an
error dialog. Unknown sizes fall back to `WIDE`.

## Testing
- Unit: mode selection incl. hysteresis; status chip rules; size sum; burst neighbours; view rotation storage.
- GUI (offscreen): each mode at 1920×1080, 960×1080, 1920×540, 1536×864 and 3840×2160 with device
  pixel ratio 2 — nothing clipped, grid has ≥ 1 column, detail panel present/hidden as specified;
  tick-box click and Shift range; badge equals ring number; Tab toggles; Xem EXIF opens the hidden
  section; existing GUI tests keep passing (updated for moved actions).
- Screenshots of all four modes on synthetic photos are sent to the owner. A real Windows run is not
  possible here; the owner checks the beta on the laptop.
