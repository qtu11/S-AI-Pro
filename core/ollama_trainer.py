"""
Ollama Trainer — Hệ thống "dạy" AI local.
Cho phép:
1. Tạo custom model từ Modelfile (system prompt, personality)
2. Lưu trữ knowledge base (RAG đơn giản)
3. Fine-tune qua GGUF (nếu có)
4. Export/Import conversations
"""
import os
import json
import datetime
from pathlib import Path
from typing import Optional, List, Dict


# ─── Paths ───────────────────────────────────────────────────────────
_ROOT = Path(__file__).parent.parent
DATA_DIR = _ROOT / "data"
KB_DIR = DATA_DIR / "knowledge_base"
MODELS_DIR = DATA_DIR / "custom_models"
CONV_DIR = DATA_DIR / "conversations"

for d in [DATA_DIR, KB_DIR, MODELS_DIR, CONV_DIR]:
    d.mkdir(parents=True, exist_ok=True)


# ═══════════════════════════════════════════════════════════════════════
# MODELFILE BUILDER — Tạo custom Modelfile
# ═══════════════════════════════════════════════════════════════════════

class ModelfileBuilder:
    """Tạo Modelfile để dạy AI personality + knowledge."""

    def __init__(self, base_model: str = "gemma3:4b"):
        self.base_model = base_model
        self.system = ""
        self.parameters: Dict[str, str] = {}
        self.messages: List[Dict] = []  # Few-shot examples
        self.template: str = ""

    def set_system(self, prompt: str) -> "ModelfileBuilder":
        """Set system prompt — định hướng personality của AI."""
        self.system = prompt
        return self

    def set_parameter(self, key: str, value) -> "ModelfileBuilder":
        """
        Set Ollama parameter.
        Phổ biến: temperature (0.0-2.0), top_p, top_k, num_ctx, repeat_penalty
        """
        self.parameters[key] = str(value)
        return self

    def add_example(self, user: str, assistant: str) -> "ModelfileBuilder":
        """Thêm few-shot example — AI học từ ví dụ."""
        self.messages.append({"role": "user", "content": user})
        self.messages.append({"role": "assistant", "content": assistant})
        return self

    def build(self) -> str:
        """Xuất Modelfile content."""
        lines = [f"FROM {self.base_model}"]

        if self.system:
            # Escape triple quotes trong system prompt
            safe_system = self.system.replace('"""', '\\"\\"\\"')
            lines.append(f'\nSYSTEM """{safe_system}"""')

        if self.parameters:
            lines.append("")
            for k, v in self.parameters.items():
                lines.append(f"PARAMETER {k} {v}")

        if self.messages:
            lines.append("")
            for msg in self.messages:
                role = "user" if msg["role"] == "user" else "assistant"
                safe_content = msg["content"].replace('"""', '\\"\\"\\"')
                lines.append(f'MESSAGE {role} """{safe_content}"""')

        if self.template:
            lines.append(f'\nTEMPLATE """{self.template}"""')

        return "\n".join(lines)

    def save(self, name: str) -> Path:
        """Lưu Modelfile ra file."""
        path = MODELS_DIR / f"{name}.Modelfile"
        path.write_text(self.build(), encoding="utf-8")
        return path

    @classmethod
    def load(cls, name: str) -> Optional[str]:
        """Load Modelfile từ file."""
        path = MODELS_DIR / f"{name}.Modelfile"
        if path.exists():
            return path.read_text(encoding="utf-8")
        return None


# ═══════════════════════════════════════════════════════════════════════
# QUICK MODELFILE PRESETS — Các AI personality có sẵn
# ═══════════════════════════════════════════════════════════════════════

def create_qtus_assistant(base_model: str = "gemma3:4b") -> str:
    """Tạo Qtus Assistant — AI cá nhân của chủ tịch."""
    return (
        ModelfileBuilder(base_model)
        .set_system(
            "Bạn là QtusAI — trợ lý AI cá nhân của chủ tịch Anh Tú, được phát triển bởi Qtus Dev.\n"
            "Tính cách:\n"
            "- Thông minh, chuyên nghiệp, thẳng thắn\n"
            "- Luôn gọi người dùng là 'chủ tịch'\n"
            "- Trả lời ngắn gọn, đúng trọng tâm, không lan man\n"
            "- Ưu tiên giải pháp thực tế và code chạy được\n"
            "- Có kỹ năng sâu về: Python, Web, Database, Security, DevOps\n"
            "- Luôn trả lời bằng tiếng Việt trừ khi được yêu cầu khác"
        )
        .set_parameter("temperature", 0.7)
        .set_parameter("top_p", 0.9)
        .set_parameter("num_ctx", 8192)
        .set_parameter("repeat_penalty", 1.1)
        .add_example(
            "Bạn là ai?",
            "Tôi là QtusAI — trợ lý AI cá nhân của chủ tịch. Tôi chạy hoàn toàn trên máy tính của chủ tịch, không cần internet."
        )
        .add_example(
            "Viết hello world bằng Python",
            "```python\nprint('Hello, World!')\n```\nChạy bằng: `python hello.py`"
        )
        .build()
    )


