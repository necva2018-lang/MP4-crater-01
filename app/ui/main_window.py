"""主視窗：整合工具列、檔案清單、設定面板、進度區。"""

import os
import threading
import tkinter.filedialog as fd
import tkinter.messagebox as msgbox

import customtkinter as ctk
from tkinterdnd2 import TkinterDnD, DND_FILES

from app.core.merger import merge_videos, OUTPUT_FORMATS
from app.utils.file_helper import is_supported_video, scan_folder, resolve_output_path
from app.ui.file_list import FileListPanel
from app.ui.settings_panel import SettingsPanel

# 狀態常數
IDLE    = "IDLE"
RUNNING = "RUNNING"
DONE    = "DONE"
ERROR   = "ERROR"


class MainWindow(TkinterDnD.Tk):
    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.title("影片合併工具")
        self.geometry("900x620")
        self.minsize(700, 480)

        self._state = IDLE
        self._cancel_event: threading.Event | None = None
        self._skipped_count = 0

        self._build_ui()
        self._set_state(IDLE)

        # 拖曳放下
        self.drop_target_register(DND_FILES)
        self.dnd_bind("<<Drop>>", self._on_drop)

    # ── 版面建置 ────────────────────────────────────────────────────

    def _build_ui(self):
        # 工具列
        toolbar = ctk.CTkFrame(self, height=44, corner_radius=0)
        toolbar.pack(fill="x", side="top")
        toolbar.pack_propagate(False)

        ctk.CTkButton(
            toolbar, text="＋ 新增檔案", width=110, command=self._add_files
        ).pack(side="left", padx=(8, 4), pady=6)
        ctk.CTkButton(
            toolbar, text="📁 匯入資料夾", width=120, command=self._import_folder
        ).pack(side="left", padx=4, pady=6)
        ctk.CTkButton(
            toolbar, text="🗑 清除全部", width=110,
            fg_color="transparent", border_width=1,
            command=self._clear_all,
        ).pack(side="left", padx=4, pady=6)

        self.status_label = ctk.CTkLabel(toolbar, text="", text_color="gray60")
        self.status_label.pack(side="left", padx=12)

        # 主體（左右分割）
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=8, pady=(4, 0))

        # 左側：檔案清單
        self.file_list = FileListPanel(
            body, on_list_changed=self._on_list_changed
        )
        self.file_list.pack(side="left", fill="both", expand=True, padx=(0, 4))

        # 右側：設定面板
        self.settings = SettingsPanel(body, width=230)
        self.settings.pack(side="right", fill="y")
        self.settings.pack_propagate(False)

        # 底部：進度區
        bottom = ctk.CTkFrame(self, corner_radius=0, height=110)
        bottom.pack(fill="x", side="bottom")
        bottom.pack_propagate(False)

        prog_row = ctk.CTkFrame(bottom, fg_color="transparent")
        prog_row.pack(fill="x", padx=12, pady=(10, 2))

        self.progress_bar = ctk.CTkProgressBar(prog_row)
        self.progress_bar.set(0)
        self.progress_bar.pack(side="left", fill="x", expand=True, padx=(0, 10))

        self.progress_label = ctk.CTkLabel(prog_row, text="0%", width=40)
        self.progress_label.pack(side="left")

        self.eta_label = ctk.CTkLabel(bottom, text="", text_color="gray60", font=ctk.CTkFont(size=12))
        self.eta_label.pack()

        btn_row = ctk.CTkFrame(bottom, fg_color="transparent")
        btn_row.pack(pady=(6, 10))

        self.start_btn = ctk.CTkButton(
            btn_row, text="▶  開始合併", width=160, height=40,
            font=ctk.CTkFont(size=15), command=self._start_merge,
        )
        self.start_btn.pack(side="left", padx=8)

        self.cancel_btn = ctk.CTkButton(
            btn_row, text="✕  取消", width=130, height=40,
            font=ctk.CTkFont(size=15),
            fg_color="#C62828", hover_color="#B71C1C",
            command=self._cancel_merge,
        )
        self.cancel_btn.pack(side="left", padx=8)

    # ── 工具列動作 ──────────────────────────────────────────────────

    def _add_files(self):
        exts = " ".join(f"*{e}" for e in [
            ".mp4", ".mkv", ".mov", ".avi", ".wmv", ".asf", ".flv",
            ".webm", ".ts", ".mts", ".m2ts", ".mpeg", ".mpg",
        ])
        paths = fd.askopenfilenames(
            title="選擇影片檔案",
            filetypes=[("影片檔案", exts), ("所有檔案", "*.*")],
        )
        if paths:
            added = self.file_list.add_files(list(paths))
            self._show_status(f"已加入 {added} 個檔案")

    def _import_folder(self):
        folder = fd.askdirectory(title="選擇資料夾")
        if folder:
            files = scan_folder(folder)
            added = self.file_list.add_files(files)
            self._show_status(f"已加入 {added} 個檔案")

    def _clear_all(self):
        self.file_list.clear()
        self._show_status("清單已清空")

    # ── 拖曳放下 ────────────────────────────────────────────────────

    def _on_drop(self, event):
        paths = self.tk.splitlist(event.data)
        files_to_add = []
        for p in paths:
            # 移除 Windows 路徑的大括號包裝
            p = p.strip("{}")
            if os.path.isdir(p):
                files_to_add.extend(scan_folder(p))
            elif is_supported_video(p):
                files_to_add.append(p)
        if files_to_add:
            added = self.file_list.add_files(files_to_add)
            skipped = len(files_to_add) - added
            msg = f"已加入 {added} 個檔案"
            if skipped:
                msg += f"，略過 {skipped} 個重複"
            self._show_status(msg)

    # ── 清單變動 ────────────────────────────────────────────────────

    def _on_list_changed(self):
        pass  # 目前由 FileListPanel 內部處理警告更新

    # ── 合併流程 ────────────────────────────────────────────────────

    def _start_merge(self):
        files = self.file_list.get_files()
        if not files:
            msgbox.showwarning("無檔案", "請先加入要合併的影片檔案。")
            return

        s = self.settings.get_settings()
        ext = OUTPUT_FORMATS[s["output_format"]]["ext"]
        output_path = resolve_output_path(s["output_dir"], s["filename"], ext)

        self._cancel_event = threading.Event()
        self._set_state(RUNNING)

        thread = threading.Thread(
            target=self._run_merge,
            args=(files, output_path, s, self._cancel_event),
            daemon=True,
        )
        thread.start()

    def _run_merge(self, files, output_path, settings, cancel_event):
        result = merge_videos(
            input_files=files,
            output_path=output_path,
            output_format=settings["output_format"],
            video_codec=settings["video_codec"],
            audio_codec=settings["audio_codec"],
            crf=settings["crf"],
            hw_accel=settings["hw_accel"],
            progress_callback=lambda pct, eta: self.after(0, self._on_progress, pct, eta),
            cancel_event=cancel_event,
        )
        self.after(0, self._on_merge_done, result, output_path)

    def _cancel_merge(self):
        if self._cancel_event:
            self._cancel_event.set()

    def _on_progress(self, percent: float, eta: float):
        self.progress_bar.set(percent / 100)
        self.progress_label.configure(text=f"{percent:.0f}%")
        if eta > 0:
            m, s = divmod(int(eta), 60)
            self.eta_label.configure(text=f"預估剩餘：{m} 分 {s:02d} 秒")

    def _on_merge_done(self, result: dict, output_path: str):
        # 顯示「複製 + 異格式」自動覆蓋提示
        if result.get("warning"):
            self._show_status(f"⚠ {result['warning']}")

        if result["success"]:
            self._set_state(DONE)
            self._on_progress(100, 0)
            self.eta_label.configure(text="合併完成！")
            msgbox.showinfo("完成", f"合併完成！\n儲存至：{output_path}")
        else:
            err = result.get("error", "未知錯誤")
            if "取消" in err:
                self._set_state(IDLE)
                self.eta_label.configure(text="已取消")
            else:
                self._set_state(ERROR)
                self.eta_label.configure(text=f"錯誤：{err}")
                msgbox.showerror("合併失敗", err)

    # ── 狀態機 ──────────────────────────────────────────────────────

    def _set_state(self, state: str):
        self._state = state
        if state == IDLE:
            self.start_btn.configure(state="normal")
            self.cancel_btn.configure(state="disabled")
            self.progress_bar.set(0)
            self.progress_label.configure(text="0%")
            self.eta_label.configure(text="")
        elif state == RUNNING:
            self.start_btn.configure(state="disabled")
            self.cancel_btn.configure(state="normal")
        elif state in (DONE, ERROR):
            self.start_btn.configure(state="normal")
            self.cancel_btn.configure(state="disabled")

    def _show_status(self, msg: str):
        self.status_label.configure(text=msg)
        self.after(4000, lambda: self.status_label.configure(text=""))
