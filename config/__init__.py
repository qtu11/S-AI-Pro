"""
QtusScreen AI Pro v3.0 — Configuration Module
Hỗ trợ: Gemini, OpenAI (GPT), Anthropic (Claude), Groq (Grok),
         DeepSeek, AIML, Ollama (local)
Bản quyền © 2025-2026 Qtus Dev (Anh Tú)
"""
import os
import sys

# ─── Đọc .env 1 lần duy nhất ───────────────────────────────────────
try:
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))
except Exception:
    pass

# ─── App Metadata ───────────────────────────────────────────────────
APP_NAME = "QtusScreen AI Pro"
APP_VERSION = "5.0"
APP_AUTHOR = "Qtus Dev (Anh Tú)"
APP_COPYRIGHT = f"Copyright © 2025-2026 {APP_AUTHOR}"

# ─── Paths ──────────────────────────────────────────────────────────
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCREENSHOT_PATH = os.path.join(PROJECT_DIR, "screen.png")
ENHANCED_PATH   = os.path.join(PROJECT_DIR, "screen_enhanced.png")
DATA_DIR        = os.path.join(PROJECT_DIR, "data")
LOGS_DIR        = os.path.join(DATA_DIR, "logs")

# Tạo thư mục cần thiết
for _d in [DATA_DIR, LOGS_DIR]:
    os.makedirs(_d, exist_ok=True)

# ─── API Keys ───────────────────────────────────────────────────────
GEMINI_API_KEY    = os.getenv("GEMINI_API_KEY", "")
OPENAI_API_KEY    = os.getenv("OPENAI_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
GROQ_API_KEY      = os.getenv("GROQ_API_KEY", "")
DEEPSEEK_API_KEY  = os.getenv("DEEPSEEK_API_KEY", "")
AIML_API_KEY      = os.getenv("AIML_API_KEY", "")
HF_TOKEN          = os.getenv("HF_TOKEN", "")

# ─── API Endpoints ──────────────────────────────────────────────────
AIML_API_URL      = os.getenv("AIML_API_URL",    "https://api.aimlapi.com/v1/chat/completions")
OPENAI_API_URL    = os.getenv("OPENAI_API_URL",   "https://api.openai.com/v1/chat/completions")
ANTHROPIC_API_URL = os.getenv("ANTHROPIC_API_URL","https://api.anthropic.com/v1/messages")
GROQ_API_URL      = os.getenv("GROQ_API_URL",     "https://api.groq.com/openai/v1/chat/completions")
DEEPSEEK_API_URL  = os.getenv("DEEPSEEK_API_URL", "https://api.deepseek.com/chat/completions")
OLLAMA_API_URL    = os.getenv("OLLAMA_API_URL",   "http://localhost:11434")

# ─── Suppress noisy warnings ────────────────────────────────────────
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
if HF_TOKEN:
    os.environ["HF_TOKEN"] = HF_TOKEN


def validate_keys() -> dict:
    """Kiểm tra API keys, trả về dict trạng thái."""
    return {
        "gemini":    bool(GEMINI_API_KEY),
        "openai":    bool(OPENAI_API_KEY),
        "anthropic": bool(ANTHROPIC_API_KEY),
        "groq":      bool(GROQ_API_KEY),
        "deepseek":  bool(DEEPSEEK_API_KEY),
        "aiml":      bool(AIML_API_KEY),
        "hf_token":  bool(HF_TOKEN),
    }


def get_available_providers() -> list:
    """Danh sách providers có API key hợp lệ."""
    providers = ["ollama"]  # Ollama luôn available (local)
    keys = validate_keys()
    mapping = {
        "gemini":    "gemini",
        "openai":    "openai",
        "anthropic": "anthropic",
        "groq":      "groq",
        "deepseek":  "deepseek",
        "aiml":      "aiml",
    }
    for key, provider in mapping.items():
        if keys[key]:
            providers.append(provider)
    return providers
