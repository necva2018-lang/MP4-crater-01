# Changelog

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
