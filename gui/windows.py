"""
Sub-windows — About, ShotWindow, AudioWindow.
"""
import os
import threading
import customtkinter as ctk

from gui.theme import *
from config import APP_NAME, APP_VERSION, APP_COPYRIGHT, APP_AUTHOR


class AboutWindow(ctk.CTkToplevel):
    """Cửa sổ thông tin hệ thống."""

    def __init__(self, master):
        super().__init__(master)
        self.title(f"Thông tin — {APP_NAME}")
        self.geometry("520x520")
        self.resizable(False, False)
        self.attributes("-topmost", True)
        self.configure(fg_color=COLORS["bg_primary"])

        # ─── Header ────────────────────────────────────────────────
        header = ctk.CTkFrame(self, fg_color=COLORS["bg_card"], corner_radius=16)
        header.pack(fill="x", padx=PAD_XL, pady=(PAD_XL, PAD_MD))

        ctk.CTkLabel(
            header, text=f"🤖 {APP_NAME}",
            font=("Inter", 24, "bold"), text_color=COLORS["accent"],
        ).pack(pady=(PAD_LG, PAD_XS))

        ctk.CTkLabel(
            header, text=f"Phiên bản {APP_VERSION} | Siêu trợ lý AI đa năng",
            font=FONT_BODY, text_color=COLORS["text_secondary"],
        ).pack(pady=(0, PAD_LG))

        # ─── Mechanism Card ────────────────────────────────────────
        mech = ctk.CTkFrame(self, **CARD)
        mech.pack(fill="both", expand=True, padx=PAD_XL, pady=PAD_SM)

        ctk.CTkLabel(
            mech, text="⚙️ Cơ chế Brain-Eye-Hand",
            font=FONT_HEADING, text_color=COLORS["text_primary"],
        ).pack(pady=(PAD_MD, PAD_SM))

        mechanisms = [
            ("🧠", "Brain", "Kết nối đa model (Gemini, GPT, Claude, Ollama) để suy luận & ra quyết định."),
            ("👁️", "Eye (Mắt thần)", "Hệ thống Vision đa năng hỗ trợ AI 'nhìn' màn hình, OCR và xác định tọa độ."),
            ("🦾", "Hand (Cánh tay)", "Automation Agent tự động click, gõ, kéo thả để hoàn thành tác vụ."),
        ]

        for emoji, title, desc in mechanisms:
            row = ctk.CTkFrame(mech, fg_color="transparent")
            row.pack(fill="x", padx=PAD_MD, pady=PAD_XS)
            ctk.CTkLabel(row, text=emoji, font=("Inter", 18)).pack(side="left", padx=(0, PAD_SM))
            text_frame = ctk.CTkFrame(row, fg_color="transparent")
            text_frame.pack(side="left", fill="x", expand=True)
            ctk.CTkLabel(text_frame, text=title, font=("Inter", 13, "bold"), text_color=COLORS["accent_light"], anchor="w").pack(anchor="w")
            ctk.CTkLabel(text_frame, text=desc, font=FONT_SMALL, text_color=COLORS["text_secondary"], wraplength=380, anchor="w", justify="left").pack(anchor="w")

        # ─── Footer ────────────────────────────────────────────────
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(fill="x", padx=PAD_XL, pady=PAD_MD)

        ctk.CTkLabel(footer, text=APP_COPYRIGHT, font=("Inter", 11, "italic"), text_color=COLORS["text_dim"]).pack()
        ctk.CTkLabel(footer, text=f"Phát triển bởi: {APP_AUTHOR}", font=("Inter", 12, "bold"), text_color=COLORS["text_accent"]).pack(pady=(PAD_XS, 0))

        ctk.CTkButton(
            footer, text="Đóng", width=100, height=32,
            **BTN_SECONDARY,
            command=self.destroy,
        ).pack(pady=(PAD_SM, 0))


class ShotWindow(ctk.CTkToplevel):
    """Cửa sổ chụp màn hình nhỏ gọn (floating)."""

    def __init__(self, master, on_capture=None):
        super().__init__(master)
        self.title("📸")
        self.geometry("40x40")
        self.resizable(False, False)
        self.attributes("-topmost", True)
        self.configure(fg_color=COLORS["bg_card"])
        self._on_capture = on_capture

        btn = ctk.CTkButton(
            self, text="📸", width=36, height=36,
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            corner_radius=8,
            font=("Inter", 18),
            command=self._capture,
        )
        btn.pack(fill="both", expand=True, padx=2, pady=2)

    def _capture(self):
        if self._on_capture:
            self._on_capture()


class AudioWindow(ctk.CTkToplevel):
    """Cửa sổ ghi âm nhỏ gọn."""

    def __init__(self, master, recorder, on_analyze=None):
        super().__init__(master)
        self.title("🎙️ Ghi âm")
        self.geometry("240x44")
        self.resizable(False, False)
        self.attributes("-topmost", True)
        self.configure(fg_color=COLORS["bg_card"])
        self.recorder = recorder
        self._on_analyze = on_analyze

        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="both", expand=True, padx=4, pady=4)

        # Language
        self.lang_var = ctk.StringVar(value="vi-VN")
        self.lang_menu = ctk.CTkOptionMenu(
            row,
            values=["vi-VN", "en-US", "zh-CN", "ja-JP", "ko-KR"],
            variable=self.lang_var,
            width=75, height=32,
            fg_color=COLORS["bg_input"],
            button_color=COLORS["accent_dim"],
            font=FONT_SMALL,
        )
        self.lang_menu.pack(side="left", padx=(0, 4))

        # Record toggle
        self.btn_rec = ctk.CTkButton(
            row, text="◉ Ghi", width=65, height=32,
            fg_color="#5a1f1f",
            hover_color="#7a2f2f",
            text_color=COLORS["error"],
            font=("Inter", 12, "bold"),
            command=self._toggle_record,
        )
        self.btn_rec.pack(side="left", padx=(0, 4))

        # Analyze
        self.btn_analyze = ctk.CTkButton(
            row, text="▶ Phân tích", width=80, height=32,
            fg_color=COLORS["accent_dim"],
            hover_color=COLORS["accent"],
            text_color=COLORS["text_primary"],
            font=FONT_SMALL,
            command=self._analyze,
        )
        self.btn_analyze.pack(side="left")

    def _toggle_record(self):
        if not self.recorder.is_recording:
            self.recorder.start()
            self.btn_rec.configure(text="■ Dừng", fg_color="#aa3333", hover_color="#cc4444")
        else:
            self.recorder.stop()
            self.btn_rec.configure(text="◉ Ghi", fg_color="#5a1f1f", hover_color="#7a2f2f")

    def _analyze(self):
        if self._on_analyze:
            lang = self.lang_var.get()
            threading.Thread(target=self._on_analyze, args=(lang,), daemon=True).start()
