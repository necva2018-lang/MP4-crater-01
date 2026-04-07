"""影片合併核心邏輯。支援快速合併（concat copy）與重新編碼兩條路線。"""

import os
import re
import subprocess
import tempfile
import threading
from typing import Callable

from app.core.ffmpeg import get_ffmpeg_path
from app.core.probe import detect_mixed_format, get_probe
from app.utils.file_helper import resolve_output_path

# 輸出格式對應表
OUTPUT_FORMATS: dict[str, dict] = {
    "MP4": {"ext": ".mp4", "vcodec": "libx264", "acodec": "aac"},
    "MKV": {"ext": ".mkv", "vcodec": "libx264", "acodec": "aac"},
    "MOV": {"ext": ".mov", "vcodec": "libx264", "acodec": "aac"},
    "AVI": {"ext": ".avi", "vcodec": "libxvid", "acodec": "mp3"},
}
DEFAULT_FORMAT = "MP4"

# 各容器格式支援直接 copy 的視訊編碼白名單
_CONTAINER_SAFE_VCODECS: dict[str, set[str]] = {
    "MP4": {"h264", "hevc", "h265", "mpeg4", "mp4v", "mjpeg", "av1", "vp9"},
    "MOV": {"h264", "hevc", "h265", "mpeg4", "mp4v", "mjpeg", "prores", "dnxhd"},
    "MKV": set(),   # MKV 幾乎支援所有編碼，留空代表永遠不需要因容器而重新編碼
    "AVI": {"mpeg4", "msmpeg4v3", "msmpeg4v2", "mpeg2video", "mjpeg", "h264"},
}
_CONTAINER_SAFE_ACODECS: dict[str, set[str]] = {
    "MP4": {"aac", "mp3", "ac3", "eac3", "opus", "flac", "alac"},
    "MOV": {"aac", "mp3", "ac3", "eac3", "pcm_s16le", "pcm_s24le", "alac"},
    "MKV": set(),
    "AVI": {"mp3", "ac3", "pcm_s16le", "aac"},
}


def _codec_incompatible_with_container(file_infos: list[dict], output_format: str) -> bool:
    """回傳 True 表示有任一輸入檔的編碼無法直接 copy 到目標容器，必須重新編碼。"""
    safe_v = _CONTAINER_SAFE_VCODECS.get(output_format, set())
    safe_a = _CONTAINER_SAFE_ACODECS.get(output_format, set())

    # 空 set 代表 MKV（不限制），直接回傳 False
    if not safe_v and not safe_a:
        return False

    for info in file_infos:
        if info.get("error"):
            continue
        if safe_v and info.get("video"):
            codec = (info["video"].get("codec") or "").lower()
            if codec and codec not in safe_v:
                return True
        if safe_a and info.get("audio"):
            codec = (info["audio"].get("codec") or "").lower()
            if codec and codec not in safe_a:
                return True
    return False

# FFmpeg stderr 進度解析用的 regex
_TIME_RE = re.compile(r"time=(\d+):(\d+):(\d+\.\d+)")
_SPEED_RE = re.compile(r"speed=\s*([\d.]+)x")


def merge_videos(
    input_files: list[str],
    output_path: str,
    output_format: str = DEFAULT_FORMAT,
    force_reencode: bool = False,
    video_codec: str = "auto",
    audio_codec: str = "auto",
    crf: int = 18,
    hw_accel: str = "none",
    progress_callback: Callable[[float, float], None] | None = None,
    cancel_event: threading.Event | None = None,
) -> dict:
    """
    合併多個影片檔案。

    Parameters
    ----------
    input_files      : 已排序的輸入檔案路徑清單
    output_path      : 輸出檔案完整路徑
    output_format    : "MP4" / "MKV" / "MOV" / "AVI"
    force_reencode   : True 時強制走重新編碼路線
    video_codec      : "auto" / "libx264" / "libx265" / "copy"
    audio_codec      : "auto" / "aac" / "mp3" / "copy"
    crf              : H.264/H.265 品質值（0~51，預設 18）
    hw_accel         : "none" / "nvenc" / "amf" / "qsv"
    progress_callback: callback(percent: float, eta_seconds: float)
    cancel_event     : 設定後中止合併

    Returns
    -------
    {"success": bool, "error": str | None, "warning": str | None}
    """
    if not input_files:
        return {"success": False, "error": "沒有輸入檔案", "warning": None}

    fmt = OUTPUT_FORMATS.get(output_format, OUTPUT_FORMATS[DEFAULT_FORMAT])

    # 分析所有輸入檔案（使用快取）
    file_infos = [get_probe(f) for f in input_files]
    total_duration = sum(
        (info["duration"] or 0.0) for info in file_infos if info["error"] is None
    )

    is_mixed = detect_mixed_format(file_infos)
    is_incompatible = _codec_incompatible_with_container(file_infos, output_format)
    need_reencode = force_reencode or is_mixed or is_incompatible

    # 「複製 + 異格式」衝突：自動覆蓋為 H.264 並記錄警告
    warning_msg = None
    if video_codec == "copy" and is_mixed:
        video_codec = "libx264"
        warning_msg = "偵測到混合格式，已自動將視訊編碼從「複製」改為 H.264"
        need_reencode = True

    # 建立暫存 concat list（UTF-8，使用絕對路徑）
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", encoding="utf-8", delete=False
        ) as f:
            concat_list_path = f.name
            for path in input_files:
                abs_path = os.path.abspath(path).replace("\\", "/")
                f.write(f"file '{abs_path}'\n")
    except OSError as e:
        return {"success": False, "error": f"無法建立暫存檔：{e}", "warning": None}

    try:
        if need_reencode:
            result = _run_reencode(
                concat_list_path, output_path, fmt,
                video_codec, audio_codec, crf, hw_accel,
                total_duration, progress_callback, cancel_event,
            )
        else:
            result = _run_concat_copy(
                concat_list_path, output_path,
                total_duration, progress_callback, cancel_event,
            )
    finally:
        try:
            os.unlink(concat_list_path)
        except OSError:
            pass

    result["warning"] = warning_msg
    return result


