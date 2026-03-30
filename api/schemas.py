"""
S-AI-Pro v6.0 — Pydantic API Schemas.
Request/Response validation cho FastAPI endpoints.
Copyright © 2025-2026 Qtus Dev (Anh Tú)
"""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, validator


# ═══════════════════════════════════════════════════════════════
# REQUEST MODELS
# ═══════════════════════════════════════════════════════════════

class TaskCreateRequest(BaseModel):
    """Request to create and start a new task."""
    goal: str = Field(..., min_length=3, max_length=2000, description="Task goal description")
    provider: str = Field(default="gemini", description="AI provider")
    brain_model: str = Field(default="", description="Brain model name")
    eye_provider: str = Field(default="auto", description="Vision provider")
    eye_model: str = Field(default="", description="Vision model name")
    max_steps: int = Field(default=15, ge=1, le=100, description="Max execution steps")
    step_delay: float = Field(default=0.5, ge=0.1, le=5.0, description="Delay between steps")
    decompose: bool = Field(default=True, description="Enable task decomposition")
    deep_think: bool = Field(default=False, description="Enable deep thinking before execution")

    @validator("goal")
    def goal_not_empty(cls, v):
        if not v or len(v.strip()) < 3:
            raise ValueError("Goal must be at least 3 characters")
        return v.strip()

    @validator("provider")
    def valid_provider(cls, v):
        valid = {"gemini", "openai", "anthropic", "groq", "deepseek", "aiml", "ollama"}
        if v.lower() not in valid:
            raise ValueError(f"Invalid provider. Must be one of: {valid}")
        return v.lower()


class TaskActionRequest(BaseModel):
    """Request to execute a single action."""
    action: str = Field(..., description="Action command (CLICK, TYPE, etc.)")
    target: str = Field(default="", description="Action target")


class AnalyzeRequest(BaseModel):
    """Request to analyze screen/file."""
    question: Optional[str] = Field(default=None)
    include_screenshot: bool = Field(default=True)
    model_name: str = Field(default="gemini-2.5-flash")
    provider: str = Field(default="gemini")


class TemplateRequest(BaseModel):
    """Request to save a task template."""
    name: str = Field(..., min_length=1, max_length=200)
    goal: str = Field(..., min_length=3, max_length=2000)
    description: str = Field(default="")


# ═══════════════════════════════════════════════════════════════
# RESPONSE MODELS
# ═══════════════════════════════════════════════════════════════

class TaskResponse(BaseModel):
    """Task details response."""
    id: str
    description: str
    status: str
    provider: str = ""
    model: str = ""
    total_steps: int = 0
    successful_steps: int = 0
    failed_steps: int = 0
    confidence: float = 0.0
    duration_ms: int = 0
    created_at: str = ""
    result: str = ""


class StepResponse(BaseModel):
    """Step details response."""
    id: str
    task_id: str
    step_number: int
    phase: str = ""
    action_type: str = ""
    target: str = ""
    reasoning: str = ""
    success: bool = False
    confidence: float = 0.0
    duration_ms: int = 0


class AgentStatusResponse(BaseModel):
    """Agent runtime status."""
    running: bool = False
    paused: bool = False
    step: int = 0
    max_steps: int = 0
    provider: str = ""
    model: str = ""
    task_id: str = ""
    goal: str = ""
    sub_tasks: List[Dict] = []
    stats: Dict[str, Any] = {}
    verification: Dict[str, Any] = {}
    learning: Dict[str, Any] = {}


class HealthResponse(BaseModel):
    """System health response."""
    status: str = "ok"
    version: str = ""
    agent_running: bool = False
    ws_clients: int = 0
    db_status: str = "ok"
    keys: Dict[str, bool] = {}
    metrics: Dict[str, Any] = {}


class ModelStatusResponse(BaseModel):
    """Model availability status."""
    provider: str
    models: List[str] = []
    default: str = ""
    vision_capable: List[str] = []


class ErrorResponse(BaseModel):
    """Standard error response."""
    error: str
    detail: str = ""
    code: int = 500
