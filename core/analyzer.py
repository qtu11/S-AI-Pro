"""
Multi-Provider AI Analyzer — Router cho tất cả AI providers.
Hỗ trợ: Gemini, OpenAI (GPT-4o), Anthropic (Claude), Groq (fast), DeepSeek, AIML, Ollama
Mỗi provider đều hỗ trợ Vision (ảnh màn hình) khi model có khả năng.
Bản quyền © 2025-2026 Qtus Dev (Anh Tú)
"""
import os
import base64
import subprocess
from typing import Optional, Generator

import requests

from config import (
    GEMINI_API_KEY, OPENAI_API_KEY, ANTHROPIC_API_KEY,
    GROQ_API_KEY, DEEPSEEK_API_KEY, AIML_API_KEY,
    OPENAI_API_URL, ANTHROPIC_API_URL, GROQ_API_URL,
    DEEPSEEK_API_URL, AIML_API_URL, OLLAMA_API_URL,
)
from config.prompts import (
    SYSTEM_INSTRUCTION,
    AIML_SYSTEM_INSTRUCTION,
    USER_ANALYSIS_PROMPT,
    VISION_OCR_PROMPT,
    VISION_SCREEN_PROMPT,
)
from core.screen import enhance_image, image_to_png_bytes
from core.file_utils import guess_mime, read_file_as_text


# ═══════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════

def _image_to_b64(image_path: str) -> str:
    """Chuyển file ảnh sang base64 string."""
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def _enhance_image_safe(image_path: str) -> str:
    """Enhance ảnh, fallback về original nếu lỗi."""
    try:
        return enhance_image(image_path)
    except Exception:
        return image_path


def _build_openai_messages(
    question: str,
    image_path: Optional[str] = None,
    file_path: Optional[str] = None,
    system_prompt: str = SYSTEM_INSTRUCTION,
) -> list:
    """Tạo messages format OpenAI (dùng cho OpenAI, Groq, DeepSeek, AIML)."""
    user_content = []

    # Text
    text = USER_ANALYSIS_PROMPT.format(question=question or "Phân tích nội dung.")
    if file_path and os.path.exists(file_path):
        file_text = read_file_as_text(file_path)
        text += f"\n\nĐính kèm file:\n```\n{file_text}\n```"
    user_content.append({"type": "text", "text": text})

    # Image (base64 inline)
    if image_path and os.path.exists(image_path):
        img_path = _enhance_image_safe(image_path)
        b64 = _image_to_b64(img_path)
        user_content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/png;base64,{b64}", "detail": "high"},
        })

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]


def _call_openai_compatible(
    url: str,
    api_key: str,
    model: str,
    messages: list,
    timeout: int = 120,
    extra_headers: dict = None,
) -> str:
    """Gọi OpenAI-compatible API (OpenAI, Groq, DeepSeek, AIML)."""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    if extra_headers:
        headers.update(extra_headers)

    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.3,
        "max_tokens": 4096,
    }

    resp = requests.post(url, headers=headers, json=payload, timeout=timeout)

    if resp.status_code == 401:
        raise RuntimeError(f"API Key không hợp lệ (401). Kiểm tra lại .env")
    if resp.status_code == 404:
        raise RuntimeError(f"Model '{model}' không tồn tại (404)")
    if resp.status_code == 429:
        raise RuntimeError(f"Quá giới hạn rate limit. Thử lại sau.")
    resp.raise_for_status()

    data = resp.json()
    try:
        return data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError):
        return str(data)


# ═══════════════════════════════════════════════════════════════════
# PROVIDER: GEMINI
# ═══════════════════════════════════════════════════════════════════

def configure_gemini(api_key: Optional[str] = None) -> None:
    """Cấu hình Gemini API key."""
    key = api_key or GEMINI_API_KEY
    if not key:
        raise RuntimeError("Thiếu GEMINI_API_KEY. Đặt trong .env")
    os.environ["GEMINI_API_KEY"] = key