# ── 快速合併（concat demuxer + -c copy） ────────────────────────────────────

def _run_concat_copy(
    concat_list_path: str,
    output_path: str,
    total_duration: float,
    progress_callback,
    cancel_event,
) -> dict:
    cmd = [
        get_ffmpeg_path(),
        "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", concat_list_path,
        "-c", "copy",
        output_path,
    ]
    return _run_ffmpeg(cmd, total_duration, progress_callback, cancel_event)


# ── 重新編碼合併 ─────────────────────────────────────────────────────────────

def _run_reencode(
    concat_list_path: str,
    output_path: str,
    fmt: dict,
    video_codec: str,
    audio_codec: str,
    crf: int,
    hw_accel: str,
    total_duration: float,
    progress_callback,
    cancel_event,
) -> dict:
    vcodec = _resolve_video_codec(video_codec, fmt, hw_accel)
    acodec = fmt["acodec"] if audio_codec == "auto" else audio_codec

    cmd = [
        get_ffmpeg_path(),
        "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", concat_list_path,
        "-fflags", "+genpts",
        "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2",
        "-c:v", vcodec,
    ]

    # libx264 / libx265 加上品質參數；硬體編碼器不支援 -crf
    if vcodec in ("libx264", "libx265"):
        cmd += ["-crf", str(crf), "-preset", "fast"]

    cmd += [
        "-c:a", acodec,
        "-b:a", "192k",
        output_path,
    ]

    return _run_ffmpeg(cmd, total_duration, progress_callback, cancel_event)


def _resolve_video_codec(video_codec: str, fmt: dict, hw_accel: str) -> str:
    """根據使用者選擇與硬體加速設定，決定實際的視訊編碼器名稱。"""
    if video_codec != "auto" and video_codec != "copy":
        # 明確指定編碼器，直接套用硬體加速後綴
        base = video_codec  # 例如 "libx264"
        return _apply_hw_accel(base, hw_accel)
    if video_codec == "copy":
        return "copy"
    # auto：使用格式預設
    return _apply_hw_accel(fmt["vcodec"], hw_accel)


def _apply_hw_accel(base_codec: str, hw_accel: str) -> str:
    """將軟體編碼器名稱轉換為對應的硬體加速版本（若有）。"""
    hw_map = {
        ("libx264", "nvenc"): "h264_nvenc",
        ("libx264", "amf"):   "h264_amf",
        ("libx264", "qsv"):   "h264_qsv",
        ("libx265", "nvenc"): "hevc_nvenc",
        ("libx265", "amf"):   "hevc_amf",
        ("libx265", "qsv"):   "hevc_qsv",
    }
    return hw_map.get((base_codec, hw_accel), base_codec)


# ── 執行 FFmpeg 並解析進度 ───────────────────────────────────────────────────

def _run_ffmpeg(
    cmd: list[str],
    total_duration: float,
    progress_callback,
    cancel_event: threading.Event | None,
) -> dict:
    try:
        proc = subprocess.Popen(
            cmd,
            stderr=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            universal_newlines=True,
            encoding="utf-8",
            errors="replace",
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    except (FileNotFoundError, OSError) as e:
        return {"success": False, "error": f"無法啟動 FFmpeg：{e}"}

    stderr_lines: list[str] = []

    for line in proc.stderr:
        stderr_lines.append(line.rstrip())

        # 取消偵測
        if cancel_event and cancel_event.is_set():
            proc.terminate()
            proc.wait()
            return {"success": False, "error": "使用者已取消"}

        # 解析進度
        if progress_callback and total_duration > 0:
            t_match = _TIME_RE.search(line)
            if t_match:
                h = float(t_match.group(1))
                m = float(t_match.group(2))
                s = float(t_match.group(3))
                elapsed = h * 3600 + m * 60 + s
                percent = min(elapsed / total_duration * 100, 100)

                eta = 0.0
                s_match = _SPEED_RE.search(line)
                if s_match:
                    speed = float(s_match.group(1))
                    if speed > 0:
                        eta = max((total_duration - elapsed) / speed, 0.0)

                progress_callback(percent, eta)

    proc.wait()

    if cancel_event and cancel_event.is_set():
        return {"success": False, "error": "使用者已取消"}

    if proc.returncode != 0:
        # 取最後 8 行有意義的錯誤訊息
        error_lines = [l for l in stderr_lines if l.strip() and not l.startswith("  ")]
        detail = "\n".join(error_lines[-8:]) if error_lines else ""
        return {"success": False, "error": f"FFmpeg 異常結束（代碼 {proc.returncode}）\n{detail}"}

    # 確認輸出檔案存在且非空
    if not os.path.exists(output_path_from_cmd(cmd)):
        return {"success": False, "error": "輸出檔案不存在"}

    return {"success": True, "error": None}


def output_path_from_cmd(cmd: list[str]) -> str:
    """從 FFmpeg 指令列取出最後一個引數作為輸出路徑。"""
    return cmd[-1]
