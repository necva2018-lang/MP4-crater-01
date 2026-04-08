# Changelog

## v0.4.0 (2026-04-09)

### 新功能：Project 模式

#### 專案資料夾
- 輸出時自動建立 `{根目錄}/{專案名稱}/` 資料夾，影片、.vmproj、history.json 全部集中在內
- 設定面板拆分為「輸出根目錄」+「專案名稱」，底部即時預覽完整輸出路徑

#### 專案儲存/載入
- 工具列新增 `💾 儲存專案` / `📂 開啟專案` 按鈕
- 存成 `.vmproj`（JSON），記錄檔案清單與所有輸出設定
- 載入後自動還原清單與設定

#### 操作歷史面板
- 右側新增固定歷史面板（190px），顯示最近 50 筆操作（合併 / SRT）
- 全域歷史存於 `%AppData%\VideoMerger\history.json`，重啟後仍保留
- 本地歷史同步寫入專案資料夾的 `history.json`
- 點擊歷史列顯示詳情彈窗（輸入檔、輸出路徑、格式、耗時、成敗）

#### 其他
- 視窗寬度從 900 → 1060px
- 新增 `app/core/project.py`（專案/歷史核心邏輯）
- 新增 `app/ui/history_panel.py`（歷史面板元件）

---

## v0.3.0 (2026-04-09)

### PyInstaller 打包（Phase 8）完成

- 新增 `build.spec`，執行 `pyinstaller build.spec -y` 即可產生 `dist/VideoMerger/VideoMerger.exe`
- 自動包含 `assets/ffmpeg.exe`、`assets/ffprobe.exe`、customtkinter、tkinterdnd2、whisper assets

### 打包 Bug 修正

- **FFmpeg 路徑錯誤**：`get_base_dir()` 改用 `sys._MEIPASS`，正確對應 PyInstaller 6.x 的 `_internal/` 目錄
- **Whisper assets 遺失**：`build.spec` 手動加入 `whisper/assets`（含 `mel_filters.npz` 等資源）
- **語音辨識 NoneType 錯誤**：`console=False` 打包後 `sys.stdout/stderr` 為 None，改為呼叫 Whisper 前暫時替換為 `io.StringIO()`

### 測試狀態
影片合併、異格式重新編碼、CC 字幕辨識，打包版全部測試通過（2026-04-09）。

---

## v0.2.0 (2026-04-08)

### 新功能：語音轉文字 SRT 字幕

#### 功能說明
- 新增 `app/core/transcriber.py`：使用 OpenAI Whisper（本機）將影片音訊辨識為 SRT 字幕檔
- 語言固定為繁體中文（`initial_prompt` 引導輸出繁體字）
- 字幕檔以 UTF-8 BOM 編碼寫入，Windows 播放器（MPC、PotPlayer）直接開啟無亂碼

#### UI 變更
- 設定面板新增「字幕設定」區塊：勾選「合併後自動產生 SRT」、選擇 Whisper 模型（tiny / base / small / medium）
- 檔案清單每列新增「CC」藍色按鈕，可對單一影片產生 SRT（存於影片同目錄）
- 辨識中進度條顯示脈衝動畫，狀態列顯示目前步驟

#### 問題修正
- 修正 Whisper 內部呼叫系統 `ffmpeg` 導致 `[WinError 2] 找不到檔案` 的錯誤
  - 根本原因：`model.transcribe(影片路徑)` 會呼叫系統 PATH 中的 `ffmpeg`，但本專案的 ffmpeg 在 `assets/` 非 PATH
  - 解法：先用 `assets/ffmpeg.exe` 提取音訊為暫存 WAV（16kHz 單聲道），再以 Python `wave` 模組讀成 numpy 陣列，直接傳給 `model.transcribe()`，完全繞過 Whisper 內部的 ffmpeg 呼叫

#### 安裝需求
```bash
pip install openai-whisper
```
首次使用時 Whisper 會自動下載模型（base ≈ 145MB）

---

## v0.1.0 (2026-04-08)

### 首次發佈

#### 核心功能
- **Phase 1**：專案骨架建立，FFmpeg / FFprobe 可用性檢查（`app/core/ffmpeg.py`）
- **Phase 2**：FFprobe 影片格式分析模組，支援解析編碼、解析度、時長、音訊資訊（`app/core/probe.py`）；含模組級快取避免重複分析
- **Phase 3**：FFmpeg 合併核心，自動判斷快速合併（concat copy）或重新編碼路線；支援進度 callback 與取消事件（`app/core/merger.py`）

#### UI
- **Phase 4**：CustomTkinter 深色主題主視窗（900×600）；工具列、可捲動檔案清單、輸出設定面板、進度條、開始／取消按鈕；合併在背景執行緒執行
- **Phase 5**：清單列拖曳排序（含橘色插入指示線）；從 Windows 檔案總管拖曳檔案 / 資料夾匯入；重複檔案自動略過
- **Phase 6**：異格式偵測警告（橘色警告列）；格式 Badge 顏色（MP4=綠、MKV/MOV=藍、ASF/WMV=橘、AVI=紫）；解析度與時長欄位自動填入
- **Phase 7**：進階設定面板（可展開）；視訊編碼 / 音訊編碼 / CRF 畫質 / 硬體加速選項；`detect_hw_accel()` 啟動時自動偵測 NVIDIA / AMD / Intel

#### 問題修正
- 修正 `tdsc`（TechSmith Screen Capture）等不相容編碼直接 copy 至 MP4 容器導致合併失敗的問題；新增容器相容性白名單，自動切換為重新編碼路線
- 合併失敗時顯示 FFmpeg 實際錯誤輸出，方便診斷

#### 支援格式
- 輸入：`.mp4` `.mkv` `.mov` `.avi` `.wmv` `.asf` `.flv` `.webm` `.ts` `.mts` `.m2ts` `.mpeg` `.mpg` `.3gp` `.ogv` `.dvr-ms` `.mxf` `.vob` `.rm` `.rmvb`
- 輸出：MP4 / MKV / MOV / AVI
