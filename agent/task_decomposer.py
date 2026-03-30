"""
S-AI-Pro v6.0 — Hierarchical Task Decomposer.
Break complex goals into phases → steps with dependency management.
Copyright © 2025-2026 Qtus Dev (Anh Tú)
"""
import re
import json
import time
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field

from core.analyzer import analyze_router
from config.models import get_default_model


# ═══════════════════════════════════════════════════════════════
# DATA STRUCTURES
# ═══════════════════════════════════════════════════════════════

@dataclass
class SubTask:
    """One sub-task within a decomposed goal."""
    id: int = 0
    phase: int = 1
    name: str = ""
    description: str = ""
    actions: List[str] = field(default_factory=list)
    dependencies: List[int] = field(default_factory=list)  # IDs of tasks that must complete first
    status: str = "pending"  # pending | running | done | failed | skipped
    steps_taken: int = 0
    max_steps: int = 10
    result: str = ""
    confidence: float = 0.0
    estimated_time: str = ""
    requires_user_input: bool = False

    def is_ready(self, completed_ids: set) -> bool:
        """Check if all dependencies are met."""
        return all(dep_id in completed_ids for dep_id in self.dependencies)


@dataclass
class TaskHierarchy:
    """Complete hierarchical breakdown of a goal."""
    goal: str = ""
    subtasks: List[SubTask] = field(default_factory=list)
    total_phases: int = 0
    estimated_total_time: str = ""
    complexity: str = "medium"
    created_at: float = field(default_factory=time.time)

    @property
    def completed_count(self) -> int:
        return sum(1 for st in self.subtasks if st.status == "done")

    @property
    def failed_count(self) -> int:
        return sum(1 for st in self.subtasks if st.status == "failed")

    @property
    def progress(self) -> float:
        if not self.subtasks:
            return 0.0
        return self.completed_count / len(self.subtasks)

    @property
    def completed_ids(self) -> set:
        return {st.id for st in self.subtasks if st.status == "done"}

    def get_next_ready(self) -> Optional[SubTask]:
        """Get next subtask that has all dependencies met and is pending."""
        for st in self.subtasks:
            if st.status == "pending" and st.is_ready(self.completed_ids):
                return st
        return None

    def mark_complete(self, subtask_id: int, result: str = "") -> None:
        for st in self.subtasks:
            if st.id == subtask_id:
                st.status = "done"
                st.result = result
                break

    def mark_failed(self, subtask_id: int, error: str = "") -> None:
        for st in self.subtasks:
            if st.id == subtask_id:
                st.status = "failed"
                st.result = error
                break

    def to_dict(self) -> Dict:
        return {
            "goal": self.goal,
            "subtasks": [
                {
                    "id": st.id, "phase": st.phase, "name": st.name,
                    "description": st.description, "status": st.status,
                    "steps_taken": st.steps_taken, "result": st.result,
                }
                for st in self.subtasks
            ],
            "progress": round(self.progress * 100, 1),
            "completed": self.completed_count,
            "total": len(self.subtasks),
        }


# ═══════════════════════════════════════════════════════════════
# PROMPTS
# ═══════════════════════════════════════════════════════════════

DECOMPOSE_PROMPT = """Break down this computer automation goal into concrete sub-tasks.

GOAL: {goal}

Rules:
1. Each sub-task must be a specific, automatable action on a computer
2. Order matters — list dependencies
3. Each sub-task should take 1-10 actions to complete
4. Be precise about what apps to open, what to click, what to type
5. Include waits for page loads

Respond as JSON array:
[
  {{
    "id": 1,
    "phase": 1,
    "name": "Short name",
    "description": "Detailed description of what to do",
    "estimated_actions": 3,
    "dependencies": [],
    "estimated_time": "30s",
    "requires_user_input": false
  }},
  {{
    "id": 2,
    "phase": 1,
    "name": "...",
    "description": "...",
    "estimated_actions": 5,
    "dependencies": [1],
    "estimated_time": "1m",
    "requires_user_input": false
  }}
]

Keep it under 10 sub-tasks for simple goals, up to 20 for complex ones."""


# ═══════════════════════════════════════════════════════════════
# TASK DECOMPOSER
# ═══════════════════════════════════════════════════════════════

