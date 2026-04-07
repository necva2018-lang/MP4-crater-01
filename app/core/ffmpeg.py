"""FFmpeg / FFprobe 路徑管理與可用性檢查。"""

import os
import subprocess
import sys


def get_base_dir() -> str:
    """回傳程式根目錄。打包後為 .exe 所在目錄，開發時為 main.py 所在目錄。"""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    # 本檔案位於 app/core/ffmpeg.py，根目錄為上兩層
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def get_ffmpeg_path() -> str:
    """回傳 ffmpeg.exe 的絕對路徑。"""
    return os.path.join(get_base_dir(), "assets", "ffmpeg.exe")


def get_ffprobe_path() -> str:
    """回傳 ffprobe.exe 的絕對路徑。"""
    return os.path.join(get_base_dir(), "assets", "ffprobe.exe")


def check_ffmpeg() -> bool:
    """執行 ffmpeg -version，確認 FFmpeg 可正常使用。回傳 True/False。"""
    try:
        result = subprocess.run(
            [get_ffmpeg_path(), "-version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        return result.returncode == 0
    except (FileNotFoundError, OSError):
        return False


def detect_hw_accel() -> list[str]:
    """
    執行 ffmpeg -hwaccels，回傳可用的硬體加速選項清單（人類可讀標籤）。
    例如：["NVENC (NVIDIA)", "AMF (AMD)", "QSV (Intel)"]
    """
    label_map = {
        "cuda":     "NVENC (NVIDIA)",
        "nvenc":    "NVENC (NVIDIA)",
        "amf":      "AMF (AMD)",
        "qsv":      "QSV (Intel)",
        "d3d11va":  "D3D11VA",
        "dxva2":    "DXVA2",
    }
    try:
        result = subprocess.run(
            [get_ffmpeg_path(), "-hwaccels"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        output = result.stdout.decode("utf-8", errors="replace")
        found = []
        seen = set()
        for line in output.splitlines():
            key = line.strip().lower()
            if key in label_map:
                label = label_map[key]
                if label not in seen:
                    found.append(label)
                    seen.add(label)
        return found
    except (FileNotFoundError, OSError):
        return []
