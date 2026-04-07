"""VideoMerger 程式進入點。"""

import tkinter.messagebox as msgbox

from app.core.ffmpeg import check_ffmpeg
from app.ui.main_window import MainWindow


def main():
    if not check_ffmpeg():
        msgbox.showerror(
            "FFmpeg 未找到",
            "找不到 FFmpeg，請確認 assets/ 資料夾內有 ffmpeg.exe 與 ffprobe.exe。\n"
            "下載位置：https://www.gyan.dev/ffmpeg/builds/",
        )
        return

    app = MainWindow()
    app.mainloop()


if __name__ == "__main__":
    main()