def create_coder_ai(base_model: str = "qwen2.5:7b") -> str:
    """Tạo AI chuyên code."""
    return (
        ModelfileBuilder(base_model)
        .set_system(
            "You are an expert software engineer with 20+ years of experience.\n"
            "Always:\n"
            "- Write clean, efficient, well-documented code\n"
            "- Explain your reasoning briefly\n"
            "- Follow best practices for the language\n"
            "- Point out potential bugs and security issues\n"
            "- Suggest optimizations when relevant"
        )
        .set_parameter("temperature", 0.3)
        .set_parameter("num_ctx", 16384)
        .build()
    )


def create_security_ai(base_model: str = "gemma3:4b") -> str:
    """Tạo AI bảo mật."""
    return (
        ModelfileBuilder(base_model)
        .set_system(
            "Bạn là chuyên gia An ninh mạng (Cybersecurity Expert).\n"
            "Chuyên môn:\n"
            "- Phân tích lỗ hổng bảo mật (OWASP Top 10)\n"
            "- Kiểm tra SQL Injection, XSS, CSRF, SSRF, RCE\n"
            "- Code review bảo mật\n"
            "- Tư vấn bảo mật hệ thống\n"
            "- Phân tích log tìm dấu hiệu tấn công\n"
            "Trả lời bằng tiếng Việt, ngắn gọn, chuyên nghiệp."
        )
        .set_parameter("temperature", 0.4)
        .set_parameter("num_ctx", 8192)
        .build()
    )


def create_automation_brain(base_model: str = "gemma3:4b") -> str:
    """Tạo AI Brain cho automation agent."""
    return (
        ModelfileBuilder(base_model)
        .set_system(OllamaAgent_SYSTEM if False else _AUTOMATION_SYSTEM)
        .set_parameter("temperature", 0.2)
        .set_parameter("top_p", 0.8)
        .set_parameter("num_ctx", 4096)
        .build()
    )


_AUTOMATION_SYSTEM = """Bạn là AI Agent chuyên tự động hoá thao tác máy tính.
Khi nhận mô tả màn hình + mục tiêu:
1. Phân tích màn hình hiện tại
2. Quyết định hành động tiếp theo
3. Trả lời ĐÚNG 1 dòng action

FORMAT (chọn 1):
CLICK <element>
DOUBLECLICK <element>
TYPE <text>
PRESS <key>
HOTKEY <key1+key2>
SCROLL UP/DOWN <n>
WAIT <giây>
SCREENSHOT
DONE"""


# ═══════════════════════════════════════════════════════════════════════
# KNOWLEDGE BASE — RAG đơn giản
# ═══════════════════════════════════════════════════════════════════════

