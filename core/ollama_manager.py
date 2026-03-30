"""
Ollama Manager — Full local AI management.
Quản lý server, models, chat, vision, modelfile.
Bản quyền © 2025-2026 Qtus Dev (Anh Tú)
"""
import os
import json
import subprocess
import threading
import time
from typing import Optional, List, Dict, Generator
import requests


# ═══════════════════════════════════════════════════════════════
# OLLAMA SERVER MANAGEMENT
# ═══════════════════════════════════════════════════════════════

OLLAMA_BASE = "http://localhost:11434"


def is_ollama_installed() -> bool:
    """Kiểm tra Ollama đã được cài đặt chưa."""
    try:
        result = subprocess.run(
            ["ollama", "--version"],
            capture_output=True, text=True, timeout=5,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def is_ollama_running() -> bool:
    """Kiểm tra Ollama server có đang chạy không."""
    try:
        resp = requests.get(f"{OLLAMA_BASE}/api/tags", timeout=3)
        return resp.status_code == 200
    except Exception:
        return False


def start_ollama_server() -> bool:
    """Khởi động Ollama server nếu chưa chạy."""
    if is_ollama_running():
        return True
    try:
        if os.name == "nt":
            subprocess.Popen(
                ["ollama", "serve"],
                creationflags=subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        else:
            subprocess.Popen(
                ["ollama", "serve"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        # Chờ server khởi động
        for _ in range(15):
            time.sleep(1)
            if is_ollama_running():
                return True
        return False
    except Exception:
        return False


def get_ollama_version() -> str:
    """Lấy phiên bản Ollama."""
    try:
        result = subprocess.run(
            ["ollama", "--version"],
            capture_output=True, text=True, timeout=5,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        return result.stdout.strip()
    except Exception:
        return "N/A"


# ═══════════════════════════════════════════════════════════════
# MODEL MANAGEMENT
# ═══════════════════════════════════════════════════════════════

def list_models() -> List[Dict]:
    """Danh sách models đã cài."""
    try:
        resp = requests.get(f"{OLLAMA_BASE}/api/tags", timeout=10)
        resp.raise_for_status()
        data = resp.json()
        models = data.get("models", [])
        result = []
        for m in models:
            size_gb = m.get("size", 0) / (1024 ** 3)
            result.append({
                "name": m.get("name", ""),
                "model": m.get("model", m.get("name", "")),
                "size": f"{size_gb:.1f}GB",
                "size_bytes": m.get("size", 0),
                "modified": m.get("modified_at", ""),
                "family": m.get("details", {}).get("family", ""),
                "params": m.get("details", {}).get("parameter_size", ""),
                "quant": m.get("details", {}).get("quantization_level", ""),
            })
        return result
    except Exception:
        return []


def list_model_names() -> List[str]:
    """Danh sách tên models nhanh."""
    models = list_models()
    return [m["name"] for m in models] if models else ["(chưa có model)"]


def list_running_models() -> List[Dict]:
    """Danh sách models đang chạy (loaded in memory)."""
    try:
        resp = requests.get(f"{OLLAMA_BASE}/api/ps", timeout=5)
        resp.raise_for_status()
        return resp.json().get("models", [])
    except Exception:
        return []


def show_model_info(model_name: str) -> Dict:
    """Xem thông tin chi tiết của model."""
    try:
        resp = requests.post(
            f"{OLLAMA_BASE}/api/show",
            json={"name": model_name},
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        return {"error": str(e)}


def pull_model(model_name: str, callback=None) -> bool:
    """
    Tải model từ Ollama registry.
    callback(status: str, progress: float) — progress 0.0-1.0
    """
    try:
        resp = requests.post(
            f"{OLLAMA_BASE}/api/pull",
            json={"name": model_name, "stream": True},
            stream=True, timeout=600,
        )
        resp.raise_for_status()

        total = 0
        completed = 0
        for line in resp.iter_lines():
            if not line:
                continue
            try:
                data = json.loads(line)
                status = data.get("status", "")
                if "total" in data:
                    total = data["total"]
                if "completed" in data:
                    completed = data["completed"]

                progress = completed / total if total > 0 else 0
                if callback:
                    callback(status, progress)

                if data.get("status") == "success":
                    if callback:
                        callback("✅ Hoàn thành!", 1.0)
                    return True
            except json.JSONDecodeError:
                continue

        return True
    except Exception as e:
        if callback:
            callback(f"❌ Lỗi: {e}", 0)
        return False


def delete_model(model_name: str) -> bool:
    """Xóa model."""
    try:
        resp = requests.delete(
            f"{OLLAMA_BASE}/api/delete",
            json={"name": model_name},
            timeout=30,
        )
        return resp.status_code == 200
    except Exception:
        return False


def unload_model(model_name: str) -> bool:
    """Giải phóng model khỏi bộ nhớ (VRAM)."""
    try:
        resp = requests.post(
            f"{OLLAMA_BASE}/api/chat",
            json={"model": model_name, "keep_alive": 0},
            timeout=10
        )
        return resp.status_code == 200
    except Exception:
        return False


def copy_model(source: str, destination: str) -> bool:
    """Copy model (tạo alias)."""
    try:
        resp = requests.post(
            f"{OLLAMA_BASE}/api/copy",
            json={"source": source, "destination": destination},
            timeout=30,
        )
        return resp.status_code == 200
    except Exception:
        return False


# ═══════════════════════════════════════════════════════════════
# MODELFILE — TẠO/DẠY AI TÙY CHỈNH
# ═══════════════════════════════════════════════════════════════

def create_model(model_name: str, modelfile: str, callback=None) -> bool:
    """
    Tạo custom model từ Modelfile content.
    Đây là cách "dạy" Ollama — tạo model với system prompt riêng.

    Ví dụ Modelfile:
    FROM gemma3:4b
    SYSTEM "Bạn là trợ lý AI thông minh, trả lời bằng tiếng Việt..."
    PARAMETER temperature 0.7
    PARAMETER top_p 0.9
    """
    try:
        resp = requests.post(
            f"{OLLAMA_BASE}/api/create",
            json={"name": model_name, "modelfile": modelfile, "stream": True},
            stream=True, timeout=300,
        )
        resp.raise_for_status()

        for line in resp.iter_lines():
            if not line:
                continue
            try:
                data = json.loads(line)
                status = data.get("status", "")
                if callback:
                    callback(status)
                if "success" in status.lower():
                    return True
            except json.JSONDecodeError:
                continue

        return True
    except Exception as e:
        if callback:
            callback(f"❌ Lỗi: {e}")
        return False


# Mẫu Modelfile cho các use case phổ biến
MODELFILE_TEMPLATES = {
    "vietnamese_assistant": """FROM {base_model}
SYSTEM \"\"\"Bạn là trợ lý AI thông minh của Qtus Dev.
- Luôn trả lời bằng tiếng Việt.
- Ngắn gọn, chính xác, chuyên nghiệp.
- Khi được hỏi về code, trả lời với giải thích rõ ràng.
- Gọi người dùng là 'chủ tịch'.\"\"\"
PARAMETER temperature 0.7
PARAMETER top_p 0.9
PARAMETER num_ctx 4096""",

    "coder": """FROM {base_model}
SYSTEM \"\"\"You are an expert programmer with 20+ years of experience.
- Write clean, efficient, well-documented code.
- Always explain your reasoning.
- Follow best practices for the language being used.
- Optimize for performance and readability.\"\"\"
PARAMETER temperature 0.3
PARAMETER top_p 0.95
PARAMETER num_ctx 8192""",

    "security_analyst": """FROM {base_model}
SYSTEM \"\"\"Bạn là chuyên gia an ninh mạng (Cybersecurity Expert).
- Phân tích lỗ hổng bảo mật chuyên sâu.
- Đề xuất giải pháp bảo mật cụ thể.
- Kiểm tra code tìm SQL Injection, XSS, CSRF, SSRF.
- Trả lời bằng tiếng Việt, ngắn gọn, chuyên nghiệp.\"\"\"
PARAMETER temperature 0.4
PARAMETER top_p 0.9
PARAMETER num_ctx 8192""",

    "automation_brain": """FROM {base_model}
SYSTEM \"\"\"Bạn là AI Agent chuyên tự động hoá thao tác máy tính.
Khi được cho ảnh chụp màn hình và mục tiêu:
1. Phân tích màn hình hiện tại.
2. Quyết định hành động tiếp theo.
3. Trả lời ĐÚNG 1 dòng action duy nhất.

Format action: CLICK [target] | TYPE [text] | PRESS [key] | HOTKEY [keys] | SCROLL [direction] | WAIT [seconds] | DONE

Ví dụ:
- CLICK nút Start
- TYPE Hello World
- PRESS enter
- HOTKEY ctrl+s
- DONE\"\"\"
PARAMETER temperature 0.2
PARAMETER top_p 0.8
PARAMETER num_ctx 4096""",
}


# ═══════════════════════════════════════════════════════════════
# CHAT — HỘI THOẠI VỚI OLLAMA
# ═══════════════════════════════════════════════════════════════

def chat(
    model_name: str,
    messages: List[Dict],
    stream: bool = True,
    images: Optional[List[str]] = None,
    timeout: int = 300,
) -> Generator[str, None, None]:
    """
    Chat với Ollama model — streaming response.

    messages: [{"role": "user/assistant/system", "content": "..."}]
    images: list of base64-encoded images (cho vision models)

    Yields: từng chunk text
    """
    payload = {
        "model": model_name,
        "messages": messages,
        "stream": stream,
    }

    # Thêm images vào message cuối (nếu có)
    if images and messages:
        last_msg = messages[-1].copy()
        last_msg["images"] = images
        payload["messages"] = messages[:-1] + [last_msg]

    try:
        resp = requests.post(
            f"{OLLAMA_BASE}/api/chat",
            json=payload,
            stream=stream,
            timeout=timeout,
        )
        resp.raise_for_status()

        if stream:
            for line in resp.iter_lines():
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    # Support for DeepSeek-R1 <thought> tags (some Ollama versions might put them here)
                    if "message" in data:
                        msg = data["message"]
                        if "content" in msg:
                            yield msg["content"]
                    
                    if data.get("done", False):
                        break
                except json.JSONDecodeError:
                    continue
        else:
            data = resp.json()
            if "message" in data and "content" in data["message"]:
                yield data["message"]["content"]
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 500:
            yield f"\n[Lỗi 500] Ollama server gặp sự cố khi nạp '{model_name}'. Có thể do thiếu VRAM hoặc model bị lỗi. Đang thử giải phóng bộ nhớ..."
            unload_model(model_name)
        else:
            yield f"\n[Lỗi API] {e}"
    except requests.exceptions.ReadTimeout:
        yield f"\n[Timeout] Model '{model_name}' xử lý quá lâu. Thử model nhẹ hơn."
    except requests.exceptions.ConnectionError:
        yield "\n[Lỗi] Không kết nối được Ollama. Chạy 'ollama serve' trước."
    except Exception as e:
        yield f"\n[Lỗi] {e}"


def chat_sync(
    model_name: str,
    messages: List[Dict],
    images: Optional[List[str]] = None,
    timeout: int = 300,
) -> str:
    """Chat không streaming — trả về toàn bộ response."""
    parts = []
    for chunk in chat(model_name, messages, stream=True, images=images, timeout=timeout):
        parts.append(chunk)
    return "".join(parts)


def generate(
    model_name: str,
    prompt: str,
    system: str = "",
    images: Optional[List[str]] = None,
    timeout: int = 300,
) -> str:
    """Generate text (không chat history) — đơn giản hơn chat."""
    payload = {
        "model": model_name,
        "prompt": prompt,
        "stream": False,
    }
    if system:
        payload["system"] = system
    if images:
        payload["images"] = images

    try:
        resp = requests.post(
            f"{OLLAMA_BASE}/api/generate",
            json=payload,
            timeout=timeout,
        )
        resp.raise_for_status()
        return resp.json().get("response", "")
    except requests.exceptions.ReadTimeout:
        return f"[Timeout] Model '{model_name}' xử lý quá lâu."
    except requests.exceptions.ConnectionError:
        return "[Lỗi] Không kết nối được Ollama."
    except Exception as e:
        return f"[Lỗi] {e}"


# ═══════════════════════════════════════════════════════════════
# VISION — GỬI ẢNH CHO OLLAMA VISION MODELS
# ═══════════════════════════════════════════════════════════════

# Models hỗ trợ vision trên Ollama
VISION_MODELS = [
    "llava", "llava:7b", "llava:13b", "llava:34b",
    "llava-llama3", "llava-phi3",
    "bakllava",
    "moondream", "moondream:1.8b",
    "llama3.2-vision", "llama3.2-vision:11b", "llama3.2-vision:90b",
    "minicpm-v",
    "granite3.2-vision",
]


def is_vision_model(model_name: str) -> bool:
    """Kiểm tra model có hỗ trợ vision không."""
    base = model_name.split(":")[0].lower()
    vision_bases = [
        "llava", "bakllava", "moondream",
        "llama3.2-vision", "minicpm-v", "granite3.2-vision",
        "gemma3",
    ]
    return any(base.startswith(v) for v in vision_bases)


def image_to_base64(image_path: str) -> str:
    """Chuyển file ảnh sang base64."""
    import base64
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def vision_analyze(
    model_name: str,
    image_path: str,
    question: str = "Mô tả chi tiết những gì bạn thấy trong ảnh.",
    timeout: int = 300,
) -> str:
    """Phân tích ảnh bằng Ollama vision model."""
    img_b64 = image_to_base64(image_path)
    return generate(
        model_name=model_name,
        prompt=question,
        images=[img_b64],
        timeout=timeout,
    )


def vision_find_element(
    model_name: str,
    image_path: str,
    element_description: str,
    timeout: int = 120,
) -> Optional[Dict]:
    """
    Dùng vision model để tìm vị trí element trên màn hình.
    Returns: {"x": float, "y": float} (tỉ lệ 0-1) hoặc None
    """
    import re

    img_b64 = image_to_base64(image_path)
    prompt = (
        f"Tìm vị trí CHÍNH XÁC của phần tử UI: \"{element_description}\"\n"
        f"Trả lời ĐÚNG format: COORDS x_ratio y_ratio\n"
        f"(x_ratio, y_ratio là số 0.0-1.0, ví dụ: COORDS 0.5 0.3)\n"
        f"Nếu không tìm thấy: NOT_FOUND"
    )

    result = generate(
        model_name=model_name,
        prompt=prompt,
        images=[img_b64],
        timeout=timeout,
    )

    match = re.search(r"COORDS\s+([\d.]+)\s+([\d.]+)", result)
    if match:
        x, y = float(match.group(1)), float(match.group(2))
        if 0 <= x <= 1 and 0 <= y <= 1:
            return {"x": x, "y": y}

    return None


# ═══════════════════════════════════════════════════════════════
# AUTO-SETUP — TỰ ĐỘNG CÀI ĐẶT & CẤU HÌNH
# ═══════════════════════════════════════════════════════════════

def auto_setup(callback=None) -> Dict:
    """
    Tự động kiểm tra & setup Ollama.
    Returns: {"installed": bool, "running": bool, "models": list, "version": str}
    """
    result = {
        "installed": False,
        "running": False,
        "models": [],
        "version": "N/A",
    }

    if callback:
        callback("Kiểm tra Ollama...")

    # 1. Check installed
    result["installed"] = is_ollama_installed()
    if not result["installed"]:
        if callback:
            callback("❌ Ollama chưa cài. Tải tại: https://ollama.com/download")
        return result

    result["version"] = get_ollama_version()
    if callback:
        callback(f"✅ Ollama {result['version']}")

    # 2. Check/start server
    if callback:
        callback("Kiểm tra Ollama server...")

    if not is_ollama_running():
        if callback:
            callback("Đang khởi động Ollama server...")
        start_ollama_server()

    result["running"] = is_ollama_running()
    if not result["running"]:
        if callback:
            callback("❌ Không thể khởi động Ollama server")
        return result

    if callback:
        callback("✅ Server đang chạy")

    # 3. List models
    result["models"] = list_models()
    if callback:
        count = len(result["models"])
        callback(f"✅ {count} model(s) đã cài")

    return result


# ═══════════════════════════════════════════════════════════════
# RECOMMENDED MODELS — GỢI Ý MODELS PHÙ HỢP
# ═══════════════════════════════════════════════════════════════

RECOMMENDED_MODELS = [
    {
        "name": "gemma3:4b",
        "desc": "Google Gemma 3 4B — Đa phương thức, cực mạnh",
        "size": "~3.3GB",
        "use": "Chat, code, nhìn màn hình (Vision)",
        "vision": True,
    },
    {
        "name": "gemma3:1b",
        "desc": "Google Gemma 3 1B — Siêu nhẹ, đa phương thức",
        "size": "~815MB",
        "use": "Automation, nhìn màn hình nhanh",
        "vision": True,
    },
    {
        "name": "deepseek-r1:7b",
        "desc": "DeepSeek R1 7B — Suy luận như o1",
        "size": "~4.7GB",
        "use": "Giải quyết vấn đề phức tạp, code",
        "vision": False,
    },
    {
        "name": "llama3.2-vision:11b",
        "desc": "Meta LLaMA 3.2 Vision 11B — Vision pro",
        "size": "~7.8GB",
        "use": "Phân tích ảnh chi tiết, Eye cho agent",
        "vision": True,
    },
    {
        "name": "moondream:latest",
        "desc": "Moondream — \"Mắt thần\" siêu nhỏ",
        "size": "~1.7GB",
        "use": "Eye cho automation, OCR nhanh",
        "vision": True,
    },
    {
        "name": "luna:latest",
        "desc": "Luna — Chatbot tinh gọn",
        "size": "~3.3GB",
        "use": "Hội thoại cơ bản",
        "vision": False,
    },
]
