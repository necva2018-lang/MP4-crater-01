"""Whisper 語音辨識模組：將影片音訊轉錄為 SRT 字幕檔。"""

import os
import subprocess
import tempfile
import threading
from typing import Callable

from app.core.ffmpeg import get_ffmpeg_path


def check_whisper() -> bool:
    """回傳 openai-whisper 是否已安裝。"""
    try:
        import whisper  # noqa: F401
        return True
    except ImportError:
        return False


def transcribe_to_srt(
    video_path: str,
    output_srt_path: str,
    model_size: str = "base",
    status_callback: Callable[[str], None] | None = None,
    cancel_event: threading.Event | None = None,
) -> dict:
    """
    使用 Whisper 辨識影片音訊，輸出 SRT 字幕檔。

    流程：先用 assets/ffmpeg.exe 提取 WAV 暫存檔，再交給 Whisper，
    避免 Whisper 自行尋找系統 PATH 中的 ffmpeg 失敗。

    Parameters
    ----------
    video_path       : 輸入影片路徑
    output_srt_path  : 輸出 .srt 檔路徑
    model_size       : "tiny" / "base" / "small" / "medium"
    status_callback  : callback(msg: str)，用於更新 UI 狀態文字
    cancel_event     : 設定後在辨識前中止

    Returns
    -------
    {"success": bool, "error": str | None}
    """
    if not check_whisper():
        return {
            "success": False,
            "error": "尚未安裝 Whisper，請執行：pip install openai-whisper",
        }

    if cancel_event and cancel_event.is_set():
        return {"success": False, "error": "使用者已取消"}

    # ── 步驟 1：用 assets/ffmpeg.exe 提取音訊為暫存 WAV ──────────────
    wav_tmp = None
    try:
        tmp_fd, wav_tmp = tempfile.mkstemp(suffix=".wav")
        os.close(tmp_fd)

        if status_callback:
            status_callback(f"提取音訊：{os.path.basename(video_path)}")

        extract_cmd = [
            get_ffmpeg_path(),
            "-y",
            "-i", video_path,
            "-ar", "16000",   # Whisper 最佳取樣率
            "-ac", "1",       # 單聲道
            "-c:a", "pcm_s16le",
            wav_tmp,
        ]
        ret = subprocess.run(
            extract_cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        if ret.returncode != 0:
            err = ret.stderr.decode("utf-8", errors="replace").strip().splitlines()
            return {"success": False, "error": f"音訊提取失敗：{err[-1] if err else '未知錯誤'}"}

        if cancel_event and cancel_event.is_set():
            return {"success": False, "error": "使用者已取消"}

        # ── 步驟 2：將 WAV 讀成 numpy 陣列（繞過 Whisper 內部的 ffmpeg 呼叫）
        import wave
        import numpy as np
        import whisper

        if status_callback:
            status_callback(f"載入 Whisper 模型（{model_size}）…")

        model = whisper.load_model(model_size)

        if cancel_event and cancel_event.is_set():
            return {"success": False, "error": "使用者已取消"}

        if status_callback:
            status_callback(f"語音辨識中：{os.path.basename(video_path)}")

        with wave.open(wav_tmp, "rb") as wf:
            frames = wf.readframes(wf.getnframes())
            audio_np = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0

        # 直接傳 numpy 陣列，Whisper 就不會去呼叫系統 ffmpeg
        result = model.transcribe(
            audio_np,
            language="zh",
            initial_prompt="以下是繁體中文的語音轉錄，請使用繁體中文輸出：",
            verbose=False,
        )

        if cancel_event and cancel_event.is_set():
            return {"success": False, "error": "使用者已取消"}

        # ── 步驟 3：輸出 SRT ──────────────────────────────────────────
        if status_callback:
            status_callback("正在寫入 SRT…")

        segments = result.get("segments", [])
        srt_content = _segments_to_srt(segments)

        # UTF-8-BOM：Windows 播放器相容性最佳
        with open(output_srt_path, "w", encoding="utf-8-sig") as f:
            f.write(srt_content)

        return {"success": True, "error": None}

    except Exception as e:
        return {"success": False, "error": f"辨識失敗：{e}"}

    finally:
        # 清除暫存 WAV
        if wav_tmp and os.path.exists(wav_tmp):
            try:
                os.unlink(wav_tmp)
            except OSError:
                pass


# ── 內部工具 ─────────────────────────────────────────────────────────────────

def _segments_to_srt(segments: list) -> str:
    """將 Whisper segments 清單轉換為標準 SRT 字串。"""
    lines = []
    for i, seg in enumerate(segments, start=1):
        start = _seconds_to_srt_time(seg["start"])
        end   = _seconds_to_srt_time(seg["end"])
        text  = seg["text"].strip()
        if not text:
            continue
        lines.append(f"{i}\n{start} --> {end}\n{text}\n")
    return "\n".join(lines)


def _seconds_to_srt_time(seconds: float) -> str:
    """將秒數轉換為 SRT 時間格式：HH:MM:SS,mmm"""
    seconds = max(seconds, 0.0)
    ms  = int(round((seconds % 1) * 1000))
    s   = int(seconds) % 60
    m   = (int(seconds) // 60) % 60
    h   = int(seconds) // 3600
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
