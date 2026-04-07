# Changelog

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
