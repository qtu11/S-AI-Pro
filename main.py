"""
QtusScreen AI Pro v5.0 — Entry Point.
Bản quyền © 2025-2026 Qtus Dev (Anh Tú)

Usage:
    python main.py          → Web Dashboard mode (default)
    python main.py --gui    → Legacy GUI mode (CustomTkinter)
    python main.py --api    → API-only mode (no dashboard)
    python main.py --cli    → CLI mode (legacy)
"""
import os
import sys
import webbrowser
import threading
import time

# Ensure project root in path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def main():
    args = sys.argv[1:]

    if "--gui" in args:
        # Legacy GUI mode (CustomTkinter)
        print("🖥️ Khởi động GUI Legacy...")
        from gui.app import QtusApp
        app = QtusApp()
        app.mainloop()

    elif "--api" in args:
        # API-only mode (no auto-open browser)
        print("🚀 Khởi động API Server...")
        import uvicorn
        uvicorn.run("api.server:app", host="0.0.0.0", port=8000, reload=False)

    elif "--cli" in args:
        # CLI legacy mode
        try:
            from qtuscreen_ai_pro import main as cli_main
            cli_main()
        except ImportError:
            print("CLI mode không khả dụng.")

    else:
        # Web Dashboard mode (default)
        from config import APP_NAME, APP_VERSION, APP_COPYRIGHT

        print(f"""
╔══════════════════════════════════════════════════════╗
║  🤖 {APP_NAME} v{APP_VERSION}                       ║
║  Professional AI Computer Agent                      ║
║  {APP_COPYRIGHT}                                     ║
╠══════════════════════════════════════════════════════╣
║  🌐 Dashboard: http://localhost:8000                 ║
║  📡 API Docs:  http://localhost:8000/docs            ║
║  🔌 WebSocket: ws://localhost:8000/ws                ║
╠══════════════════════════════════════════════════════╣
║  ✨ NEW in v5.0:                                    ║
║  • OODA Loop + Provider Failover                     ║
║  • Verify-After-Act + Self-Healing                   ║
║  • Premium Glassmorphism Dashboard                   ║
║  • System Metrics + Task Templates                   ║
╚══════════════════════════════════════════════════════╝
        """)

        # Auto-open browser after short delay
        def _open_browser():
            time.sleep(2)
            webbrowser.open("http://localhost:8000")

        threading.Thread(target=_open_browser, daemon=True).start()

        import uvicorn
        uvicorn.run(
            "api.server:app",
            host="0.0.0.0",
            port=8000,
            reload=False,
            log_level="info",
        )


if __name__ == "__main__":
    main()