class TaskDecomposer:
    """
    Break complex goals into executable subtask hierarchies.
    Uses LLM for intelligent decomposition.
    """

    def __init__(self, provider: str = "gemini", model: str = ""):
        self.provider = provider
        self.model = model or get_default_model(provider)

    def decompose(self, goal: str) -> TaskHierarchy:
        """
        Decompose a goal into a TaskHierarchy with subtasks.
        Returns structured hierarchy with dependencies.
        """
        hierarchy = TaskHierarchy(goal=goal)

        # Simple goals don't need decomposition
        if self._is_simple_goal(goal):
            hierarchy.subtasks = [SubTask(
                id=1, phase=1, name="Execute goal",
                description=goal, max_steps=15,
            )]
            hierarchy.total_phases = 1
            hierarchy.complexity = "low"
            return hierarchy

        # Use LLM to decompose complex goals
        prompt = DECOMPOSE_PROMPT.format(goal=goal)

        try:
            response = analyze_router(
                provider=self.provider,
                model_name=self.model,
                question=prompt,
            )
            subtasks = self._parse_decomposition(response)

            if subtasks:
                hierarchy.subtasks = subtasks
                hierarchy.total_phases = max(st.phase for st in subtasks)
                hierarchy.complexity = self._estimate_complexity(subtasks)
            else:
                # Fallback: single task
                hierarchy.subtasks = [SubTask(
                    id=1, phase=1, name="Execute goal",
                    description=goal, max_steps=20,
                )]
                hierarchy.total_phases = 1

        except Exception as e:
            # On error, create single-task hierarchy
            hierarchy.subtasks = [SubTask(
                id=1, phase=1, name="Execute goal",
                description=goal, max_steps=20,
            )]
            hierarchy.total_phases = 1

        return hierarchy

    def _parse_decomposition(self, response: str) -> List[SubTask]:
        """Parse LLM response into SubTask list."""
        subtasks = []

        try:
            # Extract JSON array
            json_match = re.search(r"\[[\s\S]*\]", response)
            if json_match:
                data = json.loads(json_match.group())
                for item in data:
                    st = SubTask(
                        id=item.get("id", len(subtasks) + 1),
                        phase=item.get("phase", 1),
                        name=item.get("name", ""),
                        description=item.get("description", ""),
                        dependencies=item.get("dependencies", []),
                        max_steps=min(item.get("estimated_actions", 5) * 2, 20),
                        estimated_time=item.get("estimated_time", ""),
                        requires_user_input=item.get("requires_user_input", False),
                    )
                    subtasks.append(st)
        except (json.JSONDecodeError, Exception):
            # Fallback: try to parse as numbered list
            lines = response.strip().split("\n")
            idx = 0
            for line in lines:
                line = line.strip()
                match = re.match(r"(?:SUBTASK\s+)?(\d+)[\.:]\s*(.*)", line, re.IGNORECASE)
                if match:
                    idx += 1
                    subtasks.append(SubTask(
                        id=idx,
                        phase=1,
                        name=f"Step {idx}",
                        description=match.group(2).strip(),
                        max_steps=10,
                    ))

        return subtasks

    @staticmethod
    def _is_simple_goal(goal: str) -> bool:
        """Detect if goal is simple enough to skip decomposition."""
        word_count = len(goal.split())
        simple_indicators = [
            "mở", "open", "click", "type", "gõ", "search",
            "tìm", "đóng", "close", "chạy", "run",
        ]
        # Short goals with simple verbs
        if word_count <= 8:
            goal_lower = goal.lower()
            if any(ind in goal_lower for ind in simple_indicators):
                return True
        return word_count <= 4

    @staticmethod
    def _estimate_complexity(subtasks: List[SubTask]) -> str:
        """Estimate overall complexity based on subtask count and dependencies."""
        count = len(subtasks)
        has_deps = any(st.dependencies for st in subtasks)
        has_user_input = any(st.requires_user_input for st in subtasks)

        if count <= 2 and not has_deps:
            return "low"
        elif count <= 5:
            return "medium"
        elif count <= 10 or has_user_input:
            return "high"
        else:
            return "extreme"
