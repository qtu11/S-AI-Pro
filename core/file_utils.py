"""
File utilities — MIME detection, file reading.
"""
import os
import mimetypes


_MIME_OVERRIDES = {
    ".py": "text/x-python",
    ".js": "text/javascript",
    ".ts": "text/typescript",
    ".tsx": "text/tsx",
    ".jsx": "text/jsx",
    ".css": "text/css",
    ".html": "text/html",
    ".md": "text/markdown",
    ".txt": "text/plain",
    ".json": "application/json",
    ".yaml": "text/yaml",
    ".yml": "text/yaml",
    ".toml": "text/toml",
    ".xml": "application/xml",
    ".sql": "text/x-sql",
    ".sh": "text/x-shellscript",
    ".bat": "text/x-batch",
    ".ps1": "text/x-powershell",
    ".c": "text/x-c",
    ".cpp": "text/x-c++",
    ".h": "text/x-c",
    ".java": "text/x-java",
    ".rs": "text/x-rust",
    ".go": "text/x-go",
    ".rb": "text/x-ruby",
    ".php": "text/x-php",
    ".swift": "text/x-swift",
    ".kt": "text/x-kotlin",
    ".scala": "text/x-scala",
    ".r": "text/x-r",
    ".lua": "text/x-lua",
    ".dart": "text/x-dart",
    ".vue": "text/x-vue",
    ".svelte": "text/x-svelte",
}


def guess_mime(file_path: str) -> str:
    """Xác định MIME type dựa trên extension."""
    ext = os.path.splitext(file_path)[1].lower()
    if ext in _MIME_OVERRIDES:
        return _MIME_OVERRIDES[ext]
    guess, _ = mimetypes.guess_type(file_path)
    return guess or "application/octet-stream"


def read_file_as_text(file_path: str, max_bytes: int = 800_000) -> str:
    """Đọc file dạng text, tự detect encoding."""
    try:
        with open(file_path, "rb") as f:
            data = f.read(max_bytes)
        try:
            return data.decode("utf-8", errors="replace")
        except Exception:
            return data.decode("latin-1", errors="replace")
    except Exception as e:
        return f"[Không thể đọc file: {e}]"


def get_file_info(file_path: str) -> dict:
    """Lấy thông tin file nhanh."""
    if not os.path.exists(file_path):
        return {"exists": False}
    stat = os.stat(file_path)
    return {
        "exists": True,
        "name": os.path.basename(file_path),
        "size_bytes": stat.st_size,
        "size_human": _human_size(stat.st_size),
        "ext": os.path.splitext(file_path)[1].lower(),
        "mime": guess_mime(file_path),
    }


def _human_size(size_bytes: int) -> str:
    """Convert bytes sang human readable."""
    for unit in ("B", "KB", "MB", "GB"):
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"
