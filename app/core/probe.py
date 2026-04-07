"""FFprobe 影片格式分析模組。"""

import json
import os
import subprocess

from app.core.ffmpeg import get_ffprobe_path

# 以絕對路徑為 key 的分析結果快取
_probe_cache: dict[str, dict] = {}


def probe_file(filepath: str) -> dict:
    """
    使用 FFprobe 分析影片檔案，回傳標準化的資訊字典。
    失敗時 error 欄位填入錯誤訊息，其他欄位為 None。
    """
    filepath = os.path.abspath(filepath)

    cmd = [
        get_ffprobe_path(),
        "-v", "quiet",
        "-print_format", "json",
        "-show_streams",
        "-show_format",
        filepath,
    ]

    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        if result.returncode != 0:
            err = result.stderr.decode("utf-8", errors="replace").strip()
            return _error_result(filepath, err or "FFprobe 回傳非零退出碼")

        data = json.loads(result.stdout.decode("utf-8", errors="replace"))
    except (FileNotFoundError, OSError) as e:
        return _error_result(filepath, f"找不到 ffprobe：{e}")
    except json.JSONDecodeError as e:
        return _error_result(filepath, f"JSON 解析失敗：{e}")

    # 解析串流
    video_info = None
    audio_info = None
    for stream in data.get("streams", []):
        codec_type = stream.get("codec_type", "")
        if codec_type == "video" and video_info is None:
            fps = _parse_fps(stream.get("r_frame_rate", "0/1"))
            video_info = {
                "codec":  stream.get("codec_name"),
                "width":  stream.get("width"),
                "height": stream.get("height"),
                "fps":    fps,
            }
        elif codec_type == "audio" and audio_info is None:
            audio_info = {
                "codec":       stream.get("codec_name"),
                "channels":    stream.get("channels"),
                "sample_rate": int(stream.get("sample_rate", 0)),
            }

    fmt = data.get("format", {})
    try:
        duration = float(fmt.get("duration", 0))
    except (TypeError, ValueError):
        duration = 0.0
    try:
        size_mb = int(fmt.get("size", 0)) / (1024 * 1024)
    except (TypeError, ValueError):
        size_mb = 0.0

    return {
        "path":      filepath,
        "filename":  os.path.basename(filepath),
        "extension": os.path.splitext(filepath)[1].lower(),
        "duration":  duration,
        "size_mb":   round(size_mb, 2),
        "video":     video_info,
        "audio":     audio_info,
        "error":     None,
    }


def get_probe(filepath: str) -> dict:
    """回傳快取的分析結果（若尚未分析則執行分析）。"""
    filepath = os.path.abspath(filepath)
    if filepath not in _probe_cache:
        _probe_cache[filepath] = probe_file(filepath)
    return _probe_cache[filepath]


def detect_mixed_format(file_infos: list[dict]) -> bool:
    """
    回傳 True 表示清單中有混合格式，需要重新編碼。
    判斷條件：任一檔案的 video.codec 或 audio.codec 與其他不同。
    若清單少於 2 個有效檔案，回傳 False。
    """
    valid = [f for f in file_infos if f.get("error") is None and f.get("video")]
    if len(valid) < 2:
        return False

    first_vcodec = valid[0]["video"]["codec"]
    first_acodec = valid[0]["audio"]["codec"] if valid[0].get("audio") else None

    for info in valid[1:]:
        if info["video"]["codec"] != first_vcodec:
            return True
        a_codec = info["audio"]["codec"] if info.get("audio") else None
        if a_codec != first_acodec:
            return True

    return False


# ── 內部工具函式 ────────────────────────────────────────────────────────────

def _error_result(filepath: str, message: str) -> dict:
    return {
        "path":      filepath,
        "filename":  os.path.basename(filepath),
        "extension": os.path.splitext(filepath)[1].lower(),
        "duration":  None,
        "size_mb":   None,
        "video":     None,
        "audio":     None,
        "error":     message,
    }


def _parse_fps(r_frame_rate: str) -> float:
    """將 'num/den' 格式的幀率字串轉換為浮點數。"""
    try:
        parts = r_frame_rate.split("/")
        if len(parts) == 2:
            num, den = float(parts[0]), float(parts[1])
            return round(num / den, 3) if den else 0.0
        return float(r_frame_rate)
    except (ValueError, ZeroDivisionError):
        return 0.0
