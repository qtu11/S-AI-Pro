"""
Task Templates — Built-in và custom templates.
Copyright © 2025-2026 Qtus Dev (Anh Tú)
"""
import os
import json
from typing import List, Dict, Optional
from config import DATA_DIR


BUILTIN_TEMPLATES = [
    {
        "id": "open_chrome_search",
        "name": "🔍 Tìm kiếm Google",
        "description": "Mở Chrome và tìm kiếm trên Google",
        "goal": "Mở Google Chrome, vào google.com, tìm kiếm '{query}'",
        "variables": {"query": ""},
        "category": "browser",
        "icon": "🔍",
    },
    {
        "id": "open_youtube",
        "name": "🎵 Mở YouTube",
        "description": "Mở YouTube và tìm kiếm/phát nhạc",
        "goal": "Mở Google Chrome, vào youtube.com, tìm kiếm '{query}' và phát video đầu tiên",
        "variables": {"query": ""},
        "category": "browser",
        "icon": "🎵",
    },
    {
        "id": "open_notepad",
        "name": "📝 Mở Notepad",
        "description": "Mở Notepad và gõ nội dung",
        "goal": "Mở Notepad, gõ nội dung: '{content}'",
        "variables": {"content": ""},
        "category": "system",
        "icon": "📝",
    },
    {
        "id": "screenshot_save",
        "name": "📸 Chụp màn hình",
        "description": "Chụp màn hình và lưu",
        "goal": "Chụp màn hình bằng phím Print Screen, mở Paint, dán ảnh và lưu",
        "variables": {},
        "category": "system",
        "icon": "📸",
    },
    {
        "id": "open_vscode",
        "name": "💻 Mở VS Code",
        "description": "Mở VS Code và tạo file mới",
        "goal": "Mở Visual Studio Code, tạo file mới, gõ '{content}'",
        "variables": {"content": ""},
        "category": "dev",
        "icon": "💻",
    },
    {
        "id": "open_file_explorer",
        "name": "📁 Mở File Explorer",
        "description": "Mở File Explorer và điều hướng đến thư mục",
        "goal": "Mở File Explorer, điều hướng đến '{path}'",
        "variables": {"path": ""},
        "category": "system",
        "icon": "📁",
    },
]

_CUSTOM_PATH = os.path.join(DATA_DIR, "custom_templates.json")


def get_all_templates() -> List[Dict]:
    """Lấy tất cả templates (builtin + custom)."""
    custom = _load_custom()
    return BUILTIN_TEMPLATES + custom


def get_template(template_id: str) -> Optional[Dict]:
    """Tìm template theo ID."""
    for t in get_all_templates():
        if t.get("id") == template_id:
            return t
    return None


def save_custom_template(template: Dict) -> Dict:
    """Lưu custom template."""
    custom = _load_custom()
    # Generate ID
    if not template.get("id"):
        template["id"] = f"custom_{len(custom) + 1}_{int(__import__('time').time())}"
    template["category"] = template.get("category", "custom")

    # Update or add
    found = False
    for i, t in enumerate(custom):
        if t.get("id") == template["id"]:
            custom[i] = template
            found = True
            break
    if not found:
        custom.append(template)

    _save_custom(custom)
    return template


def delete_custom_template(template_id: str) -> bool:
    """Xóa custom template."""
    custom = _load_custom()
    before = len(custom)
    custom = [t for t in custom if t.get("id") != template_id]
    if len(custom) < before:
        _save_custom(custom)
        return True
    return False


def apply_template(template_id: str, variables: Dict[str, str]) -> Optional[str]:
    """Apply template với variables → trả về goal string."""
    template = get_template(template_id)
    if not template:
        return None
    goal = template.get("goal", "")
    for key, value in variables.items():
        goal = goal.replace(f"{{{key}}}", value)
    return goal


def _load_custom() -> List[Dict]:
    try:
        if os.path.exists(_CUSTOM_PATH):
            with open(_CUSTOM_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return []


def _save_custom(templates: List[Dict]):
    try:
        with open(_CUSTOM_PATH, "w", encoding="utf-8") as f:
            json.dump(templates, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
