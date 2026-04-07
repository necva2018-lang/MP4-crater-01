"""輸出設定面板（右側）：格式、路徑、檔名、進階設定。"""

import os
import tkinter.filedialog as fd

import customtkinter as ctk

from app.core.ffmpeg import detect_hw_accel

OUTPUT_FORMATS = ["MP4", "MKV", "MOV", "AVI"]


class SettingsPanel(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)

        self._advanced_visible = False

        # ── 輸出格式 ────────────────────────────────────────────────
        ctk.CTkLabel(self, text="輸出格式").pack(anchor="w", padx=16, pady=(16, 2))
        self.format_var = ctk.StringVar(value="MP4")
        self.format_menu = ctk.CTkOptionMenu(
            self, values=OUTPUT_FORMATS, variable=self.format_var, width=200
        )
        self.format_menu.pack(anchor="w", padx=16, pady=(0, 12))

        # ── 輸出路徑 ────────────────────────────────────────────────
        ctk.CTkLabel(self, text="輸出路徑").pack(anchor="w", padx=16, pady=(0, 2))
        path_row = ctk.CTkFrame(self, fg_color="transparent")
        path_row.pack(fill="x", padx=16, pady=(0, 12))

        default_dir = os.path.join(os.path.expanduser("~"), "Desktop")
        self.path_var = ctk.StringVar(value=default_dir)
        self.path_entry = ctk.CTkEntry(path_row, textvariable=self.path_var, width=150)
        self.path_entry.pack(side="left", fill="x", expand=True)

        ctk.CTkButton(
            path_row, text="選擇", width=60, command=self._browse_dir
        ).pack(side="left", padx=(6, 0))

        # ── 檔名 ─────────────────────────────────────────────────────
        ctk.CTkLabel(self, text="檔名").pack(anchor="w", padx=16, pady=(0, 2))
        self.filename_var = ctk.StringVar(value="output")
        ctk.CTkEntry(self, textvariable=self.filename_var, width=200).pack(
            anchor="w", padx=16, pady=(0, 12)
        )

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
        # 預設收合，不 pack

        self._build_advanced_panel()

    # ── 進階設定面板內容 ────────────────────────────────────────────

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

    def _browse_dir(self):
        d = fd.askdirectory(title="選擇輸出資料夾")
        if d:
            self.path_var.set(d)

    # ── 對外讀取介面 ─────────────────────────────────────────────────

    def get_settings(self) -> dict:
        """回傳目前設定值字典。"""
        vcodec_map = {"自動": "auto", "H.264": "libx264", "H.265": "libx265", "複製": "copy"}
        acodec_map = {"自動": "auto", "AAC": "aac", "MP3": "mp3", "複製": "copy"}
        hw_map = {"無": "none", "NVENC (NVIDIA)": "nvenc", "AMF (AMD)": "amf", "QSV (Intel)": "qsv"}
        return {
            "output_format": self.format_var.get(),
            "output_dir":    self.path_var.get(),
            "filename":      self.filename_var.get() or "output",
            "video_codec":   vcodec_map.get(self.vcodec_var.get(), "auto"),
            "audio_codec":   acodec_map.get(self.acodec_var.get(), "auto"),
            "crf":           int(self.crf_var.get()),
            "hw_accel":      hw_map.get(self.hw_var.get(), "none"),
        }
