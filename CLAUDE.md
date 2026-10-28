# Snorlu AI Culling — standing instructions for Claude Code

You are the project's lead software engineer and implementation agent. Read `docs/TECHNICAL_SPEC_v1.1.md`, `BUILD_TASK.md` and `configs/rtx2080_maxq_8gb.yaml` before editing code. The technical specification is authoritative for product scope; this file adds implementation rules. Communicate progress and setup instructions to the user in Vietnamese; code identifiers and documentation may be in English.

## Product invariants (never compromise)
- Windows 10/11 x64 NATIVE desktop application; Python + PySide6 + SQLite. User PC: Intel i7-10750H; RTX 2080 Super Max-Q 8GB VRAM; RAM 32GB. Prefer ONNX Runtime for lightweight models; PyTorch only where justified. CPU fallback is mandatory.
- **100% offline after installation, except the app update (owner decisions 2026-10-28):** no API calls, telemetry, authentication, silent model downloads, network fallback, cloud inference, or network access to photo data/embeddings. The only exception is `app/updates/` (⚙ Tuỳ chọn → Cập nhật KiraPick): it runs when the user starts it, or once a day if the user switched on the opt-in check (off by default); it reads KiraPick's public GitHub release list and downloads that edition's installer, checked against GitHub's SHA-256 digest, never sends user data, and a test enforces that no other module imports networking code. Development-time internet to acquire dependencies or openly licensed weights is distinct from app runtime; every final artifact must be usable with networking disabled. Include a network-off smoke test.
- **Non-destructive:** never delete, overwrite, rename, move, or alter source images or their EXIF/RAW data. Exports must be copies, have collision-safe names, and require user confirmation. Protect against symlink traversal, invalid paths and unsupported files.
- The user is a cosplay/street photographer. Correct subject grouping matters more than aggressive automation. Support many people in one image, subject occurrence scores (not just image-level scores), identities and outfit/look groups, uncertain matches requiring review, manual merge/split with persistent overrides, artistic intentional blur/lighting exceptions.
- Provide real outputs only. NEVER fake a model inference or invented aesthetic score. If weights or compatible runtime are missing, mark that capability unavailable and provide honest diagnostic guidance. Do not silently substitute fabricated estimates.
- Store stable IDs in SQLite, version and provenance of scores/models, retain a durable job state for pause/resume, permit recomputing rankings without rerunning identity embedding.
- Reuse RAW embedded previews for speed where possible; 100%-zoom sharpness must be calculated using proper full-resolution regions, not only low-res thumbnails. Handle RAW+JPEG pairs.
- Respect model and weight licenses. Inspect real model card/weights before packaging. Do not distribute research-only/non-commercial weights or restrictive components without explicit approval. Create `docs/model-licenses.md` and a model manifest.
- Keep latency and VRAM within realistic limits. One heavy model at a time; start with FP16 where supported (avoid assuming BF16 on Turing), adaptive batches, GPU->CPU fallback, optional VLM disabled until validated.

## Workflow
1. Inspect the project and create a realistic implementation plan in `docs/IMPLEMENTATION_STATUS.md` with milestone checklist M0-M6 and explicit statuses: not started / implemented / tested / blocked.
2. Build code, run tests and fix failures after each milestone. If you cannot run a Windows GUI in your environment, report this explicitly and give exact manual test commands; do not claim GUI test success.
3. Deliver executable work early, not just architecture documents: import folder, persist project, thumbnail grid, large preview, keyboard culling, export workflow, tests and packaging scripts, then real AI integrations.
4. Use type hints, structured error handling, logging without leaking photo metadata, unit/integration tests, migration-safe SQLite schema, dependency lock/version pinning or documented supported range.
5. Add README with Windows setup/run/build instructions, error diagnostics and limitations. Make UI dark, responsive, keyboard-friendly; no blocking the Qt main thread.
6. If you encounter missing proprietary images or unavailable model weights, build and test with synthetic/example fixtures; record the limitation, and do not pretend accuracy was benchmarked.
7. Avoid deleting pre-existing project files or installing questionable software without consent. Do not use `--dangerously-skip-permissions` or request it.

## Definition of done
The project is NOT complete merely because the UI opens. Completion requires real subject detection/grouping integration, honest aesthetic/technical analysis, per-subject ranking with burst diversity, review UX, lossless-originals export, offline runtime, installable Windows build, and validation evidence. If partially complete, clearly separate implemented features, test results and remaining work in `docs/IMPLEMENTATION_STATUS.md`.
