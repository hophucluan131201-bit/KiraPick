# Model weights and licenses

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