def analyze_with_gemini(
    image_path: Optional[str] = None,
    file_path: Optional[str] = None,
    question: Optional[str] = None,
    model_name: str = "gemini-2.5-flash",
) -> str:
    """Phân tích bằng Gemini — hỗ trợ ảnh + file + text."""
    configure_gemini()

    try:
        from google import genai
        from google.genai import types
    except ImportError:
        raise RuntimeError("Thiếu google-genai. Chạy: pip install google-genai")

    client = genai.Client()
    prompt = USER_ANALYSIS_PROMPT.format(question=question or "Phân tích nội dung.")
    contents = [prompt]

    if image_path and os.path.exists(image_path):
        img_path = _enhance_image_safe(image_path)
        contents.append(
            types.Part.from_bytes(data=image_to_png_bytes(img_path), mime_type="image/png")
        )

    if file_path and os.path.exists(file_path):
        with open(file_path, "rb") as fh:
            contents.append(types.Part.from_bytes(data=fh.read(), mime_type=guess_mime(file_path)))

    try:
        response = client.models.generate_content(
            model=model_name, contents=contents,
            config=types.GenerateContentConfig(system_instruction=SYSTEM_INSTRUCTION),
        )
        return getattr(response, "text", str(response))
    except Exception as e:
        msg = str(e)
        # Fallback model nếu 404
        if ("not found" in msg.lower() or "404" in msg) and model_name != "gemini-2.5-flash":
            response = client.models.generate_content(
                model="gemini-2.5-flash", contents=contents,
                config=types.GenerateContentConfig(system_instruction=SYSTEM_INSTRUCTION),
            )
            return getattr(response, "text", str(response))
        raise


# ═══════════════════════════════════════════════════════════════════
# PROVIDER: OPENAI (GPT-4o / GPT-4o-mini / ...)
# ═══════════════════════════════════════════════════════════════════

def analyze_with_openai(
    model_name: str,
    question: str,
    image_path: Optional[str] = None,
    file_path: Optional[str] = None,
) -> str:
    """Phân tích bằng OpenAI GPT — hỗ trợ Vision (GPT-4o)."""
    if not OPENAI_API_KEY:
        raise RuntimeError("Thiếu OPENAI_API_KEY. Đặt trong .env")

    messages = _build_openai_messages(question, image_path, file_path)
    return _call_openai_compatible(OPENAI_API_URL, OPENAI_API_KEY, model_name, messages)


# ═══════════════════════════════════════════════════════════════════
# PROVIDER: ANTHROPIC (Claude)
# ═══════════════════════════════════════════════════════════════════

def analyze_with_anthropic(
    model_name: str,
    question: str,
    image_path: Optional[str] = None,
    file_path: Optional[str] = None,
) -> str:
    """Phân tích bằng Claude — hỗ trợ Vision."""
    if not ANTHROPIC_API_KEY:
        raise RuntimeError("Thiếu ANTHROPIC_API_KEY. Đặt trong .env")

    user_content = []
    text = USER_ANALYSIS_PROMPT.format(question=question or "Phân tích nội dung.")
    if file_path and os.path.exists(file_path):
        text += f"\n\nĐính kèm:\n```\n{read_file_as_text(file_path)}\n```"

    if image_path and os.path.exists(image_path):
        img_path = _enhance_image_safe(image_path)
        b64 = _image_to_b64(img_path)
        user_content.append({
            "type": "image",
            "source": {"type": "base64", "media_type": "image/png", "data": b64},
        })

    user_content.append({"type": "text", "text": text})

    payload = {
        "model": model_name,
        "max_tokens": 4096,
        "system": SYSTEM_INSTRUCTION,
        "messages": [{"role": "user", "content": user_content}],
    }

    headers = {
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }

    resp = requests.post(ANTHROPIC_API_URL, headers=headers, json=payload, timeout=120)
    if resp.status_code == 401:
        raise RuntimeError("ANTHROPIC_API_KEY không hợp lệ")
    resp.raise_for_status()

    data = resp.json()
    try:
        return data["content"][0]["text"].strip()
    except Exception:
        return str(data)


# ═══════════════════════════════════════════════════════════════════
# PROVIDER: GROQ (Grok — siêu nhanh)
# ═══════════════════════════════════════════════════════════════════

def analyze_with_groq(
    model_name: str,
    question: str,
    image_path: Optional[str] = None,
    file_path: Optional[str] = None,
) -> str:
    """Phân tích bằng Groq (LLaMA, Mixtral siêu nhanh)."""
    if not GROQ_API_KEY:
        raise RuntimeError("Thiếu GROQ_API_KEY. Đặt trong .env")

    # Groq vision: chỉ llama-3.2-*-vision
    has_vision = "vision" in model_name.lower()
    messages = _build_openai_messages(
        question,
        image_path if has_vision else None,  # Groq text models không nhận ảnh
        file_path,
    )

    # Fallback text nếu không có vision
    if image_path and not has_vision:
        try:
            vision_summary = analyze_with_gemini(image_path=image_path, question=VISION_SCREEN_PROMPT)
            messages[-1]["content"][0]["text"] += f"\n\n[Màn hình]:\n{vision_summary}"
        except Exception:
            pass

    return _call_openai_compatible(GROQ_API_URL, GROQ_API_KEY, model_name, messages)


