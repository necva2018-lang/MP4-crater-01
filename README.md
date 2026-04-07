# VideoMerger 影片合併工具

Windows 桌面應用程式，使用 FFmpeg 將多個影片檔案合併為單一檔案。支援混合格式輸入、硬體加速編碼，操作介面採深色主題。

---

## 功能特色

- **多格式輸入**：支援 20 種以上影片格式（MP4、MKV、AVI、ASF、WMV、FLV、WebM、TS 等）
- **智慧合併策略**：相同格式自動走快速合併（不重新編碼）；異格式或不相容編碼自動切換為重新編碼
- **拖曳匯入**：從檔案總管拖曳單一檔案、多個檔案或整個資料夾至視窗
- **清單排序**：以滑鼠拖曳調整合併順序
- **異格式警告**：偵測到混合格式時顯示橘色提示
- **硬體加速**：自動偵測並支援 NVIDIA (NVENC)、AMD (AMF)、Intel (QSV)
- **輸出格式**：MP4 / MKV / MOV / AVI
- **進度顯示**：即時進度條與預估剩餘時間

---

## 系統需求

| 項目 | 需求 |
|------|------|
| 作業系統 | Windows 10 / 11 (64-bit) |
| Python | 3.11 以上 |
| FFmpeg | 6.x（需自行下載放入 `assets/`） |

---

## 安裝步驟

### 1. 下載專案

```bash
git clone https://github.com/necva2018-lang/MP4-crater-01.git
cd MP4-crater-01
```

### 2. 安裝 Python 套件

```bash
pip install -r requirements.txt
```

### 3. 下載 FFmpeg

1. 前往 https://www.gyan.dev/ffmpeg/builds/
2. 下載 `ffmpeg-release-essentials.zip`
3. 解壓縮，進入 `bin/` 資料夾
4. 將 `ffmpeg.exe` 與 `ffprobe.exe` 複製到專案的 `assets/` 資料夾

```
MP4-crater-01/
└── assets/
    ├── ffmpeg.exe    ← 放這裡
    └── ffprobe.exe   ← 放這裡
```

### 4. 執行程式

```bash
python main.py
```

---

## 使用方式

### 加入影片檔案

有三種方式可以加入影片：

- 點擊工具列的 **＋ 新增檔案**，開啟多選對話框
- 點擊 **📁 匯入資料夾**，遞迴掃描資料夾內所有影片
- 從 Windows 檔案總管**直接拖曳**檔案或資料夾到視窗

### 調整合併順序

按住清單左側的 **☰** 圖示，上下拖曳即可調整順序。

### 設定輸出

| 設定項目 | 說明 |
|----------|------|
| 輸出格式 | MP4 / MKV / MOV / AVI |
| 輸出路徑 | 點擊「選擇」按鈕指定資料夾，預設為桌面 |
| 檔名 | 輸出檔名（不含副檔名），同名時自動加編號 |

### 進階設定（可展開）

點擊 **⚙ 進階設定** 展開：

| 選項 | 說明 |
|------|------|
| 視訊編碼 | 自動 / H.264 / H.265 / 複製 |
| 音訊編碼 | 自動 / AAC / MP3 / 複製 |
| 畫質 (CRF) | 0~51，數值越小畫質越好，預設 18 |
| 硬體加速 | 無 / NVIDIA / AMD / Intel（依系統自動偵測可用選項） |

### 開始合併

點擊 **▶ 開始合併**，進度條會顯示目前進度與預估剩餘時間。合併中可點擊 **✕ 取消** 中止。

---

## 支援的輸入格式

`.mp4` `.mkv` `.mov` `.avi` `.wmv` `.asf` `.flv` `.webm` `.ts` `.mts` `.m2ts` `.mpeg` `.mpg` `.3gp` `.ogv` `.dvr-ms` `.mxf` `.vob` `.rm` `.rmvb`

---

## 常見問題

**Q：合併後音視訊不同步？**
程式已自動加入 `-fflags +genpts` 修正 ASF 等格式的時間戳記問題。

**Q：某些格式合併失敗？**
部分編碼（如 TechSmith `tdsc`、WMV 系列）無法直接放入 MP4 容器，程式會自動偵測並切換為重新編碼路線。

**Q：如何合併最快？**
輸入全部使用相同格式（例如都是 H.264 MP4）時，程式走 concat copy 路線，速度最快且不損失畫質。

---

## 專案結構

```
MP4-crater-01/
├── main.py                    # 程式進入點
├── app/
│   ├── core/
│   │   ├── ffmpeg.py          # FFmpeg 路徑管理與可用性檢查
│   │   ├── probe.py           # FFprobe 影片格式分析
│   │   └── merger.py          # 合併核心邏輯
│   ├── ui/
│   │   ├── main_window.py     # 主視窗
│   │   ├── file_list.py       # 檔案清單元件
│   │   └── settings_panel.py  # 輸出設定面板
│   └── utils/
│       └── file_helper.py     # 路徑工具與資料夾掃描
├── assets/                    # 放 ffmpeg.exe / ffprobe.exe
├── requirements.txt
└── CHANGELOG.md
```

---

## 授權

個人使用。FFmpeg 採 LGPL / GPL 授權，詳見 [FFmpeg 官網](https://ffmpeg.org/legal.html)。
