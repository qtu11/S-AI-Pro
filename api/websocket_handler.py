"""
WebSocket Handler v5.0 — Event bridge + Connection manager.
Copyright © 2025-2026 Qtus Dev (Anh Tú)
"""
import asyncio
import json
import time
from typing import List, Dict, Any, Optional

from fastapi import WebSocket


class ConnectionManager:
    """Quản lý WebSocket connections."""

    def __init__(self):
        self.active: List[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)

    async def disconnect(self, ws: WebSocket):
        if ws in self.active:
            self.active.remove(ws)
        try:
            await ws.close()
        except Exception:
            pass

    async def send_to(self, ws: WebSocket, data: dict):
        try:
            await ws.send_text(json.dumps(data, ensure_ascii=False))
        except Exception:
            await self.disconnect(ws)

    async def broadcast(self, data: dict):
        dead = []
        for ws in self.active:
            try:
                await ws.send_text(json.dumps(data, ensure_ascii=False))
            except Exception:
                dead.append(ws)
        for ws in dead:
            if ws in self.active:
                self.active.remove(ws)

    @property
    def count(self) -> int:
        return len(self.active)


class EventBridge:
    """
    Bridge giữa Agent (sync) và WebSocket (async).
    Agent emit events → queue → async broadcast.
    """

    def __init__(self, manager: ConnectionManager):
        self.manager = manager
        self._queue: asyncio.Queue = None
        self._loop: asyncio.AbstractEventLoop = None
        self._running = False

    def set_loop(self, loop: asyncio.AbstractEventLoop):
        self._loop = loop
        self._queue = asyncio.Queue()
        self._running = True

    def stop(self):
        self._running = False

    # ─── Sync emit (called from Agent threads) ──────────────
    def emit(self, event_type: str, **kwargs):
        data = {"type": event_type, **kwargs}
        if self._loop and self._queue:
            self._loop.call_soon_threadsafe(self._queue.put_nowait, data)

    def emit_log(self, event: str, message: str, step: int = 0):
        self.emit("agent_log", event=event, message=message, step=step)

    def emit_status(self, status: str, step: int, max_steps: int, goal: str = ""):
        self.emit("agent_status", status=status, step=step, max_steps=max_steps, goal=goal)

    def emit_screenshot(self, b64: str, step: int):
        self.emit("agent_screenshot", image=b64, step=step)

    def emit_action(self, action: str, result: dict, step: int):
        self.emit("agent_action", action=action, result=result, step=step)

    def emit_complete(self, success: bool, steps: int, duration: float):
        self.emit("agent_complete", success=success, steps=steps, duration=round(duration, 1))

    # ─── Async processor ──────────────────────────────────────
    async def process_queue(self):
        """Continuously process queued events and broadcast."""
        while self._running:
            try:
                data = await asyncio.wait_for(self._queue.get(), timeout=1.0)
                await self.manager.broadcast(data)
            except asyncio.TimeoutError:
                continue
            except Exception:
                await asyncio.sleep(0.1)


# Singletons
ws_manager = ConnectionManager()
event_bridge = EventBridge(ws_manager)