# ═══════════════════════════════════════════════════════════════════
# PROVIDER: DEEPSEEK
# ═══════════════════════════════════════════════════════════════════

def analyze_with_deepseek(
    model_name: str,
    question: str,
    image_path: Optional[str] = None,
    file_path: Optional[str] = None,
) -> str:
    """Phân tích bằng DeepSeek."""
    if not DEEPSEEK_API_KEY:
        raise RuntimeError("Thiếu DEEPSEEK_API_KEY. Đặt trong .env")

    # DeepSeek text models không có vision (trừ deepseek-vl)
    has_vision = "vl" in model_name.lower() or "vision" in model_name.lower()

    # Nếu có ảnh nhưng model không vision → bridge Gemini
    if image_path and not has_vision:
        try:
            # Dùng Gemini 3.1 Flash-Lite làm mắt thần siêu cấp (miễn phí, nhanh)
            vision_text = analyze_with_gemini(
                image_path=image_path, 
                question=VISION_SCREEN_PROMPT,
                model_name="gemini-2.5-flash" # Fallback to stable version
            )
            question = f"{question}\n\n[👁️ MẮT THẦN PHÂN TÍCH MÀN HÌNH]:\n{vision_text}"
            image_path = None
        except Exception:
            pass

    messages = _build_openai_messages(question, image_path if has_vision else None, file_path)
    return _call_openai_compatible(DEEPSEEK_API_URL, DEEPSEEK_API_KEY, model_name, messages)


# ═══════════════════════════════════════════════════════════════════
# PROVIDER: AIML
# ═══════════════════════════════════════════════════════════════════

def analyze_with_aiml(
    model_id: str,
    question: str,
    image_path: Optional[str] = None,
    file_path: Optional[str] = None,
) -> str:
    """Phân tích bằng AIML API — hỗ trợ nhiều models."""
    if not AIML_API_KEY:
        raise RuntimeError("Thiếu AIML_API_KEY.")

    # AIML hỗ trợ vision qua image_url
    messages = _build_openai_messages(question, image_path, file_path, AIML_SYSTEM_INSTRUCTION)
    return _call_openai_compatible(AIML_API_URL, AIML_API_KEY, model_id, messages)


# ═══════════════════════════════════════════════════════════════════
# PROVIDER: OLLAMA (local)
# ═══════════════════════════════════════════════════════════════════

