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
| OSNet (torchreid) | body / outfit re-identification | code MIT | weights trained on Market-1501 / MSMT17 (research-only datasets) | **not fetched**: hosted on HuggingFace/Google Drive, blocked from the dev container; to be exported on the owner's PC |
| DINOv2-small | general visual embedding | Apache-2.0 (model card) | LVD-142M | **not fetched**: dl.fbaipublicfiles.com blocked from the dev container |

Runtime components: ONNX Runtime (MIT), NVIDIA CUDA 13 / cuDNN 9 redistributables via pip
(NVIDIA license; installed into the venv, not system-wide), OpenCV (Apache-2.0), PySide6 (LGPLv3).
