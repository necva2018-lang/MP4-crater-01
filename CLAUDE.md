# CLAUDE.md

本文件提供 Claude Code (claude.ai/code) 在此專案中的開發指引。

## 專案簡介

VideoMerger — Windows 桌面應用程式（Python 3.11 + CustomTkinter），使用 FFmpeg 合併影片檔案。目標產出：PyInstaller 打包的單一資料夾 `.exe`。

## 常用指令

```bash
# 安裝相依套件
pip install customtkinter tkinterdnd2

# 執行程式
python main.py

# 打包成 .exe
pyinstaller build.spec
# 輸出位置：dist/VideoMerger/VideoMerger.exe
```

## 架構說明

應用程式分為三層：

**核心層（`app/core/`）** — 不依賴 UI，純邏輯：
- `ffmpeg.py` — 定位 `assets/ffmpeg.exe` 與 `assets/ffprobe.exe`；使用 `get_base_dir()`（透過 `sys.frozen` 支援 PyInstaller 打包後路徑）
- `probe.py` — 封裝 `ffprobe -print_format json`；以絕對路徑為 key 維護模組層級的 `_probe_cache` 快取字典
- `merger.py` — 依 `detect_mixed_format()` 結果決定走 concat-copy 或重新編碼；寫入暫存 `concat_list.txt`；解析 FFmpeg stderr 的 `time=` 行以回報進度；接受 `cancel_event: threading.Event`

**UI 層（`app/ui/`）** — 僅使用 CustomTkinter 元件，透過 callback 呼叫核心層：
- `main_window.py` — 根視窗 `TkinterDnD.Tk()`；持有狀態機（IDLE/RUNNING/DONE/ERROR）；以 `threading.Thread(daemon=True)` 啟動合併執行緒；用 `root.after(0, ...)` 將進度更新發回主執行緒
- `file_list.py` — 可捲動清單，支援拖曳排序；每次清單變動後觸發格式分析
- `settings_panel.py` — 輸出格式／路徑／檔名設定 + 可展開的進階面板

**工具層（`app/utils/file_helper.py`）** — `SUPPORTED_INPUT_EXTENSIONS`、`scan_folder()`、重複檔案偵測、`resolve_output_path()`（自動遞增 `output_1.mp4`、`output_2.mp4`…）

## 關鍵限制

- **FFmpeg subprocess**：所有呼叫必須加 `creationflags=subprocess.CREATE_NO_WINDOW`，否則打包版會彈出黑色 cmd 視窗。
- **Concat list 編碼**：`concat_list.txt` 必須用 UTF-8 寫入絕對路徑，中文路徑才不會出錯。
- **重新編碼旗標**：必須加 `-fflags +genpts`（修正 ASF 時間戳記偏移）與 `-vf "scale=trunc(iw/2)*2:trunc(ih/2)*2"`（H.264 要求偶數解析度）。
- **PyInstaller + tkinterdnd2**：`build.spec` 的 `hiddenimports` 需加入 `'tkinterdnd2'`；若執行時找不到 CustomTkinter 資源，需將 site-packages 中的 customtkinter 加入 `datas`。
- **執行緒安全**：合併執行緒中絕對不可直接操作 Tkinter 元件，一律透過 `root.after()` 回到主執行緒。

## 開發階段順序

Phase 1（骨架 + FFmpeg 檢查）→ 2（probe 分析）→ 3（合併核心）→ 4（基本 UI）→ 5（拖曳匯入 + 排序）→ 6（異格式警告）→ 7（進階設定）→ 8（PyInstaller 打包）。各 Phase 的詳細步驟與 Checklist 見下方規格書。

---

# 影片合併工具 (VideoMerger) — 開發規格書

> 本文件為完整開發規格與步驟指引，請依照 Phase 順序開發，完成每個 Checklist 後再進入下一階段。

---

## 專案總覽

