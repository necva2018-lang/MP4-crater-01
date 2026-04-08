"""輸出設定面板（右側）：格式、專案根目錄、專案名稱、進階設定。"""

import os
import tkinter.filedialog as fd

import customtkinter as ctk

from app.core.ffmpeg import detect_hw_accel

OUTPUT_FORMATS = ["MP4", "MKV", "MOV", "AVI"]

# codec label ↔ internal value 對照表
_VCODEC_TO_LABEL = {"auto": "自動", "libx264": "H.264", "libx265": "H.265", "copy": "複製"}
_ACODEC_TO_LABEL = {"auto": "自動", "aac": "AAC",     "mp3": "MP3",       "copy": "複製"}
_HW_TO_LABEL     = {"none": "無", "nvenc": "NVENC (NVIDIA)", "amf": "AMF (AMD)", "qsv": "QSV (Intel)"}


class SettingsPanel(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)

        self._advanced_visible = False

        # ── 輸出格式 ────────────────────────────────────────────────
        ctk.CTkLabel(self, text="輸出格式").pack(anchor="w", padx=16, pady=(16, 2))
        self.format_var = ctk.StringVar(value="MP4")
        self.format_menu = ctk.CTkOptionMenu(
            self, values=OUTPUT_FORMATS, variable=self.format_var,
            width=200, command=self._update_preview,
        )
        self.format_menu.pack(anchor="w", padx=16, pady=(0, 12))

        # ── 輸出根目錄 ───────────────────────────────────────────────
        ctk.CTkLabel(self, text="輸出根目錄").pack(anchor="w", padx=16, pady=(0, 2))
        root_row = ctk.CTkFrame(self, fg_color="transparent")
        root_row.pack(fill="x", padx=16, pady=(0, 8))

        default_dir = os.path.join(os.path.expanduser("~"), "Desktop")
        self.output_root_var = ctk.StringVar(value=default_dir)
        self.output_root_var.trace_add("write", lambda *_: self._update_preview())
        ctk.CTkEntry(root_row, textvariable=self.output_root_var, width=148).pack(
            side="left", fill="x", expand=True)
        ctk.CTkButton(root_row, text="選擇", width=52,
                      command=self._browse_root_dir).pack(side="left", padx=(6, 0))

        # ── 專案名稱 ─────────────────────────────────────────────────
        ctk.CTkLabel(self, text="專案名稱").pack(anchor="w", padx=16, pady=(0, 2))
        self.project_name_var = ctk.StringVar(value="MyProject")
        self.project_name_var.trace_add("write", lambda *_: self._update_preview())
        ctk.CTkEntry(self, textvariable=self.project_name_var, width=200).pack(
            anchor="w", padx=16, pady=(0, 4))

        # ── 路徑預覽 ─────────────────────────────────────────────────
        self.preview_label = ctk.CTkLabel(
            self, text="", text_color=("gray50", "gray55"),
            font=ctk.CTkFont(size=10), wraplength=200, anchor="w", justify="left",
        )
        self.preview_label.pack(anchor="w", padx=16, pady=(0, 10))
        self._update_preview()

        # ── 字幕設定 ─────────────────────────────────────────────────
        ctk.CTkLabel(
            self, text="── 字幕設定 ──",
            text_color=("gray50", "gray55"),
            font=ctk.CTkFont(size=11),
        ).pack(anchor="w", padx=16, pady=(4, 4))

        self.auto_srt_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            self, text="合併後自動產生 SRT",
            variable=self.auto_srt_var,
        ).pack(anchor="w", padx=16, pady=(0, 6))

        model_row = ctk.CTkFrame(self, fg_color="transparent")
        model_row.pack(anchor="w", padx=16, pady=(0, 12))
        ctk.CTkLabel(model_row, text="Whisper 模型：", width=90, anchor="w").pack(side="left")
        self.whisper_model_var = ctk.StringVar(value="base")
        ctk.CTkOptionMenu(
            model_row,
            values=["tiny", "base", "small", "medium"],
            variable=self.whisper_model_var,
            width=100,
        ).pack(side="left")

        # ── 進階設定（可展開） ───────────────────────────────────────
        self.adv_toggle_btn = ctk.CTkButton(
            self,
            text="⚙  進階設定  ▶",
            command=self._toggle_advanced,
            fg_color="transparent",
            text_color=("gray60", "gray40"),
            hover_color=("gray90", "gray20"),
            anchor="w",
        )
        self.adv_toggle_btn.pack(fill="x", padx=16, pady=(4, 0))

        self.adv_frame = ctk.CTkFrame(self)
        self._build_advanced_panel()

    # ── 路徑預覽 ────────────────────────────────────────────────────

    def _update_preview(self, *_):
        root = self.output_root_var.get()
        name = self.project_name_var.get() or "MyProject"
        fmt  = self.format_var.get()
        from app.core.merger import OUTPUT_FORMATS as FMT_MAP
        ext  = FMT_MAP.get(fmt, {}).get("ext", ".mp4")
        preview = os.path.join(root, name, name + ext)
        # 縮短顯示
        if len(preview) > 42:
            preview = "…" + preview[-40:]
        self.preview_label.configure(text=preview)

    # ── 進階設定面板 ────────────────────────────────────────────────

    def _build_advanced_panel(self):
        pad = {"padx": 12, "pady": (6, 2)}

        ctk.CTkLabel(self.adv_frame, text="視訊編碼").pack(anchor="w", **pad)
        self.vcodec_var = ctk.StringVar(value="自動")
        ctk.CTkOptionMenu(
            self.adv_frame,
            values=["自動", "H.264", "H.265", "複製"],
            variable=self.vcodec_var,
            width=180,
        ).pack(anchor="w", padx=12, pady=(0, 8))

        ctk.CTkLabel(self.adv_frame, text="音訊編碼").pack(anchor="w", **pad)
        self.acodec_var = ctk.StringVar(value="自動")
        ctk.CTkOptionMenu(
            self.adv_frame,
            values=["自動", "AAC", "MP3", "複製"],
            variable=self.acodec_var,
            width=180,
        ).pack(anchor="w", padx=12, pady=(0, 8))

        ctk.CTkLabel(self.adv_frame, text="畫質 (CRF)").pack(anchor="w", **pad)
        self.crf_var = ctk.StringVar(value="18")
        ctk.CTkOptionMenu(
            self.adv_frame,
            values=[str(i) for i in range(0, 52)],
            variable=self.crf_var,
            width=100,
        ).pack(anchor="w", padx=12, pady=(0, 8))

        ctk.CTkLabel(self.adv_frame, text="硬體加速").pack(anchor="w", **pad)
        hw_options = ["無"] + detect_hw_accel()
        self.hw_var = ctk.StringVar(value="無")
        ctk.CTkOptionMenu(
            self.adv_frame,
            values=hw_options,
            variable=self.hw_var,
            width=180,
        ).pack(anchor="w", padx=12, pady=(0, 12))

    def _toggle_advanced(self):
        if self._advanced_visible:
            self.adv_frame.pack_forget()
            self.adv_toggle_btn.configure(text="⚙  進階設定  ▶")
        else:
            self.adv_frame.pack(fill="x", padx=16, pady=(0, 8))
            self.adv_toggle_btn.configure(text="⚙  進階設定  ▼")
        self._advanced_visible = not self._advanced_visible

    def _browse_root_dir(self):
        d = fd.askdirectory(title="選擇輸出根目錄")
        if d:
            self.output_root_var.set(d)

    # ── 對外讀取介面 ─────────────────────────────────────────────────

    def get_settings(self) -> dict:
        vcodec_map = {"自動": "auto", "H.264": "libx264", "H.265": "libx265", "複製": "copy"}
        acodec_map = {"自動": "auto", "AAC": "aac",       "MP3": "mp3",       "複製": "copy"}
        hw_map     = {"無": "none", "NVENC (NVIDIA)": "nvenc", "AMF (AMD)": "amf", "QSV (Intel)": "qsv"}
        name = self.project_name_var.get() or "MyProject"
        root = self.output_root_var.get()
        return {
            "output_format":  self.format_var.get(),
            "output_root":    root,
            "project_name":   name,
            "project_dir":    os.path.join(root, name),
            # 保留舊欄位相容性（某些地方仍用 output_dir）
            "output_dir":     os.path.join(root, name),
            "filename":       name,
            "video_codec":    vcodec_map.get(self.vcodec_var.get(), "auto"),
            "audio_codec":    acodec_map.get(self.acodec_var.get(), "auto"),
            "crf":            int(self.crf_var.get()),
            "hw_accel":       hw_map.get(self.hw_var.get(), "none"),
            "auto_srt":       self.auto_srt_var.get(),
            "whisper_model":  self.whisper_model_var.get(),
        }

    def set_settings(self, s: dict) -> None:
        """從字典還原所有設定（用於載入 .vmproj）。"""
        self.format_var.set(s.get("output_format", "MP4"))
        # 相容舊格式：output_root 可能不存在，fallback 到 output_dir
        root = s.get("output_root") or os.path.dirname(s.get("project_dir", "")) or s.get("output_dir", "")
        self.output_root_var.set(root)
        self.project_name_var.set(s.get("project_name") or s.get("filename", "MyProject"))
        self.vcodec_var.set(_VCODEC_TO_LABEL.get(s.get("video_codec", "auto"), "自動"))
        self.acodec_var.set(_ACODEC_TO_LABEL.get(s.get("audio_codec", "auto"), "自動"))
        self.crf_var.set(str(s.get("crf", 18)))
        self.hw_var.set(_HW_TO_LABEL.get(s.get("hw_accel", "none"), "無"))
        self.auto_srt_var.set(bool(s.get("auto_srt", False)))
        self.whisper_model_var.set(s.get("whisper_model", "base"))
        self._update_preview()
