"""
Model Registry — Danh sách models cho tất cả providers.
Bản quyền © 2025-2026 Qtus Dev (Anh Tú)
"""

# ═══════════════════════════════════════════════════════════════════
# PROVIDER → MODELS MAPPING
# ═══════════════════════════════════════════════════════════════════

PROVIDER_MODELS = {
    "gemini": [
        "gemini-2.5-pro",
        "gemini-2.5-flash",
        "gemini-2.0-flash",
        "gemini-2.0-flash-lite",
        "gemini-1.5-pro",
        "gemini-1.5-flash",
    ],
    "openai": [
        "gpt-4o",
        "gpt-4o-mini",
        "gpt-4-turbo",
        "gpt-4",
        "gpt-3.5-turbo",
        "o1",
        "o1-mini",
        "o3-mini",
    ],
    "anthropic": [
        "claude-opus-4-5",
        "claude-sonnet-4-5",
        "claude-3-5-sonnet-20241022",
        "claude-3-5-haiku-20241022",
        "claude-3-opus-20240229",
        "claude-3-haiku-20240307",
    ],
    "groq": [
        "llama-3.3-70b-versatile",
        "llama-3.1-8b-instant",
        "llama3-70b-8192",
        "llama3-8b-8192",
        "mixtral-8x7b-32768",
        "llama-3.2-90b-vision-preview",
        "llama-3.2-11b-vision-preview",
        "gemma2-9b-it",
        "deepseek-r1-distill-llama-70b",
    ],
    "deepseek": [
        "deepseek-chat",
        "deepseek-reasoner",
        "deepseek-coder",
        "deepseek-vl-7b-chat",
    ],
    "aiml": [
        "o4-mini",
        "o3",
        "gpt-4.5",
        "claude-sonnet-4-5",
        "meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo",
        "mistralai/Mistral-7B-Instruct-v0.2",
    ],
    "ollama": [
        "llama3.2-vision:11b",
        "moondream:latest",
        "deepseek-r1:7b",
        "gemma3:4b",
        "gemma3:1b",
        "luna:latest",
    ],
}

# Models mặc định cho từng provider
DEFAULT_MODELS = {
    "gemini":    "gemini-2.5-flash",
    "openai":    "gpt-4o-mini",
    "anthropic": "claude-3-5-haiku-20241022",
    "groq":      "llama-3.1-8b-instant",
    "deepseek":  "deepseek-chat",
    "aiml":      "gpt-4o-mini",
    "ollama":    "gemma3:4b",
}

# Models có khả năng Vision (xử lý ảnh)
VISION_CAPABLE = {
    "gemini": True,   # Tất cả Gemini đều hỗ trợ vision
    "openai": [       # Chỉ gpt-4o và mới hơn
        "gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "o1", "o3-mini",
    ],
    "anthropic": True,  # Tất cả Claude 3+ hỗ trợ vision
    "groq": [           # Chỉ vision models
        "llama-3.2-90b-vision-preview", "llama-3.2-11b-vision-preview",
    ],
    "deepseek": [       # Chỉ VL models
        "deepseek-vl-7b-chat",
    ],
    "aiml": True,       # Tùy model
    "ollama": [         # Vision models Ollama
        "llava", "llava:7b", "llava:13b", "llava:34b",
        "moondream", "moondream:latest",
        "llama3.2-vision", "llama3.2-vision:11b",
        "gemma3", "gemma3:4b", "gemma3:1b",
        "bakllava", "minicpm-v",
    ],
}

# ═══════════════════════════════════════════════════════════════════
# PROVIDER LABELS (hiển thị trong GUI)
# ═══════════════════════════════════════════════════════════════════

PROVIDER_LABELS = {
    "gemini":    "🔵 Gemini (Google)",
    "openai":    "🟢 OpenAI (GPT)",
    "anthropic": "🟣 Anthropic (Claude)",
    "groq":      "⚡ Groq (Fast LLaMA)",
    "deepseek":  "🔶 DeepSeek",
    "aiml":      "🌐 AIML API",
    "ollama":    "🦙 Ollama (Local)",
}

# ═══════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════

def get_models_for_provider(provider: str) -> list:
    """Lấy danh sách models cho provider."""
    provider = provider.lower()

    # Ollama: load dynamic từ server
    if provider == "ollama":
        try:
            import requests
            resp = requests.get("http://localhost:11434/api/tags", timeout=3)
            if resp.status_code == 200:
                dynamic = [m["name"] for m in resp.json().get("models", [])]
                if dynamic:
                    return dynamic
        except Exception:
            pass
        return PROVIDER_MODELS.get("ollama", ["gemma3:4b"])

    return PROVIDER_MODELS.get(provider, [])


def get_default_model(provider: str) -> str:
    """Model mặc định cho provider."""
    return DEFAULT_MODELS.get(provider.lower(), "gemma3:4b")


def is_vision_capable(provider: str, model_name: str = "") -> bool:
    """Kiểm tra provider/model có hỗ trợ vision không."""
    provider = provider.lower()
    cap = VISION_CAPABLE.get(provider, False)

    if isinstance(cap, bool):
        return cap
    if isinstance(cap, list):
        base = model_name.split(":")[0].lower()
        return any(
            model_name.lower() == v.lower() or
            model_name.lower().startswith(v.lower().split(":")[0])
            for v in cap
        )
    return False


# Re-export cho backward compatibility
OLLAMA_VISION_CAPABLE = VISION_CAPABLE["ollama"]
ALL_PROVIDERS = PROVIDER_MODELS  # Legacy alias


def is_vision_model(model_name: str) -> bool:
    """Backward compat: kiểm tra Ollama vision model."""
    return is_vision_capable("ollama", model_name)

def is_ollama_vision_model(model_name: str) -> bool:
    """Alias cho code cũ."""
    return is_vision_model(model_name)
