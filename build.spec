# -*- mode: python ; coding: utf-8 -*-
"""
VideoMerger PyInstaller 打包設定
執行：pyinstaller build.spec
輸出：dist/VideoMerger/VideoMerger.exe
"""

import sys
import os
from pathlib import Path

# Python site-packages 路徑
site_packages = Path(sys.executable).parent / "Lib" / "site-packages"
customtkinter_path = site_packages / "customtkinter"
tkinterdnd2_path   = site_packages / "tkinterdnd2"
whisper_assets_path = site_packages / "whisper" / "assets"

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
        (str(whisper_assets_path), "whisper/assets"),  # mel_filters.npz 等資源
    ],
    hiddenimports=[
        "customtkinter",
        "tkinterdnd2",
        "PIL",
        "PIL._tkinter_finder",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
    # icon="assets/icon.ico",  # 取消註解並放入 icon 圖示即可套用
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