| 項目 | 內容 |
|------|------|
| 專案名稱 | VideoMerger |
| 目標平台 | Windows 10 / 11 (64-bit) |
| 語言 | Python 3.11+ |
| UI 框架 | CustomTkinter |
| 影片處理 | FFmpeg + FFprobe |
| 打包方式 | PyInstaller → 單資料夾 .exe |
| 授權 | 個人使用 |

---

## 目錄結構（目標）

```
VideoMerger/
├── main.py                  # 程式進入點
├── app/
│   ├── __init__.py
│   ├── ui/
│   │   ├── __init__.py
│   │   ├── main_window.py   # 主視窗
│   │   ├── file_list.py     # 檔案清單元件
│   │   └── settings_panel.py# 輸出設定面板
│   ├── core/
│   │   ├── __init__.py
│   │   ├── ffmpeg.py        # FFmpeg 封裝
│   │   ├── probe.py         # FFprobe 格式分析
│   │   └── merger.py        # 合併邏輯
│   └── utils/
│       ├── __init__.py
│       └── file_helper.py   # 路徑、副檔名工具
├── assets/
│   ├── ffmpeg.exe           # FFmpeg 執行檔
│   └── ffprobe.exe          # FFprobe 執行檔
├── requirements.txt
├── build.spec               # PyInstaller 打包設定
└── CLAUDE.md                # 本規格書
```

---

## 環境需求

### Python 套件

```
customtkinter>=5.2.0
tkinterdnd2>=0.3.0
```

> 安裝指令：`pip install customtkinter tkinterdnd2`

### 外部工具

- **FFmpeg 6.x (Windows 64-bit)**
  - 下載：https://www.gyan.dev/ffmpeg/builds/
  - 選擇：`ffmpeg-release-essentials.zip`
  - 解壓後取出 `ffmpeg.exe` 與 `ffprobe.exe`，放入 `assets/` 資料夾

### 開發工具

- Python 3.11+
- pip
- PyInstaller（打包用）：`pip install pyinstaller`

---

## 支援的輸入格式

程式需支援以下副檔名作為輸入，過濾時以此清單為準：

```python
SUPPORTED_INPUT_EXTENSIONS = [
    ".mp4", ".mkv", ".mov", ".avi", ".wmv",
    ".asf", ".flv", ".webm", ".ts", ".mts",
    ".m2ts", ".mpeg", ".mpg", ".3gp", ".ogv",
    ".dvr-ms", ".mxf", ".vob", ".rm", ".rmvb"
]
```

---

## 輸出格式選項

```python
OUTPUT_FORMATS = {
    "MP4":  {"ext": ".mp4",  "vcodec": "libx264",  "acodec": "aac"},
    "MKV":  {"ext": ".mkv",  "vcodec": "libx264",  "acodec": "aac"},
    "MOV":  {"ext": ".mov",  "vcodec": "libx264",  "acodec": "aac"},
    "AVI":  {"ext": ".avi",  "vcodec": "libxvid",  "acodec": "mp3"},
}
DEFAULT_FORMAT = "MP4"
```

---

## 開發階段總覽

| Phase | 名稱 | 核心目標 |
|-------|------|---------|
| 1 | 環境建置 | 建立專案結構、確認 FFmpeg 可用 |
| 2 | 格式分析模組 | FFprobe 分析影片資訊 |
| 3 | 合併核心邏輯 | FFmpeg 合併（同格式快速 / 異格式重新編碼） |
| 4 | 基本 UI | 主視窗、清單、輸出設定、進度條 |
| 5 | 檔案管理功能 | 拖曳匯入、資料夾掃描、清單排序 |
| 6 | 異格式警告提示 | 偵測混合格式並提示使用者 |
| 7 | 進階設定 | 編碼選擇、硬體加速偵測 |
| 8 | 打包與發佈 | PyInstaller 打包成 .exe |

---

## Phase 1 — 環境建置

### 目標
建立專案骨架，確認 FFmpeg 可正常呼叫。

### 步驟

1. 建立上方的目錄結構（空的 `__init__.py` 即可）
2. 建立 `requirements.txt`，內容如下：
   ```
   customtkinter>=5.2.0
   tkinterdnd2>=0.3.0
   ```
