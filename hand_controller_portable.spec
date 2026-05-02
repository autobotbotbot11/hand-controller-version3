# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, copy_metadata


repo_root = Path(SPECPATH).resolve()

datas = [
    (str(repo_root / "artifacts"), "artifacts"),
    (str(repo_root / "assets"), "assets"),
]

for filename in ("tuning.testing.json", "tuning.recommended.json"):
    candidate = repo_root / filename
    if candidate.exists():
        datas.append((str(candidate), "."))

datas += collect_data_files("mediapipe")
datas += copy_metadata("mediapipe")
datas += copy_metadata("scikit-learn")

hiddenimports = [
    "mediapipe",
    "joblib",
    "sklearn",
    "pyautogui",
    "sklearn.neural_network",
    "sklearn.neural_network._multilayer_perceptron",
    "sklearn.neural_network._stochastic_optimizers",
    "sklearn.preprocessing",
    "sklearn.preprocessing._data",
    "sklearn.preprocessing._label",
]


a = Analysis(
    [str(repo_root / "portable_entry.py")],
    pathex=[str(repo_root)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[str(repo_root / "pyi_rth_mediapipe_first.py")],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="HandController",
    icon=str(repo_root / "assets" / "logo.ico"),
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="HandController",
)
