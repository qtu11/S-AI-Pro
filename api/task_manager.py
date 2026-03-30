"""
Task Manager — Quản lý và theo dõi các task agent.
Copyright © 2025-2026 Qtus Dev (Anh Tú)
"""
import os
import json
import time
import uuid
from typing import List, Dict, Optional
from dataclasses import dataclass, field, asdict
from config import DATA_DIR


@dataclass
class Task:
    id: str = ""
    goal: str = ""
    provider: str = ""
    brain_model: str = ""
    eye_provider: str = "auto"
    max_steps: int = 15
    status: str = "pending"   # pending | running | done | failed
    created_at: float = 0.0
    started_at: float = 0.0
    ended_at: float = 0.0
    steps_taken: int = 0
    success: bool = False
    error: str = ""


class TaskManager:
    """Quản lý tasks — lịch sử và tracking."""

    def __init__(self):
        self._current: Optional[Task] = None
        self._history_path = os.path.join(DATA_DIR, "task_history.json")
        self._history: List[Dict] = self._load()

    def create_task(self, goal: str, provider: str = "gemini",
                    brain_model: str = "", eye_provider: str = "auto",
                    max_steps: int = 15) -> Task:
        task = Task(
            id=str(uuid.uuid4())[:8],
            goal=goal,
            provider=provider,
            brain_model=brain_model,
            eye_provider=eye_provider,
            max_steps=max_steps,
            created_at=time.time(),
        )
        self._current = task
        return task

    def start_task(self, task: Task):
        task.status = "running"
        task.started_at = time.time()

    def complete_task(self, task: Task, success: bool, steps: int = 0, error: str = ""):
        task.status = "done" if success else "failed"
        task.ended_at = time.time()
        task.success = success
        task.steps_taken = steps
        task.error = error

        self._history.append(asdict(task))
        if len(self._history) > 200:
            self._history = self._history[-200:]
        self._save()

    @property
    def current(self) -> Optional[Task]:
        return self._current

    def get_history(self, limit: int = 50) -> List[Dict]:
        return self._history[-limit:]

    def _load(self) -> List[Dict]:
        try:
            if os.path.exists(self._history_path):
                with open(self._history_path, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            pass
        return []

    def _save(self):
        try:
            with open(self._history_path, "w", encoding="utf-8") as f:
                json.dump(self._history, f, ensure_ascii=False, indent=2)
        except Exception:
            pass


task_manager = TaskManager()
