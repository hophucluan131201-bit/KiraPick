# Grouping diagnostic (F3 Batch 0)

A read-only, offline report of how the automatic subject grouping compares with the owner's labels.
It does not change grouping, thresholds or any session. The code is in `app/diagnostics/grouping.py`,
and the tests are in `tests/unit/test_diagnose_grouping.py`.

```powershell
KiraPick.exe --diagnose-grouping "D:\Test\SoSanh-CUDA" D:\Test\grouping-report.json [D:\Test\labels.csv] [--cooccurrence-list D:\Test\cooccurrence.csv]
```

- **Close KiraPick first.** The diagnostic never opens the session or the learning database with SQLite. A
  read-only SQLite connection can still create `-wal`/`-shm` files and write read marks into an existing `-shm`,
  so the diagnostic avoids it entirely.
  - Before it starts, the run is refused when a `-shm` or `-journal` file exists, meaning KiraPick is open or did not
    close cleanly. Opening and closing KiraPick once clears that.
  - Otherwise the `.db` (and `-wal`) files are copied byte for byte into a private folder. The run is refused if any
    SQLite file of the source changes, appears or disappears between the check before the copy and two checks
    after it (the second after 0.5 s), or if the copy differs from the source.
  - Only the copy is opened. SQLite's recovery of the copy keeps exactly the committed transactions.
  - The source folder is only read, so the diagnostic also works when that folder is read-only. Every SQLite file
    is hashed and the folder listed before and after the run. The report states `unchanged` and `no_new_files`.
  - Photo files are never opened. Network access is blocked for the whole run.
- **Labels.** In a *copy* of a session, rename each subject `K<customer>-<costume>` (`K1-A`, `K1-B`, `K2-A`).
  - Two subjects of the same costume get the same label.
  - `K1` alone means the customer is known but the costume is not.
  - Anything else counts as *uncertain* and is excluded from the accuracy metrics: a composite such as
    `K1-A+K2-A`, a `?`, or a free name. A composite label is never split into identities.
  - An optional `labels.csv` gives labels per occurrence and overrides the subject names. Its columns are
    `occurrence_id` or `photo` (relative path), then `person` and `look`.
  - In `labels.csv`, duplicate rows are counted. Rows that contradict each other make the occurrence uncertain.
    Unknown ids and invalid rows are counted and ignored, and a file without the required columns is refused.
- **`reconstructed_baseline`.** The automatic grouping before the owner's corrections. It is not verified
  historical output. It is rebuilt on the copy by clearing every
  manual assignment, exclusion and "different" mark, then regrouping. This is done twice with the default
  thresholds, as a determinism check, and once with the owner's current learnt tuning when one applies.
  - The app keeps no record of the original automatic result. The report therefore states how well the rebuilt
    grouping agrees with the occurrences the owner never touched, and lists the limits of the rebuild.
- **Report.** Numbers only. It never contains file names, subject names, label texts, vectors or times of day.
  `check_numbers_only` enforces this before the report is written.
  - The message of an unexpected error is not written into the report, only the error type. The traceback goes
    to a separate local file, `report.json.traceback.txt`.
  - For the person level and the look level separately: pairwise precision and recall, B-cubed precision, recall
    and F1, false merges, false splits, and the manual corrections needed (photo moves + merges).
  - Pair evidence between clusters, by category, for hypotheses H1–H5: same person in another costume, same
    costume split, and different persons. For each category: face top-3 mean, median look, minimum time gap,
    interleaving, co-occurrence, and what the review queue would ask.
- **Same-label co-occurrence (P0-A).** The report counts photos where two occurrences carry the same person label.
  These are always two people for the grouping. Each such pair is given a hypothesis class, which is a reporting aid
  only and never used by the app:
  - `duplicate_face_only` — a lone face box inside the other person's box;
  - `duplicate_overlapping_bodies`;
  - `possible_reflection`;
  - `two_people_same_label`;
  - `undetermined`.

  One occurrence that holds both a person box and its face box is normal and never counted.
  - `--cooccurrence-list <file>` (explicit opt-in) writes a LOCAL CSV for the owner with the photo file names,
    subject names, hypothesis, numbers and an empty `owner_verdict` column. It never enters the shareable report,
    and it must be a different file from the report.
- **Learning audit (P0-B).** Run on a snapshot copy of `learning.db`; the original is never written.
  - It reports answers and pairs by kind and answer, and which pairs use the current cue versions.
  - It reports the learnt tuning with a reason code, the 5×5 cost grid that `tune()` searches, the cross-validation
    fold by fold, and the answers whose links change under the learnt thresholds.
  - "Same" answers whose pairs have a median look below the review look level are counted as **possible
    contamination**. This is a hint only, never proof of a costume change.
  - The tuning is re-run without those answers, and the labelled session is rebuilt with that tuning
    (`reconstructed_baseline.filtered_learning`). Both happen on the copies only.