3. 下載 FFmpeg，將 `ffmpeg.exe` 和 `ffprobe.exe` 放入 `assets/`
4. 建立 `app/core/ffmpeg.py`，實作以下功能：
   - `get_ffmpeg_path()` → 回傳 `assets/ffmpeg.exe` 的絕對路徑
   - `get_ffprobe_path()` → 回傳 `assets/ffprobe.exe` 的絕對路徑
   - `check_ffmpeg()` → 執行 `ffmpeg -version`，確認可用，回傳 `True/False`
5. 建立 `main.py`，啟動時呼叫 `check_ffmpeg()`，若失敗顯示錯誤訊息並結束

### Checklist
- [ ] 目錄結構建立完成
- [ ] `pip install -r requirements.txt` 無錯誤
- [ ] `assets/ffmpeg.exe` 與 `assets/ffprobe.exe` 存在
- [ ] `check_ffmpeg()` 回傳 `True`
- [ ] `main.py` 可正常執行（不崩潰）

---

## Phase 2 — 格式分析模組

### 目標
使用 FFprobe 分析每個輸入檔案的影片資訊。

### 步驟

1. 建立 `app/core/probe.py`，實作 `probe_file(filepath: str) -> dict`
2. 呼叫 FFprobe 指令：
   ```
   ffprobe -v quiet -print_format json -show_streams -show_format <filepath>
   ```
3. 解析 JSON 輸出，回傳以下結構：
   ```python
   {
       "path":       "/path/to/file.asf",
       "filename":   "file.asf",
       "extension":  ".asf",
       "duration":   125.4,         # 秒
       "size_mb":    45.2,          # MB
       "video": {
           "codec":     "wmv3",     # 視訊編碼
           "width":     1280,
           "height":    720,
           "fps":       30.0,
       },
       "audio": {
           "codec":     "wmav2",    # 音訊編碼
           "channels":  2,
           "sample_rate": 44100,
       },
       "error": None                # 分析失敗時放錯誤訊息
   }
   ```
4. 若檔案分析失敗，`error` 欄位填入錯誤訊息，其他欄位填 `None`

### 異格式偵測邏輯

```python
def detect_mixed_format(file_infos: list[dict]) -> bool:
    """
    回傳 True 表示清單中有混合格式，需要重新編碼。
    判斷條件：任一檔案的 video.codec 或 audio.codec 與其他不同。
    """
```

### Checklist
- [ ] `probe_file()` 可正確分析 MP4 檔案
- [ ] `probe_file()` 可正確分析 ASF 檔案
- [ ] `probe_file()` 在檔案損毀時不崩潰，`error` 有值
- [ ] `detect_mixed_format()` 正確判斷混合格式

---

## Phase 3 — 合併核心邏輯

### 目標
實作 FFmpeg 合併，支援快速合併（同格式）與重新編碼（異格式）。

### 步驟

1. 建立 `app/core/merger.py`，實作 `merge_videos()` 函式

#### 函式簽名

```python
def merge_videos(
    input_files: list[str],      # 輸入檔案路徑清單（已排序）
    output_path: str,            # 輸出檔案完整路徑
    output_format: str,          # "MP4" / "MKV" / "MOV" / "AVI"
    force_reencode: bool = False, # 強制重新編碼
    video_codec: str = "auto",   # "auto" / "libx264" / "libx265" / "copy"
    audio_codec: str = "auto",   # "auto" / "aac" / "mp3" / "copy"
    hw_accel: str = "none",      # "none" / "nvenc" / "amf" / "qsv"
    progress_callback=None,      # callback(percent: float, eta_seconds: float)
    cancel_event=None,           # threading.Event，設定時中止合併
) -> dict:                       # {"success": bool, "error": str | None}
```

#### 合併策略判斷

```
輸入檔案清單
      │
      ▼
detect_mixed_format()
      │
  ┌───┴───┐
  │ False │ → 所有格式相同 → concat demuxer（快速，不重新編碼）
  │ True  │ → 混合格式     → re-encode（重新編碼後合併）
  └───────┘
  force_reencode=True 時，強制走 re-encode 路線
```

