"""
S-AI-Pro v6.0 — SQLite Schema & Database Initialization.
Tables: tasks, steps, logs, models_cache, patterns, sessions.
Copyright © 2025-2026 Qtus Dev (Anh Tú)
"""
import os
import sqlite3
from config import DATA_DIR

DB_NAME = "sai_pro.db"


def get_db_path() -> str:
    return os.path.join(DATA_DIR, DB_NAME)


def get_connection() -> sqlite3.Connection:
    """Thread-safe connection (each thread gets its own)."""
    conn = sqlite3.connect(get_db_path(), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


# ═══════════════════════════════════════════════════════════════
# SCHEMA DDL
# ═══════════════════════════════════════════════════════════════

SCHEMA_SQL = """
-- ── Tasks ────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS tasks (
    id              TEXT PRIMARY KEY,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    description     TEXT NOT NULL,
    status          TEXT DEFAULT 'pending'
                    CHECK(status IN ('pending','planning','running','completed','failed','paused','timeout')),
    primary_model   TEXT DEFAULT '',
    secondary_model TEXT DEFAULT '',
    provider        TEXT DEFAULT 'gemini',
    max_steps       INTEGER DEFAULT 30,
    timeout_seconds INTEGER DEFAULT 600,
    total_steps     INTEGER DEFAULT 0,
    successful_steps INTEGER DEFAULT 0,
    failed_steps    INTEGER DEFAULT 0,
    confidence      REAL DEFAULT 0.0,
    result          TEXT DEFAULT '',
    error_message   TEXT DEFAULT '',
    duration_ms     INTEGER DEFAULT 0,
    metadata        TEXT DEFAULT '{}'
);

-- ── Steps (each action within a task) ────────────────
CREATE TABLE IF NOT EXISTS steps (
    id              TEXT PRIMARY KEY,
    task_id         TEXT NOT NULL,
    step_number     INTEGER NOT NULL,
    phase           TEXT DEFAULT 'act'
                    CHECK(phase IN ('observe','orient','decide','act','verify')),
    action_type     TEXT DEFAULT '',
    action_data     TEXT DEFAULT '{}',
    target          TEXT DEFAULT '',
    screenshot_before TEXT DEFAULT '',
    screenshot_after  TEXT DEFAULT '',
    screen_hash_before TEXT DEFAULT '',
    screen_hash_after  TEXT DEFAULT '',
    reasoning       TEXT DEFAULT '',
    thinking        TEXT DEFAULT '',
    plan            TEXT DEFAULT '',
    success         INTEGER DEFAULT 0,
    confidence      REAL DEFAULT 0.0,
    duration_ms     INTEGER DEFAULT 0,
    error_message   TEXT DEFAULT '',
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE
);

-- ── Logs ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS logs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id         TEXT DEFAULT '',
    step_number     INTEGER DEFAULT 0,
    level           TEXT DEFAULT 'INFO'
                    CHECK(level IN ('DEBUG','INFO','WARNING','ERROR','CRITICAL')),
    event_type      TEXT DEFAULT 'system',
    message         TEXT NOT NULL,
    context         TEXT DEFAULT '{}',
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE SET NULL
);

-- ── Learned Patterns ─────────────────────────────────
CREATE TABLE IF NOT EXISTS patterns (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    pattern_type    TEXT DEFAULT 'success'
                    CHECK(pattern_type IN ('success','failure','website','timing')),
    goal            TEXT DEFAULT '',
    actions         TEXT DEFAULT '[]',
    website_url     TEXT DEFAULT '',
    data            TEXT DEFAULT '{}',
    confidence      REAL DEFAULT 0.0,
    use_count       INTEGER DEFAULT 0,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ── Model Performance Cache ──────────────────────────
CREATE TABLE IF NOT EXISTS models_cache (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    provider        TEXT NOT NULL,
    model_name      TEXT NOT NULL,
    task_type       TEXT DEFAULT 'general',
    avg_latency_ms  REAL DEFAULT 0.0,
    avg_confidence  REAL DEFAULT 0.0,
    total_calls     INTEGER DEFAULT 0,
    success_count   INTEGER DEFAULT 0,
    failure_count   INTEGER DEFAULT 0,
    last_used       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(provider, model_name, task_type)
);

-- ── Sessions ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS sessions (
    id              TEXT PRIMARY KEY,
    task_id         TEXT DEFAULT '',
    goal            TEXT DEFAULT '',
    status          TEXT DEFAULT 'active',
    total_actions   INTEGER DEFAULT 0,
    successful      INTEGER DEFAULT 0,
    failed          INTEGER DEFAULT 0,
    duration_ms     INTEGER DEFAULT 0,
    started_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ended_at        TIMESTAMP,
    summary         TEXT DEFAULT '',
    FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE SET NULL
);

-- ── Indexes ──────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_steps_task_id ON steps(task_id);
CREATE INDEX IF NOT EXISTS idx_steps_step_number ON steps(task_id, step_number);
CREATE INDEX IF NOT EXISTS idx_logs_task_id ON logs(task_id);
CREATE INDEX IF NOT EXISTS idx_logs_level ON logs(level);
CREATE INDEX IF NOT EXISTS idx_logs_created ON logs(created_at);
CREATE INDEX IF NOT EXISTS idx_patterns_type ON patterns(pattern_type);
CREATE INDEX IF NOT EXISTS idx_patterns_goal ON patterns(goal);
CREATE INDEX IF NOT EXISTS idx_models_provider ON models_cache(provider, model_name);
CREATE INDEX IF NOT EXISTS idx_sessions_task ON sessions(task_id);
"""

# ═══════════════════════════════════════════════════════════════


def init_db() -> None:
    """Initialize database and create tables if not exist."""
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = get_connection()
    try:
        conn.executescript(SCHEMA_SQL)
        conn.commit()
        print(f"[DB] SQLite initialized: {get_db_path()}")
    except Exception as e:
        print(f"[DB] Error initializing: {e}")
    finally:
        conn.close()


def reset_db() -> None:
    """Drop and recreate all tables (DANGEROUS)."""
    db_path = get_db_path()
    if os.path.exists(db_path):
        os.remove(db_path)
    init_db()
