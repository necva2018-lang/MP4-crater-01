# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 專案簡介

VideoMerger — Windows 桌面應用程式（Python 3.11 + CustomTkinter），使用 FFmpeg 合併影片檔案並支援 Whisper 語音辨識產生 SRT 字幕。目標產出：PyInstaller 打包的單一資料夾 `.exe`。

## 常用指令

```bash
# 安裝相依套件（含 Whisper）
pip install customtkinter tkinterdnd2 openai-whisper

# 執行程式
python main.py

# 打包成 .exe（輸出至 dist/VideoMerger/VideoMerger.exe）
pyinstaller build.spec
```

## 架構說明

三層結構：**核心層** → **UI 層** → **工具層**，UI 層只透過 callback 呼叫核心層，不直接操作檔案系統或 FFmpeg。

### 核心層（`app/core/`）

| 檔案 | 職責 |
|------|------|
| `ffmpeg.py` | 定位 `assets/ffmpeg.exe` 與 `ffprobe.exe`；`get_base_dir()` 透過 `sys.frozen` 支援 PyInstaller 打包後路徑 |
| `probe.py` | 封裝 `ffprobe`；模組層級 `_probe_cache` 以絕對路徑為 key 快取結果；`detect_mixed_format()` 比對所有檔案的 vcodec/acodec |
| `merger.py` | 合併策略判斷（見下方）；進度解析 FFmpeg stderr `time=` 行；`CHUNK_SIZE=8` 超過時啟用分批合併 |
| `transcriber.py` | 用 `assets/ffmpeg.exe` 先提取 WAV 暫存檔，再將 numpy 陣列直接傳給 Whisper（繞過 Whisper 內建的系統 ffmpeg 查找）；SRT 以 UTF-8-BOM 輸出 |
| `project.py` | `.vmproj` 專案檔（JSON）的儲存/載入；歷史紀錄寫入 `%AppData%/VideoMerger/history.json`，同步輸出可讀的 `history.log`（UTF-8-BOM）|

### UI 層（`app/ui/`）

| 檔案 | 職責 |
|------|------|
| `main_window.py` | 根視窗 `TkinterDnD.Tk()`；狀態機：IDLE / RUNNING / TRANSCRIBING / BATCH_SRT / DONE / ERROR；所有背景執行緒透過 `root.after(0, ...)` 回到主執行緒更新 UI |
| `file_list.py` | 可捲動清單，支援拖曳排序；每次清單變動後觸發格式分析 |
| `settings_panel.py` | 輸出格式、路徑、專案名稱、進階設定（編碼、CRF、硬體加速、Whisper 模型）|
| `history_panel.py` | 右側歷史面板，顯示 `project.py` 讀取的全域歷史，支援刷新 |

### 工具層（`app/utils/file_helper.py`）

`SUPPORTED_INPUT_EXTENSIONS`、`scan_folder()`、重複檔案偵測、`resolve_output_path()`（自動遞增 `output_1.mp4`）。

## 合併策略

```
detect_mixed_format()  +  _codec_incompatible_with_container()
         │
  need_reencode=True？
         ├── No  → _run_concat_copy()（fast, -c copy）
         └── Yes → len(files) > CHUNK_SIZE(8)？
                       ├── No  → _run_reencode()
                       └── Yes → _chunked_reencode()（分批重新編碼，最後 concat-copy 合併）
```

`_CONTAINER_SAFE_VCODECS` / `_CONTAINER_SAFE_ACODECS` 定義各容器可直接 copy 的白名單；MKV 為空 set，代表不限制。

## 關鍵限制

- **FFmpeg subprocess**：所有呼叫必須加 `creationflags=subprocess.CREATE_NO_WINDOW`，否則打包版會彈出黑色 cmd 視窗。
- **Concat list 編碼**：暫存 `concat_list.txt` 以 UTF-8 寫入絕對路徑（Windows 反斜線轉正斜線），中文路徑才不會出錯。
- **重新編碼旗標**：必須加 `-fflags +genpts`（修正 ASF 時間戳記）與 `-vf "scale=trunc(iw/2)*2:trunc(ih/2)*2"`（H.264 要求偶數解析度）。
- **執行緒安全**：合併/辨識執行緒中絕對不可直接操作 Tkinter 元件，一律透過 `root.after()` 回到主執行緒。
- **Whisper + PyInstaller**：`sys.stdout/stderr` 在 `console=False` 打包後為 `None`，`transcriber.py` 已用假 stream 替代，避免 tqdm 崩潰。

## PyInstaller 打包注意事項

`build.spec` 的 `datas` 已包含 `customtkinter`、`tkinterdnd2`、`whisper/assets`（mel_filters.npz 等）的 site-packages 路徑。若路徑不符，修改 `build.spec` 頂部的 `site_packages` 計算邏輯即可。啟用圖示時取消註解 `icon="assets/icon.ico"` 那行。