#### 快速合併（concat demuxer）

1. 建立暫存 txt 檔（`concat_list.txt`），格式如下：
   ```
   file '/absolute/path/to/file1.mp4'
   file '/absolute/path/to/file2.mp4'
   ```
2. 執行：
   ```
   ffmpeg -f concat -safe 0 -i concat_list.txt -c copy <output_path>
   ```

#### 重新編碼合併（re-encode）

1. 建立 `concat_list.txt`（同上）
2. 執行（以 MP4 輸出為例）：
   ```
   ffmpeg -f concat -safe 0 -i concat_list.txt
          -fflags +genpts
          -vf "scale=trunc(iw/2)*2:trunc(ih/2)*2"
          -c:v libx264 -crf 18 -preset fast
          -c:a aac -b:a 192k
          <output_path>
   ```
   > `-fflags +genpts` 修正 ASF 等格式的時間戳記問題  
   > `-vf scale` 確保解析度為偶數（H.264 必要條件）

#### 進度解析

從 FFmpeg stderr 輸出解析進度，FFmpeg 輸出格式為：
```
frame=  120 fps= 30 q=28.0 size=    1024kB time=00:00:04.00 bitrate=2097.2kbits/s speed=1.0x
```
- 解析 `time=HH:MM:SS.ss` 取得已處理時長
- 除以總時長（所有輸入檔案的 duration 加總）得出百分比
- 計算 ETA：`(總時長 - 已處理時長) / speed`

#### 輸出檔名衝突處理

```python
def resolve_output_path(output_dir: str, filename: str, ext: str) -> str:
    """
    若 output_dir/filename.ext 已存在，自動加上編號：
    output.mp4 → output_1.mp4 → output_2.mp4 ...
    """
```

### Checklist
- [ ] 相同格式（MP4+MP4）快速合併成功
- [ ] 異格式（MP4+ASF）重新編碼合併成功
- [ ] ASF 輸入合併後音視訊同步正常
- [ ] 進度 callback 有正確回傳 0~100
- [ ] 取消功能可在 3 秒內停止 FFmpeg
- [ ] 輸出檔名衝突時自動加編號

---

## Phase 4 — 基本 UI

### 目標
建立主視窗，包含檔案清單、輸出設定、進度條與操作按鈕。

### 視窗規格

| 項目 | 規格 |
|------|------|
| 視窗標題 | 影片合併工具 |
| 預設大小 | 900 x 600 px |
| 最小大小 | 700 x 480 px |
| 主題 | CustomTkinter Dark（深色主題） |

### 版面配置

```
┌──────────────────────────────────────────────────────┐
│  工具列：[＋ 新增檔案]  [📁 匯入資料夾]  [🗑 清除全部] │
├───────────────────────────────┬──────────────────────┤
│  檔案清單（左側，可捲動）        │  輸出設定（右側）     │
│                               │                      │
│  # | 檔名 | 格式 | 解析度 | 時長│  輸出格式 [MP4 ▼]   │
│  ─────────────────────────── │                      │
│  1 | a.mp4| MP4 | 1080p | 2:30│  輸出路徑            │
│  2 | b.asf| ASF |  720p | 1:45│  [___________] [選擇]│
│                               │                      │
│  ⚠️ 偵測到混合格式             │  檔名                │
│     將進行重新編碼              │  [output__________] │
│                               │                      │
│                               │  [⚙️ 進階設定]       │
├───────────────────────────────┴──────────────────────┤
│  ████████████░░░░░  60%    預估剩餘時間：1 分 20 秒    │
│                                                      │
│               [▶ 開始合併]    [✕ 取消]               │
└──────────────────────────────────────────────────────┘
```

### 元件說明

#### 工具列（Toolbar）
- `[＋ 新增檔案]`：開啟多選檔案對話框，過濾 `SUPPORTED_INPUT_EXTENSIONS`
- `[📁 匯入資料夾]`：開啟資料夾選擇對話框，遞迴掃描所有影片檔
- `[🗑 清除全部]`：清空清單

