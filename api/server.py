"""
QtusScreen AI Pro v5.0 — FastAPI Server + WebSocket + Web Dashboard.
+ System metrics, templates, pause/resume, provider switch.
Copyright © 2025-2026 Qtus Dev (Anh Tú)
"""
import os
import sys
import json
import time
import asyncio
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, Form
from fastapi.responses import JSONResponse, StreamingResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from config import APP_NAME, APP_VERSION, APP_COPYRIGHT
from config.models import get_models_for_provider, get_default_model, PROVIDER_MODELS
from core.screen import capture_screen
from core.analyzer import analyze_router
from core.system_monitor import system_monitor

from api.websocket_handler import ws_manager, event_bridge
from api.task_manager import task_manager

# ═══════════════════════════════════════════════════════════════
# APP SETUP
# ═══════════════════════════════════════════════════════════════

app = FastAPI(title=f"{APP_NAME} API", version=APP_VERSION)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_WEB_DIR = os.path.join(_ROOT, "web")
if os.path.exists(_WEB_DIR):
    app.mount("/static", StaticFiles(directory=_WEB_DIR), name="static")

_agent_instance = None
_metrics_task = None

# ═══════════════════════════════════════════════════════════════
# STARTUP / SHUTDOWN
# ═══════════════════════════════════════════════════════════════

@app.on_event("startup")
async def startup():
    loop = asyncio.get_event_loop()
    event_bridge.set_loop(loop)
    asyncio.create_task(event_bridge.process_queue())

    # Start system monitor
    system_monitor.start(interval=3.0)

    # Start metrics broadcast
    global _metrics_task
    _metrics_task = asyncio.create_task(_broadcast_metrics())

    print(f"🤖 {APP_NAME} v{APP_VERSION} — Server started")
    print(f"🌐 Dashboard: http://localhost:8000")
    print(f"📡 API Docs:  http://localhost:8000/docs")


@app.on_event("shutdown")
async def shutdown():
    event_bridge.stop()
    system_monitor.stop()
    if _metrics_task:
        _metrics_task.cancel()
    global _agent_instance
    if _agent_instance and _agent_instance.is_running:
        _agent_instance.stop()


async def _broadcast_metrics():
    """Broadcast system metrics every 5s."""
    while True:
        try:
            await asyncio.sleep(5)
            metrics = system_monitor.get_metrics()
            await ws_manager.broadcast({
                "type": "system_metrics",
                **metrics,
            })
        except asyncio.CancelledError:
            break
        except Exception:
            pass

# ═══════════════════════════════════════════════════════════════
# WEB DASHBOARD
# ═══════════════════════════════════════════════════════════════

@app.get("/", response_class=HTMLResponse)
def serve_dashboard():
    index_path = os.path.join(_WEB_DIR, "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h1>Web Dashboard not found.</h1>")

# ═══════════════════════════════════════════════════════════════
# WEBSOCKET
# ═══════════════════════════════════════════════════════════════

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)

    from config import validate_keys
    await ws_manager.send_to(websocket, {
        "type": "health",
        "version": APP_VERSION,
        "keys": validate_keys(),
    })
    await ws_manager.send_to(websocket, {
        "type": "system_info",
        "python": sys.version.split()[0],
        "platform": sys.platform,
    })

    try:
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                await _handle_ws_message(websocket, msg)
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        await ws_manager.disconnect(websocket)
    except Exception:
        await ws_manager.disconnect(websocket)


async def _handle_ws_message(websocket: WebSocket, msg: dict):
    msg_type = msg.get("type", "")

    if msg_type == "ping":
        await ws_manager.send_to(websocket, {"type": "pong"})

    elif msg_type == "agent_start":
        await _start_agent_from_ws(msg)

    elif msg_type == "agent_stop":
        global _agent_instance
        if _agent_instance and _agent_instance.is_running:
            _agent_instance.stop()
            event_bridge.emit_log("system", "⛔ Agent dừng theo lệnh người dùng")

    elif msg_type == "agent_pause":
        if _agent_instance and _agent_instance.is_running:
            _agent_instance.pause()

    elif msg_type == "agent_resume":
        if _agent_instance and _agent_instance.is_running:
            _agent_instance.resume()

    elif msg_type == "capture_screen":
        await _capture_and_send()


async def _start_agent_from_ws(msg: dict):
    global _agent_instance

    if _agent_instance and _agent_instance.is_running:
        event_bridge.emit_log("error", "Agent đang chạy!")
        return

    goal = msg.get("goal", "").strip()
    if not goal:
        event_bridge.emit_log("error", "Mục tiêu trống!")
        return

    provider = msg.get("provider", "gemini")
    brain_model = msg.get("brain_model", "") or get_default_model(provider)
    eye_provider = msg.get("eye_provider", "auto")
    eye_model = msg.get("eye_model", "")
    max_steps = int(msg.get("max_steps", 15))
    step_delay = float(msg.get("step_delay", 0.5))

    task = task_manager.create_task(
        goal=goal, provider=provider,
        brain_model=brain_model, eye_provider=eye_provider,
        max_steps=max_steps,
    )
    task_manager.start_task(task)

    await ws_manager.broadcast({
        "type": "task_created",
        "id": task.id,
        "goal": goal,
        "status": "running",
    })

    # Use new AgentOrchestrator v5.0
    from agent.orchestrator import AgentOrchestrator

    _agent_instance = AgentOrchestrator(
        brain_provider=provider,
        brain_model=brain_model,
        eye_provider=eye_provider,
        eye_model=eye_model,
        max_steps=max_steps,
        step_delay=step_delay,
        event_bridge=event_bridge,
    )
    _agent_instance.run(goal, blocking=False)


