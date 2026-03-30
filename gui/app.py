"""
QtusScreen AI Pro v3.0 — Main Application Window.
Premium GUI with tabbed layout, streaming output, and advanced controls.
Bản quyền © 2025-2026 Qtus Dev (Anh Tú)
"""
import os
import sys
import time
import threading
from tkinter import filedialog
from typing import Optional
from PIL import Image

import customtkinter as ctk

# Ensure project root is in sys.path
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from config import APP_NAME, APP_VERSION, APP_COPYRIGHT
from config.models import get_models_for_provider, is_vision_capable
from gui.theme import *
from gui.widgets import StatusBar, ModelSelector, OutputBox, QuestionBox
from gui.windows import AboutWindow, ShotWindow, AudioWindow
from core.screen import capture_screen
from core.audio import AudioRecorder


class QtusApp(ctk.CTk):
    """Main Application — QtusScreen AI Pro v3.0."""

    def __init__(self):
        super().__init__()

        # ─── Window Setup ──────────────────────────────────────────
        self.title(f"{APP_NAME} v{APP_VERSION}")
        self.geometry("1100x760")
        self.minsize(700, 500)
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        self.configure(fg_color=COLORS["bg_primary"])

        # ─── State ─────────────────────────────────────────────────
        self.file_path: Optional[str] = None
        self.image_path: Optional[str] = None
        self.audio_recorder = AudioRecorder()
        self._busy = False

        # ─── Build UI ──────────────────────────────────────────────
        self._build_header()
        self._build_toolbar()
        self._build_tabs()
        self._build_status_bar()

        # ─── Keyboard Shortcuts ────────────────────────────────────
        self.bind("<Control-Return>", lambda e: self._on_analyze())
        self.bind("<F5>", lambda e: self._on_screenshot())

        # ─── Responsive ───────────────────────────────────────────
        self.bind("<Configure>", self._on_resize)

    # ═══════════════════════════════════════════════════════════════
    # BUILD UI
    # ═══════════════════════════════════════════════════════════════

    def _build_header(self):
        """Header bar — Logo + title + quick buttons."""
        header = ctk.CTkFrame(self, fg_color=COLORS["bg_secondary"], height=52, corner_radius=0)
        header.pack(fill="x")
        header.pack_propagate(False)

        # Logo + Title
        title_frame = ctk.CTkFrame(header, fg_color="transparent")
        title_frame.pack(side="left", padx=PAD_LG)

        ctk.CTkLabel(
            title_frame, text="🤖",
            font=("Inter", 24),
        ).pack(side="left", padx=(0, PAD_SM))

        ctk.CTkLabel(
            title_frame, text=APP_NAME,
            font=("Inter", 17, "bold"),
            text_color=COLORS["accent_light"],
        ).pack(side="left")

        ctk.CTkLabel(
            title_frame, text=f"v{APP_VERSION}",
            font=FONT_SMALL,
            text_color=COLORS["text_dim"],
        ).pack(side="left", padx=(PAD_XS, 0))

        # Right side buttons
        right = ctk.CTkFrame(header, fg_color="transparent")
        right.pack(side="right", padx=PAD_LG)

        self.btn_about = ctk.CTkButton(
            right, text="ℹ️", width=36, height=36,
            fg_color="transparent", hover_color=COLORS["bg_hover"],
            text_color=COLORS["text_secondary"], corner_radius=8,
            font=("Inter", 16), command=self._show_about,
        )
        self.btn_about.pack(side="right", padx=PAD_XS)

    def _build_toolbar(self):
        """Toolbar — Model selector + action buttons."""
        toolbar = ctk.CTkFrame(self, fg_color=COLORS["bg_secondary"], height=50, corner_radius=0)
        toolbar.pack(fill="x", pady=(1, 0))
        toolbar.pack_propagate(False)

        # Model Selector
        self.model_selector = ModelSelector(toolbar)
        self.model_selector.pack(side="left", padx=PAD_LG)

        # Action buttons
        actions = ctk.CTkFrame(toolbar, fg_color="transparent")
        actions.pack(side="right", padx=PAD_LG)

        self.btn_screenshot = ctk.CTkButton(
            actions, text="📸 Chụp", width=90, height=34,
            fg_color=COLORS["bg_card"], hover_color=COLORS["bg_hover"],
            text_color=COLORS["text_primary"], border_color=COLORS["border"],
            border_width=1, corner_radius=10, font=("Inter", 12),
            command=self._on_screenshot,
        )
        self.btn_screenshot.pack(side="left", padx=PAD_XS)

        self.btn_upload = ctk.CTkButton(
            actions, text="📂 File", width=80, height=34,
            fg_color=COLORS["bg_card"], hover_color=COLORS["bg_hover"],
            text_color=COLORS["text_primary"], border_color=COLORS["border"],
            border_width=1, corner_radius=10, font=("Inter", 12),
            command=self._on_select_file,
        )
        self.btn_upload.pack(side="left", padx=PAD_XS)

        self.btn_shot_win = ctk.CTkButton(
            actions, text="🪟📸", width=50, height=34,
            fg_color="transparent", hover_color=COLORS["bg_hover"],
            text_color=COLORS["text_secondary"], corner_radius=8,
            font=("Inter", 16), command=self._open_shot_window,
        )
        self.btn_shot_win.pack(side="left", padx=PAD_XS)

        self.btn_audio_win = ctk.CTkButton(
            actions, text="🎙️", width=50, height=34,
            fg_color="transparent", hover_color=COLORS["bg_hover"],
            text_color=COLORS["text_secondary"], corner_radius=8,
            font=("Inter", 16), command=self._open_audio_window,
        )
        self.btn_audio_win.pack(side="left", padx=PAD_XS)

    def _build_tabs(self):
        """Tabbed content area."""
        self.tabview = ctk.CTkTabview(
            self,
            fg_color=COLORS["bg_primary"],
            segmented_button_fg_color=COLORS["bg_secondary"],
            segmented_button_selected_color=COLORS["accent"],
            segmented_button_selected_hover_color=COLORS["accent_hover"],
            segmented_button_unselected_color=COLORS["bg_card"],
            segmented_button_unselected_hover_color=COLORS["bg_hover"],
            text_color=COLORS["text_primary"],
            corner_radius=0,
        )
        self.tabview.pack(fill="both", expand=True, padx=0, pady=0)

        # ─── Tab 1: Phân Tích ──────────────────────────────────────
        tab_analyze = self.tabview.add("🤖 Phân Tích")
        tab_analyze.configure(fg_color=COLORS["bg_primary"])

        # Context info (file/image attached)
        self.context_frame = ctk.CTkFrame(tab_analyze, fg_color=COLORS["bg_secondary"], height=30, corner_radius=8)
        self.context_frame.pack(fill="x", padx=PAD_MD, pady=(PAD_SM, 0))
        self.context_label = ctk.CTkLabel(
            self.context_frame, text="📎 Chưa có đính kèm",
            font=FONT_SMALL, text_color=COLORS["text_dim"],
        )
        self.context_label.pack(side="left", padx=PAD_MD, pady=PAD_XS)

        self.btn_clear_ctx = ctk.CTkButton(
            self.context_frame, text="✕", width=24, height=24,
            fg_color="transparent", hover_color=COLORS["bg_hover"],
            text_color=COLORS["text_secondary"], corner_radius=8,
            font=("Inter", 14), command=self._clear_context,
        )
        self.btn_clear_ctx.pack(side="right", padx=PAD_SM)

        # Question input
        self.question_box = QuestionBox(tab_analyze)
        self.question_box.pack(fill="x", padx=PAD_MD, pady=PAD_SM)

        # Action row
        action_row = ctk.CTkFrame(tab_analyze, fg_color="transparent")
        action_row.pack(fill="x", padx=PAD_MD, pady=(0, PAD_SM))

        self.btn_analyze = ctk.CTkButton(
            action_row, text="🤖 Phân Tích", height=42,
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            text_color="#ffffff",
            font=("Inter", 14, "bold"),
            corner_radius=12,
            command=self._on_analyze,
        )
        self.btn_analyze.pack(side="left", fill="x", expand=True, padx=(0, PAD_SM))

        self.btn_clear = ctk.CTkButton(
            action_row, text="🧹 Xóa", height=42, width=90,
            fg_color="#3d1515", hover_color="#5a1f1f",
            text_color=COLORS["error"], corner_radius=10,
            font=("Inter", 12), command=self._on_clear,
        )
        self.btn_clear.pack(side="right")

        # Output
        self.output_box = OutputBox(tab_analyze)
        self.output_box.pack(fill="both", expand=True, padx=PAD_MD, pady=(0, PAD_SM))

        # ─── Tab 2: Tự Động Hoá ───────────────────────────────────
        tab_auto = self.tabview.add("🖱️ Tự Động Hoá")
        tab_auto.configure(fg_color=COLORS["bg_primary"])

        # Instructions
        auto_info = ctk.CTkFrame(tab_auto, **CARD)
        auto_info.pack(fill="x", padx=PAD_MD, pady=PAD_SM)
        ctk.CTkLabel(
            auto_info, text="🦾 Automation Agent (Brain-Eye-Hand)",
            font=FONT_HEADING, text_color=COLORS["accent_light"],
        ).pack(anchor="w", padx=PAD_MD, pady=(PAD_SM, PAD_XS))
        ctk.CTkLabel(
            auto_info,
            text="Nhập mục tiêu (VD: 'Mở Notepad, gõ Hello World') → Agent sẽ tự phân tích và thực hiện.\n"
                 "Hỗ trợ: CLICK, DOUBLECLICK, RIGHTCLICK, TYPE, PRESS, HOTKEY, SCROLL, DRAG, WAIT",
            font=FONT_SMALL, text_color=COLORS["text_secondary"],
            wraplength=800, justify="left",
        ).pack(anchor="w", padx=PAD_MD, pady=(0, PAD_SM))

        # Auto question
        self.auto_question = QuestionBox(tab_auto)
        self.auto_question.pack(fill="x", padx=PAD_MD, pady=PAD_SM)

        # Settings row
        settings_row = ctk.CTkFrame(tab_auto, fg_color="transparent")
        settings_row.pack(fill="x", padx=PAD_MD, pady=(0, PAD_SM))

        ctk.CTkLabel(settings_row, text="Max steps:", font=FONT_SMALL, text_color=COLORS["text_dim"]).pack(side="left")
        self.auto_steps_var = ctk.StringVar(value="10")
        self.auto_steps = ctk.CTkOptionMenu(
            settings_row, values=["5", "10", "15", "20", "30"],
            variable=self.auto_steps_var,
            width=70, height=28,
            fg_color=COLORS["bg_input"],
            button_color=COLORS["accent_dim"],
            font=FONT_SMALL,
        )
        self.auto_steps.pack(side="left", padx=PAD_SM)

        # Eye mode selector
        ctk.CTkLabel(settings_row, text="Eye:", font=FONT_SMALL, text_color=COLORS["text_dim"]).pack(side="left", padx=(PAD_LG, 4))
        self.eye_mode_var = ctk.StringVar(value="auto")
        self.eye_mode = ctk.CTkOptionMenu(
            settings_row, values=["auto", "gemini", "ollama"],
            variable=self.eye_mode_var,
            width=110, height=28,
            fg_color=COLORS["bg_input"],
            button_color=COLORS["accent_dim"],
            font=FONT_SMALL,
            command=self._on_eye_mode_change,
        )
        self.eye_mode.pack(side="left")

        self.eye_status = ctk.CTkLabel(
            settings_row, text="👁️ Tự động (Khớp với Não)",
            font=FONT_SMALL, text_color=COLORS["success"],
        )
        self.eye_status.pack(side="left", padx=PAD_SM)

        # Run automation button
        self.btn_automate = ctk.CTkButton(
            tab_auto, text="🚀 Khởi động Agent", height=44,
            fg_color=COLORS["success"],
            hover_color="#00c065",
            text_color="#000000",
            font=("Inter", 14, "bold"),
            corner_radius=12,
            command=self._on_automate,
        )
        self.btn_automate.pack(fill="x", padx=PAD_MD, pady=(0, PAD_SM))

        # Auto output
        self.auto_output = OutputBox(tab_auto)
        self.auto_output.pack(fill="both", expand=True, padx=PAD_MD, pady=(0, PAD_SM))

        # ─── Tab 3: Cài Đặt ───────────────────────────────────────
        tab_settings = self.tabview.add("⚙️ Cài Đặt")
        tab_settings.configure(fg_color=COLORS["bg_primary"])

        # API Keys status
        keys_card = ctk.CTkFrame(tab_settings, **CARD)
        keys_card.pack(fill="x", padx=PAD_MD, pady=PAD_SM)
        ctk.CTkLabel(keys_card, text="🔑 API Keys", font=FONT_HEADING, text_color=COLORS["text_primary"]).pack(anchor="w", padx=PAD_MD, pady=(PAD_SM, PAD_XS))

        from config import validate_keys
        keys = validate_keys()
        for name, ok in keys.items():
            status_text = f"{'✅' if ok else '❌'} {name.upper()}: {'Đã cấu hình' if ok else 'Chưa đặt'}"
            color = COLORS["success"] if ok else COLORS["error"]
            ctk.CTkLabel(
                keys_card, text=status_text,
                font=FONT_BODY, text_color=color,
            ).pack(anchor="w", padx=PAD_XL, pady=PAD_XS)

        ctk.CTkLabel(
            keys_card, text="Cấu hình trong file .env tại thư mục gốc dự án.",
            font=FONT_SMALL, text_color=COLORS["text_dim"],
        ).pack(anchor="w", padx=PAD_XL, pady=(PAD_XS, PAD_MD))

        # System info
        sys_card = ctk.CTkFrame(tab_settings, **CARD)
        sys_card.pack(fill="x", padx=PAD_MD, pady=PAD_SM)
        ctk.CTkLabel(sys_card, text="💻 Hệ thống", font=FONT_HEADING, text_color=COLORS["text_primary"]).pack(anchor="w", padx=PAD_MD, pady=(PAD_SM, PAD_XS))

        # GPU check — lazy import để không kéo torch vào startup
        gpu_text = "CPU (torch chưa import)"
        def _check_gpu():
            try:
                import torch
                if torch.cuda.is_available():
                    return torch.cuda.get_device_name(0)
                return "CPU"
            except Exception:
                return "N/A"
        # Chạy trong thread để không block UI
        def _update_gpu():
            g = _check_gpu()
            try:
                for w in sys_card.winfo_children():
                    if hasattr(w, 'cget') and 'GPU:' in str(w.cget('text')):
                        w.configure(text=f"GPU: {g}")
            except Exception:
                pass
        threading.Thread(target=_update_gpu, daemon=True).start()

        sys_info = [
            f"Python: {sys.version.split()[0]}",
            f"Platform: {sys.platform}",
            f"GPU: {gpu_text}",
            f"Project: {_PROJECT_ROOT}",
        ]
        for info in sys_info:
            ctk.CTkLabel(sys_card, text=info, font=FONT_SMALL, text_color=COLORS["text_secondary"]).pack(anchor="w", padx=PAD_XL, pady=2)

        ctk.CTkLabel(sys_card, text="", font=FONT_SMALL).pack(pady=PAD_XS)  # spacer

        # Shortcuts info
        short_card = ctk.CTkFrame(tab_settings, **CARD)
        short_card.pack(fill="x", padx=PAD_MD, pady=PAD_SM)
        ctk.CTkLabel(short_card, text="⌨️ Phím tắt", font=FONT_HEADING, text_color=COLORS["text_primary"]).pack(anchor="w", padx=PAD_MD, pady=(PAD_SM, PAD_XS))

        shortcuts = [
            ("Ctrl + Enter", "Phân tích nhanh"),
            ("F5", "Chụp màn hình"),
        ]
        for key, desc in shortcuts:
            row = ctk.CTkFrame(short_card, fg_color="transparent")
            row.pack(fill="x", padx=PAD_XL, pady=2)
            ctk.CTkLabel(row, text=key, font=("Cascadia Code", 11), text_color=COLORS["accent_light"], width=130, anchor="w").pack(side="left")
            ctk.CTkLabel(row, text=desc, font=FONT_SMALL, text_color=COLORS["text_secondary"]).pack(side="left")

        ctk.CTkLabel(short_card, text="", font=FONT_SMALL).pack(pady=PAD_XS)

        # ─── Tab 4: Ollama Hub ─────────────────────────────────────
        tab_ollama = self.tabview.add("🦙 Ollama")
        tab_ollama.configure(fg_color=COLORS["bg_primary"])

        # Scrollable container
        ollama_scroll = ctk.CTkScrollableFrame(
            tab_ollama, fg_color=COLORS["bg_primary"],
        )
        ollama_scroll.pack(fill="both", expand=True, padx=0, pady=0)

        # --- Server Status ---
        server_card = ctk.CTkFrame(ollama_scroll, **CARD)
        server_card.pack(fill="x", padx=PAD_MD, pady=PAD_SM)

        server_head = ctk.CTkFrame(server_card, fg_color="transparent")
        server_head.pack(fill="x", padx=PAD_MD, pady=PAD_SM)
        ctk.CTkLabel(server_head, text="🦙 Ollama Server", font=FONT_HEADING, text_color=COLORS["text_primary"]).pack(side="left")

        self.ollama_status = ctk.CTkLabel(
            server_head, text="🔍 Kiểm tra...",
            font=FONT_SMALL, text_color=COLORS["text_dim"],
        )
        self.ollama_status.pack(side="left", padx=PAD_MD)

        ctk.CTkButton(
            server_head, text="🔄 Refresh", width=80, height=28,
            fg_color=COLORS["bg_input"], hover_color=COLORS["bg_hover"],
            text_color=COLORS["text_primary"], corner_radius=8, font=FONT_SMALL,
            command=self._refresh_ollama,
        ).pack(side="right", padx=PAD_XS)

        ctk.CTkButton(
            server_head, text="▶ Start Server", width=110, height=28,
            fg_color=COLORS["accent_dim"], hover_color=COLORS["accent"],
            text_color=COLORS["text_primary"], corner_radius=8, font=FONT_SMALL,
            command=self._start_ollama,
        ).pack(side="right", padx=PAD_XS)

        # --- Models Installed ---
        models_card = ctk.CTkFrame(ollama_scroll, **CARD)
        models_card.pack(fill="x", padx=PAD_MD, pady=PAD_SM)

        models_head = ctk.CTkFrame(models_card, fg_color="transparent")
        models_head.pack(fill="x", padx=PAD_MD, pady=PAD_SM)
        ctk.CTkLabel(models_head, text="📦 Models đã cài", font=FONT_HEADING, text_color=COLORS["text_primary"]).pack(side="left")

        self.ollama_models_frame = ctk.CTkFrame(models_card, fg_color="transparent")
        self.ollama_models_frame.pack(fill="x", padx=PAD_MD, pady=(0, PAD_SM))

        self.ollama_models_label = ctk.CTkLabel(
            self.ollama_models_frame, text="(đang tải...)",
            font=FONT_SMALL, text_color=COLORS["text_dim"],
        )
        self.ollama_models_label.pack(anchor="w")

        # --- Pull / Delete Model ---
        pull_card = ctk.CTkFrame(ollama_scroll, **CARD)
        pull_card.pack(fill="x", padx=PAD_MD, pady=PAD_SM)
        ctk.CTkLabel(pull_card, text="📥 Tải / Xóa Model", font=FONT_HEADING, text_color=COLORS["text_primary"]).pack(anchor="w", padx=PAD_MD, pady=(PAD_SM, PAD_XS))

        pull_row = ctk.CTkFrame(pull_card, fg_color="transparent")
        pull_row.pack(fill="x", padx=PAD_MD, pady=PAD_SM)

        self.pull_entry = ctk.CTkEntry(
            pull_row, placeholder_text="Tên model (VD: gemma3:4b, llava:7b)",
            fg_color=COLORS["bg_input"], border_color=COLORS["border"],
            text_color=COLORS["text_primary"], font=FONT_BODY,
            corner_radius=8, height=34,
        )
        self.pull_entry.pack(side="left", fill="x", expand=True, padx=(0, PAD_SM))

        ctk.CTkButton(
            pull_row, text="⬇ Pull", width=70, height=34,
            fg_color=COLORS["success"], hover_color="#00c065",
            text_color="#000", corner_radius=8, font=("Inter", 12, "bold"),
            command=self._pull_model,
        ).pack(side="left", padx=(0, PAD_XS))

        ctk.CTkButton(
            pull_row, text="🗑 Xóa", width=70, height=34,
            fg_color="#3d1515", hover_color="#5a1f1f",
            text_color=COLORS["error"], corner_radius=8, font=("Inter", 12),
            command=self._delete_model,
        ).pack(side="left")

        # Pull progress
        self.pull_progress = ctk.CTkLabel(
            pull_card, text="",
            font=FONT_SMALL, text_color=COLORS["text_secondary"],
        )
        self.pull_progress.pack(anchor="w", padx=PAD_MD, pady=(0, PAD_SM))

        # Recommended models
        rec_card = ctk.CTkFrame(ollama_scroll, **CARD)
        rec_card.pack(fill="x", padx=PAD_MD, pady=PAD_SM)
        ctk.CTkLabel(rec_card, text="⭐ Models gợi ý", font=FONT_HEADING, text_color=COLORS["text_primary"]).pack(anchor="w", padx=PAD_MD, pady=(PAD_SM, PAD_XS))

        from core.ollama_manager import RECOMMENDED_MODELS
        for m in RECOMMENDED_MODELS:
            row = ctk.CTkFrame(rec_card, fg_color="transparent")
            row.pack(fill="x", padx=PAD_MD, pady=2)
            icon = "👁️" if m["vision"] else "🧠"
            ctk.CTkLabel(
                row, text=f"{icon} {m['name']} — {m['desc']} ({m['size']})",
                font=FONT_SMALL, text_color=COLORS["text_secondary"],
                wraplength=800, justify="left", anchor="w",
            ).pack(side="left", fill="x", expand=True)
            ctk.CTkButton(
                row, text="Pull", width=50, height=24,
                fg_color=COLORS["accent_dim"], hover_color=COLORS["accent"],
                text_color=COLORS["text_primary"], corner_radius=6, font=FONT_TINY,
                command=lambda name=m["name"]: self._quick_pull(name),
            ).pack(side="right")

        ctk.CTkLabel(rec_card, text="", font=FONT_TINY).pack(pady=2)

        # --- Modelfile Creator (Dạy AI) ---
        mf_card = ctk.CTkFrame(ollama_scroll, **CARD)
        mf_card.pack(fill="x", padx=PAD_MD, pady=PAD_SM)
        ctk.CTkLabel(mf_card, text="🧪 Tạo Model Tùy Chỉnh (Dạy AI)", font=FONT_HEADING, text_color=COLORS["accent_light"]).pack(anchor="w", padx=PAD_MD, pady=(PAD_SM, PAD_XS))
        ctk.CTkLabel(
            mf_card, text="Tạo AI riêng bằng cách chọn base model + viết system prompt.",
            font=FONT_SMALL, text_color=COLORS["text_dim"],
        ).pack(anchor="w", padx=PAD_MD)

        mf_name_row = ctk.CTkFrame(mf_card, fg_color="transparent")
        mf_name_row.pack(fill="x", padx=PAD_MD, pady=PAD_SM)
        ctk.CTkLabel(mf_name_row, text="Tên:", font=FONT_SMALL, text_color=COLORS["text_dim"]).pack(side="left")
        self.mf_name_entry = ctk.CTkEntry(
            mf_name_row, placeholder_text="my-assistant",
            fg_color=COLORS["bg_input"], border_color=COLORS["border"],
            text_color=COLORS["text_primary"], font=FONT_BODY,
            corner_radius=8, height=30, width=150,
        )
        self.mf_name_entry.pack(side="left", padx=PAD_SM)

        ctk.CTkLabel(mf_name_row, text="Template:", font=FONT_SMALL, text_color=COLORS["text_dim"]).pack(side="left", padx=(PAD_MD, 4))
        self.mf_template_var = ctk.StringVar(value="vietnamese_assistant")
        ctk.CTkOptionMenu(
            mf_name_row,
            values=["vietnamese_assistant", "coder", "security_analyst", "automation_brain", "custom"],
            variable=self.mf_template_var,
            width=160, height=28,
            fg_color=COLORS["bg_input"], button_color=COLORS["accent_dim"],
            font=FONT_SMALL, command=self._load_modelfile_template,
        ).pack(side="left")

        ctk.CTkLabel(mf_name_row, text="Base:", font=FONT_SMALL, text_color=COLORS["text_dim"]).pack(side="left", padx=(PAD_MD, 4))
        self.mf_base_var = ctk.StringVar(value="gemma3:4b")
        self.mf_base_menu = ctk.CTkOptionMenu(
            mf_name_row, values=["gemma3:4b"],
            variable=self.mf_base_var,
            width=120, height=28,
            fg_color=COLORS["bg_input"], button_color=COLORS["accent_dim"],
            font=FONT_SMALL,
        )
        self.mf_base_menu.pack(side="left")

        self.mf_textbox = ctk.CTkTextbox(
            mf_card, height=120,
            fg_color=COLORS["bg_input"], text_color=COLORS["text_primary"],
            font=FONT_MONO_SMALL, corner_radius=8,
            border_color=COLORS["border"], border_width=1,
        )
        self.mf_textbox.pack(fill="x", padx=PAD_MD, pady=PAD_SM)

        mf_btn_row = ctk.CTkFrame(mf_card, fg_color="transparent")
        mf_btn_row.pack(fill="x", padx=PAD_MD, pady=(0, PAD_SM))

        ctk.CTkButton(
            mf_btn_row, text="🚀 Tạo Model", height=32,
            fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"],
            text_color="#fff", corner_radius=8, font=("Inter", 13, "bold"),
            command=self._create_model,
        ).pack(side="left", padx=(0, PAD_SM))

        self.mf_status = ctk.CTkLabel(
            mf_btn_row, text="",
            font=FONT_SMALL, text_color=COLORS["text_dim"],
        )
        self.mf_status.pack(side="left")

        # --- Chat Ollama ---
        chat_card = ctk.CTkFrame(ollama_scroll, **CARD)
        chat_card.pack(fill="x", padx=PAD_MD, pady=PAD_SM)
        ctk.CTkLabel(chat_card, text="💬 Chat với Ollama (local)", font=FONT_HEADING, text_color=COLORS["text_primary"]).pack(anchor="w", padx=PAD_MD, pady=(PAD_SM, PAD_XS))

        chat_model_row = ctk.CTkFrame(chat_card, fg_color="transparent")
        chat_model_row.pack(fill="x", padx=PAD_MD, pady=PAD_SM)
        ctk.CTkLabel(chat_model_row, text="Model:", font=FONT_SMALL, text_color=COLORS["text_dim"]).pack(side="left")
        self.chat_model_var = ctk.StringVar(value="gemma3:4b")
        self.chat_model_menu = ctk.CTkOptionMenu(
            chat_model_row, values=["gemma3:4b"],
            variable=self.chat_model_var,
            width=160, height=28,
            fg_color=COLORS["bg_input"], button_color=COLORS["accent_dim"],
            font=FONT_SMALL,
        )
        self.chat_model_menu.pack(side="left", padx=PAD_SM)

        ctk.CTkButton(
            chat_model_row, text="🧹 Reset Chat", width=100, height=28,
            fg_color=COLORS["bg_input"], hover_color=COLORS["bg_hover"],
            text_color=COLORS["text_secondary"], corner_radius=8, font=FONT_SMALL,
            command=self._reset_ollama_chat,
        ).pack(side="right")

        self.chat_output = ctk.CTkTextbox(
            chat_card, height=180,
            fg_color=COLORS["bg_input"], text_color=COLORS["text_primary"],
            font=FONT_MONO_SMALL, corner_radius=8,
            border_color=COLORS["border"], border_width=1, wrap="word",
        )
        self.chat_output.pack(fill="x", padx=PAD_MD, pady=(0, PAD_SM))

        chat_input_row = ctk.CTkFrame(chat_card, fg_color="transparent")
        chat_input_row.pack(fill="x", padx=PAD_MD, pady=(0, PAD_SM))

        self.chat_entry = ctk.CTkEntry(
            chat_input_row, placeholder_text="Nhập tin nhắn...",
            fg_color=COLORS["bg_input"], border_color=COLORS["border"],
            text_color=COLORS["text_primary"], font=FONT_BODY,
            corner_radius=8, height=34,
        )
        self.chat_entry.pack(side="left", fill="x", expand=True, padx=(0, PAD_SM))
        self.chat_entry.bind("<Return>", lambda e: self._send_ollama_chat())

        ctk.CTkButton(
            chat_input_row, text="📤 Gửi", width=70, height=34,
            fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"],
            text_color="#fff", corner_radius=8, font=("Inter", 12, "bold"),
            command=self._send_ollama_chat,
        ).pack(side="right")

        # State for ollama
        self._ollama_chat_history = []

        # Auto-refresh on tab load
        self.after(500, self._refresh_ollama)
        self._load_modelfile_template("vietnamese_assistant")

        # ─── Tab 5: Train AI ───────────────────────────────────────
        tab_train = self.tabview.add("🎓 Train AI")
        tab_train.configure(fg_color=COLORS["bg_primary"])

        train_scroll = ctk.CTkScrollableFrame(tab_train, fg_color=COLORS["bg_primary"])
        train_scroll.pack(fill="both", expand=True)

        # Header
        hdr = ctk.CTkFrame(train_scroll, fg_color=COLORS["bg_secondary"], corner_radius=14)
        hdr.pack(fill="x", padx=PAD_MD, pady=PAD_SM)
        ctk.CTkLabel(
            hdr, text="🎓 Dạy AI — Tạo model AI riêng với personality tùy chỉnh",
            font=FONT_HEADING, text_color=COLORS["accent_light"],
        ).pack(anchor="w", padx=PAD_MD, pady=(PAD_SM, PAD_XS))
        ctk.CTkLabel(
            hdr,
            text="Chọn preset → đặt tên → chọn base model → bấm Train. AI mới sẽ xuất hiện trong danh sách Ollama.",
            font=FONT_SMALL, text_color=COLORS["text_dim"],
        ).pack(anchor="w", padx=PAD_MD, pady=(0, PAD_SM))

        # Quick Train Presets
        from core.ollama_trainer import QUICK_PRESETS
        for preset_key, preset_info in QUICK_PRESETS.items():
            pc = ctk.CTkFrame(train_scroll, **CARD)
            pc.pack(fill="x", padx=PAD_MD, pady=PAD_SM)

            ph = ctk.CTkFrame(pc, fg_color="transparent")
            ph.pack(fill="x", padx=PAD_MD, pady=PAD_SM)

            ctk.CTkLabel(
                ph, text=preset_info["label"],
                font=FONT_BODY, text_color=COLORS["text_primary"],
            ).pack(side="left")
            ctk.CTkLabel(
                ph, text=f"  — {preset_info['desc']}",
                font=FONT_SMALL, text_color=COLORS["text_dim"],
            ).pack(side="left")

            pr = ctk.CTkFrame(pc, fg_color="transparent")
            pr.pack(fill="x", padx=PAD_MD, pady=(0, PAD_SM))

            ctk.CTkLabel(pr, text="Tên:", font=FONT_SMALL, text_color=COLORS["text_dim"]).pack(side="left")
            name_var = ctk.StringVar(value=f"my-{preset_key.replace('_', '-')}")
            name_entry = ctk.CTkEntry(
                pr, textvariable=name_var, width=140, height=28,
                fg_color=COLORS["bg_input"], border_color=COLORS["border"],
                text_color=COLORS["text_primary"], font=FONT_SMALL, corner_radius=6,
            )
            name_entry.pack(side="left", padx=PAD_XS)

            ctk.CTkLabel(pr, text="Base:", font=FONT_SMALL, text_color=COLORS["text_dim"]).pack(side="left", padx=(PAD_SM, 4))
            base_var = ctk.StringVar(value=preset_info["default_base"])
            base_entry = ctk.CTkEntry(
                pr, textvariable=base_var, width=120, height=28,
                fg_color=COLORS["bg_input"], border_color=COLORS["border"],
                text_color=COLORS["text_primary"], font=FONT_SMALL, corner_radius=6,
            )
            base_entry.pack(side="left", padx=PAD_XS)

            status_lbl = ctk.CTkLabel(pr, text="", font=FONT_SMALL, text_color=COLORS["text_dim"])
            status_lbl.pack(side="left", padx=PAD_SM)

            ctk.CTkButton(
                pr, text="🚀 Train", width=80, height=28,
                fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"],
                text_color="#fff", corner_radius=8, font=("Inter", 12, "bold"),
                command=lambda pk=preset_key, nv=name_var, bv=base_var, sl=status_lbl: self._quick_train(pk, nv, bv, sl),
            ).pack(side="right")

        # Custom Modelfile
        custom_card = ctk.CTkFrame(train_scroll, **CARD)
        custom_card.pack(fill="x", padx=PAD_MD, pady=PAD_SM)
        ctk.CTkLabel(custom_card, text="✏️ Custom Modelfile", font=FONT_HEADING, text_color=COLORS["text_primary"]).pack(anchor="w", padx=PAD_MD, pady=(PAD_SM, PAD_XS))

        custom_row = ctk.CTkFrame(custom_card, fg_color="transparent")
        custom_row.pack(fill="x", padx=PAD_MD, pady=PAD_SM)

        ctk.CTkLabel(custom_row, text="Tên:", font=FONT_SMALL, text_color=COLORS["text_dim"]).pack(side="left")
        self.custom_train_name = ctk.CTkEntry(
            custom_row, placeholder_text="my-custom-ai", width=140, height=28,
            fg_color=COLORS["bg_input"], border_color=COLORS["border"],
            text_color=COLORS["text_primary"], font=FONT_SMALL, corner_radius=6,
        )
        self.custom_train_name.pack(side="left", padx=PAD_XS)

        ctk.CTkLabel(custom_row, text="Base:", font=FONT_SMALL, text_color=COLORS["text_dim"]).pack(side="left", padx=(PAD_SM, 4))
        self.custom_train_base = ctk.CTkEntry(
            custom_row, placeholder_text="gemma3:4b", width=120, height=28,
            fg_color=COLORS["bg_input"], border_color=COLORS["border"],
            text_color=COLORS["text_primary"], font=FONT_SMALL, corner_radius=6,
        )
        self.custom_train_base.pack(side="left", padx=PAD_XS)

        self.custom_train_status = ctk.CTkLabel(custom_row, text="", font=FONT_SMALL, text_color=COLORS["text_dim"])
        self.custom_train_status.pack(side="left", padx=PAD_SM)

        ctk.CTkButton(
            custom_row, text="▼ Tải template", width=110, height=28,
            fg_color=COLORS["bg_input"], hover_color=COLORS["bg_hover"],
            text_color=COLORS["text_secondary"], corner_radius=8, font=FONT_SMALL,
            command=self._load_custom_template,
        ).pack(side="right")

        ctk.CTkButton(
            custom_row, text="🚀 Train", width=80, height=28,
            fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"],
            text_color="#fff", corner_radius=8, font=("Inter", 12, "bold"),
            command=self._custom_train,
        ).pack(side="right", padx=PAD_XS)

        self.custom_modelfile_box = ctk.CTkTextbox(
            custom_card, height=200,
            fg_color=COLORS["bg_input"], text_color=COLORS["text_primary"],
            font=FONT_MONO_SMALL, corner_radius=8,
            border_color=COLORS["border"], border_width=1,
        )
        self.custom_modelfile_box.pack(fill="x", padx=PAD_MD, pady=(0, PAD_SM))
        self.custom_modelfile_box.insert("1.0",
            'FROM gemma3:4b\nSYSTEM """Bạn là AI thông minh..."""\nPARAMETER temperature 0.7\nPARAMETER num_ctx 4096'
        )

        # ─── Tab 6: Knowledge Base ─────────────────────────────────
        tab_kb = self.tabview.add("📚 Knowledge")
        tab_kb.configure(fg_color=COLORS["bg_primary"])

        kb_scroll = ctk.CTkScrollableFrame(tab_kb, fg_color=COLORS["bg_primary"])
        kb_scroll.pack(fill="both", expand=True)

        # Add knowledge
        add_kb_card = ctk.CTkFrame(kb_scroll, **CARD)
        add_kb_card.pack(fill="x", padx=PAD_MD, pady=PAD_SM)
        ctk.CTkLabel(add_kb_card, text="➕ Thêm Kiến Thức (RAG)", font=FONT_HEADING, text_color=COLORS["text_primary"]).pack(anchor="w", padx=PAD_MD, pady=(PAD_SM, PAD_XS))
        ctk.CTkLabel(
            add_kb_card, text="AI sẽ sử dụng kiến thức này khi trả lời. Hữu ích để dạy AI về domain cụ thể.",
            font=FONT_SMALL, text_color=COLORS["text_dim"],
        ).pack(anchor="w", padx=PAD_MD)

        kb_title_row = ctk.CTkFrame(add_kb_card, fg_color="transparent")
        kb_title_row.pack(fill="x", padx=PAD_MD, pady=PAD_SM)
        ctk.CTkLabel(kb_title_row, text="Tiêu đề:", font=FONT_SMALL, text_color=COLORS["text_dim"]).pack(side="left")
        self.kb_title_entry = ctk.CTkEntry(
            kb_title_row, placeholder_text="Tên kiến thức...",
            fg_color=COLORS["bg_input"], border_color=COLORS["border"],
            text_color=COLORS["text_primary"], font=FONT_BODY, corner_radius=8, height=30,
        )
        self.kb_title_entry.pack(side="left", fill="x", expand=True, padx=PAD_SM)

        ctk.CTkLabel(kb_title_row, text="Tags:", font=FONT_SMALL, text_color=COLORS["text_dim"]).pack(side="left")
        self.kb_tags_entry = ctk.CTkEntry(
            kb_title_row, placeholder_text="tag1, tag2",
            fg_color=COLORS["bg_input"], border_color=COLORS["border"],
            text_color=COLORS["text_primary"], font=FONT_BODY, corner_radius=8, height=30, width=130,
        )
        self.kb_tags_entry.pack(side="left", padx=PAD_SM)

        self.kb_content_box = ctk.CTkTextbox(
            add_kb_card, height=100,
            fg_color=COLORS["bg_input"], text_color=COLORS["text_primary"],
            font=FONT_BODY, corner_radius=8,
            border_color=COLORS["border"], border_width=1, wrap="word",
        )
        self.kb_content_box.pack(fill="x", padx=PAD_MD, pady=(0, PAD_SM))

        kb_btn_row = ctk.CTkFrame(add_kb_card, fg_color="transparent")
        kb_btn_row.pack(fill="x", padx=PAD_MD, pady=(0, PAD_SM))
        ctk.CTkButton(
            kb_btn_row, text="💾 Lưu kiến thức", height=32,
            fg_color=COLORS["success"], hover_color="#00c065",
            text_color="#000", corner_radius=8, font=("Inter", 12, "bold"),
            command=self._save_knowledge,
        ).pack(side="left", padx=(0, PAD_SM))
        self.kb_status = ctk.CTkLabel(kb_btn_row, text="", font=FONT_SMALL, text_color=COLORS["text_dim"])
        self.kb_status.pack(side="left")

        # Search + List knowledge
        search_kb_card = ctk.CTkFrame(kb_scroll, **CARD)
        search_kb_card.pack(fill="x", padx=PAD_MD, pady=PAD_SM)
        ctk.CTkLabel(search_kb_card, text="🔍 Tìm kiếm & Quản lý", font=FONT_HEADING, text_color=COLORS["text_primary"]).pack(anchor="w", padx=PAD_MD, pady=(PAD_SM, PAD_XS))

        kb_search_row = ctk.CTkFrame(search_kb_card, fg_color="transparent")
        kb_search_row.pack(fill="x", padx=PAD_MD, pady=PAD_SM)
        self.kb_search_entry = ctk.CTkEntry(
            kb_search_row, placeholder_text="Tìm kiến thức...",
            fg_color=COLORS["bg_input"], border_color=COLORS["border"],
            text_color=COLORS["text_primary"], font=FONT_BODY, corner_radius=8, height=30,
        )
        self.kb_search_entry.pack(side="left", fill="x", expand=True, padx=(0, PAD_SM))
        self.kb_search_entry.bind("<Return>", lambda e: self._search_knowledge())
        ctk.CTkButton(
            kb_search_row, text="🔍 Tìm", width=70, height=30,
            fg_color=COLORS["accent_dim"], hover_color=COLORS["accent"],
            text_color=COLORS["text_primary"], corner_radius=8, font=FONT_SMALL,
            command=self._search_knowledge,
        ).pack(side="left", padx=(0, PAD_XS))
        ctk.CTkButton(
            kb_search_row, text="📋 Tất cả", width=80, height=30,
            fg_color=COLORS["bg_input"], hover_color=COLORS["bg_hover"],
            text_color=COLORS["text_secondary"], corner_radius=8, font=FONT_SMALL,
            command=self._list_all_knowledge,
        ).pack(side="left")

        self.kb_results_frame = ctk.CTkFrame(search_kb_card, fg_color="transparent")
        self.kb_results_frame.pack(fill="x", padx=PAD_MD, pady=(0, PAD_SM))
        ctk.CTkLabel(
            self.kb_results_frame, text="(Bấm 'Tất cả' để xem danh sách)",
            font=FONT_SMALL, text_color=COLORS["text_dim"],
        ).pack(anchor="w")

        # Chat with KB
        kb_chat_card = ctk.CTkFrame(kb_scroll, **CARD)
        kb_chat_card.pack(fill="x", padx=PAD_MD, pady=PAD_SM)
        ctk.CTkLabel(kb_chat_card, text="💡 Hỏi AI với Knowledge Base", font=FONT_HEADING, text_color=COLORS["text_primary"]).pack(anchor="w", padx=PAD_MD, pady=(PAD_SM, PAD_XS))
        ctk.CTkLabel(
            kb_chat_card, text="AI sẽ tìm kiến thức liên quan và đưa vào context trước khi trả lời.",
            font=FONT_SMALL, text_color=COLORS["text_dim"],
        ).pack(anchor="w", padx=PAD_MD)

        self.kb_chat_out = ctk.CTkTextbox(
            kb_chat_card, height=150,
            fg_color=COLORS["bg_input"], text_color=COLORS["text_primary"],
            font=FONT_MONO_SMALL, corner_radius=8,
            border_color=COLORS["border"], border_width=1, wrap="word",
        )
        self.kb_chat_out.pack(fill="x", padx=PAD_MD, pady=(PAD_SM, 0))

        kb_ask_row = ctk.CTkFrame(kb_chat_card, fg_color="transparent")
        kb_ask_row.pack(fill="x", padx=PAD_MD, pady=PAD_SM)
        self.kb_ask_entry = ctk.CTkEntry(
            kb_ask_row, placeholder_text="Hỏi AI với knowledge base...",
            fg_color=COLORS["bg_input"], border_color=COLORS["border"],
            text_color=COLORS["text_primary"], font=FONT_BODY, corner_radius=8, height=34,
        )
        self.kb_ask_entry.pack(side="left", fill="x", expand=True, padx=(0, PAD_SM))
        self.kb_ask_entry.bind("<Return>", lambda e: self._kb_ask())
        ctk.CTkButton(
            kb_ask_row, text="💡 Hỏi", width=70, height=34,
            fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"],
            text_color="#fff", corner_radius=8, font=("Inter", 12, "bold"),
            command=self._kb_ask,
        ).pack(side="right")

    def _build_status_bar(self):
        """Status bar ở cuối."""
        self.status_bar = StatusBar(self)
        self.status_bar.pack(fill="x", side="bottom")

    # ═══════════════════════════════════════════════════════════════
    # ACTIONS
    # ═══════════════════════════════════════════════════════════════

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        self.status_bar.set_busy(busy)
        state = "disabled" if busy else "normal"
        for btn in [self.btn_analyze, self.btn_automate, self.btn_screenshot, self.btn_upload]:
            try:
                btn.configure(state=state)
            except Exception:
                pass

    def _update_context(self) -> None:
        """Cập nhật context label."""
        parts = []
        if self.image_path:
            parts.append(f"📸 {os.path.basename(self.image_path)}")
        if self.file_path:
            parts.append(f"📂 {os.path.basename(self.file_path)}")
        if parts:
            self.context_label.configure(text="📎 " + " | ".join(parts), text_color=COLORS["text_accent"])
        else:
            self.context_label.configure(text="📎 Chưa có đính kèm", text_color=COLORS["text_dim"])

    def _clear_context(self) -> None:
        self.image_path = None
        self.file_path = None
        self._update_context()

    def _on_screenshot(self) -> None:
        try:
            self.image_path = capture_screen()
            self.output_box.log(f"📸 Đã chụp màn hình: {self.image_path}")
            self._update_context()
        except Exception as e:
            self.output_box.log(f"[LỖI] Chụp màn hình: {e}")

    def _on_select_file(self) -> None:
        path = filedialog.askopenfilename(
            title="Chọn file phân tích",
            filetypes=[
                ("Code & Text", "*.py *.ts *.tsx *.js *.html *.css *.txt *.md *.json *.yaml *.yml *.sql"),
                ("Images", "*.png *.jpg *.jpeg *.webp *.bmp *.gif"),
                ("Tất cả", "*.*"),
            ],
        )
        if path:
            self.file_path = path
            self.output_box.log(f"📂 Đã chọn file: {path}")
            self._update_context()

    def _on_clear(self) -> None:
        self.output_box.clear()
        self.question_box.clear()
        self._clear_context()
        self.status_bar.set_status("🧹 Đã xóa")

    def _on_analyze(self) -> None:
        if self._busy:
            return
        question = self.question_box.get_text()
        provider = self.model_selector.provider
        model = self.model_selector.model

        def task():
            try:
                self._set_busy(True)

                # --- AUTO-EYE: Tự động chụp nếu chưa có ảnh ---
                if not self.image_path:
                    from core.screen import capture_screen
                    self.output_box.log("📸 [Hệ thống] Đang tự động quét màn hình...")
                    # Ẩn cửa sổ 1 tích tắc để chụp nội dung phía dưới
                    self.withdraw()
                    time.sleep(0.3)
                    self.image_path = capture_screen()
                    self.deiconify()
                    self._update_context()
                    self.output_box.log(f"✅ Đã quét xong: {os.path.basename(self.image_path)}")

                # Check blocked models
                # Kiểm tra model đặc biệt không hỗ trợ
                _blocked_keywords = ("live", "tts", "image-gen", "embedding")
                if any(kw in model.lower() for kw in _blocked_keywords):
                    self.output_box.log(f"[LỖI] Model '{model}' không hỗ trợ text/vision chat. Chọn model khác.")
                    return

                # Configure API
                from core.analyzer import configure_gemini, analyze_router, analyze_with_aiml, analyze_with_ollama
                from config import AIML_API_KEY

                if provider in ("gemini", "aiml"):
                    try:
                        configure_gemini()
                    except Exception as e:
                        self.output_box.log(f"[LỖI] GEMINI_API_KEY: {e}")
                        return

                if provider == "aiml" and not AIML_API_KEY:
                    self.output_box.log("[LỖI] AIML_API_KEY chưa được đặt.")
                    return

                # Run analysis (Streaming)
                self.output_box.log(f"\n⏳ Đang phân tích... (Provider: {provider}, Model: {model})")
                self.output_box.log("\n═══ KẾT QUẢ ═══\n")
                
                from core.analyzer import stream_router
                
                full_text = ""
                for chunk in stream_router(
                    provider=provider,
                    model_name=model,
                    image_path=self.image_path,
                    file_path=self.file_path,
                    question=question if question else None,
                ):
                    full_text += chunk
                    # Update UI realtime
                    self.output_box.textbox.insert("end", chunk)
                    self.output_box.textbox.see("end")
                    self.update_idletasks() # Force UI refresh
                
                # Sau khi streaming xong, gọi log lần cuối để format lại các block <thought> nếu có
                # (Vì log() có logic re.split thẻ thought)
                if "<thought>" in full_text:
                    self.output_box.clear()
                    self.output_box.log(f"\n✅ Đã hoàn tất phân tích (Provider: {provider}, Model: {model})")
                    self.output_box.log("\n═══ KẾT QUẢ (ĐÃ ĐỊNH DẠNG) ═══\n")
                    self.output_box.log(full_text)
            except Exception as e:
                self.output_box.log(f"[LỖI] {e}")
            finally:
                self._set_busy(False)

        threading.Thread(target=task, daemon=True).start()

    def _on_automate(self) -> None:
        """Chạy AI Agent: Nhìn màn hình → Suy nghĩ → Thao tác → Lặp lại."""
        if self._busy:
            # Nếu đang chạy → dừng
            if hasattr(self, "_current_agent") and self._current_agent:
                self._current_agent.stop()
                self.auto_output.log("\n⛔ Đang dừng agent...")
                self.btn_automate.configure(text="🤖 Khởi động Agent", fg_color=COLORS["success"])
            return

        instruction = self.auto_question.get_text()
        if not instruction:
            self.auto_output.log("⚠️ Vui lòng nhập mục tiêu.")
            return

        provider = self.model_selector.provider
        model = self.model_selector.model
        max_steps = int(self.auto_steps_var.get())
        eye_mode = self.eye_mode_var.get()

        # Đổi nút thành "Dừng"
        self.btn_automate.configure(text="⛔ Dừng Agent", fg_color=COLORS["error"])

        def log(event: str, msg: str):
            """Log realtime với icon theo event type."""
            prefix = {
                "see":   "👁️",
                "think": "🧠",
                "act":   "✋",
                "done":  "🎯",
                "error": "❌",
            }.get(event, "•")
            self.auto_output.log(f"{prefix} {msg}")

        def task():
            try:
                self._set_busy(True)
                self.auto_output.log("━" * 50)
                self.auto_output.log(f"🚀 Agent khởi động — Brain: {provider}/{model}")
                self.auto_output.log(f"🎯 Mục tiêu: \"{instruction}\"")
                self.auto_output.log(f"📋 Max: {max_steps} bước | Eye: {eye_mode}")
                self.auto_output.log("━" * 50)

                # ── KHỞI CHẠY AGENT ĐA NỀN TẢNG ──────────────────────
                from agent.ollama_agent import AutonomousAgent
                
                # Xác định eye_provider dựa trên setting GUI
                eye_p = "ollama" if eye_mode == "ollama" else eye_mode
                
                # Khởi tạo và chạy Agent hợp nhất
                agent = AutonomousAgent(
                    brain_provider=provider,
                    brain_model=model,
                    eye_provider=eye_p,
                    eye_model=self.ollama_eye_var.get() if eye_p == "ollama" else "",
                    max_steps=max_steps,
                    step_delay=0.6,
                    callback=log,
                    hide_ui_callback=lambda: self.after(0, self.iconify),
                    show_ui_callback=lambda: self.after(0, self.deiconify)
                )
                
                self._current_agent = agent
                agent.run(instruction, blocking=True)


            except Exception as e:
                import traceback
                self.auto_output.log(f"❌ Lỗi: {e}\n{traceback.format_exc()}")
            finally:
                self._set_busy(False)
                self._current_agent = None
                self.btn_automate.configure(text="🤖 Khởi động Agent", fg_color=COLORS["success"])

        threading.Thread(target=task, daemon=True).start()




    def _show_about(self) -> None:
        try:
            AboutWindow(self)
        except Exception as e:
            self.output_box.log(f"[LỖI] {e}")

    def _open_shot_window(self) -> None:
        def on_capture():
            try:
                self.image_path = capture_screen()
                self.output_box.log(f"📸 Chụp (cửa sổ phụ): {self.image_path}")
                self._update_context()
            except Exception as e:
                self.output_box.log(f"[LỖI] {e}")
        try:
            ShotWindow(self, on_capture=on_capture)
        except Exception as e:
            self.output_box.log(f"[LỖI] {e}")

    def _open_audio_window(self) -> None:
        def on_analyze(lang):
            try:
                if not self.audio_recorder.wav_path:
                    self.output_box.log("[LỖI] Chưa ghi âm.")
                    return
                transcript = self.audio_recorder.transcribe(language=lang)
                self.output_box.log(f"🎤 Transcript: {transcript}")

                # Auto-analyze with current model
                from core.analyzer import analyze_router, configure_gemini
                try:
                    configure_gemini()
                except Exception:
                    pass

                provider = self.model_selector.provider
                model = self.model_selector.model
                ans = analyze_router(
                    provider=provider, model_name=model,
                    image_path=self.image_path, file_path=None,
                    question=transcript,
                )
                self.output_box.log("\n═══ KẾT QUẢ TỪ ÂM THANH ═══\n")
                self.output_box.log(ans)
            except Exception as e:
                self.output_box.log(f"[LỖI Audio] {e}")

        try:
            AudioWindow(self, recorder=self.audio_recorder, on_analyze=on_analyze)
        except Exception as e:
            self.output_box.log(f"[LỖI] {e}")

    def _on_resize(self, event) -> None:
        """Responsive adjustments."""
        try:
            w = self.winfo_width()
            if w < 600:
                self.btn_screenshot.configure(text="📸")
                self.btn_upload.configure(text="📂")
            else:
                self.btn_screenshot.configure(text="📸 Chụp")
                self.btn_upload.configure(text="📂 File")
        except Exception:
            pass

    # ═══════════════════════════════════════════════════════════════
    # OLLAMA HANDLERS
    # ═══════════════════════════════════════════════════════════════

    def _refresh_ollama(self) -> None:
        """Refresh Ollama status + model list."""
        def task():
            from core.ollama_manager import is_ollama_installed, is_ollama_running, list_models, get_ollama_version

            if not is_ollama_installed():
                self.ollama_status.configure(
                    text="❌ Chưa cài Ollama — Tải tại: ollama.com/download",
                    text_color=COLORS["error"],
                )
                self.ollama_models_label.configure(text="(Ollama chưa cài)")
                return

            version = get_ollama_version()
            running = is_ollama_running()

            if running:
                self.ollama_status.configure(
                    text=f"✅ Đang chạy | {version}",
                    text_color=COLORS["success"],
                )
            else:
                self.ollama_status.configure(
                    text=f"⚠️ Server tắt | {version} — Bấm 'Start Server'",
                    text_color=COLORS["warning"],
                )
                self.ollama_models_label.configure(text="(Server chưa chạy)")
                return

            # Refresh models
            models = list_models()
            # Clear old
            for widget in self.ollama_models_frame.winfo_children():
                widget.destroy()

            if not models:
                ctk.CTkLabel(
                    self.ollama_models_frame, text="(Chưa có model nào. Vào 'Models gợi ý' để Pull)",
                    font=FONT_SMALL, text_color=COLORS["text_dim"],
                ).pack(anchor="w")
            else:
                for m in models:
                    row = ctk.CTkFrame(self.ollama_models_frame, fg_color="transparent")
                    row.pack(fill="x", pady=1)
                    from config.models import is_vision_capable
                    icon = "👁️" if is_vision_capable("ollama", m["name"]) else "🧠"
                    ctk.CTkLabel(
                        row,
                        text=f"{icon} {m['name']}  ({m.get('params','')} | {m['size']} | {m.get('quant','')})",
                        font=FONT_SMALL, text_color=COLORS["text_secondary"],
                    ).pack(side="left")

            # Update model dropdowns
            names = [m["name"] for m in models] if models else ["(chưa có)"]
            try:
                self.chat_model_menu.configure(values=names)
                self.mf_base_menu.configure(values=names)
                if names and names[0] != "(chưa có)":
                    self.chat_model_var.set(names[0])
                    self.mf_base_var.set(names[0])
            except Exception:
                pass

        threading.Thread(target=task, daemon=True).start()

    def _start_ollama(self) -> None:
        """Start Ollama server."""
        def task():
            self.ollama_status.configure(text="⏳ Đang khởi động...", text_color=COLORS["warning"])
            from core.ollama_manager import start_ollama_server
            ok = start_ollama_server()
            if ok:
                self.ollama_status.configure(text="✅ Server đã khởi động!", text_color=COLORS["success"])
                self._refresh_ollama()
            else:
                self.ollama_status.configure(text="❌ Không thể khởi động", text_color=COLORS["error"])

        threading.Thread(target=task, daemon=True).start()

    def _pull_model(self) -> None:
        """Pull model từ Ollama registry."""
        name = self.pull_entry.get().strip()
        if not name:
            self.pull_progress.configure(text="⚠️ Nhập tên model trước")
            return

        def callback(status, progress):
            pct = f" ({progress*100:.0f}%)" if progress > 0 else ""
            self.pull_progress.configure(text=f"⬇ {status}{pct}")

        def task():
            self.pull_progress.configure(text=f"⬇ Đang tải {name}...")
            from core.ollama_manager import pull_model
            ok = pull_model(name, callback=callback)
            if ok:
                self.pull_progress.configure(text=f"✅ {name} đã cài xong!")
                self._refresh_ollama()
            else:
                self.pull_progress.configure(text=f"❌ Lỗi tải {name}")

        threading.Thread(target=task, daemon=True).start()

    def _quick_pull(self, name: str) -> None:
        """Quick pull từ recommended list."""
        self.pull_entry.delete(0, "end")
        self.pull_entry.insert(0, name)
        self._pull_model()

    def _delete_model(self) -> None:
        """Xóa model."""
        name = self.pull_entry.get().strip()
        if not name:
            self.pull_progress.configure(text="⚠️ Nhập tên model cần xóa")
            return

        def task():
            from core.ollama_manager import delete_model
            self.pull_progress.configure(text=f"🗑 Đang xóa {name}...")
            ok = delete_model(name)
            if ok:
                self.pull_progress.configure(text=f"✅ Đã xóa {name}")
                self._refresh_ollama()
            else:
                self.pull_progress.configure(text=f"❌ Lỗi xóa {name}")

        threading.Thread(target=task, daemon=True).start()

    def _load_modelfile_template(self, template_name: str) -> None:
        """Load Modelfile template vào textbox."""
        from core.ollama_manager import MODELFILE_TEMPLATES
        if template_name == "custom":
            self.mf_textbox.delete("1.0", "end")
            self.mf_textbox.insert("1.0", 'FROM {base_model}\nSYSTEM """Viết system prompt ở đây..."""\nPARAMETER temperature 0.7')
            return
        template = MODELFILE_TEMPLATES.get(template_name, "")
        self.mf_textbox.delete("1.0", "end")
        self.mf_textbox.insert("1.0", template)

    def _create_model(self) -> None:
        """Tạo custom model từ Modelfile."""
        name = self.mf_name_entry.get().strip()
        if not name:
            self.mf_status.configure(text="⚠️ Nhập tên model", text_color=COLORS["warning"])
            return

        base = self.mf_base_var.get()
        modelfile_raw = self.mf_textbox.get("1.0", "end").strip()

        # Replace {base_model}
        modelfile = modelfile_raw.replace("{base_model}", base)

        def callback(status):
            self.mf_status.configure(text=status)

        def task():
            from core.ollama_manager import create_model
            self.mf_status.configure(text=f"⏳ Đang tạo '{name}' từ {base}...", text_color=COLORS["warning"])
            ok = create_model(name, modelfile, callback=callback)
            if ok:
                self.mf_status.configure(text=f"✅ Model '{name}' đã tạo thành công!", text_color=COLORS["success"])
                self._refresh_ollama()
            else:
                self.mf_status.configure(text=f"❌ Lỗi tạo model", text_color=COLORS["error"])

        threading.Thread(target=task, daemon=True).start()

    def _reset_ollama_chat(self) -> None:
        """Reset chat history."""
        self._ollama_chat_history = []
        self.chat_output.delete("1.0", "end")
        self.chat_output.insert("1.0", "💬 Chat đã reset. Nhập tin nhắn để bắt đầu.\n")

    def _send_ollama_chat(self) -> None:
        """Gửi tin nhắn và nhận response streaming."""
        msg = self.chat_entry.get().strip()
        if not msg:
            return
        self.chat_entry.delete(0, "end")

        model = self.chat_model_var.get()
        if not model or model == "(chưa có)":
            self.chat_output.insert("end", "\n⚠️ Chưa có model. Tải model trước.\n")
            return

        # Add user message
        self._ollama_chat_history.append({"role": "user", "content": msg})
        self.chat_output.insert("end", f"\n👤 Bạn: {msg}\n")
        self.chat_output.insert("end", f"🤖 {model}: ")
        self.chat_output.see("end")

        def task():
            from core.ollama_manager import chat
            full_response = []
            for chunk in chat(model, self._ollama_chat_history, stream=True):
                full_response.append(chunk)
                self.chat_output.insert("end", chunk)
                self.chat_output.see("end")

            response_text = "".join(full_response)
            self._ollama_chat_history.append({"role": "assistant", "content": response_text})
            self.chat_output.insert("end", "\n")
            self.chat_output.see("end")

        threading.Thread(target=task, daemon=True).start()

    # ═══════════════════════════════════════════════════════════════
    # TRAIN AI HANDLERS
    # ═══════════════════════════════════════════════════════════════

    def _quick_train(self, preset_key: str, name_var, base_var, status_lbl) -> None:
        """Train model từ quick preset."""
        name = name_var.get().strip()
        base = base_var.get().strip()
        if not name or not base:
            status_lbl.configure(text="⚠️ Nhập tên + base", text_color=COLORS["warning"])
            return

        def task():
            from core.ollama_trainer import quick_train
            def callback(msg):
                try:
                    status_lbl.configure(text=msg[:60])
                except Exception:
                    pass
            status_lbl.configure(text="⏳ Đang train...", text_color=COLORS["warning"])
            ok = quick_train(preset_key, name, base, callback=callback)
            if ok:
                status_lbl.configure(text=f"✅ '{name}' sẵn sàng!", text_color=COLORS["success"])
                self._refresh_ollama()
            else:
                status_lbl.configure(text="❌ Train thất bại", text_color=COLORS["error"])

        threading.Thread(target=task, daemon=True).start()

    def _load_custom_template(self) -> None:
        """Load Modelfile template vào custom textbox."""
        from core.ollama_trainer import create_qtus_assistant
        base = self.custom_train_base.get().strip() or "gemma3:4b"
        template = create_qtus_assistant(base)
        self.custom_modelfile_box.delete("1.0", "end")
        self.custom_modelfile_box.insert("1.0", template)

    def _custom_train(self) -> None:
        """Train custom model từ Modelfile content."""
        name = self.custom_train_name.get().strip()
        base = self.custom_train_base.get().strip() or "gemma3:4b"
        modelfile_raw = self.custom_modelfile_box.get("1.0", "end").strip()
        if not name:
            self.custom_train_status.configure(text="⚠️ Nhập tên model", text_color=COLORS["warning"])
            return

        modelfile = modelfile_raw.replace("{base_model}", base)
        if not modelfile.startswith("FROM"):
            modelfile = f"FROM {base}\n{modelfile}"

        def task():
            from core.ollama_manager import create_model
            def callback(msg):
                try:
                    self.custom_train_status.configure(text=msg[:80])
                except Exception:
                    pass
            self.custom_train_status.configure(text=f"⏳ Tạo '{name}'...", text_color=COLORS["warning"])
            ok = create_model(name, modelfile, callback=callback)
            if ok:
                self.custom_train_status.configure(text=f"✅ '{name}' xong!", text_color=COLORS["success"])
                self._refresh_ollama()
            else:
                self.custom_train_status.configure(text="❌ Lỗi!", text_color=COLORS["error"])

        threading.Thread(target=task, daemon=True).start()

    # ═══════════════════════════════════════════════════════════════
    # KNOWLEDGE BASE HANDLERS
    # ═══════════════════════════════════════════════════════════════

    def _get_kb(self):
        from core.ollama_trainer import KnowledgeBase
        return KnowledgeBase("default")

    def _save_knowledge(self) -> None:
        title = self.kb_title_entry.get().strip()
        content = self.kb_content_box.get("1.0", "end").strip()
        tags_raw = self.kb_tags_entry.get().strip()
        tags = [t.strip() for t in tags_raw.split(",") if t.strip()]
        if not title or not content:
            self.kb_status.configure(text="⚠️ Nhập tiêu đề và nội dung", text_color=COLORS["warning"])
            return
        try:
            kb = self._get_kb()
            kb.add(title, content, tags)
            self.kb_status.configure(text=f"✅ Đã lưu! KB: {kb.size} items", text_color=COLORS["success"])
            self.kb_title_entry.delete(0, "end")
            self.kb_tags_entry.delete(0, "end")
            self.kb_content_box.delete("1.0", "end")
        except Exception as e:
            self.kb_status.configure(text=f"❌ {e}", text_color=COLORS["error"])

    def _render_kb_results(self, entries) -> None:
        for widget in self.kb_results_frame.winfo_children():
            widget.destroy()
        if not entries:
            ctk.CTkLabel(self.kb_results_frame, text="(Không có kết quả)", font=FONT_SMALL, text_color=COLORS["text_dim"]).pack(anchor="w")
            return
        for e in entries:
            row = ctk.CTkFrame(self.kb_results_frame, fg_color=COLORS["bg_input"], corner_radius=8)
            row.pack(fill="x", pady=2)
            ctk.CTkLabel(
                row, text=f"[{e['id']}] {e['title']}  — {e['content'][:80]}...",
                font=FONT_SMALL, text_color=COLORS["text_secondary"], anchor="w",
            ).pack(side="left", fill="x", expand=True, padx=PAD_SM, pady=4)
            ctk.CTkButton(
                row, text="🗑", width=30, height=24,
                fg_color="transparent", hover_color="#3d1515",
                text_color=COLORS["error"], corner_radius=6, font=FONT_SMALL,
                command=lambda eid=e["id"]: self._delete_knowledge(eid),
            ).pack(side="right", padx=4)

    def _search_knowledge(self) -> None:
        query = self.kb_search_entry.get().strip()
        if not query:
            return
        self._render_kb_results(self._get_kb().search(query))

    def _list_all_knowledge(self) -> None:
        self._render_kb_results(self._get_kb().list_all())

    def _delete_knowledge(self, entry_id: int) -> None:
        if self._get_kb().delete(entry_id):
            self._list_all_knowledge()

    def _kb_ask(self) -> None:
        """Hỏi AI với knowledge base context."""
        question = self.kb_ask_entry.get().strip()
        if not question:
            return
        self.kb_ask_entry.delete(0, "end")
        model = getattr(self, "chat_model_var", None)
        model = model.get() if model else "gemma3:4b"

        self.kb_chat_out.insert("end", f"\n👤 {question}\n")
        self.kb_chat_out.see("end")

        def task():
            from core.ollama_manager import chat, is_ollama_running
            if not is_ollama_running():
                self.kb_chat_out.insert("end", "❌ Ollama chưa chạy\n")
                return

            kb = self._get_kb()
            ctx = kb.to_context(question)
            full_q = question + (f"\n\n{ctx}" if ctx else "")

            relevant_count = len(kb.search(question))
            self.kb_chat_out.insert("end", f"🤖 {model}")
            if ctx:
                self.kb_chat_out.insert("end", f" [📚 {relevant_count} KB]")
            self.kb_chat_out.insert("end", ": ")
            self.kb_chat_out.see("end")

            messages = [{"role": "user", "content": full_q}]
            for chunk in chat(model, messages, stream=True):
                self.kb_chat_out.insert("end", chunk)
                self.kb_chat_out.see("end")
            self.kb_chat_out.insert("end", "\n")

        threading.Thread(target=task, daemon=True).start()
    def _on_eye_mode_change(self, mode: str) -> None:
        """Cập nhật nhãn trạng thái khi đổi mode Eye."""
        text = {
            "auto": "👁️ Tự động (Khớp với Não)",
            "gemini": "👁️ Gemini Vision API (Cloud)",
            "ollama": "👁️ Ollama Vision (Local)",
        }.get(mode, "👁️ Mắt thần")
        self.eye_status.configure(text=text)
