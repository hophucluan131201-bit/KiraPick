# PyInstaller spec for the Windows installer (also builds on Linux for checks).
#   pyinstaller --noconfirm --clean packaging/kirapick.spec
# Output: dist/KiraPick/ (one folder). Model weights are NOT bundled here:
# the build script copies the verified files to "dist/KiraPick/models".
# ruff: noqa
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

a = Analysis(
    [str(ROOT / "packaging" / "launcher.py")],
    pathex=[str(ROOT)],
    binaries=msvc_runtime,
    datas=[
        (str(ROOT / "configs" / "model-manifest.json"), "configs"),
        (str(ROOT / "packaging" / "kirapick.png"), "assets"),
    ],
    hiddenimports=["app.selftest"],
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
_UNUSED = ("translations", "opengl32sw.dll")
a.datas = [d for d in a.datas if not any(u in d[0].replace("\\", "/").split("/") for u in _UNUSED)]
a.binaries = [b for b in a.binaries if Path(b[0]).name.lower() not in _UNUSED]

pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="KiraPick",
    console=False,  # a windowed app; --self-test writes its report to a file
    icon=str(icon) if icon.exists() and sys.platform == "win32" else None,
    version=str(ROOT / "packaging" / "version_info.txt") if sys.platform == "win32" else None,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name=APP_NAME)
