"""
Custom Widgets — AnimatedButton, StatusBar, ModelSelector, OutputBox.
"""
import customtkinter as ctk
from gui.theme import *


class GlowButton(ctk.CTkButton):
    """Button với hover glow effect."""

    def __init__(self, master, glow_color=None, **kwargs):
        # Merge style
        style = BTN_PRIMARY.copy()
        style.update(kwargs)
        super().__init__(master, **style)
        self._glow_color = glow_color or COLORS["accent_light"]
        self._original_fg = style.get("fg_color", COLORS["accent"])

    def _on_enter(self, event):
        try:
            self.configure(fg_color=self._glow_color)
        except Exception:
            pass

    def _on_leave(self, event):
        try:
            self.configure(fg_color=self._original_fg)
        except Exception:
            pass


class StatusBar(ctk.CTkFrame):
    """Status bar ở cuối cửa sổ — status text + progress."""

    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color=COLORS["bg_secondary"], height=32, **kwargs)
        self.pack_propagate(False)

        self.status_label = ctk.CTkLabel(
            self, text="✨ Sẵn sàng",
            font=FONT_SMALL, text_color=COLORS["text_secondary"],
        )
        self.status_label.pack(side="left", padx=PAD_MD)

        self.progress = ctk.CTkProgressBar(
            self, width=120, height=4,
            fg_color=COLORS["bg_input"],
            progress_color=COLORS["accent"],
        )
        self.progress.pack(side="left", padx=PAD_SM)
        self.progress.set(0)
        self.progress.pack_forget()  # Ẩn mặc định

        self.copyright_label = ctk.CTkLabel(
            self, text="© 2025-2026 Qtus Dev",
            font=FONT_TINY, text_color=COLORS["text_dim"],
        )
        self.copyright_label.pack(side="right", padx=PAD_MD)

    def set_status(self, text: str, color: str = None) -> None:
        self.status_label.configure(
            text=text,
            text_color=color or COLORS["text_secondary"],
        )

    def set_busy(self, busy: bool) -> None:
        if busy:
            self.progress.pack(side="left", padx=PAD_SM, before=self.copyright_label)
            self.progress.set(0)
            self.progress.configure(mode="indeterminate")
            self.progress.start()
            self.set_status("⏳ Đang xử lý...", COLORS["warning"])
        else:
            self.progress.stop()
            self.progress.pack_forget()
            self.set_status("✨ Sẵn sàng", COLORS["success"])


