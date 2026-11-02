# Hoàn tác (Ctrl+Z) và Gộp chủ thể

## Using it

- **Ctrl+Z** or **Chỉnh sửa → Hoàn tác** undoes the newest action. The menu names that action.
- Undoable actions:
  - Chọn/Loại, sao, ❤ and the Q/W/R focus labels;
  - gộp (merge), gán/chuyển (assign/move), bỏ ảnh khỏi chủ thể (remove), tạo chủ thể mới, đặt tên;
  - đánh dấu "khác nhau", including the answers given in "Cần xem lại".
- Actions are undone newest first (one history).
- Ctrl+Z inside a text field (search, names) undoes the typing only. Plain **Z** still zooms.
- **After reopening a folder**, subject corrections can still be undone. Chọn/Loại/sao from before closing cannot,
  because they are kept in memory only so that P/X stays fast. The status bar says so.
- If the data changed since an action, its undo is refused and nothing changes. Examples: the photos were analysed
  again, or another app version edited the assignments.
- **Đánh số lại** (renumbering) clears the subject history; its confirmation says so.
- Bounds: the newest 50 subject corrections (at most 1 MB) and 200 photo decisions.

## Gộp chủ thể (LOOK merge: same person, same costume)

- Tick two or more subjects, then press 🔗 Gộp. The dialog lets you:
  - choose the subject to keep;
  - name the result;
  - see each subject's photos.
- The dialog warns about:
  - photos that show several of the subjects (only the most prominent person stays in each);
  - subjects marked "khác nhau". The merge is blocked unless you tick "Bỏ dấu …".
  - an earlier ⭐ selection, which is then marked "cần chọn lại".
- "Khác nhau" marks against other subjects move to the kept subject.
- Chọn/Loại, sao and ❤ never change, because they belong to the photo.
- Cross-costume association of one person (PERSON layer) is not part of this. It needs session schema v8 and is not
  implemented.

## How it works (app/undo/manager.py)

- **Subject corrections** store the exact changed rows of `occurrences`, `subjects` and `subject_pairs`, before and
  after. They are kept in `project.config_json["undo"]`, written in the same transaction as the correction (schema v7,
  no migration).
- **Undo** restores the "before" rows. It refuses when a row the correction set by hand has changed since, or when a
  deleted subject's id is in use again.
- **Learning examples** of a correction are written after the session commit. They use an operation id reserved
  beforehand in `learning.db`: negative, at most `OP_BASE` = −2⁴⁰, one cue-less reservation row each, which is never
  read as an example.
  - An undo deletes exactly those rows. A cleanup record in the session is retried until `learning.db` confirms it.
  - Ordinary answers keep numbering 1, 2, 3 …
