"""右側歷史面板：顯示全域操作紀錄，點擊可查看詳情。"""

import os
from datetime import datetime

import customtkinter as ctk

from app.core.project import load_global_history


class HistoryPanel(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self._build_ui()
        self.refresh()

    # ── 版面 ────────────────────────────────────────────────────────

    def _build_ui(self):
        # 標題列
        header = ctk.CTkFrame(self, fg_color=("gray85", "gray20"), corner_radius=0)
        header.pack(fill="x")

        ctk.CTkLabel(
            header, text="📋 操作紀錄",
            font=ctk.CTkFont(size=12, weight="bold"),
        ).pack(side="left", padx=10, pady=6)

        ctk.CTkButton(
            header, text="↻", width=28, height=24,
            fg_color="transparent",
            text_color=("gray50", "gray60"),
            hover_color=("gray75", "gray30"),
            command=self.refresh,
        ).pack(side="right", padx=6, pady=4)

        # 捲動清單
        self.scroll = ctk.CTkScrollableFrame(self, label_text="")
        self.scroll.pack(fill="both", expand=True)

    # ── 對外 API ────────────────────────────────────────────────────

    def refresh(self):
        """重新從全域歷史讀取並重繪清單。"""
        for w in self.scroll.winfo_children():
            w.destroy()

        records = load_global_history(limit=50)
        if not records:
            ctk.CTkLabel(
                self.scroll, text="尚無操作紀錄",
                text_color=("gray60", "gray50"),
                font=ctk.CTkFont(size=11),
            ).pack(pady=20)
            return

        for rec in records:
            self._add_row(rec)

    # ── 內部渲染 ────────────────────────────────────────────────────

    def _add_row(self, rec: dict):
        success = rec.get("success", False)
        icon    = "✅" if success else "❌"
        ts      = rec.get("timestamp", "")
        try:
            dt   = datetime.fromisoformat(ts)
            time_str = dt.strftime("%m/%d %H:%M")
        except (ValueError, TypeError):
            time_str = ts[:16] if ts else "—"

        proj_name = rec.get("project_name", "—")
        rec_type  = "合併" if rec.get("type") == "merge" else "字幕"

        # 顯示文字：截短過長的專案名
        disp_name = proj_name if len(proj_name) <= 14 else proj_name[:13] + "…"
        label_text = f"{icon} {time_str}\n    [{rec_type}] {disp_name}"

        row = ctk.CTkButton(
            self.scroll,
            text=label_text,
            anchor="w",
            fg_color="transparent",
            text_color=("#2e7d32", "#81c784") if success else ("#c62828", "#ef9a9a"),
            hover_color=("gray85", "gray25"),
            font=ctk.CTkFont(size=11),
            height=44,
            command=lambda r=rec: self._show_detail(r),
        )
        row.pack(fill="x", padx=2, pady=1)

    def _show_detail(self, rec: dict):
        """彈出詳情視窗。"""
        win = ctk.CTkToplevel(self)
        win.title("操作詳情")
        win.geometry("420x300")
        win.resizable(False, False)
        win.grab_set()

        success     = rec.get("success", False)
        rec_type    = "合併" if rec.get("type") == "merge" else "SRT 字幕"
        ts          = rec.get("timestamp", "—")
        proj_name   = rec.get("project_name", "—")
        input_files = rec.get("input_files", [])
        input_count = rec.get("input_count", len(input_files))
        output_path = rec.get("output_path", "—")
        fmt         = rec.get("output_format", "—")
        duration    = rec.get("duration_sec", 0.0)
        error       = rec.get("error", None)

        # 耗時格式化
        try:
            m, s = divmod(int(duration), 60)
            dur_str = f"{m} 分 {s:02d} 秒" if m else f"{s} 秒"
        except (TypeError, ValueError):
            dur_str = "—"

        # 輸入檔案字串（最多顯示 5 個）
        if len(input_files) > 5:
            files_str = "、".join(input_files[:5]) + f" 等 {input_count} 個"
        else:
            files_str = "、".join(input_files) if input_files else "—"

        status_str = "✅ 成功" if success else f"❌ 失敗：{error or '未知錯誤'}"
        status_color = ("#2e7d32", "#81c784") if success else ("#c62828", "#ef9a9a")

        frame = ctk.CTkFrame(win, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=20, pady=16)

        rows = [
            ("專案",   proj_name),
            ("類型",   rec_type),
            ("時間",   ts.replace("T", "  ")),
            ("輸入",   files_str),
            ("輸出",   output_path),
            ("格式",   fmt),
            ("耗時",   dur_str),
        ]
        for label, value in rows:
            row_f = ctk.CTkFrame(frame, fg_color="transparent")
            row_f.pack(fill="x", pady=1)
            ctk.CTkLabel(row_f, text=f"{label}：", width=44, anchor="e",
                         font=ctk.CTkFont(weight="bold"),
                         text_color=("gray50", "gray55")).pack(side="left")
            # 縮短過長路徑
            disp_val = value
            if len(disp_val) > 45:
                disp_val = "…" + disp_val[-43:]
            ctk.CTkLabel(row_f, text=disp_val, anchor="w",
                         wraplength=310).pack(side="left", padx=(4, 0))

        # 狀態列
        ctk.CTkLabel(
            frame, text=status_str,
            text_color=status_color,
            font=ctk.CTkFont(size=13, weight="bold"),
        ).pack(pady=(8, 0))

        ctk.CTkButton(win, text="關閉", width=80,
                      command=win.destroy).pack(pady=(0, 12))
