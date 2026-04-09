@echo off
chcp 65001 >nul
setlocal

echo ========================================
echo  VideoMerger 綠色程式打包工具
echo ========================================
echo.

:: 確認 assets 存在
if not exist "assets\ffmpeg.exe" (
    echo [錯誤] 找不到 assets\ffmpeg.exe
    echo        請先從 https://www.gyan.dev/ffmpeg/builds/ 下載 FFmpeg
    echo        將 ffmpeg.exe 與 ffprobe.exe 放入 assets\ 資料夾
    pause
    exit /b 1
)
if not exist "assets\ffprobe.exe" (
    echo [錯誤] 找不到 assets\ffprobe.exe
    pause
    exit /b 1
)

:: 安裝 / 更新打包相依套件
echo [1/4] 確認 PyInstaller 已安裝...
pip install pyinstaller --quiet
if errorlevel 1 (
    echo [錯誤] pip install pyinstaller 失敗
    pause
    exit /b 1
)

:: 清除舊的輸出
echo [2/4] 清除舊的建置輸出...
if exist "dist\VideoMerger" (
    rmdir /s /q "dist\VideoMerger"
    echo        已清除 dist\VideoMerger\
)
if exist "build" (
    rmdir /s /q "build"
    echo        已清除 build\
)

:: 執行 PyInstaller
echo [3/4] 開始打包（這可能需要幾分鐘）...
pyinstaller build.spec
if errorlevel 1 (
    echo.
    echo [錯誤] 打包失敗，請查閱上方錯誤訊息
    pause
    exit /b 1
)

:: 建立發布壓縮包
echo [4/4] 建立發布壓縮包...
set ZIPNAME=VideoMerger_portable.zip

:: 使用 PowerShell 壓縮
powershell -Command "Compress-Archive -Path 'dist\VideoMerger' -DestinationPath 'dist\%ZIPNAME%' -Force"
if errorlevel 1 (
    echo [警告] 建立 ZIP 失敗，但 dist\VideoMerger\ 資料夾可直接使用
) else (
    echo        已建立 dist\%ZIPNAME%
)

echo.
echo ========================================
echo  打包完成！
echo ========================================
echo.
echo  攜出方式（擇一）：
echo    1. 壓縮包：dist\%ZIPNAME%
echo    2. 資料夾：dist\VideoMerger\
echo.
echo  執行方式：
echo    直接執行 VideoMerger\VideoMerger.exe
echo    （歷史紀錄自動儲存於 VideoMerger\data\）
echo.
echo  注意：Whisper 語音模型（約 74MB~1.5GB）
echo    首次使用「轉字幕」功能時會自動下載到：
echo    VideoMerger\data\whisper_models\
echo    若要預先內建模型，請見 README.md
echo.

:: 詢問是否開啟輸出資料夾
set /p OPEN="是否開啟輸出資料夾？(Y/N): "
if /i "%OPEN%"=="Y" explorer "dist\VideoMerger"

endlocal
pause
