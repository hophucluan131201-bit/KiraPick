# Grouping diagnostic (F3 Batch 0)

A read-only, offline report of how the automatic subject grouping compares with the owner's labels.
It does not change grouping, thresholds or any session. The code is in `app/diagnostics/grouping.py`,
and the tests are in `tests/unit/test_diagnose_grouping.py`.

```powershell
KiraPick.exe --diagnose-grouping "D:\Test\SoSanh-CUDA" D:\Test\grouping-report.json [D:\Test\labels.csv]
```

- **Close KiraPick first.** The session database and the learning data are snapshotted through SQLite's backup API
  on a read-only connection. The snapshot includes committed changes still in the write-ahead log, never another
  connection's uncommitted changes, and never checkpoints or writes the source. Everything is computed on copies of
  that snapshot.
  - The data files (`.db`, `-wal`) are hashed before and after the run, and the report states whether they are
    unchanged. If KiraPick changed them during the run, the report says so.
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
