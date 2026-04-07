"""路徑、副檔名工具與資料夾掃描。"""

import os

SUPPORTED_INPUT_EXTENSIONS = [
    ".mp4", ".mkv", ".mov", ".avi", ".wmv",
    ".asf", ".flv", ".webm", ".ts", ".mts",
    ".m2ts", ".mpeg", ".mpg", ".3gp", ".ogv",
    ".dvr-ms", ".mxf", ".vob", ".rm", ".rmvb",
]


def is_supported_video(path: str) -> bool:
    """判斷檔案是否為支援的影片格式。"""
    ext = os.path.splitext(path)[1].lower()
    return ext in SUPPORTED_INPUT_EXTENSIONS


def scan_folder(folder_path: str, recursive: bool = True) -> list[str]:
    """
    掃描資料夾中所有支援的影片檔。
    recursive=True 時遞迴掃描子資料夾。
    回傳檔案路徑清單，依資料夾名稱 + 檔名排序。
    """
    results = []
    if recursive:
        for root, _, files in os.walk(folder_path):
            for f in files:
                full = os.path.join(root, f)
                if is_supported_video(full):
                    results.append(os.path.abspath(full))
    else:
        for f in os.listdir(folder_path):
            full = os.path.join(folder_path, f)
            if os.path.isfile(full) and is_supported_video(full):
                results.append(os.path.abspath(full))

    results.sort(key=lambda p: (os.path.dirname(p), os.path.basename(p)))
    return results


def resolve_output_path(output_dir: str, filename: str, ext: str) -> str:
    """
    若 output_dir/filename.ext 已存在，自動加上編號：
    output.mp4 → output_1.mp4 → output_2.mp4 ...
    """
    candidate = os.path.join(output_dir, filename + ext)
    if not os.path.exists(candidate):
        return candidate
    counter = 1
    while True:
        candidate = os.path.join(output_dir, f"{filename}_{counter}{ext}")
        if not os.path.exists(candidate):
            return candidate
        counter += 1
