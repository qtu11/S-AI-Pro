#!/usr/bin/env python3
"""
auto_setup.py — Tự động cài đặt toàn bộ dependencies & Ollama.
Chạy trên máy mới: python auto_setup.py
"""
import sys
import os
import subprocess
import platform
import urllib.request
import time

ROOT = os.path.dirname(os.path.abspath(__file__))

# ─── Colors ──────────────────────────────────────────────────────────
def _c(color, text):
    colors = {"green": "\033[92m", "red": "\033[91m", "yellow": "\033[93m",
              "cyan": "\033[96m", "bold": "\033[1m", "reset": "\033[0m"}
    if sys.platform == "win32":
        return text  # Windows CMD không hỗ trợ ANSI tốt
    return f"{colors.get(color, '')}{text}{colors['reset']}"

def info(msg): print(f"  ℹ {msg}")
def ok(msg):   print(f"  ✅ {msg}")
def warn(msg): print(f"  ⚠️  {msg}")
def err(msg):  print(f"  ❌ {msg}")
def step(msg): print(f"\n{'─'*50}\n  🔧 {msg}")


# ═══════════════════════════════════════════════════════════════════
# 1. PIP PACKAGES
# ═══════════════════════════════════════════════════════════════════

CORE_PACKAGES = [
    # Core AI
    ("google-genai",        "google.genai"),
    ("requests",            "requests"),
    ("python-dotenv",       "dotenv"),
    ("Pillow",              "PIL"),
    ("numpy",               "numpy"),

    # GUI
    ("customtkinter",       "customtkinter"),

    # Screen
    ("mss",                 "mss"),
    ("pyautogui",           "pyautogui"),

    # API providers
    ("openai",              "openai"),
    ("anthropic",           "anthropic"),

    # Audio
    ("sounddevice",         "sounddevice"),
    ("soundfile",           "soundfile"),
    ("SpeechRecognition",   "speech_recognition"),
]

# Heavy packages — optional, chỉ cài khi cần offline vision
OPTIONAL_PACKAGES = [
    ("torch",               "torch"),
    ("transformers",        "transformers"),
    ("accelerate",          "accelerate"),
    ("einops",              "einops"),
]

SERVER_PACKAGES = [
    ("fastapi",             "fastapi"),
    ("uvicorn",             "uvicorn"),
    ("python-multipart",    None),
]


def pip_install(package_name: str, check_import: str = None) -> bool:
    """Cài package nếu chưa có. Returns True nếu OK."""
    # Kiểm tra import trước
    if check_import:
        try:
            __import__(check_import)
            return True  # Đã cài rồi
        except ImportError:
            pass

    info(f"Cài đặt {package_name}...")
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", package_name, "--quiet", "--upgrade"],
        capture_output=True, text=True,
    )
    if result.returncode == 0:
        ok(f"{package_name} đã cài")
        return True
    else:
        err(f"Cài {package_name} thất bại: {result.stderr[:100]}")
        return False


def install_all_packages(include_optional=False, include_server=True):
    step("Cài đặt Python packages (Core)")
    failed = []

    for pkg, imp in CORE_PACKAGES:
        if not pip_install(pkg, imp):
            failed.append(pkg)

    if include_server:
        step("Cài đặt API Server packages")
        for pkg, imp in SERVER_PACKAGES:
            if not pip_install(pkg, imp):
                failed.append(pkg)

    if include_optional:
        step("Cài đặt Vision packages (optional, nặng ~4GB)")
        for pkg, imp in OPTIONAL_PACKAGES:
            if not pip_install(pkg, imp):
                failed.append(pkg)

    if failed:
        warn(f"Các packages cài thất bại: {', '.join(failed)}")
    else:
        ok("Tất cả packages đã cài xong!")

    return failed


# ═══════════════════════════════════════════════════════════════════
# 2. OLLAMA
# ═══════════════════════════════════════════════════════════════════

def check_ollama_installed() -> bool:
    try:
        r = subprocess.run(["ollama", "--version"], capture_output=True, timeout=5)
        return r.returncode == 0
    except Exception:
        return False


