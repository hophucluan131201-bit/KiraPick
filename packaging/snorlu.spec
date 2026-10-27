# PyInstaller spec for the Windows installer (also builds on Linux for checks).
#   pyinstaller --noconfirm --clean packaging/snorlu.spec
# Output: dist/Snorlu AI Culling/ (one folder). Model weights are NOT bundled here:
# the build script copies the verified files to "dist/Snorlu AI Culling/models".
# ruff: noqa
import sys
from pathlib import Path

ROOT = Path(SPECPATH).parent
APP_NAME = "Snorlu AI Culling"
icon = ROOT / "packaging" / "snorlu.ico"

a = Analysis(
    [str(ROOT / "packaging" / "launcher.py")],
    pathex=[str(ROOT)],
    datas=[
        (str(ROOT / "configs" / "model-manifest.json"), "configs"),
    ],
    hiddenimports=["app.selftest"],
    excludes=[
        "tkinter", "pytest", "pytestqt", "IPython", "matplotlib", "scipy", "pandas",
        "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtQml", "PySide6.QtQuick",
        "PySide6.Qt3DCore", "PySide6.QtMultimedia", "PySide6.QtPdf", "PySide6.QtCharts",
        "PySide6.QtDataVisualization", "PySide6.QtNetwork", "PySide6.QtWebSockets", "PySide6.QtBluetooth",
        "PySide6.QtPositioning", "PySide6.QtSql", "PySide6.QtTest",
    ],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Snorlu",
    console=False,  # a windowed app; --self-test writes its report to a file
    icon=str(icon) if icon.exists() and sys.platform == "win32" else None,
    version=str(ROOT / "packaging" / "version_info.txt") if sys.platform == "win32" else None,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name=APP_NAME)