async def _capture_and_send():
    try:
        from core.perception import capture_screen_to_image, smart_resize, image_to_base64
        image = capture_screen_to_image()
        preview = smart_resize(image, 1600)
        b64 = image_to_base64(preview, "JPEG", 90)
        await ws_manager.broadcast({
            "type": "agent_screenshot",
            "image": b64,
            "step": 0,
        })
    except Exception as e:
        event_bridge.emit_log("error", f"Lỗi chụp màn hình: {e}")

# ═══════════════════════════════════════════════════════════════
# REST API
# ═══════════════════════════════════════════════════════════════

@app.get("/api/health")
def health():
    from config import validate_keys
    return {
        "status": "ok",
        "version": APP_VERSION,
        "keys": validate_keys(),
        "agent_running": _agent_instance.is_running if _agent_instance else False,
        "ws_clients": ws_manager.count,
    }


@app.get("/api/models/{provider}")
def get_models(provider: str):
    models = get_models_for_provider(provider)
    return {"provider": provider, "models": models}


@app.get("/api/ollama/models")
def ollama_models():
    try:
        models = get_models_for_provider("ollama")
        return {"models": models}
    except Exception:
        return {"models": PROVIDER_MODELS.get("ollama", [])}


@app.get("/api/tasks")
def list_tasks(limit: int = 50):
    return {"tasks": task_manager.get_history(limit)}


@app.get("/api/screenshot.png")
def screenshot_png():
    path = capture_screen()
    def _iter():
        with open(path, "rb") as f:
            yield from f
    return StreamingResponse(_iter(), media_type="image/png")


@app.post("/api/analyze")
async def analyze(
    question: Optional[str] = Form(None),
    include_screenshot: bool = Form(True),
    model_name: str = Form("gemini-2.5-flash"),
    provider: str = Form("gemini"),
    file: Optional[UploadFile] = File(None),
):
    import tempfile
    image_path = None
    file_path = None

    try:
        if include_screenshot:
            image_path = capture_screen()

        if file is not None:
            suffix = os.path.splitext(file.filename or "upload.bin")[1]
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                file_path = tmp.name
                content = await file.read()
                tmp.write(content)

        text = analyze_router(
            provider=provider, model_name=model_name,
            image_path=image_path, file_path=file_path,
            question=question,
        )
        return {"answer": text}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
    finally:
        if file_path and os.path.exists(file_path):
            try: os.remove(file_path)
            except Exception: pass


# ─── Agent Control API ──────────────────────────────────────

@app.post("/api/agent/start")
async def agent_start(
    goal: str = Form(...),
    provider: str = Form("gemini"),
    brain_model: str = Form(""),
    max_steps: int = Form(15),
):
    await _start_agent_from_ws({
        "goal": goal, "provider": provider,
        "brain_model": brain_model, "max_steps": max_steps,
    })
    return {"status": "started", "goal": goal}


@app.post("/api/agent/stop")
def agent_stop():
    global _agent_instance
    if _agent_instance and _agent_instance.is_running:
        _agent_instance.stop()
        return {"status": "stopped"}
    return {"status": "not_running"}


@app.post("/api/agent/pause")
def agent_pause():
    if _agent_instance and _agent_instance.is_running:
        _agent_instance.pause()
        return {"status": "paused"}
    return {"status": "not_running"}


@app.post("/api/agent/resume")
def agent_resume():
    if _agent_instance and _agent_instance.is_running:
        _agent_instance.resume()
        return {"status": "resumed"}
    return {"status": "not_running"}


@app.get("/api/agent/status")
def agent_status():
    if _agent_instance:
        return _agent_instance.get_status()
    return {"running": False, "step": 0}


# ─── System API ─────────────────────────────────────────────

@app.get("/api/system/metrics")
def system_metrics():
    return system_monitor.get_metrics()


@app.get("/api/system/metrics/history")
def system_metrics_history(last_n: int = 60):
    return {"history": system_monitor.get_history(last_n)}


# ─── Template API ───────────────────────────────────────────

@app.get("/api/templates")
def list_templates():
    from config.templates import get_all_templates
    return {"templates": get_all_templates()}


@app.post("/api/templates")
async def save_template(
    name: str = Form(...),
    goal: str = Form(...),
    description: str = Form(""),
):
    from config.templates import save_custom_template
    template = save_custom_template({
        "name": name, "goal": goal,
        "description": description,
    })
    return {"template": template}


@app.delete("/api/templates/{template_id}")
def delete_template(template_id: str):
    from config.templates import delete_custom_template
    ok = delete_custom_template(template_id)
    return {"deleted": ok}


# ─── Memory API ─────────────────────────────────────────────

@app.get("/api/memory/patterns")
def get_patterns():
    if _agent_instance:
        return {"stats": _agent_instance.memory.get_stats()}
    return {"stats": {}}


@app.delete("/api/memory/clear")
def clear_memory():
    if _agent_instance:
        _agent_instance.memory.reset()
        return {"status": "cleared"}
    return {"status": "no_agent"}


# ─── Legacy Compat ──────────────────────────────────────────

@app.get("/health")
def health_legacy():
    return health()

@app.get("/models")
def models_legacy():
    return {"providers": PROVIDER_MODELS}

@app.get("/screenshot.png")
def screenshot_legacy():
    return screenshot_png()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.server:app", host="0.0.0.0", port=8000, reload=False)