def check_ollama_running() -> bool:
    try:
        import requests as req
        r = req.get("http://localhost:11434/api/tags", timeout=3)
        return r.status_code == 200
    except Exception:
        return False


def install_ollama():
    """Hướng dẫn / tự động cài Ollama."""
    step("Cài đặt Ollama")
    sys_name = platform.system().lower()

    if sys_name == "windows":
        print()
        print("  Ollama chưa được cài. Để cài Ollama trên Windows:")
        print("  1. Truy cập: https://ollama.com/download/windows")
        print("  2. Tải file OllamaSetup.exe và chạy")
        print("  3. Sau khi cài xong, chạy lại: python auto_setup.py")
        print()
        warn("Tự động cài Ollama trên Windows cần người dùng chạy installer.")

        # Thử tải installer tự động
        try:
            url = "https://github.com/ollama/ollama/releases/latest/download/OllamaSetup.exe"
            dest = os.path.join(os.path.expanduser("~"), "Downloads", "OllamaSetup.exe")
            print(f"  📥 Đang tải OllamaSetup.exe vào {dest}...")
            urllib.request.urlretrieve(url, dest)
            ok(f"Đã tải xong! Mở file: {dest} để cài đặt")

            # Tự động mở file
            os.startfile(dest)
            print("  ⏳ Đang mở installer... Sau khi cài xong bấm Enter để tiếp tục.")
            input()
        except Exception as e:
            err(f"Không tự động tải được: {e}")

    elif sys_name == "darwin":  # macOS
        try:
            info("Cài Ollama qua brew...")
            subprocess.run(["brew", "install", "ollama"], check=True)
            ok("Ollama đã cài!")
        except Exception:
            print("  curl -fsSL https://ollama.com/install.sh | sh")

    else:  # Linux
        try:
            info("Cài Ollama qua script...")
            subprocess.run(
                "curl -fsSL https://ollama.com/install.sh | sh",
                shell=True, check=True,
            )
            ok("Ollama đã cài!")
        except Exception as e:
            err(f"Lỗi cài Ollama: {e}")


def start_ollama_server():
    """Khởi động Ollama server."""
    info("Khởi động Ollama server...")
    try:
        if platform.system() == "Windows":
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
        # Chờ
        for i in range(15):
            time.sleep(1)
            if check_ollama_running():
                ok("Ollama server đang chạy!")
                return True
            print(f"  Chờ... ({i+1}/15)")
        err("Ollama server không khởi động được trong 15s")
        return False
    except Exception as e:
        err(f"Lỗi start server: {e}")
        return False


def pull_recommended_models():
    """Pull models gợi ý nếu chưa có."""
    step("Kiểm tra Ollama models")

    try:
        import requests as req
        r = req.get("http://localhost:11434/api/tags", timeout=5)
        installed = [m["name"] for m in r.json().get("models", [])]
    except Exception:
        installed = []

    if installed:
        ok(f"Đã có {len(installed)} model(s): {', '.join(installed[:5])}")
        return

    warn("Chưa có model Ollama nào!")
    print()
    print("  Models gợi ý (chọn 1+):")
    MODELS = [
        ("gemma3:4b",        "~3GB",  "Text - nhẹ, đa năng"),
        ("llama3.2:3b",      "~2GB",  "Text - siêu nhẹ"),
        ("moondream:1.8b",   "~1.5GB","Vision - nhẹ nhất (cần cho Eye offline)"),
        ("llava:7b",         "~4.5GB","Vision - mạnh hơn"),
    ]
    for i, (name, size, desc) in enumerate(MODELS, 1):
        print(f"  [{i}] {name} ({size}) — {desc}")

    print()
    choice = input("  Nhập số model muốn tải (VD: 1,3 = model 1 và 3) hoặc Enter để bỏ qua: ").strip()
    if choice:
        import requests as req
        for idx in choice.split(","):
            try:
                model_name = MODELS[int(idx.strip()) - 1][0]
                print(f"  📥 Đang tải {model_name}...")
                resp = req.post(
                    "http://localhost:11434/api/pull",
                    json={"name": model_name, "stream": True},
                    stream=True, timeout=3600,
                )
                for line in resp.iter_lines():
                    if line:
                        import json
                        data = json.loads(line)
                        status = data.get("status", "")
                        if "completed" in data and "total" in data and data["total"] > 0:
                            pct = data["completed"] / data["total"] * 100
                            print(f"\r  {status}: {pct:.1f}%", end="", flush=True)
                        elif status:
                            print(f"\r  {status}          ", end="", flush=True)
                        if data.get("status") == "success":
                            print()
                            ok(f"{model_name} đã tải xong!")
            except (IndexError, ValueError):
                err(f"Số không hợp lệ: {idx}")
            except Exception as e:
                err(f"Lỗi tải model: {e}")