class ModelSelector(ctk.CTkFrame):
    """Provider + Model cascading selector. Hỗ trợ tất cả providers."""

    ALL_PROVIDERS = [
        "gemini", "openai", "anthropic", "groq", "deepseek", "aiml", "ollama"
    ]

    def __init__(self, master, on_change=None, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self._on_change = on_change

        # Provider
        self.provider_var = ctk.StringVar(value="ollama")
        ctk.CTkLabel(self, text="Provider", font=FONT_SMALL, text_color=COLORS["text_dim"]).pack(side="left", padx=(0, 4))
        self.provider_menu = ctk.CTkOptionMenu(
            self,
            values=self.ALL_PROVIDERS,
            variable=self.provider_var,
            width=110, height=30,
            fg_color=COLORS["bg_input"],
            button_color=COLORS["accent_dim"],
            button_hover_color=COLORS["accent"],
            dropdown_fg_color=COLORS["bg_card"],
            dropdown_hover_color=COLORS["bg_hover"],
            font=FONT_SMALL,
            command=self._on_provider_change,
        )
        self.provider_menu.pack(side="left", padx=(0, PAD_MD))

        # Model
        self.model_var = ctk.StringVar(value="gemma3:4b")
        ctk.CTkLabel(self, text="Model", font=FONT_SMALL, text_color=COLORS["text_dim"]).pack(side="left", padx=(0, 4))
        self.model_menu = ctk.CTkOptionMenu(
            self,
            values=["gemma3:4b"],
            variable=self.model_var,
            width=220, height=30,
            fg_color=COLORS["bg_input"],
            button_color=COLORS["accent_dim"],
            button_hover_color=COLORS["accent"],
            dropdown_fg_color=COLORS["bg_card"],
            dropdown_hover_color=COLORS["bg_hover"],
            font=FONT_SMALL,
        )
        self.model_menu.pack(side="left")

        # Init models list
        self._on_provider_change("ollama")

    def _on_provider_change(self, provider: str) -> None:
        from config.models import get_models_for_provider, get_default_model
        models = get_models_for_provider(provider) or [f"{provider}-default"]
        self.model_menu.configure(values=models)
        default = get_default_model(provider)
        if default not in models:
            default = models[0]
        self.model_var.set(default)
        if self._on_change:
            self._on_change(provider, default)

    def refresh_models(self) -> None:
        """Reload model list (hữu ích khi Ollama pull xong)."""
        self._on_provider_change(self.provider_var.get())

    @property
    def provider(self) -> str:
        return self.provider_var.get()

    @property
    def model(self) -> str:
        return self.model_var.get()



class OutputBox(ctk.CTkFrame):
    """Output text box với header + clear button."""

    def __init__(self, master, **kwargs):
        super().__init__(master, **CARD, **kwargs)

        # Header
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=PAD_MD, pady=(PAD_SM, 0))

        ctk.CTkLabel(
            header, text="📋 Kết quả",
            font=FONT_HEADING, text_color=COLORS["text_primary"],
        ).pack(side="left")

        self.btn_clear = ctk.CTkButton(
            header, text="🧹",
            fg_color="transparent", hover_color=COLORS["bg_hover"],
            text_color=COLORS["text_secondary"], corner_radius=8,
            width=30, height=28, font=("Inter", 16),
            command=self.clear,
        )
        self.btn_clear.pack(side="right")

        self.btn_copy = ctk.CTkButton(
            header, text="📋",
            fg_color="transparent", hover_color=COLORS["bg_hover"],
            text_color=COLORS["text_secondary"], corner_radius=8,
            width=30, height=28, font=("Inter", 16),
            command=self.copy_all,
        )
        self.btn_copy.pack(side="right", padx=(0, 4))

        # Text area
        self.textbox = ctk.CTkTextbox(
            self,
            fg_color=COLORS["bg_input"],
            text_color=COLORS["text_primary"],
            font=FONT_MONO_SMALL,
            corner_radius=10,
            border_color=COLORS["border"],
            border_width=1,
            wrap="word",
        )
        self.textbox.pack(fill="both", expand=True, padx=PAD_MD, pady=PAD_SM)

    def log(self, text: str) -> None:
        """Append text with special formatting for thinking blocks."""
        import re
        
        # Define tags for formatting (Note: font option is forbidden in ctk.CTkTextbox)
        self.textbox.tag_config("thinking", foreground=COLORS["accent_light"])
        
        # Check for <thought> blocks
        parts = re.split(r"(<thought>.*?</thought>)", text, flags=re.DOTALL)
        
        for part in parts:
            if part.startswith("<thought>") and part.endswith("</thought>"):
                content = part[9:-10].strip()
                self.textbox.insert("end", "🧠 SUY NGHĨ:\n", "thinking")
                self.textbox.insert("end", f"{content}\n\n", "thinking")
            else:
                self.textbox.insert("end", part)
        
        if not text.endswith("\n"):
            self.textbox.insert("end", "\n")
            
        self.textbox.see("end")

    def clear(self) -> None:
        self.textbox.delete("1.0", "end")

    def copy_all(self) -> None:
        """Copy toàn bộ output."""
        content = self.textbox.get("1.0", "end").strip()
        if content:
            self.clipboard_clear()
            self.clipboard_append(content)

    def set_text(self, text: str) -> None:
        """Replace toàn bộ."""
        self.textbox.delete("1.0", "end")
        self.textbox.insert("1.0", text)
        self.textbox.see("end")


class QuestionBox(ctk.CTkFrame):
    """Input câu hỏi với label + textbox."""

    def __init__(self, master, **kwargs):
        super().__init__(master, **CARD, **kwargs)

        ctk.CTkLabel(
            self, text="💬 Câu hỏi / Lệnh",
            font=FONT_HEADING, text_color=COLORS["text_primary"],
        ).pack(anchor="w", padx=PAD_MD, pady=(PAD_SM, 0))

        self.textbox = ctk.CTkTextbox(
            self, height=80,
            fg_color=COLORS["bg_input"],
            text_color=COLORS["text_primary"],
            font=FONT_BODY,
            corner_radius=10,
            border_color=COLORS["border"],
            border_width=1,
            wrap="word",
        )
        self.textbox.pack(fill="x", padx=PAD_MD, pady=PAD_SM)

    def get_text(self) -> str:
        return self.textbox.get("1.0", "end").strip()

    def clear(self) -> None:
        self.textbox.delete("1.0", "end")
