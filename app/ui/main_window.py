"""主視窗：整合工具列、檔案清單、設定面板、歷史面板、進度區。"""

import os
import time
import threading
import tkinter.filedialog as fd
import tkinter.messagebox as msgbox

import customtkinter as ctk
from tkinterdnd2 import TkinterDnD, DND_FILES

from app.core.merger import merge_videos, OUTPUT_FORMATS
from app.core.transcriber import check_whisper, transcribe_to_srt
from app.core.project import (
    ensure_project_dir, get_project_output_path,
    save_project, load_project,
    make_and_save_record,
)
from app.utils.file_helper import is_supported_video, scan_folder
from app.ui.file_list import FileListPanel
from app.ui.settings_panel import SettingsPanel
from app.ui.history_panel import HistoryPanel

# 狀態常數
IDLE         = "IDLE"
RUNNING      = "RUNNING"
TRANSCRIBING = "TRANSCRIBING"
BATCH_SRT    = "BATCH_SRT"
DONE         = "DONE"
ERROR        = "ERROR"


class MainWindow(TkinterDnD.Tk):
    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.title("影片合併工具")
        self.geometry("1060x620")
        self.minsize(860, 480)

        self._state = IDLE
        self._cancel_event: threading.Event | None = None
        self._merge_start_time: float = 0.0
        self._current_project_dir: str = ""
        self._current_project_name: str = ""
        self._current_input_files: list[str] = []
        self._batch_cancel_event: threading.Event | None = None
        self._pulse_job = None
        self._pulse_dir = 1
        self._pulse_val = 0.0

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

        # 分隔
        ctk.CTkFrame(toolbar, width=1, height=28,
                     fg_color=("gray70", "gray40")).pack(side="left", padx=8, pady=8)

        ctk.CTkButton(
            toolbar, text="💾 儲存專案", width=110,
            fg_color="transparent", border_width=1,
            command=self._save_project,
        ).pack(side="left", padx=4, pady=6)
        ctk.CTkButton(
            toolbar, text="📂 開啟專案", width=110,
            fg_color="transparent", border_width=1,
            command=self._open_project,
        ).pack(side="left", padx=4, pady=6)

        # 分隔
        ctk.CTkFrame(toolbar, width=1, height=28,
                     fg_color=("gray70", "gray40")).pack(side="left", padx=8, pady=8)

        self.srt_batch_btn = ctk.CTkButton(
            toolbar, text="🎤 批次轉字幕", width=120,
            fg_color=("#1565C0", "#1976D2"),
            hover_color=("#0D47A1", "#1565C0"),
            command=self._start_batch_srt,
        )
        self.srt_batch_btn.pack(side="left", padx=4, pady=6)

        self.status_label = ctk.CTkLabel(toolbar, text="", text_color="gray60")
        self.status_label.pack(side="left", padx=12)

        # 主體（三欄）
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=8, pady=(4, 0))

        # 左側：檔案清單
        self.file_list = FileListPanel(
            body,
            on_list_changed=self._on_list_changed,
            on_generate_srt=self._generate_srt_for_file,
        )
        self.file_list.pack(side="left", fill="both", expand=True, padx=(0, 4))

        # 中間：設定面板
        self.settings = SettingsPanel(body, width=250)
        self.settings.pack(side="left", fill="y", padx=(0, 4))
        self.settings.pack_propagate(False)

        # 右側：歷史面板
        self.history_panel = HistoryPanel(body, width=190)
        self.history_panel.pack(side="right", fill="y")
        self.history_panel.pack_propagate(False)

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

        self.eta_label = ctk.CTkLabel(
            bottom, text="", text_color="gray60", font=ctk.CTkFont(size=12))
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

    # ── 專案儲存/載入 ────────────────────────────────────────────────

    def _save_project(self):
        files = self.file_list.get_files()
        if not files:
            msgbox.showwarning("無檔案", "請先加入要合併的影片檔案。")
            return
        s = self.settings.get_settings()
        project_dir  = ensure_project_dir(s["output_root"], s["project_name"])
        project_name = s["project_name"]
        try:
            vmproj_path = save_project(project_dir, project_name, files, s)
            self._show_status(f"已儲存：{os.path.basename(vmproj_path)}")
        except OSError as e:
            msgbox.showerror("儲存失敗", str(e))

    def _open_project(self):
        path = fd.askopenfilename(
            title="開啟專案",
            filetypes=[("VideoMerger 專案", "*.vmproj"), ("所有檔案", "*.*")],
        )
        if not path:
            return
        try:
            data = load_project(path)
        except ValueError as e:
            msgbox.showerror("開啟失敗", str(e))
            return
        self.file_list.clear()
        added = self.file_list.add_files(data["files"])
        self.settings.set_settings(data["settings"])
        self._show_status(f"已載入：{os.path.basename(path)}（{added} 個檔案）")

    # ── 拖曳放下 ────────────────────────────────────────────────────

    def _on_drop(self, event):
        paths = self.tk.splitlist(event.data)
        files_to_add = []
        for p in paths:
            p = p.strip("{}")
            if os.path.isdir(p):
                files_to_add.extend(scan_folder(p))
            elif is_supported_video(p):
                files_to_add.append(p)
        if files_to_add:
            added   = self.file_list.add_files(files_to_add)
            skipped = len(files_to_add) - added
            msg = f"已加入 {added} 個檔案"
            if skipped:
                msg += f"，略過 {skipped} 個重複"
            self._show_status(msg)

    # ── 清單變動 ────────────────────────────────────────────────────

    def _on_list_changed(self):
        pass

    # ── 合併流程 ────────────────────────────────────────────────────

    def _start_merge(self):
        files = self.file_list.get_files()
        if not files:
            msgbox.showwarning("無檔案", "請先加入要合併的影片檔案。")
            return

        s            = self.settings.get_settings()
        project_name = s["project_name"] or "MyProject"
        project_dir  = ensure_project_dir(s["output_root"], project_name)
        ext          = OUTPUT_FORMATS[s["output_format"]]["ext"]
        output_path  = get_project_output_path(project_dir, project_name, ext)

        # 記錄以供歷史用
        self._current_project_dir  = project_dir
        self._current_project_name = project_name
        self._current_input_files  = list(files)
        self._merge_start_time     = time.time()

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
        self.after(0, self._on_merge_done, result, output_path, settings)

    def _cancel_merge(self):
        if self._cancel_event:
            self._cancel_event.set()
        if self._batch_cancel_event:
            self._batch_cancel_event.set()

    def _on_progress(self, percent: float, eta: float):
        self.progress_bar.set(percent / 100)
        self.progress_label.configure(text=f"{percent:.0f}%")
        if eta > 0:
            m, s = divmod(int(eta), 60)
            self.eta_label.configure(text=f"預估剩餘：{m} 分 {s:02d} 秒")

    def _on_merge_done(self, result: dict, output_path: str, settings: dict):
        duration_sec = time.time() - self._merge_start_time

        if result.get("warning"):
            self._show_status(f"⚠ {result['warning']}")

        if result["success"]:
            self._on_progress(100, 0)
            self.eta_label.configure(text="合併完成！")

            # 寫入歷史
            make_and_save_record(
                record_type="merge",
                project_name=self._current_project_name,
                project_dir=self._current_project_dir,
                input_files=self._current_input_files,
                output_path=output_path,
                success=True,
                error=None,
                duration_sec=duration_sec,
                output_format=settings["output_format"],
            )
            self.history_panel.refresh()

            if settings.get("auto_srt"):
                self._set_state(TRANSCRIBING)
                srt_path = os.path.splitext(output_path)[0] + ".srt"
                self._start_transcription(
                    video_path=output_path,
                    srt_path=srt_path,
                    model_size=settings["whisper_model"],
                    on_done=lambda r: self._on_srt_done(r, output_path, auto=True),
                )
            else:
                self._set_state(DONE)
                msgbox.showinfo("完成", f"合併完成！\n儲存至：{output_path}")
        else:
            err = result.get("error", "未知錯誤")

            # 寫入失敗歷史
            make_and_save_record(
                record_type="merge",
                project_name=self._current_project_name,
                project_dir=self._current_project_dir,
                input_files=self._current_input_files,
                output_path=output_path,
                success=False,
                error=err,
                duration_sec=duration_sec,
                output_format=settings["output_format"],
            )
            self.history_panel.refresh()

            if "取消" in err:
                self._set_state(IDLE)
                self.eta_label.configure(text="已取消")
            else:
                self._set_state(ERROR)
                self.eta_label.configure(text=f"錯誤：{err}")
                msgbox.showerror("合併失敗", err)

    # ── 批次轉字幕 ───────────────────────────────────────────────────

    def _start_batch_srt(self):
        """批次對清單所有檔案進行語音辨識，SRT 存至使用者指定目錄。"""
        if not check_whisper():
            msgbox.showwarning(
                "尚未安裝 Whisper",
                "請先在終端機執行：\npip install openai-whisper",
            )
            return

        files = self.file_list.get_files()
        if not files:
            msgbox.showwarning("無檔案", "請先加入要辨識的影片檔案。")
            return

        # 選擇 SRT 輸出目錄（預設使用目前專案目錄）
        s = self.settings.get_settings()
        default_dir = s.get("project_dir") or s.get("output_root", "")
        out_dir = fd.askdirectory(
            title="選擇 SRT 字幕輸出目錄",
            initialdir=default_dir or os.path.expanduser("~"),
        )
        if not out_dir:
            return

        model_size = s.get("whisper_model", "base")
        self._batch_cancel_event = threading.Event()
        self._set_state(BATCH_SRT)
        self.progress_bar.set(0)
        self.progress_label.configure(text="0%")
        self.eta_label.configure(text=f"準備辨識 {len(files)} 個檔案…")

        thread = threading.Thread(
            target=self._run_batch_srt,
            args=(files, out_dir, model_size, self._batch_cancel_event),
            daemon=True,
        )
        thread.start()

    def _run_batch_srt(self, files: list[str], out_dir: str,
                       model_size: str, cancel_event: threading.Event):
        total    = len(files)
        success  = 0
        failed   = 0
        skipped  = 0
        start_t  = time.time()

        os.makedirs(out_dir, exist_ok=True)

        for idx, video_path in enumerate(files, start=1):
            if cancel_event.is_set():
                skipped = total - idx + 1
                break

            basename = os.path.splitext(os.path.basename(video_path))[0]
            srt_path = os.path.join(out_dir, basename + ".srt")

            # 更新進度
            self.after(0, self._batch_progress_update,
                       idx, total, os.path.basename(video_path))

            result = transcribe_to_srt(
                video_path=video_path,
                output_srt_path=srt_path,
                model_size=model_size,
                status_callback=lambda msg: self.after(
                    0, self.eta_label.configure, {"text": msg}),
                cancel_event=cancel_event,
            )

            if result["success"]:
                success += 1
                make_and_save_record(
                    record_type="srt",
                    project_name=self._current_project_name or basename,
                    project_dir=self._current_project_dir or out_dir,
                    input_files=[video_path],
                    output_path=srt_path,
                    success=True,
                    error=None,
                    duration_sec=time.time() - start_t,
                    output_format="SRT",
                )
            else:
                failed += 1
                make_and_save_record(
                    record_type="srt",
                    project_name=self._current_project_name or basename,
                    project_dir=self._current_project_dir or out_dir,
                    input_files=[video_path],
                    output_path=srt_path,
                    success=False,
                    error=result.get("error"),
                    duration_sec=time.time() - start_t,
                    output_format="SRT",
                )

        self.after(0, self._on_batch_srt_done, success, failed, skipped, out_dir)

    def _batch_progress_update(self, idx: int, total: int, filename: str):
        pct = (idx - 1) / total * 100
        self.progress_bar.set(pct / 100)
        self.progress_label.configure(text=f"{idx}/{total}")
        self.eta_label.configure(text=f"辨識中：{filename}")

    def _on_batch_srt_done(self, success: int, failed: int,
                           skipped: int, out_dir: str):
        self._stop_pulse()
        self.history_panel.refresh()
        self.progress_bar.set(1.0)
        self.progress_label.configure(text="完成")

        lines = [f"批次轉字幕完成！\n輸出目錄：{out_dir}\n"]
        lines.append(f"✅ 成功：{success} 個")
        if failed:
            lines.append(f"❌ 失敗：{failed} 個")
        if skipped:
            lines.append(f"⏭ 已略過（取消）：{skipped} 個")

        self._set_state(DONE)
        self.eta_label.configure(text=f"完成 {success}/{success+failed} 個")
        msgbox.showinfo("批次轉字幕完成", "\n".join(lines))

    # ── SRT 產生流程 ─────────────────────────────────────────────────

    def _generate_srt_for_file(self, video_path: str):
        if not check_whisper():
            msgbox.showwarning(
                "尚未安裝 Whisper",
                "請先在終端機執行：\npip install openai-whisper",
            )
            return
        if self._state == TRANSCRIBING:
            msgbox.showinfo("辨識中", "目前已有辨識工作進行中，請稍候。")
            return

        srt_path   = os.path.splitext(video_path)[0] + ".srt"
        model_size = self.settings.get_settings().get("whisper_model", "base")
        self._merge_start_time = time.time()
        self._set_state(TRANSCRIBING)
        self._start_transcription(
            video_path=video_path,
            srt_path=srt_path,
            model_size=model_size,
            on_done=lambda r: self._on_srt_done(r, srt_path, auto=False),
        )

    def _start_transcription(self, video_path, srt_path, model_size, on_done):
        def worker():
            result = transcribe_to_srt(
                video_path=video_path,
                output_srt_path=srt_path,
                model_size=model_size,
                status_callback=lambda msg: self.after(0, self.eta_label.configure, {"text": msg}),
            )
            self.after(0, on_done, result)

        threading.Thread(target=worker, daemon=True).start()

    def _on_srt_done(self, result: dict, path: str, auto: bool):
        self._stop_pulse()
        duration_sec = time.time() - self._merge_start_time
        srt_path = os.path.splitext(path)[0] + ".srt" if auto else path

        if result["success"]:
            self._set_state(DONE)
            self.eta_label.configure(text="字幕產生完成！")
            make_and_save_record(
                record_type="srt",
                project_name=self._current_project_name,
                project_dir=self._current_project_dir,
                input_files=[path],
                output_path=srt_path,
                success=True,
                error=None,
                duration_sec=duration_sec,
                output_format="SRT",
            )
            self.history_panel.refresh()
            msgbox.showinfo("完成", f"SRT 字幕已產生：\n{srt_path}")
        else:
            err = result.get("error", "未知錯誤")
            self._set_state(ERROR)
            self.eta_label.configure(text=f"辨識失敗：{err}")
            make_and_save_record(
                record_type="srt",
                project_name=self._current_project_name,
                project_dir=self._current_project_dir,
                input_files=[path],
                output_path=srt_path,
                success=False,
                error=err,
                duration_sec=duration_sec,
                output_format="SRT",
            )
            self.history_panel.refresh()
            msgbox.showerror("語音辨識失敗", err)

    # ── 脈衝進度動畫 ────────────────────────────────────────────────

    def _start_pulse(self):
        self._pulse_val = 0.0
        self._pulse_dir = 1
        self._pulse_step()

    def _pulse_step(self):
        self._pulse_val += self._pulse_dir * 0.03
        if self._pulse_val >= 1.0:
            self._pulse_val, self._pulse_dir = 1.0, -1
        elif self._pulse_val <= 0.0:
            self._pulse_val, self._pulse_dir = 0.0, 1
        self.progress_bar.set(self._pulse_val)
        self._pulse_job = self.after(80, self._pulse_step)

    def _stop_pulse(self):
        if self._pulse_job:
            self.after_cancel(self._pulse_job)
            self._pulse_job = None
        self.progress_bar.set(0)

    # ── 狀態機 ──────────────────────────────────────────────────────

    def _set_state(self, state: str):
        self._state = state
        if state == IDLE:
            self._stop_pulse()
            self.start_btn.configure(state="normal")
            self.cancel_btn.configure(state="disabled")
            self.srt_batch_btn.configure(state="normal")
            self.progress_bar.set(0)
            self.progress_label.configure(text="0%")
            self.eta_label.configure(text="")
        elif state == RUNNING:
            self.start_btn.configure(state="disabled")
            self.cancel_btn.configure(state="normal")
            self.srt_batch_btn.configure(state="disabled")
        elif state == TRANSCRIBING:
            self.start_btn.configure(state="disabled")
            self.cancel_btn.configure(state="disabled")
            self.srt_batch_btn.configure(state="disabled")
            self.progress_label.configure(text="辨識中")
            self._start_pulse()
        elif state == BATCH_SRT:
            self.start_btn.configure(state="disabled")
            self.cancel_btn.configure(state="normal")   # 允許取消批次
            self.srt_batch_btn.configure(state="disabled")
            self._start_pulse()
        elif state in (DONE, ERROR):
            self._stop_pulse()
            self.start_btn.configure(state="normal")
            self.cancel_btn.configure(state="disabled")
            self.srt_batch_btn.configure(state="normal")

    def _show_status(self, msg: str):
        self.status_label.configure(text=msg)
        self.after(4000, lambda: self.status_label.configure(text=""))