# ═══════════════════════════════════════════════════════════════════
# 3. .ENV SETUP
# ═══════════════════════════════════════════════════════════════════

def setup_env():
    """Tạo/cập nhật file .env."""
    step("Cấu hình API Keys (.env)")

    env_path = os.path.join(ROOT, ".env")
    existing = {}
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    existing[k.strip()] = v.strip()

    KEYS = [
        ("GEMINI_API_KEY",   "Google Gemini API Key (https://aistudio.google.com)"),
        ("OPENAI_API_KEY",   "OpenAI API Key — GPT-4o (https://platform.openai.com)"),
        ("ANTHROPIC_API_KEY","Anthropic API Key — Claude (https://console.anthropic.com)"),
        ("GROQ_API_KEY",     "Groq API Key — Grok fast (https://console.groq.com)"),
        ("DEEPSEEK_API_KEY", "DeepSeek API Key (https://platform.deepseek.com)"),
        ("AIML_API_KEY",     "AIML API Key (https://aimlapi.com) — tùy chọn"),
        ("HF_TOKEN",         "HuggingFace Token — chỉ cần cho offline vision"),
    ]

    updated = dict(existing)
    changed = False

    for key, desc in KEYS:
        current = existing.get(key, "")
        if current:
            ok(f"{key}: đã có")
        else:
            print(f"\n  📌 {desc}")
            val = input(f"  {key} (bỏ qua Enter): ").strip()
            if val:
                updated[key] = val
                changed = True

    if changed:
        with open(env_path, "w", encoding="utf-8") as f:
            f.write("# QtusScreen AI Pro — API Keys\n")
            f.write("# Không commit file này lên git!\n\n")
            for k, v in updated.items():
                f.write(f"{k}={v}\n")
        ok(f".env đã lưu tại {env_path}")
    else:
        info(".env không thay đổi")


# ═══════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════

def main():
    print()
    print("╔══════════════════════════════════════════════════╗")
    print("║   QtusScreen AI Pro — Auto Setup & First Run    ║")
    print("║   Qtus Dev (Anh Tú) © 2025-2026                ║")
    print("╚══════════════════════════════════════════════════╝")
    print()

    # Kiểm tra Python version
    if sys.version_info < (3, 10):
        err(f"Python {sys.version_info.major}.{sys.version_info.minor} — Cần Python 3.10+")
        sys.exit(1)
    ok(f"Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")

    # 1. Cài packages
    include_optional = "--with-vision" in sys.argv
    install_all_packages(include_optional=include_optional)

    # 2. Ollama
    step("Kiểm tra Ollama")
    if check_ollama_installed():
        ok("Ollama đã được cài")
    else:
        warn("Ollama chưa cài!")
        install_ollama()

    if check_ollama_installed():
        if not check_ollama_running():
            start_ollama_server()
        else:
            ok("Ollama server đang chạy")

        pull_recommended_models()

    # 3. .env
    setup_env()

    # 4. Xong
    print()
    print("╔══════════════════════════════════════════════════╗")
    print("║   ✅ Setup hoàn tất! Chạy: python main.py       ║")
    print("╚══════════════════════════════════════════════════╝")
    print()


if __name__ == "__main__":
    main()
