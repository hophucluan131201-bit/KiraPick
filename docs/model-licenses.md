# Model weights and licenses

> **Since LIC-1 (2026-11-06) the allow-list `configs/model-policy.json` decides which weights are shipped and opened**
> (verified: YOLOX-S/M, YuNet, eDifFIQA, MediaPipe ×2; pending: SFace, CLIP + prompts, LAION, YoutuReID; never:
> ArcFace, TOPIQ ×3). The per-file basis is in `docs/legal/phuong-an-3.0.1.md` (appendix B); what a package carries
> is listed in `THIRD_PARTY_NOTICES.md`. The table below is the development history and still describes the
> weights earlier versions shipped; it is not copied into the installer any more.

Pinned in [`configs/model-manifest.json`](../configs/model-manifest.json) (SHA-256, size, source URL).
Fetched once with `scripts/fetch_models.py` into `models/weights/` (git-ignored). The app verifies
the hash before use and never downloads at runtime.

Intended use (owner's decision, 2026-10-27): personal use and free sharing with friends as open
source. Re-check this table before any commercial distribution.

| Model | Task | License (verified from) | Training data / caveats | Status |
|---|---|---|---|---|
| YuNet 2023mar (`face_detection_yunet_2023mar.onnx`) | face detection | MIT — `opencv_zoo/models/face_detection_yunet/LICENSE` @48b10fa | libfacedetection.train (WIDER FACE). Best for faces ~10–300 px → run at 640 and 1600 px | in use |
| SFace 2021dec (`face_recognition_sface_2021dec.onnx`) | 128-d face embedding | Apache-2.0 — `opencv_zoo/models/face_recognition_sface/LICENSE` @48b10fa | MobileFaceNet trained with SFace loss on public face-recognition datasets; dataset terms not re-reviewed | in use |
| YOLOX-S / YOLOX-M (`yolox_s.onnx`, `yolox_m.onnx`) | person detection (COCO class 0) | Apache-2.0 — `Megvii-BaseDetection/YOLOX/LICENSE`, release 0.1.1rc0 | COCO 2017 (images under Flickr terms, annotations CC BY 4.0) | in use (M on GPU, S on CPU) |
| eDifFIQA(T) jun2024 (`ediffiqa_tiny_jun2024.onnx`) | face image quality (0..1) | **CC BY 4.0** — `opencv_zoo/models/face_image_quality_assessment_ediffiqa/LICENSE` @48b10fa. Attribution required when redistributing: Babnik, Peer, Štruc, “eDifFIQA: Towards Efficient Face Image Quality Assessment based on Denoising Diffusion Probabilistic Models”, IEEE T-BIOM 2024; OpenCV Zoo | MobileFaceNet backbone + quality head (trained on face-recognition data, terms not re-reviewed). Judges faces for *recognition* quality (blur, pose, occlusion), not beauty | in use (optional: without it, “mặt” is N/A) |
| MediaPipe Face Landmarker v2 (`mediapipe_face_landmarks_v2.onnx`, `mediapipe_face_blendshapes_v2.onnx`) | 478 face landmarks; 52 blendshapes (eyeBlinkLeft/Right used) | Apache-2.0 — MediaPipe model card “Face Mesh V2” / “Blendshape V2”, `face_landmarker.task` v1 float16 from storage.googleapis.com/mediapipe-models | Converted to ONNX opset 17 with tf2onnx 1.16.1 (`scripts/convert_mediapipe.py`), outputs match TFLite (4e-4 px / 1e-6). Kept in `models/converted/` (6.8 MB) | in use (eyes open/closed) |
| TOPIQ IAA ResNet50 (`topiq_iaa_res50.onnx`, beta 0.3) | aesthetic hint (1..10, AVA) | **PolyForm Noncommercial 1.0.0** — IQA-PyTorch (Chaofeng Chen); checkpoint `cfanet_iaa_ava_res50-3cd62bb3.pth` from its GitHub release v0.1-weights | Trained on AVA (photo-contest ratings, research dataset); general photography, not cosplay. Converted at build time (`scripts/convert_topiq.py`, 280 MB, not byte-reproducible → `.sha256` sidecar). **Non-commercial weights: approved by the owner on 2026-10-27 for this non-commercial app**; remove before any commercial use | beta only (weight 10/110) |
| ArcFace R50 WebFace600K (`w600k_r50.onnx`, member of InsightFace `buffalo_l.zip` release v0.7, beta 0.3) | 512-d face embedding (grouping people) | **Non-commercial research only** — InsightFace `model_zoo/README.md`: “ALL models are available for non-commercial research purposes only” (code is MIT) | WebFace600K (subset of WebFace260M, research dataset). Pair AUC on the owner's labelled shoot 0.959 from 400 px thumbnails vs 0.945 for SFace at full resolution; clearest gain for photos far apart in time. **Approved by the owner on 2026-10-27 for this non-commercial app, with a disclaimer** (README, installer notes); remove before any commercial use. Without it the app falls back to SFace | beta only (optional, `identity_plus`) |
| YoutuReID 2021nov (`person_reid_youtu_2021nov.onnx`, beta 0.3) | 768-d whole-body embedding (look of a person) | Apache-2.0 — `opencv_zoo/models/person_reid_youtureid/LICENSE` @48b10fa (Tencent Youtu Lab) | Trained on Market-1501, DukeMTMC-reID and MSMT17 (source: ReID-Team/ReID_extra_testdata README). Those datasets are research datasets with their own terms (DukeMTMC was withdrawn by its authors in 2019); the weights' Apache-2.0 licence does not settle the data terms. Street pedestrians, not cosplay: mixed 50/50 with the outfit-colour descriptor, never links photos on its own | beta only (optional, `identity_plus`) |
| OpenAI CLIP ViT-L/14, image tower (`clip_l14_image.onnx`, 2.2) | 768-d image embedding: personal taste, LAION aesthetic, style tags | Code **MIT** (openai/CLIP); weights `ViT-L-14.pt` pinned by the SHA-256 in OpenAI's URL. **Model card: “Any deployed use case of the model – whether commercial or not – is currently out of scope”**, English only, never for face recognition/surveillance | Trained on OpenAI's undisclosed web image–text data. Converted at build time (`scripts/convert_clip.py`; ONNX vs PyTorch cosine 1.000000; fp16 weights 610 MB; preprocessing identical to open_clip on 8 owner NEFs). **Owner accepted the model-card caveat on 2026-10-28 for this non-commercial app, with a disclaimer**; KiraPick uses it only for photo aesthetics/taste, never to identify people | 2.2 (optional, `quality_plus`) |
| LAION improved aesthetic predictor `sac+logos+ava1-l14-linearMSE.pth` (`laion_aesthetic.onnx`, 2.2) | aesthetic score 1..10 from the CLIP embedding | **Apache-2.0** — christophschuhmann/improved-aesthetic-predictor (MD5 b1047fd7…521a, SHA-256 21dd590f…f1e0) | Trained on SAC, LAION-Logos and AVA ratings. On 8 owner NEFs it spanned 4.97–6.02 (mapped 4.8 → 0 .. 6.2 → 100; to be re-checked on a full shoot) | 2.2 (optional) |
| KiraPick style prompts (`clip_prompts_v1.npz`, 2.2) | 22 style concepts (intentional blur, low-key, backlight, close-up…) | derived from OpenAI CLIP (same caveat) | CLIP text embeddings of fixed English prompts with a neutral counterpart each; a tag needs a margin ≥ 0.03 (0.02 tagged sharp owner photos as “motion blur”) | 2.2 (optional) |
| TOPIQ NR ResNet50 KonIQ (`topiq_nr_koniq_res50.onnx`, 2.2) | technical quality 0..1 (noise, blur, compression) | **PolyForm Noncommercial 1.0.0** — IQA-PyTorch; `cfanet_nr_koniq_res50-9a73138b.pth` (SHA-256 9a73138b…354c) | KonIQ-10k (research dataset). 20 % of the focus criterion. Same owner approval as TOPIQ IAA | 2.2 (optional) |
| TOPIQ NR face ResNet50 CGFIQA (`topiq_nr_face_res50.onnx`, 2.2) | face quality 0..1 | **PolyForm Noncommercial 1.0.0** — IQA-PyTorch Hugging Face weights `topiq_nr_cgfiqa_res50-0a8b8e4f.pth` (SHA-256 0a8b8e4f…7898) | CGFIQA-40k (research dataset); trained on aligned 512 px faces, KiraPick feeds an unaligned 1.5× face crop, so it is a hint (half of the face criterion) | 2.2 (optional) |
| MediaPipe Pose 2023mar (`pose_estimation_mediapipe_2023mar.onnx`) | 33 body keypoints | Apache-2.0 — `opencv_zoo/models/pose_estimation_mediapipe/LICENSE` | — | **evaluated, not used**: fed with YOLOX boxes (no MediaPipe person detector) it put shoulders on the face in close-ups and invented legs under dresses on the owner's photos (2026-10-27); pose diversity uses a silhouette layout descriptor instead |
| OSNet (torchreid) | body / outfit re-identification | code MIT | weights trained on Market-1501 / MSMT17 (research-only datasets) | **not fetched**: hosted on HuggingFace/Google Drive, blocked from the dev container; to be exported on the owner's PC |
| DINOv2-small | general visual embedding | Apache-2.0 (model card) | LVD-142M | **not fetched**: dl.fbaipublicfiles.com blocked from the dev container |

**Installer size (2.0.1):** `scripts/shrink_models.py` stores the weights of ArcFace, YoutuReID,
SFace, TOPIQ and YOLOX-M as float16 with a Cast back to float32 (compute stays float32; only weight
values are rounded). It checks every model against the original before replacing it and writes a
`<file>.sha256` sidecar `"<sha256> <size> fp16w-of:<original sha256>"`; the registry accepts a
shrunk file only if it names the pinned original. Weights 751 MB → 402 MB. On the owner's 439
thumbnails: ArcFace cosine mean 0.99983 (min 0.963, one tiny face), ReID ≥ 0.999998, TOPIQ |Δ| ≤ 0.004
on 1–10, YOLOX-M 2 of 1253 boxes differ; grouping precision/recall identical. A modified file in
the licence sense: the weights are the same models in another number format.

Runtime components: ONNX Runtime (MIT), NVIDIA CUDA 13 / cuDNN 9 redistributables via pip
(NVIDIA license; installed into the venv, not system-wide), OpenCV (Apache-2.0), PySide6 (LGPLv3).

## Updates

Models change only with a new KiraPick installer (⚙ Tuỳ chọn → “Cập nhật KiraPick” downloads it from the
GitHub releases, SHA-256 checked); every bundled model is listed above with its licence.

## Media sự kiện — terms check for commercial use (Mốc 0, 2026-11-06)

Media is commercial work (owner, 2026-11-06). It may load only the weights in `configs/media-models.json` with status
`verified` or `approved_with_risk` (`app/media/models.py`; tests in `tests/unit/test_media_models.py`). ArcFace, TOPIQ,
LAION, YoutuReID and eDifFIQA are listed under `never`.

What was checked, from the primary sources (2026-11-06):

| Weight | Code / weights licence | Training data | Finding | Status |
|---|---|---|---|---|
| YOLOX-S / -M (`person_detector_s/m`) | Repo LICENSE: Apache-2.0 (Megvii 2021-2022). The text does not name the released weights. | COCO (the README's training recipe; not stated per weight). COCO annotations CC BY 4.0; images under their own Flickr licences. | No commercial restriction found on code or weights. Residual risk: the weights are not explicitly covered by the licence text, and COCO images carry their own terms. | `pending`: needs an owner decision (MOD-3) |
| YuNet 2023mar (`face_detector`) | opencv_zoo: "All files in this directory are licensed under MIT License". Training repo libfacedetection.train: BSD-3-Clause; no separate weights licence. | **WIDER FACE** (libfacedetection.train README). WIDER FACE's own terms are for non-commercial research. | Weights MIT, but trained on a research-only dataset. Whether dataset terms carry over to weights is legally unsettled. | `pending`: needs MOD-3 |
| SFace 2021dec (`face_embedder`) | opencv_zoo: "All files in this directory are licensed under Apache 2.0 License". | **Not stated** in opencv_zoo; the page refers only to the SFace paper. Face-recognition training sets of that period are typically research-only. | Weights Apache-2.0; training data unverified. | `pending`: needs MOD-3 |
| MediaPipe Face Landmarker v2 + blendshapes (`face_mesh`, `face_blendshapes`) | Google's model cards for Face Mesh V2 and Blendshape V2 state Apache License 2.0. No licence text found for the `.task` bundle itself. | Not checked. | Not needed in the Beta (eyes-open scoring is for auto-pick, UX-2 = later). | `pending` (not blocking) |
| CLIP ViT-L/14 (`clip_l14_image`, `clip_prompts`) | MIT code; OpenAI model card: deployed use out of scope. | OpenAI internal data. | Owner accepted the risk for Media (MOD-1). | `approved_with_risk` |

**Consequence today:**
- `scripts/media_model_report.py --milestone 1` **blocks** the first Media build: YOLOX-S and YuNet are needed from
  milestone 1 and have no fallback.
- Nothing ships until the owner decides MOD-3, or replacements with commercial-clean training data are found.

Sources:
- https://github.com/Megvii-BaseDetection/YOLOX (LICENSE, README)
- https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet
- https://github.com/ShiqiYu/libfacedetection.train
- https://github.com/opencv/opencv_zoo/tree/main/models/face_recognition_sface
- MediaPipe model cards: Face Mesh V2, Blendshape V2 (storage.googleapis.com/mediapipe-assets)
