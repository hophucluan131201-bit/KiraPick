# Implementation assignment: Snorlu AI Photo Culling (offline Windows app)

Implement this product in the CURRENT project directory. Read `CLAUDE.md`, `docs/TECHNICAL_SPEC_v1.1.md`, and `configs/rtx2080_maxq_8gb.yaml` FULLY first. They are the source of truth. **This is an engineering/build request, not a request for a speculative essay, mockup, or only a plan.**

## User outcome
A Windows `.exe` app can ingest 500–5,000 RAW/JPEG images from a cosplay/street photoshoot, detect distinct human subjects, assign each photo to zero/multiple subject groups, recognize a person even across shots where face is less visible using multi-cue evidence and uncertain-review, rank photographs separately for EACH subject on sharpness, lighting, color, composition, camera angle, pose/expression and artistry, and recommend a diverse top-N set plus burst alternatives. The user keeps final control. All inference works offline. The machine has 8GB VRAM and 32GB system RAM.

## Nonnegotiable functionalities
1. Native GUI: dark design with library/folder sidebar, subjects panel, thumbnail grid, large preview, ranking panel, score breakdown, filmstrip/next-prev controls, import/progress/cancel, review queue, and export. Support keyboard controls (arrow keys, Keep, Reject, star ratings, compare, zoom 100%).
2. RAW/JPG: safe ingestion, embedded thumbnail extraction, asynchronous caching, full-resolution detail inspection, metadata; dedupe imports; preserve RAW+JPEG association; Windows Unicode paths. Support RAW formats only where actually tested; report unsupported codecs cleanly.
3. Subjects: detect 0..N humans and faces per image; record separate subject occurrence per photo. Compute embeddings using an appropriately licensed model. Use face and body cues, outfit/look session and constrained clustering. DO NOT label actual names without user input. Never silently merge uncertain identities. Multi-person photos are linked to multiple subject collections. Manual merge/split/relabel survives re-analysis.
4. Per-subject quality: technical measurable evidence calculated from SUBJECT region (including eye/face/body focus where available), not only overall frame. Show criterion-level scores and confidence. Separate measurable quality from subjective aesthetics. Style-aware presets cosplay/street/portrait so intended motion blur, dramatic low key and colored stage lights are not incorrectly rejected.
5. Ranking: group bursts and near duplicates; choose best + backup per burst; diversify top-N by pose, angle and scene; explain suggestions based only on measurable signals and model outputs. Never pretend objective artistic truth. User may adjust weights and rerank without recomputing detection/embeddings.
6. Storage: SQLite with migrations, persistent stable IDs, job queue + status, caching, source-file fingerprint, model version/provenance and manual selections. Pause/resume after application restart.
7. Export: keep originals untouched. Copy selected photos by subject (duplicates in output folders allowed, with collision handling), CSV and JSON. Export UI previews before copy. Consider XMP sidecar only after explicit opt-in and validation.
8. Runtime security: offline, no API key, no accidental outbound calls, no optional cloud fallback or background download. User-facing diagnostics when model is missing/unsupported. Package the executable and licensed weights for true disconnected operation, if lawful and feasible; clearly document remaining packaging blockers otherwise.

## Execution roadmap
- **M0 — Feasibility + safety foundation:** inspect Python, torch/ONNX and CUDA compatibility for Turing compute 7.5; document pinned versions and license caveats; implement GPU/CPU capability detection, configuration, error handling, model manifest, and isolated smoke tests. Obtain user approval before installing dependencies that modify system-wide settings or licensing-sensitive model downloads.
- **M1 — Real desktop MVP:** working PySide6 app, import images, image grid, large preview, RAW thumbnail pipeline, zoom, rating/keep/reject, SQLite persistence, import progress, basic copy export, keyboard shortcuts, unit/integration tests. **Finish, run and verify this first.**
- **M2 — Real identity engine:** integrate licensed person/face detectors, face embedding and person re-ID model; build occurrence association and uncertain-review UI, merge/split and confidence tests. Never hardcode fabricated identities or mock score output in production.
- **M3 — Quality analysis:** calculate measurable blur/focus, clipping, exposure and color properties per subject and frame; add more aesthetic features with traceable model outputs; seven configurable scoring categories; human-readable reason strings linked to evidence.
- **M4 — Best Shot:** near-duplicate/burst grouping, within-burst ranking and backup images, top-N diversity, manual overrides, incremental reranking, tests.
- **M5 — Optional local VLM:** only if supported on 8GB VRAM by benchmark; use a compatible quantized local model, model-unload policies, candidate-only analysis and timeout; never require VLM for core culling. Don't treat VLM commentary as measurable fact.
- **M6 — Release:** Windows packaging script/installer, versioned model bundle and licenses, smoke tests with network disabled, README, runbook, profiling, acceptance matrix and truthful completion status.

## Performance guidance
Do not estimate throughput as achieved performance. Measure performance on the actual machine and dataset. One heavy GPU job at a time, target 6GB VRAM app-side initially with adaptive backoff, CPU fallback, limit input resolution where safe, serialize VLM and vision heavy jobs. Qt main UI must not freeze during analysis.

## Implementation instructions
- Start by examining available files, create a minimal project structure and update `docs/IMPLEMENTATION_STATUS.md`.
- Briefly announce plan, **then write actual working code now**, beginning M0 + M1; continue to next milestone if possible within session/context budget.
- After each milestone run automated tests, record exact commands/output in implementation status and fix failures.
- If no real model weights are available, complete functional plumbing/tests and mark AI capability 'not installed' visibly, rather than returning random confidence/scores.
- Do not stop after writing a plan. Do not solicit low-value design choices already decided in the specification. Ask for approval only if a genuinely destructive/system-wide step or a licensing decision is needed.
- Prioritize clean, functional native UI and correct data model over demo illusions; maintain a visible TODO/status report instead of overclaiming.
- When you finish the current session, summarize modified files, executable commands, test results, any constraints and the EXACT next prompt to continue.
