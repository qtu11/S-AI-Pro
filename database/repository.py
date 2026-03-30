"""
S-AI-Pro v6.0 — Data Access Layer (Repository Pattern).
Thread-safe CRUD cho tasks, steps, logs, patterns.
Copyright © 2025-2026 Qtus Dev (Anh Tú)
"""
import json
import uuid
import time
import sqlite3
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field, asdict

from database.schema import get_connection


def _gen_id() -> str:
    return str(uuid.uuid4())[:12]


def _now_iso() -> str:
    from datetime import datetime
    return datetime.now().isoformat()


# ═══════════════════════════════════════════════════════════════
# TASK REPOSITORY
# ═══════════════════════════════════════════════════════════════

class TaskRepository:
    """CRUD operations for tasks table."""

    @staticmethod
    def create(
        description: str,
        provider: str = "gemini",
        primary_model: str = "",
        max_steps: int = 30,
        timeout_seconds: int = 600,
    ) -> str:
        task_id = _gen_id()
        conn = get_connection()
        try:
            conn.execute(
                """INSERT INTO tasks (id, description, provider, primary_model, max_steps, timeout_seconds)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (task_id, description, provider, primary_model, max_steps, timeout_seconds),
            )
            conn.commit()
        finally:
            conn.close()
        return task_id

    @staticmethod
    def get(task_id: str) -> Optional[Dict]:
        conn = get_connection()
        try:
            row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    @staticmethod
    def update_status(task_id: str, status: str, **kwargs) -> None:
        conn = get_connection()
        try:
            sets = ["status = ?", "updated_at = ?"]
            vals = [status, _now_iso()]
            for k, v in kwargs.items():
                sets.append(f"{k} = ?")
                vals.append(v)
            vals.append(task_id)
            conn.execute(f"UPDATE tasks SET {', '.join(sets)} WHERE id = ?", vals)
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def update_progress(
        task_id: str,
        total_steps: int = 0,
        successful_steps: int = 0,
        failed_steps: int = 0,
        confidence: float = 0.0,
        duration_ms: int = 0,
    ) -> None:
        conn = get_connection()
        try:
            conn.execute(
                """UPDATE tasks SET total_steps=?, successful_steps=?, failed_steps=?,
                   confidence=?, duration_ms=?, updated_at=? WHERE id=?""",
                (total_steps, successful_steps, failed_steps, confidence, duration_ms, _now_iso(), task_id),
            )
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def complete(task_id: str, success: bool, result: str = "", error: str = "", duration_ms: int = 0) -> None:
        status = "completed" if success else "failed"
        conn = get_connection()
        try:
            conn.execute(
                """UPDATE tasks SET status=?, result=?, error_message=?, duration_ms=?, updated_at=?
                   WHERE id=?""",
                (status, result, error, duration_ms, _now_iso(), task_id),
            )
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def list_recent(limit: int = 50) -> List[Dict]:
        conn = get_connection()
        try:
            rows = conn.execute(
                "SELECT * FROM tasks ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    @staticmethod
    def delete(task_id: str) -> bool:
        conn = get_connection()
        try:
            cursor = conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()


# ═══════════════════════════════════════════════════════════════
# STEP REPOSITORY
# ═══════════════════════════════════════════════════════════════

class StepRepository:
    """CRUD operations for steps table."""

    @staticmethod
    def create(
        task_id: str,
        step_number: int,
        phase: str = "act",
        action_type: str = "",
        action_data: dict = None,
        target: str = "",
        reasoning: str = "",
        thinking: str = "",
        plan: str = "",
        screen_hash_before: str = "",
    ) -> str:
        step_id = _gen_id()
        conn = get_connection()
        try:
            conn.execute(
                """INSERT INTO steps (id, task_id, step_number, phase, action_type, action_data,
                   target, reasoning, thinking, plan, screen_hash_before)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (step_id, task_id, step_number, phase, action_type,
                 json.dumps(action_data or {}), target, reasoning, thinking, plan, screen_hash_before),
            )
            conn.commit()
        finally:
            conn.close()
        return step_id

    @staticmethod
    def complete_step(
        step_id: str,
        success: bool,
        confidence: float = 0.0,
        duration_ms: int = 0,
        screen_hash_after: str = "",
        error_message: str = "",
    ) -> None:
        conn = get_connection()
        try:
            conn.execute(
                """UPDATE steps SET success=?, confidence=?, duration_ms=?,
                   screen_hash_after=?, error_message=? WHERE id=?""",
                (int(success), confidence, duration_ms, screen_hash_after, error_message, step_id),
            )
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def get_steps_for_task(task_id: str) -> List[Dict]:
        conn = get_connection()
        try:
            rows = conn.execute(
                "SELECT * FROM steps WHERE task_id=? ORDER BY step_number", (task_id,)
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    @staticmethod
    def get_last_n_steps(task_id: str, n: int = 10) -> List[Dict]:
        conn = get_connection()
        try:
            rows = conn.execute(
                "SELECT * FROM steps WHERE task_id=? ORDER BY step_number DESC LIMIT ?",
                (task_id, n),
            ).fetchall()
            return [dict(r) for r in reversed(rows)]
        finally:
            conn.close()


# ═══════════════════════════════════════════════════════════════
# LOG REPOSITORY
# ═══════════════════════════════════════════════════════════════

class LogRepository:
    """CRUD operations for logs table."""

    @staticmethod
    def write(
        message: str,
        level: str = "INFO",
        event_type: str = "system",
        task_id: str = "",
        step_number: int = 0,
        context: dict = None,
    ) -> None:
        conn = get_connection()
        try:
            conn.execute(
                """INSERT INTO logs (task_id, step_number, level, event_type, message, context)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (task_id, step_number, level, event_type, message, json.dumps(context or {})),
            )
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def get_logs(task_id: str = "", level: str = "", limit: int = 100) -> List[Dict]:
        conn = get_connection()
        try:
            query = "SELECT * FROM logs WHERE 1=1"
            params = []
            if task_id:
                query += " AND task_id = ?"
                params.append(task_id)
            if level:
                query += " AND level = ?"
                params.append(level)
            query += " ORDER BY created_at DESC LIMIT ?"
            params.append(limit)
            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    @staticmethod
    def clear_old(days: int = 7) -> int:
        conn = get_connection()
        try:
            cursor = conn.execute(
                "DELETE FROM logs WHERE created_at < datetime('now', ?)",
                (f"-{days} days",),
            )
            conn.commit()
            return cursor.rowcount
        finally:
            conn.close()


# ═══════════════════════════════════════════════════════════════
# PATTERN REPOSITORY
# ═══════════════════════════════════════════════════════════════

class PatternRepository:
    """CRUD operations for patterns (learning data)."""

    @staticmethod
    def save_pattern(
        pattern_type: str,
        goal: str = "",
        actions: list = None,
        data: dict = None,
        confidence: float = 0.0,
    ) -> None:
        conn = get_connection()
        try:
            conn.execute(
                """INSERT INTO patterns (pattern_type, goal, actions, data, confidence)
                   VALUES (?, ?, ?, ?, ?)""",
                (pattern_type, goal, json.dumps(actions or []),
                 json.dumps(data or {}), confidence),
            )
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def find_similar(goal: str, limit: int = 5) -> List[Dict]:
        conn = get_connection()
        try:
            # Simple keyword matching — will be enhanced with embeddings later
            words = goal.lower().split()
            if not words:
                return []
            conditions = " OR ".join(["LOWER(goal) LIKE ?" for _ in words])
            params = [f"%{w}%" for w in words[:5]]
            params.append(limit)
            rows = conn.execute(
                f"""SELECT * FROM patterns WHERE pattern_type='success'
                    AND ({conditions})
                    ORDER BY use_count DESC, confidence DESC LIMIT ?""",
                params,
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    @staticmethod
    def increment_use(pattern_id: int) -> None:
        conn = get_connection()
        try:
            conn.execute(
                "UPDATE patterns SET use_count = use_count + 1, updated_at = ? WHERE id = ?",
                (_now_iso(), pattern_id),
            )
            conn.commit()
        finally:
            conn.close()


# ═══════════════════════════════════════════════════════════════
# MODEL PERFORMANCE CACHE
# ═══════════════════════════════════════════════════════════════

class ModelCacheRepository:
    """Track model performance metrics."""

    @staticmethod
    def record_call(
        provider: str,
        model_name: str,
        task_type: str = "general",
        latency_ms: float = 0.0,
        confidence: float = 0.0,
        success: bool = True,
    ) -> None:
        conn = get_connection()
        try:
            # Upsert
            existing = conn.execute(
                "SELECT * FROM models_cache WHERE provider=? AND model_name=? AND task_type=?",
                (provider, model_name, task_type),
            ).fetchone()

            if existing:
                row = dict(existing)
                total = row["total_calls"] + 1
                new_avg_lat = ((row["avg_latency_ms"] * row["total_calls"]) + latency_ms) / total
                new_avg_conf = ((row["avg_confidence"] * row["total_calls"]) + confidence) / total
                sc = row["success_count"] + (1 if success else 0)
                fc = row["failure_count"] + (0 if success else 1)
                conn.execute(
                    """UPDATE models_cache SET avg_latency_ms=?, avg_confidence=?,
                       total_calls=?, success_count=?, failure_count=?, last_used=?
                       WHERE provider=? AND model_name=? AND task_type=?""",
                    (new_avg_lat, new_avg_conf, total, sc, fc, _now_iso(),
                     provider, model_name, task_type),
                )
            else:
                conn.execute(
                    """INSERT INTO models_cache
                       (provider, model_name, task_type, avg_latency_ms, avg_confidence,
                        total_calls, success_count, failure_count)
                       VALUES (?, ?, ?, ?, ?, 1, ?, ?)""",
                    (provider, model_name, task_type, latency_ms, confidence,
                     1 if success else 0, 0 if success else 1),
                )
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def get_best_model(task_type: str = "general") -> Optional[Dict]:
        conn = get_connection()
        try:
            row = conn.execute(
                """SELECT * FROM models_cache WHERE task_type=? AND total_calls >= 3
                   ORDER BY (success_count * 1.0 / total_calls) DESC, avg_latency_ms ASC
                   LIMIT 1""",
                (task_type,),
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    @staticmethod
    def get_all_stats() -> List[Dict]:
        conn = get_connection()
        try:
            rows = conn.execute(
                "SELECT * FROM models_cache ORDER BY total_calls DESC"
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()