def _ensure_ollama_running() -> bool:
    """Đảm bảo Ollama đang chạy. Trả về True nếu OK."""
    try:
        requests.get(f"{OLLAMA_API_URL}/api/tags", timeout=2)
        return True
    except Exception:
        pass

    # Thử start
    try:
        startupinfo = None
        if os.name == "nt":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        subprocess.Popen(
            ["ollama", "serve"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            startupinfo=startupinfo,
        )
        import time
        for _ in range(10):
            time.sleep(1)
            try:
                requests.get(f"{OLLAMA_API_URL}/api/tags", timeout=1)
                return True
            except Exception:
                pass
    except Exception:
        pass
    return False


def stream_ollama(
    model_name: str,
    question: str,
    image_path: Optional[str] = None,
    file_path: Optional[str] = None,
    timeout: int = 300,
) -> Generator[str, None, None]:
    """Phân tích bằng Ollama local LLM — bản streaming."""
    if not _ensure_ollama_running():
        yield "[LỖI Ollama] Server không khởi động được. Chạy 'ollama serve' trong terminal."
        return

    from core.ollama_manager import chat, is_vision_model

    content = question or "Phân tích nội dung."
    if file_path and os.path.exists(file_path):
        content += f"\n\nĐính kèm:\n```\n{read_file_as_text(file_path)}\n```"

    images = None
    if image_path and os.path.exists(image_path):
        if is_vision_model(model_name):
            images = [base64.b64encode(open(image_path, "rb").read()).decode("utf-8")]
        else:
            vision_text = ""
            try:
                from core.ollama_manager import list_model_names, generate, image_to_base64
                if "moondream:latest" in list_model_names():
                    img_b64 = image_to_base64(image_path)
                    vision_text = generate(
                        model_name="moondream:latest",
                        prompt=VISION_SCREEN_PROMPT,
                        images=[img_b64],
                        timeout=60
                    )
            except Exception:
                pass

            if not vision_text and GEMINI_API_KEY:
                try:
                    vision_text = analyze_with_gemini(image_path=image_path, question=VISION_SCREEN_PROMPT)
                except Exception:
                    pass
            
            if vision_text:
                content += f"\n\n[👁️ MẮT THẦN PHÂN TÍCH MÀN HÌNH]:\n{vision_text}"

    messages = [
        {"role": "system", "content": AIML_SYSTEM_INSTRUCTION},
        {"role": "user", "content": content},
    ]

    try:
        for chunk in chat(model_name, messages, images=images, timeout=timeout):
            yield chunk
    except Exception as e:
        yield f"[LỖI Ollama] {e}"


def analyze_with_ollama(
    model_name: str,
    question: str,
    image_path: Optional[str] = None,
    file_path: Optional[str] = None,
) -> str:
    """Bản đồng bộ cho analyze_with_ollama."""
    parts = []
    for chunk in stream_ollama(model_name, question, image_path, file_path):
        parts.append(chunk)
    return "".join(parts)


# ═══════════════════════════════════════════════════════════════════
# MAIN ROUTER
# ═══════════════════════════════════════════════════════════════════

def analyze_router(
    provider: str,
    model_name: str,
    image_path: Optional[str] = None,
    file_path: Optional[str] = None,
    question: Optional[str] = None,
) -> str:
    """
    Router chính — dispatch tới provider phù hợp.
    Tự động xử lý vision (ảnh màn hình) theo khả năng của model.

    Providers: gemini | openai | anthropic | groq | deepseek | aiml | ollama
    """
    provider = (provider or "gemini").lower().strip()
    q = question or "Phân tích nội dung."

    try:
        if provider == "gemini":
            return analyze_with_gemini(image_path, file_path, q, model_name)

        elif provider == "openai":
            return analyze_with_openai(model_name, q, image_path, file_path)

        elif provider in ("anthropic", "claude"):
            return analyze_with_anthropic(model_name, q, image_path, file_path)

        elif provider in ("groq", "grok"):
            return analyze_with_groq(model_name, q, image_path, file_path)

        elif provider == "deepseek":
            return analyze_with_deepseek(model_name, q, image_path, file_path)

        elif provider == "aiml":
            return analyze_with_aiml(model_name, q, image_path, file_path)

        elif provider == "ollama":
            return analyze_with_ollama(model_name, q, image_path, file_path)

        else:
            # Unknown provider → fallback Gemini
            if GEMINI_API_KEY:
                return analyze_with_gemini(image_path, file_path, q, "gemini-2.5-flash")
            elif OPENAI_API_KEY:
                return analyze_with_openai("gpt-4o-mini", q, image_path, file_path)
            else:
                return analyze_with_ollama(model_name, q, image_path, file_path)

    except RuntimeError as e:
        # Lỗi cấu hình (thiếu key) → thông báo rõ ràng
        return f"[LỖI Cấu hình] {e}\n→ Chạy 'python auto_setup.py' để cấu hình."
    except requests.exceptions.ConnectionError:
        return f"[LỖI Mạng] Không kết nối được {provider}. Kiểm tra internet."
    except requests.exceptions.Timeout:
        return f"[LỖI Timeout] {provider}/{model_name} xử lý quá lâu."
    except Exception as e:
        return f"[LỖI {provider}] {type(e).__name__}: {e}"
def stream_router(
    provider: str,
    model_name: str,
    image_path: Optional[str] = None,
    file_path: Optional[str] = None,
    question: Optional[str] = None,
) -> Generator[str, None, None]:
    """Bản streaming của router."""
    provider = (provider or "gemini").lower().strip()
    
    if provider == "ollama":
        for chunk in stream_ollama(model_name, question, image_path, file_path):
            yield chunk
    else:
        # Với các provider khác (Cloud), tạm thời dùng bản sync rồi yield 1 lần
        # (Để nâng cấp streaming cloud sau nếu cần)
        yield analyze_router(provider, model_name, image_path, file_path, question)
