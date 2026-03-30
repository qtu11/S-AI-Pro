"""
S-AI-Pro v6.0 — Self-Learning System.
Learn from execution history, build website profiles, optimize timing.
Copyright © 2025-2026 Qtus Dev (Anh Tú)
"""
import time
import json
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from collections import defaultdict

from database.repository import PatternRepository, ModelCacheRepository


# ═══════════════════════════════════════════════════════════════
# DATA STRUCTURES
# ═══════════════════════════════════════════════════════════════

@dataclass
class ExecutionInsight:
    """Insight extracted from task execution."""
    insight_type: str = ""     # timing, pattern, error, optimization
    description: str = ""
    data: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    applicable_to: str = ""    # goal pattern this applies to


@dataclass
class WebsiteProfile:
    """Learned profile of a frequently-visited website."""
    url_pattern: str = ""
    page_load_time: float = 3.0       # seconds
    autocomplete_delay: float = 0.3    # seconds
    common_elements: List[str] = field(default_factory=list)
    interaction_pattern: str = ""      # how elements respond
    visit_count: int = 0
    last_visit: float = 0.0


# ═══════════════════════════════════════════════════════════════
# LEARNER
# ═══════════════════════════════════════════════════════════════

class AgentLearner:
    """
    Self-learning system that:
    1. Extracts patterns from execution history
    2. Learns timing optimizations
    3. Builds website profiles
    4. Recognizes error patterns
    5. Suggests optimizations for future runs
    """

    def __init__(self):
        self._timing_data: Dict[str, List[float]] = defaultdict(list)
        self._action_patterns: Dict[str, int] = defaultdict(int)
        self._error_patterns: Dict[str, int] = defaultdict(int)
        self._website_profiles: Dict[str, WebsiteProfile] = {}
        self._insights: List[ExecutionInsight] = []

    def learn_from_execution(
        self,
        goal: str,
        steps: List[Dict],
        success: bool,
        total_duration: float,
    ) -> List[ExecutionInsight]:
        """
        Extract insights from a completed task execution.
        Called after each task completes.
        """
        insights = []

        if not steps:
            return insights

        # ── 1. Save success/failure pattern ──
        actions = [s.get("action", "") for s in steps if s.get("action")]
        if success and actions:
            PatternRepository.save_pattern(
                pattern_type="success",
                goal=goal,
                actions=actions,
                data={
                    "total_steps": len(steps),
                    "duration_ms": int(total_duration * 1000),
                },
                confidence=0.8,
            )
            insights.append(ExecutionInsight(
                insight_type="pattern",
                description=f"Success pattern saved: {len(actions)} actions",
                confidence=0.8,
            ))

        # ── 2. Learn timing patterns ──
        timing_insight = self._analyze_timing(steps)
        if timing_insight:
            insights.append(timing_insight)

        # ── 3. Detect repeated error patterns ──
        error_insight = self._analyze_errors(steps)
        if error_insight:
            insights.append(error_insight)

        # ── 4. Learn action sequences ──
        sequence_insight = self._analyze_sequences(steps)
        if sequence_insight:
            insights.append(sequence_insight)

        self._insights.extend(insights)
        return insights

    def get_recommendation(self, goal: str) -> Optional[Dict]:
        """
        Get recommendation based on past learning.
        Returns similar pattern if found.
        """
        # Check database for similar patterns
        similar = PatternRepository.find_similar(goal, limit=3)
        if similar:
            best = similar[0]
            try:
                actions = json.loads(best.get("actions", "[]"))
            except json.JSONDecodeError:
                actions = []

            if actions:
                PatternRepository.increment_use(best["id"])
                return {
                    "source": "learned_pattern",
                    "actions": actions,
                    "confidence": best.get("confidence", 0.5),
                    "use_count": best.get("use_count", 0),
                }
        return None

    def get_optimal_delay(self, action_type: str) -> float:
        """Get optimized delay for an action type based on learning."""
        key = action_type.upper()
        if key in self._timing_data and len(self._timing_data[key]) >= 3:
            # Use average of last 10 timings
            recent = self._timing_data[key][-10:]
            avg = sum(recent) / len(recent)
            return max(0.1, avg * 1.2)  # Add 20% buffer

        # Defaults
        defaults = {
            "CLICK": 0.3,
            "TYPE": 0.5,
            "PRESS": 0.2,
            "HOTKEY": 0.5,
            "SCROLL": 0.3,
            "WAIT": 0.0,
        }
        return defaults.get(key, 0.3)

    def record_model_performance(
        self,
        provider: str,
        model_name: str,
        task_type: str,
        latency_ms: float,
        confidence: float,
        success: bool,
    ) -> None:
        """Record model performance for future routing decisions."""
        ModelCacheRepository.record_call(
            provider=provider,
            model_name=model_name,
            task_type=task_type,
            latency_ms=latency_ms,
            confidence=confidence,
            success=success,
        )

    def get_best_model(self, task_type: str = "general") -> Optional[Dict]:
        """Get best performing model for a task type."""
        return ModelCacheRepository.get_best_model(task_type)

    # ─── Analysis Methods ────────────────────────────────────

    def _analyze_timing(self, steps: List[Dict]) -> Optional[ExecutionInsight]:
        """Analyze timing patterns in execution."""
        for step in steps:
            action = step.get("action", "")
            duration = step.get("duration_ms", 0)
            if action and duration > 0:
                action_type = action.split()[0].upper() if action else ""
                self._timing_data[action_type].append(duration / 1000.0)

        # Check for slow actions
        slow_actions = []
        for action_type, times in self._timing_data.items():
            if times and sum(times[-5:]) / len(times[-5:]) > 5.0:
                slow_actions.append(action_type)

        if slow_actions:
            return ExecutionInsight(
                insight_type="timing",
                description=f"Slow actions detected: {', '.join(slow_actions)}",
                data={"slow_actions": slow_actions},
                confidence=0.7,
            )
        return None

    def _analyze_errors(self, steps: List[Dict]) -> Optional[ExecutionInsight]:
        """Analyze error patterns."""
        errors = [s for s in steps if not s.get("success", True)]

        for err in errors:
            action = err.get("action", "UNKNOWN")
            self._error_patterns[action] += 1

        # Find recurring errors
        recurring = {a: c for a, c in self._error_patterns.items() if c >= 3}
        if recurring:
            return ExecutionInsight(
                insight_type="error",
                description=f"Recurring errors: {list(recurring.keys())}",
                data={"patterns": recurring},
                confidence=0.8,
            )
        return None

    def _analyze_sequences(self, steps: List[Dict]) -> Optional[ExecutionInsight]:
        """Analyze common action sequences."""
        actions = [s.get("action", "").split()[0].upper() for s in steps if s.get("action")]

        # Find 2-gram patterns
        for i in range(len(actions) - 1):
            pair = f"{actions[i]}→{actions[i+1]}"
            self._action_patterns[pair] += 1

        # Find common patterns
        common = {p: c for p, c in self._action_patterns.items() if c >= 5}
        if common:
            top = sorted(common.items(), key=lambda x: -x[1])[:3]
            return ExecutionInsight(
                insight_type="pattern",
                description=f"Common sequences: {[p[0] for p in top]}",
                data={"sequences": dict(top)},
                confidence=0.6,
            )
        return None

    def get_insights_summary(self) -> Dict:
        """Get summary of all learned insights."""
        return {
            "total_insights": len(self._insights),
            "timing_entries": sum(len(v) for v in self._timing_data.values()),
            "error_patterns": len(self._error_patterns),
            "action_patterns": len(self._action_patterns),
            "website_profiles": len(self._website_profiles),
            "recent_insights": [
                {"type": i.insight_type, "desc": i.description}
                for i in self._insights[-5:]
            ],
        }
