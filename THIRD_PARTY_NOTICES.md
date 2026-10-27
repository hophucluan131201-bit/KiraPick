# Third-party notices

Software
- Python 3.12 - PSF License
- Qt 6 / PySide6 6.12 (Essentials) - LGPL-3.0. Qt libraries are shipped as separate,
  replaceable DLLs in this folder; source: https://download.qt.io / https://code.qt.io
- OpenCV 4.14 (opencv-python-headless) - Apache-2.0
- ONNX Runtime 1.24 (DirectML build) - MIT; DirectML.dll - Microsoft DirectML redistributable
  license (redistributed with the app as permitted)
- NumPy - BSD-3-Clause
- Pillow - MIT-CMU (HPND)
- rawpy - MIT; LibRaw - LGPL-2.1 or CDDL-1.0
- ExifRead - BSD-3-Clause
- PyYAML - MIT
- PyInstaller bootloader - GPL-2.0 with the PyInstaller bootloader exception
- Microsoft Visual C++ runtime DLLs (msvcp140*, vcruntime140_1, concrt140, vcomp140) - redistributed
  app-locally under the Microsoft Visual C++ Redistributable license terms

AI model weights (bundled, verified by SHA-256; see docs/model-licenses.md in the source)
- YuNet face detector 2023mar (OpenCV Zoo) - MIT, Shiqi Yu
- SFace face recognition 2021dec (OpenCV Zoo) - Apache-2.0
- YOLOX-S and YOLOX-M (Megvii-BaseDetection/YOLOX 0.1.1rc0) - Apache-2.0
- MediaPipe Face Landmarker v2 (face mesh + blendshapes, Google) - Apache-2.0; converted to ONNX
  (scripts/convert_mediapipe.py)
- TOPIQ image aesthetics (CFANet, ResNet50, AVA) from IQA-PyTorch - PolyForm Noncommercial 1.0.0,
  Copyright (c) 2022 Chaofeng Chen; C. Chen et al., "TOPIQ: A Top-down Approach from Semantics to
  Distortions for Image Quality Assessment", IEEE TIP 2024. Non-commercial use only.
- eDifFIQA(T) face image quality jun2024 (OpenCV Zoo) - CC BY 4.0.
  Attribution: Ž. Babnik, P. Peer, V. Štruc, "eDifFIQA: Towards Efficient Face Image
  Quality Assessment based on Denoising Diffusion Probabilistic Models",
  IEEE Transactions on Biometrics, Behavior, and Identity Science, 2024.
  https://github.com/LSIbabnikz/eDifFIQA

No component downloads anything at run time; the application works with networking disabled.
