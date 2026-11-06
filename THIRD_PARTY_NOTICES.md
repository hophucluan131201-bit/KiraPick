# Third-party notices

The full licence texts are in `docs\licenses\` (see `INDEX.txt` there). They are collected at build time by
`scripts/collect_licenses.py`; `scripts/check_package.py` refuses a package without them.

## Software

- Python 3.13 — PSF License (`Python-LICENSE.txt`); Python packages of the build with their licences:
  `python-packages.txt`
- Qt 6 / PySide6 6.12 (Essentials) — LGPL-3.0 (`LGPL-3.0.txt`, which supplements `GPL-3.0.txt`). The Qt libraries
  are separate, replaceable DLLs in this folder; source: https://download.qt.io / https://code.qt.io
- OpenCV 4.14 (opencv-python-headless) — Apache-2.0 (`Apache-2.0.txt`); packaging MIT (`opencv-python-LICENSE.txt`);
  bundled libraries: `opencv-LICENSE-3RD-PARTY.txt`. The video module's FFmpeg library is not shipped (the app
  reads no video).
- ONNX Runtime 1.24 — MIT (`onnxruntime-LICENSE.txt`), notices `onnxruntime-ThirdPartyNotices.txt`
- DirectML edition: DirectML.dll 1.15.4 — Microsoft DirectML licence terms (`DirectML-LICENSE.txt`,
  `DirectML-ThirdPartyNotices.txt`), redistributed in this application as those terms allow
- CUDA edition: ONNX Runtime GPU — MIT; NVIDIA CUDA runtime, cuBLAS, cuFFT, cuRAND, NVRTC and cuDNN DLLs from
  NVIDIA's pip wheels — NVIDIA licence agreements (`NVIDIA-*-License.txt`). The TensorRT provider is not shipped.
- OpenVINO edition: ONNX Runtime OpenVINO Execution Provider and Intel OpenVINO — Apache-2.0
- rawpy — MIT (`rawpy-LICENSE.txt`); LibRaw — LGPL-2.1 or CDDL-1.0 (`LibRaw-LICENSE.txt`, `LGPL-2.1.txt`)
- NumPy — BSD-3-Clause; Pillow — MIT-CMU (HPND); ExifRead — BSD-3-Clause; PyYAML — MIT
- PyInstaller bootloader — GPL-2.0 with the PyInstaller bootloader exception
- Microsoft Visual C++ runtime DLLs (msvcp140*, vcruntime140_1, concrt140, vcomp140) — redistributed app-locally
  under the Microsoft Visual C++ Redistributable licence terms

## AI model weights in this package

Every weight file is pinned by SHA-256 in `configs/model-policy.json`; the app opens no other file.

- YOLOX-S and YOLOX-M person detectors (Megvii-BaseDetection/YOLOX, release 0.1.1rc0) — Apache-2.0
  (`Apache-2.0.txt`), Copyright (c) Megvii Inc. YOLOX-M is stored with float16 weights (changed from the original).
- YuNet face detector 2023mar (OpenCV Zoo) — MIT, Copyright (c) 2020 Shiqi Yu (`MIT-YuNet.txt`); training
  repository libfacedetection.train — BSD-3-Clause (`BSD-3-Clause-libfacedetection.train.txt`)
- eDifFIQA(T) face image quality jun2024 (OpenCV Zoo) — CC BY 4.0 (`CC-BY-4.0.txt`,
  https://creativecommons.org/licenses/by/4.0/). Attribution: Ž. Babnik, P. Peer, V. Štruc, "eDifFIQA: Towards
  Efficient Face Image Quality Assessment based on Denoising Diffusion Probabilistic Models", IEEE Transactions on
  Biometrics, Behavior, and Identity Science, 2024; https://github.com/LSIbabnikz/eDifFIQA. Used unchanged.
- MediaPipe Face Landmarker v2: face mesh and blendshapes (Google) — Apache-2.0 per Google's model cards
  (`Apache-2.0.txt`). Changed from the original: converted from `face_landmarker.task` (SHA-256 64184e22…c9ff) to
  ONNX with `scripts/convert_mediapipe.py`.

No component downloads anything at run time; the application works with networking disabled (the only exception is
the update check the user starts in ⚙ Tuỳ chọn → Cập nhật KiraPick).

## Not shipped

Weights that earlier versions shipped and this one neither ships nor opens (licence terms, or no basis for paid
work yet): InsightFace ArcFace (w600k_r50), TOPIQ aesthetic / technical / face quality, YoutuReID, SFace, OpenAI CLIP
ViT-L/14 with its style prompts, and the LAION aesthetic head. See docs/legal/phuong-an-3.0.1.md in the source.
