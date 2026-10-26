# Continuation prompts for Claude Code

Use `claude -c` in the project directory to continue the most recent session, then paste whichever prompt fits.

## Continue where left off
Read CLAUDE.md, BUILD_TASK.md, docs/TECHNICAL_SPEC_v1.1.md and docs/IMPLEMENTATION_STATUS.md. Continue implementing the first unfinished milestone. Do not restate a plan without creating code. First run existing tests, fix failures, implement missing features, run tests again, and update exact milestone statuses. Never invent results.

## Force review / audit
Audit code against every FR requirement in docs/TECHNICAL_SPEC_v1.1.md and the offline/non-destructive invariants. Produce an evidence-based PASS/PARTIAL/FAIL list pointing to source files and tests. Fix the highest-priority issues rather than claiming unsupported completion.

## Verify true offline release
With networking disabled, test app startup, import RAW/JPEG, model availability, person grouping, per-subject scoring, best-shot ranking, manual corrections, pause/resume and copy export. Record CPU/GPU, VRAM peaks and timings using actual hardware results only. Fix failures; record known limitations.

## Final packaging
Build a native Windows distribution with PyInstaller or a suitable Windows packaging tool. Do not assume the model weights are bundled. Create a manifest containing exact weight path, size/hash, license and provenance; stop release if required licensed weights are missing. Verify the built app without Python installed in a clean environment if available.
