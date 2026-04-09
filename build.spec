# -*- mode: python ; coding: utf-8 -*-
"""
VideoMerger PyInstaller 打包設定（綠色程式版）
執行：pyinstaller build.spec
輸出：dist/VideoMerger/VideoMerger.exe

目錄結構（攜出時壓縮整個 VideoMerger/ 資料夾）：
    VideoMerger/
    ├── VideoMerger.exe
    ├── _internal/          ← PyInstaller 自動產生，包含所有相依套件
    │   ├── assets/
    │   │   ├── ffmpeg.exe
    │   │   └── ffprobe.exe
    │   └── whisper/assets/ ← mel_filters.npz 等語音辨識資源
    └── data/               ← 首次執行後自動建立（歷史紀錄）
"""

import sys
import os
from pathlib import Path

# Python site-packages 路徑
site_packages = Path(sys.executable).parent / "Lib" / "site-packages"
customtkinter_path  = site_packages / "customtkinter"
tkinterdnd2_path    = site_packages / "tkinterdnd2"
whisper_assets_path = site_packages / "whisper" / "assets"

# 確認必要資源存在（打包前檢查）
missing = []
for p, name in [
    (customtkinter_path,  "customtkinter"),
    (tkinterdnd2_path,    "tkinterdnd2"),
    (whisper_assets_path, "whisper/assets"),
    (Path("assets/ffmpeg.exe"),  "assets/ffmpeg.exe"),
    (Path("assets/ffprobe.exe"), "assets/ffprobe.exe"),
]:
    if not p.exists():
        missing.append(f"  ✗ {name}  ({p})")
if missing:
    print("\n[build.spec] 以下資源不存在，請確認後再打包：")
    for m in missing:
        print(m)
    raise SystemExit(1)

a = Analysis(
    ["main.py"],
    pathex=["."],
    binaries=[
        ("assets/ffmpeg.exe",  "assets"),
        ("assets/ffprobe.exe", "assets"),
    ],
    datas=[
        (str(customtkinter_path),  "customtkinter"),
        (str(tkinterdnd2_path),    "tkinterdnd2"),
        (str(whisper_assets_path), "whisper/assets"),
    ],
    hiddenimports=[
        "customtkinter",
        "tkinterdnd2",
        "PIL",
        "PIL._tkinter_finder",
        # Whisper 相依
        "whisper",
        "numpy",
        "torch",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # 排除不需要的大型套件以縮小體積
        "matplotlib",
        "scipy",
        "IPython",
        "jupyter",
        "notebook",
        "pandas",
        "sklearn",
        "sklearn.utils._weight_vector",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="VideoMerger",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,          # 不顯示 cmd 黑視窗
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # icon="assets/icon.ico",  # 取消此行註解並放入圖示即可套用
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="VideoMerger",
)
