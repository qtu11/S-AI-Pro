"""
Theme Module — Color palette, fonts, spacing cho GUI premium.
"""

# ─── Color Palette (Deep Space) ─────────────────────────────────────
COLORS = {
    # Backgrounds
    "bg_primary": "#08080f",
    "bg_secondary": "#10101c",
    "bg_card": "#151525",
    "bg_input": "#1a1a2e",
    "bg_hover": "#222240",

    # Accents
    "accent": "#6c63ff",
    "accent_hover": "#5a52d4",
    "accent_light": "#8b85ff",
    "accent_dim": "#3d3799",
    "cyan": "#00d4ff",
    "cyan_dim": "#007a99",

    # Status
    "success": "#00e676",
    "warning": "#ffab40",
    "error": "#ff5252",
    "info": "#448aff",

    # Text
    "text_primary": "#f0f0f8",
    "text_secondary": "#8888aa",
    "text_dim": "#555570",
    "text_accent": "#a5a0ff",

    # Borders
    "border": "#2a2a42",
    "border_light": "#3a3a5a",
    "border_accent": "#6c63ff40",
}

# ─── Button Styles ──────────────────────────────────────────────────
BTN_PRIMARY = {
    "fg_color": COLORS["accent"],
    "hover_color": COLORS["accent_hover"],
    "text_color": "#ffffff",
    "corner_radius": 10,
    "font": ("Inter", 13, "bold"),
}

BTN_SECONDARY = {
    "fg_color": COLORS["bg_card"],
    "hover_color": COLORS["bg_hover"],
    "text_color": COLORS["text_primary"],
    "border_color": COLORS["border"],
    "border_width": 1,
    "corner_radius": 10,
    "font": ("Inter", 12),
}

BTN_DANGER = {
    "fg_color": "#3d1515",
    "hover_color": "#5a1f1f",
    "text_color": COLORS["error"],
    "corner_radius": 10,
    "font": ("Inter", 12),
}

BTN_SUCCESS = {
    "fg_color": "#0d3320",
    "hover_color": "#15503a",
    "text_color": COLORS["success"],
    "corner_radius": 10,
    "font": ("Inter", 12),
}

BTN_ICON = {
    "fg_color": "transparent",
    "hover_color": COLORS["bg_hover"],
    "text_color": COLORS["text_secondary"],
    "corner_radius": 8,
    "width": 36,
    "height": 36,
    "font": ("Inter", 16),
}

# ─── Fonts ──────────────────────────────────────────────────────────
FONT_TITLE = ("Inter", 22, "bold")
FONT_HEADING = ("Inter", 15, "bold")
FONT_BODY = ("Inter", 13)
FONT_SMALL = ("Inter", 11)
FONT_TINY = ("Inter", 9)
FONT_MONO = ("Cascadia Code", 12)
FONT_MONO_SMALL = ("Cascadia Code", 11)

# ─── Spacing ────────────────────────────────────────────────────────
PAD_XS = 4
PAD_SM = 8
PAD_MD = 12
PAD_LG = 16
PAD_XL = 24

# ─── Card Style ─────────────────────────────────────────────────────
CARD = {
    "fg_color": COLORS["bg_card"],
    "corner_radius": 14,
    "border_color": COLORS["border"],
    "border_width": 1,
}

# ─── Input Style ────────────────────────────────────────────────────
INPUT = {
    "fg_color": COLORS["bg_input"],
    "border_color": COLORS["border"],
    "border_width": 1,
    "corner_radius": 10,
    "text_color": COLORS["text_primary"],
    "font": FONT_BODY,
}
