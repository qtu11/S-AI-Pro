"""
Agent Memory v2.0 — Short-term + Long-term + Semantic + Action Graph.
Copyright © 2025-2026 Qtus Dev (Anh Tú)
"""
import os
import json
import time
import hashlib
from typing import List, Dict, Optional, Tuple, Set
from dataclasses import dataclass, field, asdict
from collections import deque

from config import DATA_DIR


@dataclass
class ActionRecord:
    """Ghi nhận một action đã thực hiện."""
    step: int = 0
    action: str = ""
    target: str = ""
    result_ok: bool = False
    result_msg: str = ""
    timestamp: float = field(default_factory=time.time)
    screenshot_hash: str = ""
    provider: str = ""


@dataclass
class ScreenState:
    """Trạng thái màn hình tại một thời điểm."""
    step: int = 0
    description: str = ""
    timestamp: float = field(default_factory=time.time)
    image_hash: str = ""
    classification: str = ""  # loading, normal, dialog, error


@dataclass
class ActionNode:
    """Node trong action graph."""
    action: str = ""
    screen_before_hash: str = ""
    screen_after_hash: str = ""
    success: bool = False
    count: int = 0


class AgentMemory:
    """
    Bộ nhớ Agent v2.0:
    - Short-term: 30 actions + 10 screenshots (context window mở rộng)
    - Long-term: Success patterns + Failure patterns (file-based)
    - Action Graph: Theo dõi chuỗi action → screen transitions
    - Error Pattern Detection: Nhận diện lỗi lặp
    - Session History: Lưu full session cho replay
    """

    def __init__(self, max_actions: int = 30, max_screens: int = 10):
        self.max_actions = max_actions
        self.max_screens = max_screens

        # Short-term
        self.actions: deque = deque(maxlen=max_actions)
        self.screens: deque = deque(maxlen=max_screens)
        self.current_goal: str = ""
        self.current_plan: List[str] = []
        self.current_step: int = 0
        self.failed_actions: List[str] = []

        # Action Graph (v2)
        self._action_graph: Dict[str, ActionNode] = {}
        self._error_patterns: List[str] = []
        self._action_sequence: List[str] = []

        # Session log
        self._session_log: List[Dict] = []

        # Long-term
        self._patterns_path = os.path.join(DATA_DIR, "agent_patterns.json")
        self._sessions_path = os.path.join(DATA_DIR, "agent_sessions.json")
        self.success_patterns: List[Dict] = []
        self.failure_patterns: List[str] = []
        self._load_patterns()

    # ─── Short-term Memory ──────────────────────────────────────

    def reset(self, goal: str = ""):
        self.actions.clear()
        self.screens.clear()
        self.current_goal = goal
        self.current_plan = []
        self.current_step = 0
        self.failed_actions = []
        self._action_sequence = []
        self._error_patterns = []
        self._session_log = [{
            "type": "start",
            "goal": goal,
            "timestamp": time.time(),
        }]

    def record_action(self, step: int, action: str, target: str = "",
                      result_ok: bool = True, result_msg: str = "",
                      provider: str = ""):
        record = ActionRecord(
            step=step, action=action, target=target,
            result_ok=result_ok, result_msg=result_msg,
            provider=provider,
        )
        self.actions.append(record)
        self._action_sequence.append(action.strip().upper())

        if not result_ok:
            self.failed_actions.append(action.strip().upper())
            self._detect_error_pattern()

        # Session log
        self._session_log.append({
            "type": "action",
            "step": step,
            "action": action,
            "ok": result_ok,
            "msg": result_msg,
            "timestamp": time.time(),
        })

    def record_screen(self, step: int, description: str, image_hash: str = "",
                      classification: str = ""):
        state = ScreenState(
            step=step, description=description,
            image_hash=image_hash, classification=classification,
        )
        self.screens.append(state)

    def set_plan(self, plan: List[str]):
        self.current_plan = plan

    # ─── History Text (for prompts) ──────────────────────────────

    def get_action_history_text(self, last_n: int = 10) -> str:
        if not self.actions:
            return "None"
        lines = []
        recent = list(self.actions)[-last_n:]
        for rec in recent:
            status = "✅" if rec.result_ok else "❌"
            lines.append(f"Step {rec.step}: {rec.action} → {status} {rec.result_msg}")
        return "\n".join(lines)

    def get_screen_history_text(self, last_n: int = 3) -> str:
        if not self.screens:
            return "None"
        lines = []
        recent = list(self.screens)[-last_n:]
        for s in recent:
            lines.append(f"[Step {s.step}] {s.description[:200]}")
        return "\n".join(lines)

    def get_failed_actions_text(self) -> str:
        if not self.failed_actions:
            return ""
        unique = list(set(self.failed_actions[-8:]))
        return "⚠️ AVOID these failed actions: " + ", ".join(unique)

    # ─── Loop Detection ──────────────────────────────────────────

    def detect_loop(self, current_hash: str, threshold: int = 3) -> bool:
        if not current_hash:
            return False
        recent_hashes = [s.image_hash for s in list(self.screens)[-threshold:]]
        if len(recent_hashes) >= threshold and all(h == current_hash for h in recent_hashes):
            return True
        return False

    def is_action_failed_before(self, action: str) -> bool:
        return action.strip().upper() in self.failed_actions

    # ─── Error Pattern Detection (v2) ────────────────────────────

    def _detect_error_pattern(self):
        """Phát hiện pattern lỗi lặp."""
        if len(self._action_sequence) < 4:
            return

        # Check lặp 2 action cuối
        last_4 = self._action_sequence[-4:]
        if last_4[0] == last_4[2] and last_4[1] == last_4[3]:
            pattern = f"{last_4[0]}→{last_4[1]}"
            if pattern not in self._error_patterns:
                self._error_patterns.append(pattern)

    def get_error_patterns(self) -> List[str]:
        return self._error_patterns

    # ─── Action Graph (v2) ───────────────────────────────────────

    def update_action_graph(self, action: str, screen_before: str,
                            screen_after: str, success: bool):
        """Cập nhật graph: action nào dẫn đến screen nào."""
        key = f"{action}|{screen_before[:8]}"
        if key in self._action_graph:
            node = self._action_graph[key]
            node.count += 1
            if success:
                node.success = True
                node.screen_after_hash = screen_after
        else:
            self._action_graph[key] = ActionNode(
                action=action,
                screen_before_hash=screen_before,
                screen_after_hash=screen_after,
                success=success,
                count=1,
            )

    def predict_best_action(self, screen_hash: str) -> Optional[str]:
        """Dựa vào graph, gợi ý action tốt nhất cho screen hiện tại."""
        candidates = []
        for key, node in self._action_graph.items():
            if node.screen_before_hash[:8] == screen_hash[:8] and node.success:
                candidates.append((node.action, node.count))

        if candidates:
            candidates.sort(key=lambda x: -x[1])
            return candidates[0][0]
        return None

    # ─── Long-term Memory (Patterns) ─────────────────────────────

    def save_success_pattern(self, goal: str, actions: List[str]):
        pattern = {
            "goal": goal,
            "actions": actions,
            "timestamp": time.time(),
        }
        self.success_patterns.append(pattern)
        if len(self.success_patterns) > 200:
            self.success_patterns = self.success_patterns[-200:]
        self._save_patterns()

    def find_similar_pattern(self, goal: str) -> Optional[List[str]]:
        """Tìm pattern tương tự — keyword matching cải tiến."""
        goal_lower = goal.lower()
        goal_words = set(goal_lower.split())

        best_match = None
        best_score = 0.0

        for p in reversed(self.success_patterns):
            p_goal = p.get("goal", "").lower()
            p_words = set(p_goal.split())

            # Jaccard similarity
            if not goal_words or not p_words:
                continue
            intersection = goal_words & p_words
            union = goal_words | p_words
            score = len(intersection) / len(union)

            if score > best_score and score >= 0.4:
                best_score = score
                best_match = p.get("actions", [])

        return best_match

    # ─── Session Management ──────────────────────────────────────

    def save_session(self):
        """Lưu session hiện tại."""
        if not self._session_log:
            return

        self._session_log.append({
            "type": "end",
            "total_steps": self.current_step,
            "timestamp": time.time(),
        })

        try:
            sessions = []
            if os.path.exists(self._sessions_path):
                with open(self._sessions_path, "r", encoding="utf-8") as f:
                    sessions = json.load(f)

            sessions.append({
                "goal": self.current_goal,
                "log": self._session_log,
                "timestamp": time.time(),
            })

            # Keep last 50 sessions
            sessions = sessions[-50:]

            with open(self._sessions_path, "w", encoding="utf-8") as f:
                json.dump(sessions, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def get_sessions(self, limit: int = 20) -> List[Dict]:
        """Lấy lịch sử sessions."""
        try:
            if os.path.exists(self._sessions_path):
                with open(self._sessions_path, "r", encoding="utf-8") as f:
                    sessions = json.load(f)
                return sessions[-limit:]
        except Exception:
            pass
        return []

    # ─── Persistence ─────────────────────────────────────────────

    def _save_patterns(self):
        try:
            with open(self._patterns_path, "w", encoding="utf-8") as f:
                json.dump({
                    "success": self.success_patterns[-100:],
                    "failures": list(set(self.failure_patterns[-100:])),
                }, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _load_patterns(self):
        try:
            if os.path.exists(self._patterns_path):
                with open(self._patterns_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.success_patterns = data.get("success", [])
                self.failure_patterns = data.get("failures", [])
        except Exception:
            pass

    def get_stats(self) -> Dict:
        """Thống kê memory."""
        total = len(self.actions)
        ok = sum(1 for a in self.actions if a.result_ok)
        return {
            "total_actions": total,
            "successful": ok,
            "failed": total - ok,
            "success_rate": round(ok / max(total, 1) * 100, 1),
            "patterns_saved": len(self.success_patterns),
            "error_patterns": len(self._error_patterns),
            "sessions_saved": len(self.get_sessions()),
        }