#### 檔案清單（File List）
- 欄位：`#`（序號）、`檔名`、`格式`（副檔名大寫）、`解析度`、`時長`（mm:ss）
- `格式` 欄位：不同格式用不同顏色標示（MP4=綠、ASF=橘、其他=灰）
- 每列有 `[✕]` 按鈕可刪除單一檔案
- 混合格式警告列：清單下方顯示 `⚠️ 偵測到混合格式，將進行重新編碼`

#### 輸出設定面板（Settings Panel）
- `輸出格式`：OptionMenu，選項為 MP4 / MKV / MOV / AVI，預設 MP4
- `輸出路徑`：Entry + `[選擇]` 按鈕（開啟資料夾對話框），預設為桌面
- `檔名`：Entry，預設為 `output`（程式自動補副檔名）
- `[⚙️ 進階設定]`：展開/收合進階設定區塊

#### 進度區（Progress Area）
- 進度條：CustomTkinter CTkProgressBar，0~100%
- 進度文字：`60%    預估剩餘時間：1 分 20 秒`
- 合併中：`[▶ 開始合併]` 停用、`[✕ 取消]` 啟用
- 閒置中：`[▶ 開始合併]` 啟用、`[✕ 取消]` 停用

### 狀態機

```
IDLE → （點擊開始合併）→ RUNNING → （完成）→ DONE
                                  → （取消）→ IDLE
                                  → （錯誤）→ ERROR
```

### 執行緒設計

**重要**：合併必須在背景執行緒執行，避免 UI 凍結。

```python
import threading

def start_merge():
    cancel_event = threading.Event()
    thread = threading.Thread(target=run_merge, args=(cancel_event,), daemon=True)
    thread.start()

def run_merge(cancel_event):
    result = merge_videos(..., cancel_event=cancel_event, progress_callback=on_progress)
    # 使用 root.after() 回到主執行緒更新 UI

def on_progress(percent, eta):
    root.after(0, lambda: update_progress_ui(percent, eta))
```

### Checklist
- [ ] 視窗可正常開啟，深色主題正確顯示
- [ ] `[＋ 新增檔案]` 開啟檔案對話框，成功加入清單
- [ ] `[📁 匯入資料夾]` 掃描資料夾並加入所有影片檔
- [ ] `[🗑 清除全部]` 清空清單
- [ ] 清單每列 `[✕]` 可刪除單一檔案
- [ ] 輸出格式下拉可切換
- [ ] 輸出路徑選擇可正常作用
- [ ] 合併中進度條有更新
- [ ] 合併完成後彈出提示
- [ ] 取消後 UI 回到 IDLE 狀態

---

## Phase 5 — 檔案管理功能

### 目標
加入拖曳匯入與清單排序功能。

### 拖曳匯入（Drag & Drop）

使用 `tkinterdnd2` 實作：
- 支援從 Windows 檔案總管拖曳 **單一檔案**、**多個檔案**、**資料夾** 到視窗
- 放入資料夾時，遞迴掃描所有影片檔

```python
from tkinterdnd2 import TkinterDnD, DND_FILES

root = TkinterDnD.Tk()
file_list_widget.drop_target_register(DND_FILES)
file_list_widget.dnd_bind('<<Drop>>', on_drop)

def on_drop(event):
    paths = root.tk.splitlist(event.data)
    for path in paths:
        if os.path.isdir(path):
            scan_folder(path)
        elif is_supported_video(path):
            add_file(path)
```

### 清單排序（拖曳排序）

- 使用滑鼠點住列，上下拖曳調整順序
- 顯示拖曳中的視覺提示（被拖曳列呈半透明，目標位置顯示橫線）

```python
# 實作方式：記錄 drag_start_index，在 ButtonRelease 時計算 drop_index
def on_drag_start(event): ...
def on_drag_motion(event): ...
def on_drag_release(event): ...
```

### 資料夾掃描規格

