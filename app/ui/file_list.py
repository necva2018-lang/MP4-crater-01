"""檔案清單元件：顯示待合併影片，支援新增、刪除、拖曳排序、異格式警告。"""

import os
import threading

import customtkinter as ctk

from app.core.probe import get_probe, detect_mixed_format

# 格式 Badge 顏色
FORMAT_COLORS: dict[str, str] = {
    ".mp4":  "#4CAF50",
    ".mkv":  "#2196F3",
    ".mov":  "#2196F3",
    ".asf":  "#FF9800",
    ".wmv":  "#FF9800",
    ".avi":  "#9C27B0",
}
DEFAULT_COLOR = "#757575"

ROW_HEIGHT = 30   # 每列大約高度（px），用於計算拖曳目標位置


class FileListPanel(ctk.CTkFrame):
    def __init__(self, master, on_list_changed=None, on_generate_srt=None, **kwargs):
        super().__init__(master, **kwargs)
        self._on_list_changed = on_list_changed
        self._on_generate_srt = on_generate_srt
        self._files: list[str] = []
        self._info_cache: dict[str, dict] = {}

        # 拖曳排序狀態
        self._drag_index: int | None = None      # 正在拖曳的列索引
        self._drag_indicator: ctk.CTkFrame | None = None  # 插入位置指示線
        self._drag_y_start: int = 0              # 按下時的 Y 座標
        self._row_widgets: list[ctk.CTkFrame] = []  # 各列 widget 參考

        self._build_ui()

    # ── 版面 ────────────────────────────────────────────────────────

    def _build_ui(self):
        # 欄位標頭
        header = ctk.CTkFrame(self, fg_color=("gray85", "gray20"))
        header.pack(fill="x", padx=0, pady=(0, 1))
        for col, (text, w) in enumerate([
            ("☰", 24), ("#", 28), ("檔名", 195), ("格式", 58), ("解析度", 68), ("時長", 52), ("", 30)
        ]):
            ctk.CTkLabel(
                header, text=text, width=w, anchor="w",
                font=ctk.CTkFont(size=12, weight="bold")
            ).grid(row=0, column=col, padx=(6 if col == 0 else 2, 2), pady=4, sticky="w")

        # 可捲動清單區
        self.scroll_frame = ctk.CTkScrollableFrame(self, label_text="")
        self.scroll_frame.pack(fill="both", expand=True)

        # 混合格式警告
        self.warn_label = ctk.CTkLabel(
            self,
            text="⚠  偵測到混合格式，將進行重新編碼",
            text_color="#FF9800",
            font=ctk.CTkFont(size=12),
        )

    # ── 對外 API ────────────────────────────────────────────────────

    def get_files(self) -> list[str]:
        return list(self._files)

    def add_files(self, paths: list[str]) -> int:
        """加入檔案，回傳實際新增數量（略過重複）。"""
        added = 0
        for p in paths:
            abs_p = os.path.abspath(p)
            if abs_p not in self._files:
                self._files.append(abs_p)
                added += 1
        if added:
            self._refresh_list()
            self._async_probe_new()
        return added

    def remove_file(self, index: int):
        if 0 <= index < len(self._files):
            self._files.pop(index)
            self._refresh_list()
            self._update_warning()
            if self._on_list_changed:
                self._on_list_changed()

    def clear(self):
        self._files.clear()
        self._info_cache.clear()
        self._refresh_list()
        self._update_warning()
        if self._on_list_changed:
            self._on_list_changed()

    # ── 內部渲染 ────────────────────────────────────────────────────

    def _refresh_list(self):
        for w in self.scroll_frame.winfo_children():
            w.destroy()
        self._row_widgets.clear()

        for idx, path in enumerate(self._files):
            self._add_row(idx, path)

        if self._on_list_changed:
            self._on_list_changed()

    def _add_row(self, idx: int, path: str):
        info      = self._info_cache.get(path)
        filename  = os.path.basename(path)
        ext       = os.path.splitext(path)[1].lower()
        fmt_text  = ext.lstrip(".").upper() if ext else "?"
        fmt_color = FORMAT_COLORS.get(ext, DEFAULT_COLOR)
        res_text  = self._format_res(info)
        dur_text  = self._format_dur(info)

        row = ctk.CTkFrame(
            self.scroll_frame,
            fg_color=("gray92", "gray17"),
            corner_radius=4,
        )
        row.pack(fill="x", pady=1, padx=2)
        self._row_widgets.append(row)

        # 拖曳把手
        handle = ctk.CTkLabel(
            row, text="☰", width=24, cursor="fleur",
            text_color=("gray60", "gray50"),
        )
        handle.pack(side="left", padx=(4, 0))

        # 序號
        ctk.CTkLabel(row, text=str(idx + 1), width=28, anchor="e").pack(side="left", padx=2)
        # 檔名
        disp_name = filename if len(filename) <= 26 else filename[:24] + "…"
        ctk.CTkLabel(row, text=disp_name, width=195, anchor="w").pack(side="left", padx=2)
        # 格式 badge
        ctk.CTkLabel(
            row, text=fmt_text, width=58, anchor="center",
            text_color=fmt_color, font=ctk.CTkFont(weight="bold"),
        ).pack(side="left", padx=2)
        # 解析度
        ctk.CTkLabel(row, text=res_text, width=68, anchor="center").pack(side="left", padx=2)
        # 時長
        ctk.CTkLabel(row, text=dur_text, width=52, anchor="center").pack(side="left", padx=2)
        # 刪除按鈕
        ctk.CTkButton(
            row, text="✕", width=28, height=24,
            fg_color="transparent", text_color=("gray50", "gray60"),
            hover_color=("gray80", "gray30"),
            command=lambda i=idx: self.remove_file(i),
        ).pack(side="left", padx=(2, 2))

        # 字幕按鈕（CC）
        if self._on_generate_srt:
            ctk.CTkButton(
                row, text="CC", width=34, height=24,
                fg_color="transparent", text_color=("#2196F3", "#64B5F6"),
                hover_color=("gray80", "gray30"),
                font=ctk.CTkFont(size=11, weight="bold"),
                command=lambda p=path: self._on_generate_srt(p),
            ).pack(side="left", padx=(0, 4))

        # 綁定拖曳事件到把手（及整列）
        for widget in (handle, row):
            widget.bind("<ButtonPress-1>",   lambda e, i=idx: self._drag_start(e, i))
            widget.bind("<B1-Motion>",        self._drag_motion)
            widget.bind("<ButtonRelease-1>",  self._drag_release)

    def _update_warning(self):
        infos = [self._info_cache[p] for p in self._files if p in self._info_cache]
        if detect_mixed_format(infos):
            self.warn_label.pack(fill="x", padx=8, pady=(2, 6))
        else:
            self.warn_label.pack_forget()

    # ── 拖曳排序 ────────────────────────────────────────────────────

    def _drag_start(self, event, idx: int):
        self._drag_index = idx
        self._drag_y_start = event.y_root
        # 被拖曳列變半透明（降低亮度模擬效果）
        if 0 <= idx < len(self._row_widgets):
            self._row_widgets[idx].configure(fg_color=("gray80", "gray25"))

    def _drag_motion(self, event):
        if self._drag_index is None:
            return
        # 計算插入位置
        target = self._calc_drop_index(event.y_root)
        self._show_indicator(target)

    def _drag_release(self, event):
        if self._drag_index is None:
            return

        src = self._drag_index
        dst = self._calc_drop_index(event.y_root)

        # 移除指示線
        self._hide_indicator()

        # 執行重新排序
        if dst != src and dst != src + 1:
            item = self._files.pop(src)
            # 插入目標前需修正索引（移除後索引偏移）
            insert_at = dst if dst < src else dst - 1
            self._files.insert(insert_at, item)
            self._refresh_list()
            self._update_warning()
            if self._on_list_changed:
                self._on_list_changed()
        else:
            # 無移動，還原顏色
            if 0 <= src < len(self._row_widgets):
                self._row_widgets[src].configure(fg_color=("gray92", "gray17"))

        self._drag_index = None

    def _calc_drop_index(self, y_root: int) -> int:
        """根據滑鼠 Y 座標計算插入位置（0 = 最上方，n = 最下方）。"""
        if not self._row_widgets:
            return 0
        for i, row in enumerate(self._row_widgets):
            try:
                row_y = row.winfo_rooty()
                row_h = row.winfo_height() or ROW_HEIGHT
                if y_root < row_y + row_h // 2:
                    return i
            except Exception:
                pass
        return len(self._row_widgets)

    def _show_indicator(self, insert_index: int):
        """在目標列上方顯示橘色插入指示線。"""
        self._hide_indicator()
        rows = self._row_widgets
        if not rows:
            return

        # 找參考 widget 放指示線
        if insert_index < len(rows):
            ref = rows[insert_index]
            self._drag_indicator = ctk.CTkFrame(
                self.scroll_frame, height=2, fg_color="#FF9800", corner_radius=0
            )
            self._drag_indicator.place(
                x=0, y=ref.winfo_y() - 1,
                relwidth=1,
            )
        else:
            ref = rows[-1]
            self._drag_indicator = ctk.CTkFrame(
                self.scroll_frame, height=2, fg_color="#FF9800", corner_radius=0
            )
            self._drag_indicator.place(
                x=0, y=ref.winfo_y() + ref.winfo_height(),
                relwidth=1,
            )

    def _hide_indicator(self):
        if self._drag_indicator:
            try:
                self._drag_indicator.destroy()
            except Exception:
                pass
            self._drag_indicator = None

    # ── 背景 probe ──────────────────────────────────────────────────

    def _async_probe_new(self):
        pending = [p for p in self._files if p not in self._info_cache]
        if not pending:
            return

        def worker():
            for p in pending:
                info = get_probe(p)
                self._info_cache[p] = info
            self.after(0, self._on_probe_done)

        threading.Thread(target=worker, daemon=True).start()

    def _on_probe_done(self):
        self._refresh_list()
        self._update_warning()

    # ── 格式化工具 ──────────────────────────────────────────────────

    @staticmethod
    def _format_res(info: dict | None) -> str:
        if not info or info.get("error") or not info.get("video"):
            return "—"
        h = info["video"].get("height")
        return f"{h}p" if h else "—"

    @staticmethod
    def _format_dur(info: dict | None) -> str:
        if not info or info.get("error") or info.get("duration") is None:
            return "—"
        try:
            total = int(info["duration"])
            return f"{total // 60:02d}:{total % 60:02d}"
        except (TypeError, ValueError):
            return "—"
