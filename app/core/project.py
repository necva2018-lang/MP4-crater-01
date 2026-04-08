"""專案儲存/載入與操作歷史記錄管理。"""

import json
import os
import uuid
from datetime import datetime

PROJECT_EXT  = ".vmproj"
HISTORY_FILE = "history.json"
HISTORY_MAX  = 200          # 全域歷史最多保留筆數


# ── 專案資料夾 ───────────────────────────────────────────────────────────────

def ensure_project_dir(root: str, project_name: str) -> str:
    """建立 {root}/{project_name}/ 資料夾並回傳完整路徑。"""
    project_dir = os.path.join(root, project_name)
    os.makedirs(project_dir, exist_ok=True)
    return project_dir


def get_project_output_path(project_dir: str, project_name: str, ext: str) -> str:
    """回傳 {project_dir}/{project_name}{ext}，例如 D:/v/Proj/Proj.mp4。"""
    return os.path.join(project_dir, project_name + ext)


# ── 專案檔 (.vmproj) ─────────────────────────────────────────────────────────

def save_project(project_dir: str, project_name: str,
                 files: list[str], settings: dict) -> str:
    """
    將目前的檔案清單與設定儲存為 .vmproj。

    Returns
    -------
    儲存後的完整路徑
    """
    os.makedirs(project_dir, exist_ok=True)
    data = {
        "version":    1,
        "saved_at":   datetime.now().isoformat(timespec="seconds"),
        "files":      files,
        "settings":   settings,
    }
    filepath = os.path.join(project_dir, project_name + PROJECT_EXT)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return filepath


def load_project(vmproj_path: str) -> dict:
    """
    讀取 .vmproj 檔案。

    Returns
    -------
    {"files": list[str], "settings": dict}
    若讀取失敗則拋出 ValueError。
    """
    try:
        with open(vmproj_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if "files" not in data or "settings" not in data:
            raise ValueError("專案檔格式不正確")
        return {"files": data["files"], "settings": data["settings"]}
    except (json.JSONDecodeError, OSError) as e:
        raise ValueError(f"無法讀取專案檔：{e}") from e


# ── 全域歷史（AppData）────────────────────────────────────────────────────────

def get_global_history_dir() -> str:
    """回傳 %AppData%\\VideoMerger\\，若不存在則建立。"""
    appdata = os.environ.get("APPDATA", os.path.expanduser("~"))
    d = os.path.join(appdata, "VideoMerger")
    os.makedirs(d, exist_ok=True)
    return d


def get_global_history_path() -> str:
    return os.path.join(get_global_history_dir(), HISTORY_FILE)


def _read_history_file(path: str) -> list[dict]:
    """讀取歷史 JSON，失敗時回傳空清單。"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("records", []) if isinstance(data, dict) else []
    except (json.JSONDecodeError, OSError):
        return []


def _write_history_file(path: str, records: list[dict]) -> None:
    """寫入歷史 JSON。"""
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"version": 1, "records": records}, f,
                  ensure_ascii=False, indent=2)


def _make_record(
    record_type: str,
    project_name: str,
    project_dir: str,
    input_files: list[str],
    output_path: str,
    success: bool,
    error: str | None,
    duration_sec: float,
    output_format: str,
) -> dict:
    """建立一筆歷史記錄 dict。"""
    now = datetime.now()
    return {
        "id":           now.strftime("%Y%m%d_%H%M%S_") + uuid.uuid4().hex[:4],
        "timestamp":    now.isoformat(timespec="seconds"),
        "type":         record_type,     # "merge" | "srt"
        "project_name": project_name,
        "project_dir":  project_dir,
        "input_files":  [os.path.basename(f) for f in input_files],
        "input_count":  len(input_files),
        "output_path":  output_path,
        "success":      success,
        "error":        error,
        "duration_sec": round(duration_sec, 1),
        "output_format": output_format,
    }


def append_global_history(record: dict) -> None:
    """追加一筆記錄到全域歷史，超過 HISTORY_MAX 時刪除最舊的。"""
    path = get_global_history_path()
    records = _read_history_file(path)
    records.append(record)
    if len(records) > HISTORY_MAX:
        records = records[-HISTORY_MAX:]
    _write_history_file(path, records)


def load_global_history(limit: int = 50) -> list[dict]:
    """回傳最新的 limit 筆記錄（最新在最前）。"""
    records = _read_history_file(get_global_history_path())
    return list(reversed(records[-limit:]))


# ── 本地歷史（專案資料夾內）──────────────────────────────────────────────────

def append_local_history(project_dir: str, record: dict) -> None:
    """追加一筆記錄到專案資料夾的 history.json。"""
    path = os.path.join(project_dir, HISTORY_FILE)
    records = _read_history_file(path)
    records.append(record)
    _write_history_file(path, records)


# ── 工廠函式（方便 main_window 呼叫）────────────────────────────────────────

def make_and_save_record(
    record_type: str,
    project_name: str,
    project_dir: str,
    input_files: list[str],
    output_path: str,
    success: bool,
    error: str | None,
    duration_sec: float,
    output_format: str,
) -> dict:
    """
    建立記錄並同時寫入全域與本地歷史，回傳記錄 dict。
    """
    record = _make_record(
        record_type, project_name, project_dir,
        input_files, output_path, success, error,
        duration_sec, output_format,
    )
    append_global_history(record)
    if project_dir:
        try:
            append_local_history(project_dir, record)
        except OSError:
            pass
    return record