```python
def scan_folder(folder_path: str, recursive: bool = True) -> list[str]:
    """
    掃描資料夾中所有影片檔。
    recursive=True 時掃描子資料夾。
    回傳檔案路徑清單，依資料夾名稱 + 檔名排序。
    """
```

### 重複檔案處理

- 加入前檢查是否已在清單中（比對絕對路徑）
- 若重複，略過並在狀態列顯示：`已略過 N 個重複檔案`

### Checklist
- [ ] 從檔案總管拖曳單一檔案到視窗，成功加入
- [ ] 拖曳多個檔案，全部成功加入
- [ ] 拖曳資料夾，遞迴掃描所有影片檔並加入
- [ ] 拖曳排序可正常調整順序
- [ ] 重複檔案被略過，有提示訊息

---

## Phase 6 — 異格式警告提示

### 目標
每次清單變動後，自動分析格式並顯示警告。

### 邏輯

```
清單變動（新增/刪除/排序）
         │
         ▼
  對所有檔案執行 probe_file()
  （若已分析過，使用快取，不重複分析）
         │
         ▼
  執行 detect_mixed_format()
         │
    ┌────┴────┐
    │ True    │ → 顯示 ⚠️ 警告列（橘色）
    │ False   │ → 隱藏警告列
    └─────────┘
```

### 格式分析快取

```python
# 使用 dict 快取，key 為絕對路徑
_probe_cache: dict[str, dict] = {}

def get_probe(filepath: str) -> dict:
    if filepath not in _probe_cache:
        _probe_cache[filepath] = probe_file(filepath)
    return _probe_cache[filepath]
```

### 格式 Badge 顏色

| 格式 | 顏色 |
|------|------|
| MP4 | `#4CAF50`（綠） |
| MKV | `#2196F3`（藍） |
| ASF / WMV | `#FF9800`（橘） |
| AVI | `#9C27B0`（紫） |
| 其他 | `#757575`（灰） |

### 清單欄位補充（Phase 2 分析後填入）

分析完成後，清單各列需顯示：
- `格式`：副檔名大寫（`MP4`、`ASF`）
- `解析度`：`1080p` / `720p`（以高度為準）
- `時長`：`mm:ss`（不足補零，例如 `02:30`）

### Checklist
- [ ] 加入單一格式，無警告顯示
- [ ] 加入混合格式，橘色警告正確顯示
- [ ] 刪除異格式檔案後，警告自動消失
- [ ] 格式 badge 顏色正確
- [ ] 解析度與時長欄位正確顯示

---

## Phase 7 — 進階設定

### 目標
提供編碼選擇與硬體加速選項。

### 進階設定面板（可展開/收合）

```
[⚙️ 進階設定 ▼]
┌───────────────────────────────┐
│ 視訊編碼: [自動       ▼]      │  → 自動 / H.264 / H.265 / 複製
│ 音訊編碼: [自動       ▼]      │  → 自動 / AAC / MP3 / 複製
│ 畫質(CRF): [18  ▼]           │  → 0~51，預設 18
│ 硬體加速: [無          ▼]     │  → 無 / NVIDIA / AMD / Intel
└───────────────────────────────┘
```

### 硬體加速偵測

```python
def detect_hw_accel() -> list[str]:
    """
    執行 ffmpeg -hwaccels 並解析輸出，
    回傳可用的加速選項清單。
    例如：["nvenc", "amf", "qsv"]
    """
```

啟動時執行一次，將可用選項填入下拉選單。

### 編碼對應

| 選擇 | 視訊參數 |
|------|---------|
| 自動 | 依輸出格式決定（同 Phase 3 預設） |
| H.264 | `-c:v libx264` |
| H.265 | `-c:v libx265` |
| 複製 | `-c:v copy`（不重新編碼） |
| H.264 + NVIDIA | `-c:v h264_nvenc` |
| H.264 + AMD | `-c:v h264_amf` |
| H.264 + Intel | `-c:v h264_qsv` |

> **注意**：選擇「複製」但清單有異格式時，自動覆蓋為 H.264，並顯示提示。