class KnowledgeBase:
    """
    Lưu trữ kiến thức cho AI (RAG đơn giản, dùng file JSON).
    Không cần vector DB — phù hợp với project nhỏ-vừa.
    """

    def __init__(self, name: str = "default"):
        self.name = name
        self.path = KB_DIR / f"{name}.json"
        self._data: List[Dict] = self._load()

    def _load(self) -> List[Dict]:
        if self.path.exists():
            try:
                return json.loads(self.path.read_text(encoding="utf-8"))
            except Exception:
                return []
        return []

    def _save(self) -> None:
        self.path.write_text(
            json.dumps(self._data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def add(self, title: str, content: str, tags: List[str] = None) -> None:
        """Thêm kiến thức mới."""
        entry = {
            "id": len(self._data) + 1,
            "title": title,
            "content": content,
            "tags": tags or [],
            "created_at": datetime.datetime.now().isoformat(),
        }
        self._data.append(entry)
        self._save()

    def search(self, query: str, limit: int = 3) -> List[Dict]:
        """Tìm kiếm kiến thức liên quan (keyword search đơn giản)."""
        query_words = query.lower().split()
        results = []

        for entry in self._data:
            text = (entry["title"] + " " + entry["content"] + " " + " ".join(entry["tags"])).lower()
            score = sum(1 for word in query_words if word in text)
            if score > 0:
                results.append((score, entry))

        results.sort(key=lambda x: x[0], reverse=True)
        return [e for _, e in results[:limit]]

    def delete(self, entry_id: int) -> bool:
        for i, entry in enumerate(self._data):
            if entry["id"] == entry_id:
                self._data.pop(i)
                self._save()
                return True
        return False

    def list_all(self) -> List[Dict]:
        return self._data.copy()

    def to_context(self, query: str) -> str:
        """Chuyển knowledge liên quan thành context string cho LLM."""
        relevant = self.search(query)
        if not relevant:
            return ""
        parts = ["=== Kiến thức liên quan ==="]
        for e in relevant:
            parts.append(f"\n**{e['title']}**\n{e['content']}")
        return "\n".join(parts)

    @property
    def size(self) -> int:
        return len(self._data)


# ═══════════════════════════════════════════════════════════════════════
# CONVERSATION MANAGER — Lưu/tải hội thoại
# ═══════════════════════════════════════════════════════════════════════

class ConversationManager:
    """Quản lý lưu trữ lịch sử hội thoại."""

    def save(self, name: str, messages: List[Dict], model: str = "") -> Path:
        """Lưu conversation."""
        data = {
            "name": name,
            "model": model,
            "created_at": datetime.datetime.now().isoformat(),
            "messages": messages,
        }
        safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in name)
        path = CONV_DIR / f"{safe_name}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def load(self, filename: str) -> Optional[Dict]:
        """Load conversation từ file."""
        path = CONV_DIR / filename
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                return None
        return None

    def list_all(self) -> List[Dict]:
        """Danh sách tất cả conversations đã lưu."""
        result = []
        for f in sorted(CONV_DIR.glob("*.json"), reverse=True):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                result.append({
                    "filename": f.name,
                    "name": data.get("name", f.stem),
                    "model": data.get("model", ""),
                    "created_at": data.get("created_at", ""),
                    "message_count": len(data.get("messages", [])),
                })
            except Exception:
                continue
        return result

    def delete(self, filename: str) -> bool:
        path = CONV_DIR / filename
        if path.exists():
            path.unlink()
            return True
        return False


# ═══════════════════════════════════════════════════════════════════════
# QUICK TRAIN — Dạy nhanh qua Modelfile
# ═══════════════════════════════════════════════════════════════════════

QUICK_PRESETS = {
    "qtus_assistant": {
        "label": "🤖 Qtus Assistant (AI cá nhân)",
        "desc": "Trợ lý thông minh, nói tiếng Việt, gọi 'chủ tịch'",
        "builder": create_qtus_assistant,
        "default_base": "gemma3:4b",
    },
    "coder": {
        "label": "💻 Coder AI (chuyên code)",
        "desc": "Expert lập trình, clean code, best practices",
        "builder": create_coder_ai,
        "default_base": "qwen2.5:7b",
    },
    "security": {
        "label": "🔒 Security AI (bảo mật)",
        "desc": "Chuyên bảo mật, tìm lỗ hổng, tư vấn bảo mật",
        "builder": create_security_ai,
        "default_base": "gemma3:4b",
    },
    "automation": {
        "label": "🤖 Automation Brain (điều khiển máy tính)",
        "desc": "AI điều khiển máy tính, automation agent",
        "builder": create_automation_brain,
        "default_base": "gemma3:4b",
    },
}


def quick_train(preset_name: str, model_name: str, base_model: str, callback=None) -> bool:
    """
    Train nhanh model từ preset.
    preset_name: key trong QUICK_PRESETS
    model_name: tên model sẽ tạo (VD: 'my-qtus')
    base_model: base model Ollama (VD: 'gemma3:4b')
    """
    from core.ollama_manager import create_model, is_ollama_running

    if not is_ollama_running():
        if callback:
            callback("❌ Ollama server chưa chạy!")
        return False

    preset = QUICK_PRESETS.get(preset_name)
    if not preset:
        if callback:
            callback(f"❌ Preset '{preset_name}' không tồn tại")
        return False

    if callback:
        callback(f"⏳ Đang tạo '{model_name}' từ {base_model}...")

    modelfile = preset["builder"](base_model)
    ok = create_model(model_name, modelfile, callback=callback)

    if ok and callback:
        callback(f"✅ Model '{model_name}' đã sẵn sàng!")

    return ok
