# PyInstaller spec for the Windows installer (also builds on Linux for checks).
#   pyinstaller --noconfirm --clean packaging/kirapick.spec
# Output: dist/KiraPick/ (one folder). Model weights are NOT bundled here:
# the build script copies the verified files to "dist/KiraPick/models".
# ruff: noqa
import os
import sys
from pathlib import Path

ROOT = Path(SPECPATH).parent
APP_NAME = "KiraPick"
icon = ROOT / "packaging" / "kirapick.ico"

# Microsoft Visual C++ runtime next to the app (app-local deployment, allowed by the VC++
# redistributable terms): ONNX Runtime and OpenCV need msvcp140.dll, which a PC without the
# "VC++ Redistributable" lacks. PySide6 ships these files; put copies in the top folder,
# which the PyInstaller bootloader adds to the DLL search path.
msvc_runtime = []
if sys.platform == "win32":
    import importlib.util

    pyside_dir = Path(importlib.util.find_spec("PySide6").origin).parent
    for pattern in ("msvcp140*.dll", "vcruntime140_1.dll", "concrt140.dll", "vcomp140.dll"):
        msvc_runtime += [(str(f), ".") for f in pyside_dir.glob(pattern)]

# Edition (scripts/build_windows.ps1 -Edition): which ONNX Runtime build's native files to add.
EDITION = os.environ.get("KIRAPICK_EDITION", "directml")
edition_bins = []
if EDITION == "cuda" and sys.platform == "win32":
    # CUDA 12 / cuDNN 9 DLLs from NVIDIA's pip wheels, next to KiraPick.exe (on the DLL search path),
    # so onnxruntime_providers_cuda.dll finds them without a CUDA installation.
    import importlib.util

    nvidia = Path(importlib.util.find_spec("nvidia").submodule_search_locations[0])
    # cuDNN is never bundled (LIC-7 b): the user installs cuDNN 9 (app/ai/runtime.py finds it)
    edition_bins += [(str(f), ".") for f in nvidia.glob("*/bin/*.dll") if not f.name.lower().startswith("cudnn")]

a = Analysis(
    [str(ROOT / "packaging" / "launcher.py")],
    pathex=[str(ROOT)],
    binaries=msvc_runtime + edition_bins,
    datas=[
        (str(ROOT / "configs" / "model-manifest.json"), "configs"),
        (str(ROOT / "configs" / "model-policy.json"), "configs"),  # the allow-list (LIC-1): read at every start
        (str(ROOT / "packaging" / "kirapick.png"), "assets"),
    ],
    hiddenimports=["app.selftest"] + (["openvino", "onnxruntime.tools.add_openvino_win_libs"]
                                      if EDITION == "openvino" else []),
    excludes=[
        "tkinter", "pytest", "onnx", "pytestqt", "IPython", "matplotlib", "scipy", "pandas",
        "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtQml", "PySide6.QtQuick",
        "PySide6.Qt3DCore", "PySide6.QtMultimedia", "PySide6.QtPdf", "PySide6.QtCharts",
        "PySide6.QtDataVisualization", "PySide6.QtNetwork", "PySide6.QtWebSockets", "PySide6.QtBluetooth",
        "PySide6.QtPositioning", "PySide6.QtSql", "PySide6.QtTest",
    ],
    noarchive=False,
)
# Not needed by this widgets-only app: Qt's own translations (the UI text is the app's own; no
# QTranslator is loaded) and the software OpenGL renderer (no OpenGL / Qt Quick is used).
# LIC-1 S8: FFmpeg (opencv_videoio_ffmpeg, LGPL-2.1; the app never reads video) and the TensorRT provider (never
# used) are not shipped. See docs/legal/danh-sach-file-ban-tiep-theo.md.
_UNUSED = ("translations", "opengl32sw.dll", "opencv_videoio_ffmpeg4140_64.dll", "onnxruntime_providers_tensorrt.dll")
a.datas = [d for d in a.datas if not any(u in d[0].replace("\\", "/").split("/") for u in _UNUSED)]
a.binaries = [b for b in a.binaries if Path(b[0]).name.lower() not in _UNUSED]
# NVIDIA DLLs once only: the copies next to KiraPick.exe (edition_bins) are the ones loaded; the same files that
# PyInstaller also collects under nvidia/<pkg>/bin/ are duplicates
_top = {Path(b[0]).name.lower() for b in a.binaries if "/" not in b[0].replace("\\", "/")}
a.binaries = [b for b in a.binaries
              if not (b[0].replace("\\", "/").startswith("nvidia/") and Path(b[0]).name.lower() in _top)]
a.binaries = [b for b in a.binaries if not Path(b[0]).name.lower().startswith("cudnn")]  # LIC-7 b

pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="KiraPick",
    console=os.environ.get("KIRAPICK_CONSOLE") == "1",  # windowed app; a console build only to diagnose a build
    icon=str(icon) if icon.exists() and sys.platform == "win32" else None,
    version=str(ROOT / "packaging" / "version_info.txt") if sys.platform == "win32" else None,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name=APP_NAME)