### Checklist
- [ ] 進階設定面板可正常展開/收合
- [ ] 硬體加速偵測執行成功，有效選項正確列出
- [ ] 選擇 H.265 合併輸出正常
- [ ] 選擇 NVIDIA 加速（若有顯卡）合併正常

---

## Phase 8 — 打包與發佈

### 目標
使用 PyInstaller 打包成可分發的 Windows 應用程式。

### 打包設定（build.spec）

```python
# build.spec
a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[
        ('assets/ffmpeg.exe',  'assets'),
        ('assets/ffprobe.exe', 'assets'),
    ],
    datas=[],
    hiddenimports=['customtkinter', 'tkinterdnd2'],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name='VideoMerger',
    console=False,    # 不顯示 cmd 視窗
    icon='assets/icon.ico',
)
coll = COLLECT(
    exe, a.binaries, a.zipfiles, a.datas,
    name='VideoMerger',
)
```

### 打包指令

```bash
pyinstaller build.spec
```

輸出位置：`dist/VideoMerger/`

### 發佈包結構

```
VideoMerger/           ← 壓縮此資料夾分享
├── VideoMerger.exe
├── assets/
│   ├── ffmpeg.exe
│   └── ffprobe.exe
└── _internal/
```

### 打包前確認清單

- [ ] `assets/icon.ico` 圖示存在（可用線上工具將 PNG 轉 ICO）
- [ ] 所有 import 都在 `hiddenimports` 中
- [ ] 打包後在**無安裝 Python 的乾淨電腦**上測試

### Checklist
- [ ] `pyinstaller build.spec` 無錯誤
- [ ] `dist/VideoMerger/VideoMerger.exe` 可直接執行
- [ ] 在無 Python 的電腦執行正常
- [ ] 合併功能在打包版本中正常運作
- [ ] 視窗不顯示 cmd 黑視窗

---

## 常見問題與解法

### Q1：ASF 合併後音視訊不同步
**解法**：在 FFmpeg 參數加入 `-fflags +genpts`（Phase 3 已涵蓋）

### Q2：H.264 解析度不是偶數導致錯誤
**解法**：加入 `-vf "scale=trunc(iw/2)*2:trunc(ih/2)*2"`（Phase 3 已涵蓋）

### Q3：中文路徑在 FFmpeg 出錯
**解法**：concat list txt 檔使用 UTF-8 編碼，並以絕對路徑寫入

### Q4：拖曳 tkinterdnd2 在打包後失效
**解法**：在 `build.spec` 的 `hiddenimports` 加入 `'tkinterdnd2'`，並確認 DLL 被正確包含

### Q5：PyInstaller 找不到 CustomTkinter 資源
**解法**：在 Analysis 的 `datas` 加入：
```python
datas=[('你的Python路徑/site-packages/customtkinter', 'customtkinter')]
```

---

## 快速開發參考

### 取得執行檔路徑（打包後也有效）

```python
import sys, os

def get_base_dir() -> str:
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

def get_asset(filename: str) -> str:
    return os.path.join(get_base_dir(), 'assets', filename)
```

### 在背景執行 FFmpeg 並解析進度

```python
import subprocess, threading, re

def run_ffmpeg(cmd: list, total_duration: float, progress_cb, cancel_event):
    proc = subprocess.Popen(
        cmd,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        encoding='utf-8',
        errors='replace',
        creationflags=subprocess.CREATE_NO_WINDOW,  # 不顯示 cmd 視窗
    )
    time_pattern = re.compile(r'time=(\d+):(\d+):(\d+\.\d+)')
    for line in proc.stderr:
        if cancel_event.is_set():
            proc.terminate()
            return {"success": False, "error": "已取消"}
        m = time_pattern.search(line)
        if m and total_duration > 0:
            h, min_, sec = float(m.group(1)), float(m.group(2)), float(m.group(3))
            elapsed = h * 3600 + min_ * 60 + sec
            percent = min(elapsed / total_duration * 100, 100)
            progress_cb(percent)
    proc.wait()
    return {"success": proc.returncode == 0, "error": None}
```

---

*規格書版本：1.0 | 最後更新：2026-04-07*
