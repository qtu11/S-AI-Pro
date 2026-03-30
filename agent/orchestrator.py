"""
S-AI-Pro v6.0 — Agent Orchestrator (5-Layer Cognitive OODA Loop).
Architecture: Observe → Orient → Decide → Act → Verify
+ Task Decomposition, Self-Healing, Provider Failover, Self-Learning
+ SQLite Persistence, Advanced Reasoning, Semantic Vision
Copyright © 2025-2026 Qtus Dev (Anh Tú)
"""
import os
import re
import time
import asyncio
import threading
from typing import Optional, List, Dict, Callable, Any
from dataclasses import dataclass, field

import pyautogui

from agent.eye import CloudEye, OllamaEye, ocr_find_element
from agent.hand import AutoHand
from agent.memory import AgentMemory
from agent.reasoning import ReasoningEngine, ActionPlan
from agent.vision_processor import VisionProcessor, ScreenshotCache
from agent.task_decomposer import TaskDecomposer, TaskHierarchy, SubTask
from agent.self_checker import SelfChecker, VerificationResult
from agent.learner import AgentLearner

from config.models import get_default_model, PROVIDER_MODELS
from config import (
    GEMINI_API_KEY, OPENAI_API_KEY, ANTHROPIC_API_KEY,
    GROQ_API_KEY, DEEPSEEK_API_KEY,
)
from core.perception import (
    capture_screen_to_image,
    compute_screen_hash,
    compute_screen_diff,
    image_to_base64,
    smart_resize,
)

# Database (lazy import to avoid circular)
_db_initialized = False


def _ensure_db():
    global _db_initialized
    if not _db_initialized:
        try:
            from database.schema import init_db
            init_db()
            _db_initialized = True
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════════
# DATA STRUCTURES
# ═══════════════════════════════════════════════════════════════

@dataclass
class ActionResult:
    """Execution result of a single action."""
    ok: bool = False
    msg: str = ""
    action: str = ""
    screen_changed: bool = False


PROVIDER_FAILOVER_CHAIN = []


def _build_failover_chain(primary: str) -> list:
    """Build failover chain based on available API keys."""
    available = []
    key_map = {
        "gemini": GEMINI_API_KEY,
        "openai": OPENAI_API_KEY,
        "anthropic": ANTHROPIC_API_KEY,
        "groq": GROQ_API_KEY,
        "deepseek": DEEPSEEK_API_KEY,
    }

    if primary == "ollama" or key_map.get(primary):
        available.append(primary)

    for provider, key in key_map.items():
        if provider != primary and key:
            available.append(provider)

    if "ollama" not in available:
        available.append("ollama")

    return available


class AgentOrchestrator:
    """
    S-AI-Pro v6.0 — 5-Layer Cognitive OODA Loop Orchestrator.

    Architecture layers:
    ┌─────────────────────────────────────────────────┐
    │  Layer 5: Strategic Planning                    │
    │  (TaskDecomposer + Deep Reasoning)              │
    ├─────────────────────────────────────────────────┤
    │  Layer 4: Tactical Reasoning                    │
    │  (ReasoningEngine + Action Planning)            │
    ├─────────────────────────────────────────────────┤
    │  Layer 3: Vision Understanding                  │
    │  (VisionProcessor + Semantic Analysis)          │
    ├─────────────────────────────────────────────────┤
    │  Layer 2: Action Execution                      │
    │  (AutoHand + Click/Type/Hotkey)                 │
    ├─────────────────────────────────────────────────┤
    │  Layer 1: Verification & Learning               │
    │  (SelfChecker + AgentLearner)                   │
    └─────────────────────────────────────────────────┘

    OODA Loop: Observe → Orient → Decide → Act → Verify
    Features:
    - Task Decomposition (complex goals → subtasks)
    - Provider Failover (Gemini → OpenAI → Ollama auto-switch)
    - Self-Healing (retry with different strategies)
    - Self-Learning (patterns, timing, model performance)
    - SQLite Persistence (tasks, steps, logs)
    """

    def __init__(
        self,
        brain_provider: str = "gemini",
        brain_model: str = "",
        eye_provider: str = "auto",
        eye_model: str = "",
        max_steps: int = 30,
        step_delay: float = 0.5,
        event_bridge=None,
        callback: Optional[Callable] = None,
        enable_decomposition: bool = True,
        enable_deep_thinking: bool = False,
        enable_learning: bool = True,
    ):
        self.brain_provider = brain_provider
        self.brain_model = brain_model or get_default_model(brain_provider)
        self.eye_provider = eye_provider
        self.eye_model = eye_model
        self.max_steps = max_steps
        self.step_delay = step_delay
        self.event_bridge = event_bridge
        self.callback = callback
        self.enable_decomposition = enable_decomposition
        self.enable_deep_thinking = enable_deep_thinking
        self.enable_learning = enable_learning

        # Failover
        self._failover_chain = _build_failover_chain(brain_provider)
        self._current_provider_idx = 0
        self._rate_limit_cooldown: Dict[str, float] = {}

        # ── Layer 5: Strategic Planning ──
        self.task_decomposer = TaskDecomposer(
            provider=brain_provider, model=self.brain_model,
        )
        self.task_hierarchy: Optional[TaskHierarchy] = None

        # ── Layer 4: Tactical Reasoning ──
        self.reasoning = ReasoningEngine(
            provider=brain_provider,
            model=self.brain_model,
        )

        # ── Layer 3: Vision Understanding ──
        self.vision = VisionProcessor(
            provider=self._get_eye_provider(),
            model=eye_model or get_default_model(self._get_eye_provider()),
        )

        # ── Layer 2: Action Execution ──
        self.hand = AutoHand()

        # ── Layer 1: Verification & Learning ──
        self.checker = SelfChecker(vision_processor=self.vision)
        self.learner = AgentLearner()

        # Legacy memory (kept for backward compat)
        self.memory = AgentMemory()

        # State
        self._running = False
        self._paused = False
        self._thread: Optional[threading.Thread] = None
        self._start_time = 0.0
        self._task_id: Optional[str] = None

        # Stats
        self.total_actions = 0
        self.successful_actions = 0
        self.failed_actions_count = 0
        self.provider_switches = 0

    # ═══════════════════════════════════════════════════════════════
    # PUBLIC API
    # ═══════════════════════════════════════════════════════════════

    def run(self, goal: str, blocking: bool = False) -> None:
        """Start the agent."""
        if self._running:
            return
        self._running = True
        self._paused = False
        self._start_time = time.time()
        self.memory.reset(goal)
        self.task_hierarchy = None
        self.total_actions = 0
        self.successful_actions = 0
        self.failed_actions_count = 0
        self.provider_switches = 0
        self.checker.reset_failure_count()

        # Init DB
        _ensure_db()

        # Create task in DB
        try:
            from database.repository import TaskRepository
            self._task_id = TaskRepository.create(
                description=goal,
                provider=self._get_active_provider(),
                primary_model=self._get_active_model(),
                max_steps=self.max_steps,
            )
            TaskRepository.update_status(self._task_id, "running")
        except Exception:
            self._task_id = None

        def _run():
            try:
                self.hand._cursor.move_to(-100, -100)
                self._main_loop(goal)
            except Exception as e:
                self._log("error", f"💥 Agent crash: {e}")
            finally:
                self._running = False
                try:
                    self.hand._cursor.hide()
                except Exception:
                    pass
                duration = time.time() - self._start_time
                success = self.successful_actions > 0
                self._emit_complete(success, self.memory.current_step, duration)

                # Persist final state
                self._finalize_task(success, duration)

        if blocking:
            _run()
        else:
            self._thread = threading.Thread(target=_run, daemon=True)
            self._thread.start()

    def stop(self) -> None:
        self._running = False

    def pause(self) -> None:
        self._paused = True
        self._log("system", "⏸️ Agent tạm dừng")

    def resume(self) -> None:
        self._paused = False
        self._log("system", "▶️ Agent tiếp tục")

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def is_paused(self) -> bool:
        return self._paused

    def get_status(self) -> dict:
        """Return current agent status."""
        return {
            "running": self._running,
            "paused": self._paused,
            "step": self.memory.current_step,
            "max_steps": self.max_steps,
            "provider": self._get_active_provider(),
            "model": self.brain_model,
            "task_id": self._task_id or "",
            "sub_tasks": self.task_hierarchy.to_dict() if self.task_hierarchy else {},
            "stats": {
                "total_actions": self.total_actions,
                "successful": self.successful_actions,
                "failed": self.failed_actions_count,
                "provider_switches": self.provider_switches,
                "duration": round(time.time() - self._start_time, 1) if self._start_time else 0,
            },
            "verification": self.checker.get_stats(),
            "learning": self.learner.get_insights_summary() if self.enable_learning else {},
        }

    # ═══════════════════════════════════════════════════════════════
    # MAIN OODA LOOP (5-Layer Cognitive Architecture)
    # ═══════════════════════════════════════════════════════════════

    def _main_loop(self, goal: str) -> None:
        active_provider = self._get_active_provider()
        active_model = self._get_active_model()

        self._log("think", f"🚀 S-AI-Pro v6.0 — Brain: {active_provider}/{active_model}")
        self._log("think", f"🎯 Mục tiêu: {goal}")
        self._log("system", f"🔄 Failover chain: {' → '.join(self._failover_chain)}")
        self._emit_status("planning", 0, self.max_steps, goal)

        # ── Layer 5: Strategic Planning ──
        if self.enable_decomposition:
            self._log("think", "📊 Phân tích & phân tách mục tiêu...")
            self.task_hierarchy = self.task_decomposer.decompose(goal)
            if self.task_hierarchy and len(self.task_hierarchy.subtasks) > 1:
                self._log("plan", f"📋 Phân tách thành {len(self.task_hierarchy.subtasks)} subtasks:")
                for st in self.task_hierarchy.subtasks:
                    self._log("plan", f"  {st.id}. {st.name}: {st.description}")
                    self._emit_subtask_update(st)

        # Check for learned patterns
        if self.enable_learning:
            recommendation = self.learner.get_recommendation(goal)
            if recommendation:
                self._log("think", f"💡 Có pattern đã học (confidence={recommendation['confidence']:.1f})")

        # Deep thinking (if enabled)
        if self.enable_deep_thinking:
            self._log("think", "🧠 Deep thinking mode...")
            deep = self.reasoning.think_deeply(goal)
            if deep.thinking:
                self._log("think", f"💭 {deep.thinking[:300]}")
            self._log("think", f"📊 Complexity: {deep.complexity}, Confidence: {deep.confidence:.1f}")

        # Initialize Eye
        eye = self._init_eye()
        fail_count = 0
        prev_image = None
        consecutive_no_change = 0

        for step in range(1, self.max_steps + 1):
            if not self._running:
                self._log("done", "⛔ Agent dừng theo yêu cầu.")
                break

            # Handle pause
            while self._paused and self._running:
                time.sleep(0.5)
            if not self._running:
                break

            self.memory.current_step = step
            self._log("see", f"\n{'═' * 50}")
            self._log("see", f"📸 BƯỚC {step}/{self.max_steps}")

            # ══════════════════════════════════════════════════
            # PHASE 1: OBSERVE (Layer 3)
            # ══════════════════════════════════════════════════
            self._emit_status("seeing", step, self.max_steps, goal)
            screen_image = capture_screen_to_image()
            screen_hash = compute_screen_hash(screen_image)

            # Screen diff
            diff_info = ""
            screen_changed = True
            if prev_image:
                diff = compute_screen_diff(prev_image, screen_image)
                diff_info = f"[Screen: {diff['description']}]"
                screen_changed = diff["changed"]
                if not screen_changed:
                    consecutive_no_change += 1
                    if step > 2:
                        self._log("see", f"⚠️ Màn hình không đổi (lần {consecutive_no_change})")
                else:
                    consecutive_no_change = 0

            # Loop detection (self-healing)
            if self.memory.detect_loop(screen_hash, threshold=3):
                self._log("error", "🔄 LOOP — Màn hình không đổi 3 bước!")
                fail_count += 1
                if fail_count >= 4:
                    self._log("error", "❌ Quá nhiều loop. Agent dừng.")
                    break

                # Self-healing strategies
                self._log("think", "🔧 Self-healing...")
                recovery_actions = self.checker.suggest_recovery(
                    self.memory.get_last_action_text(), attempts=fail_count,
                )
                for ra in recovery_actions[:2]:
                    self._log("act", f"🔧 Recovery: {ra}")
                    self._execute(ra, "", eye)
                    time.sleep(0.5)
                continue

            self.memory.record_screen(step, "", screen_hash)

            # Send preview to UI
            preview = smart_resize(screen_image, 1600)
            preview_b64 = image_to_base64(preview, "JPEG", 90)
            self._emit_screenshot(preview_b64, step)

            # ══════════════════════════════════════════════════
            # PHASE 2: ORIENT (Layer 3 — Vision Understanding)
            # ══════════════════════════════════════════════════
            self._log("see", "👁️ Đang quét màn hình...")
            temp_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "screen.png")
            screen_image.save(temp_path, "PNG")

            try:
                screen_desc = eye.describe_screen(temp_path)

                if self._is_rate_limited(screen_desc) or "[LỖI" in screen_desc:
                    raise RuntimeError(screen_desc)

                preview_text = screen_desc[:300].replace("\n", " | ")
                self._log("see", f"Màn hình: {preview_text}...")

            except Exception as e:
                self._log("error", f"Lỗi Eye: {str(e)[:150]}")
                self._handle_rate_limit("eye")
                time.sleep(1)
                eye = self._init_eye()
                continue

            mx, my = pyautogui.position()
            screen_context = (
                f"{screen_desc}\n---\n"
                f"MOUSE: ({mx}, {my})\n"
                f"{diff_info}\n"
                f"Resolution: {screen_image.size[0]}x{screen_image.size[1]}\n"
                f"Step: {step}/{self.max_steps}"
            )

            # ══════════════════════════════════════════════════
            # PHASE 3: DECIDE (Layer 4 — Tactical Reasoning)
            # ══════════════════════════════════════════════════
            self._emit_status("thinking", step, self.max_steps, goal)
            self._log("think", f"🧠 Đang suy nghĩ ({self._get_active_provider()})...")

            # Update reasoning engine provider (may have changed due to failover)
            self.reasoning.provider = self._get_active_provider()
            self.reasoning.model = self._get_active_model()

            hist_text = self.memory.get_action_history_text(last_n=8)
            failed_text = self.memory.get_failed_actions_text()

            # Load skill file
            skill_text = ""
            skill_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "ai_skill.md")
            try:
                if os.path.exists(skill_path):
                    with open(skill_path, "r", encoding="utf-8") as f:
                        skill_text = f.read()
            except Exception:
                pass

            plan = self._decide_with_failover(
                goal, screen_context, step, hist_text, failed_text, skill_text,
            )

            # Handle decision errors
            if plan.error_detected:
                fail_count += 1
                self._log("error", f"⚠️ Brain error: {plan.error_message}")
                if "rate limit" in plan.error_message.lower():
                    self._handle_rate_limit("brain")
                if fail_count >= 4:
                    self._log("error", "❌ Brain thất bại quá nhiều. Dừng.")
                    break
                time.sleep(1.5)
                continue

            if not plan.actions:
                fail_count += 1
                self._log("error", f"⚠️ Brain không trả action (lần {fail_count}/4)")
                if fail_count >= 4:
                    self._log("error", "❌ Dừng — không có action.")
                    break
                if fail_count >= 2:
                    self._handle_rate_limit("brain_empty")
                time.sleep(1.5)
                continue

            fail_count = 0
            combo = " → ".join(plan.actions)
            self._log("think", f"▶ Combo: {combo}")

            if plan.thought:
                self._log("think", f"💭 {plan.thought[:250]}")
            if plan.plan_text:
                self._log("plan", f"📋 Kế hoạch:\n{plan.plan_text}")
            if plan.check_state:
                self._log("see", f"🔎 Nhận định:\n{plan.check_state}")

            self._emit_thinking(plan.thought or "", plan.plan_text or "")

            # ══════════════════════════════════════════════════
            # PHASE 4: ACT (Layer 2 — Execution)
            # ══════════════════════════════════════════════════
            self._emit_status("acting", step, self.max_steps, goal)
            screen_before = screen_image  # Save for verification
            is_done = False

            for act in plan.actions:
                if not self._running:
                    break

                act_upper = act.strip().upper()
                if act_upper == "DONE":
                    self._log("done", "\n✅ Agent đã hoàn thành mục tiêu!")
                    is_done = True
                    all_actions = [a.action for a in self.memory.actions]
                    self.memory.save_success_pattern(goal, all_actions)
                    break

                self._log("act", f"✋ Thực thi: {act}")
                result = self._execute(act, temp_path, eye)
                self.total_actions += 1

                self.memory.record_action(
                    step=step, action=act,
                    result_ok=result.ok, result_msg=result.msg,
                )
                self._emit_action(act, {"ok": result.ok, "msg": result.msg}, step)

                # Persist step in DB
                self._persist_step(step, act, result)

                if result.ok:
                    self.successful_actions += 1
                    self._log("act", f"✅ {result.msg}")
                else:
                    self.failed_actions_count += 1
                    self._log("error", f"❌ {result.msg}")
                    if "Không tìm thấy" in result.msg:
                        self._log("think", "🔧 Element không tìm thấy — thử phương án khác.")
                        break

                # Smart delay based on learning
                if self.enable_learning:
                    action_type = act.split()[0].upper() if act.strip() else "CLICK"
                    delay = self.learner.get_optimal_delay(action_type)
                else:
                    delay = max(0.15, self.step_delay)
                time.sleep(delay)

            if is_done:
                break

            # ══════════════════════════════════════════════════
            # PHASE 5: VERIFY (Layer 1 — Verification & Learning)
            # ══════════════════════════════════════════════════
            if plan.actions and not is_done:
                verification = self.checker.verify_action(
                    screen_before=screen_before,
                    action=plan.actions[-1] if plan.actions else "",
                    delay=0.3,
                )

                if verification.action_succeeded:
                    self._log("see", f"✅ Verify: Thành công (diff={verification.diff_ratio:.2f})")
                else:
                    self._log("see", f"⚠️ Verify: Có thể thất bại (diff={verification.diff_ratio:.2f})")

                    # Check if stuck
                    if self.checker.is_stuck(threshold=3):
                        self._log("error", "🔄 Agent bị kẹt! Kích hoạt recovery...")
                        recovery_plan = self.reasoning.plan_recovery(
                            goal=goal,
                            failed_actions=[a.action for a in self.memory.actions[-5:]],
                            screen_state=screen_desc[:300],
                            attempts=self.checker.get_failure_streak(),
                        )
                        if recovery_plan.actions:
                            for ra in recovery_plan.actions[:3]:
                                self._log("act", f"🔧 Recovery: {ra}")
                                self._execute(ra, temp_path, eye)
                                time.sleep(0.5)
                            self.checker.reset_failure_count()

            prev_image = screen_image
        else:
            self._log("done", f"⏱️ Đạt giới hạn {self.max_steps} bước.")

        # ── Post-execution Learning ──
        if self.enable_learning:
            duration = time.time() - self._start_time
            steps_data = [
                {"action": a.action, "success": a.ok, "duration_ms": 0}
                for a in self.memory.actions
            ]
            insights = self.learner.learn_from_execution(
                goal=goal, steps=steps_data,
                success=self.successful_actions > 0,
                total_duration=duration,
            )
            if insights:
                self._log("think", f"📚 Learned {len(insights)} insights from this execution")

    # ═══════════════════════════════════════════════════════════════
    # DECIDE WITH FAILOVER
    # ═══════════════════════════════════════════════════════════════

    def _decide_with_failover(
        self, goal: str, screen_context: str, step: int,
        history: str, failed_text: str, skill_text: str,
    ) -> ActionPlan:
        """Run reasoning with automatic provider failover."""
        for attempt in range(len(self._failover_chain)):
            self.reasoning.provider = self._get_active_provider()
            self.reasoning.model = self._get_active_model()

            plan = self.reasoning.plan_actions(
                goal=goal,
                screen_context=screen_context,
                step=step,
                max_steps=self.max_steps,
                history=history,
                failed_text=failed_text,
                skill_text=skill_text,
            )

            if plan.error_detected and "rate limit" in plan.error_message.lower():
                self._handle_rate_limit("brain")
                continue

            return plan

        return ActionPlan(error_detected=True, error_message="All providers exhausted")

    # ═══════════════════════════════════════════════════════════════
    # PROVIDER FAILOVER
    # ═══════════════════════════════════════════════════════════════

    def _get_active_provider(self) -> str:
        idx = min(self._current_provider_idx, len(self._failover_chain) - 1)
        return self._failover_chain[idx]

    def _get_active_model(self) -> str:
        provider = self._get_active_provider()
        if provider == self.brain_provider:
            return self.brain_model
        return get_default_model(provider)

    def _get_eye_provider(self) -> str:
        if self.eye_provider and self.eye_provider != "auto":
            return self.eye_provider
        return self._get_active_provider()

    @staticmethod
    def _is_rate_limited(response: str) -> bool:
        signals = [
            "429", "RESOURCE_EXHAUSTED", "rate limit", "quota",
            "Too Many Requests", "RateLimitError",
        ]
        response_upper = response.upper()
        return any(s.upper() in response_upper for s in signals)

    def _handle_rate_limit(self, source: str = "unknown"):
        current = self._get_active_provider()
        self._rate_limit_cooldown[current] = time.time() + 60

        if self._current_provider_idx < len(self._failover_chain) - 1:
            self._current_provider_idx += 1
            new_provider = self._get_active_provider()
            new_model = self._get_active_model()
            self.provider_switches += 1
            self._log("system",
                f"🔄 FAILOVER: {current} → {new_provider}/{new_model}")
            self._emit_status("provider_switch", self.memory.current_step, self.max_steps,
                f"Chuyển từ {current} → {new_provider}")
        else:
            self._log("error", "⚠️ Tất cả providers rate limit! Chờ 30s...")
            time.sleep(30)
            self._current_provider_idx = 0
            self._rate_limit_cooldown.clear()

    # ═══════════════════════════════════════════════════════════════
    # EYE — INIT
    # ═══════════════════════════════════════════════════════════════

    def _init_eye(self):
        effective = self.eye_provider
        if not effective or effective == "auto":
            effective = self._get_active_provider()

        if effective == "ollama":
            eye = OllamaEye(self.eye_model)
            selected = eye.auto_select_model() if not self.eye_model else self.eye_model
            if selected:
                self._log("see", f"👁️ Eye: Ollama ({selected})")
                return eye
            else:
                self._log("see", "⚠️ Ollama kh vision → fallback Cloud")
                effective = "gemini" if GEMINI_API_KEY else self._get_active_provider()

        model = self.eye_model or get_default_model(effective)
        self._log("see", f"👁️ Eye: {effective}/{model}")
        return CloudEye(provider=effective, model_name=model)

    # ═══════════════════════════════════════════════════════════════
    # HAND — EXECUTE
    # ═══════════════════════════════════════════════════════════════

    def _execute(self, action: str, img_path: str, eye) -> ActionResult:
        """Execute action with retry logic."""
        action = action.strip()
        action_upper = action.upper()

        try:
            if action_upper == "DONE":
                return ActionResult(ok=True, msg="Hoàn thành", action=action)
            if action_upper == "SCREENSHOT":
                return ActionResult(ok=True, msg="Chụp lại", action=action)

            # WAIT
            m = re.match(r"WAIT\s+([\d.]+)", action, re.IGNORECASE)
            if m:
                s = min(float(m.group(1)), 30)
                time.sleep(s)
                return ActionResult(ok=True, msg=f"Đã chờ {s}s", action=action)

            # HOTKEY
            m = re.match(r"HOTKEY\s+(.+)", action, re.IGNORECASE)
            if m:
                self.hand.hotkey(m.group(1).strip())
                return ActionResult(ok=True, msg=f"Hotkey: {m.group(1)}", action=action)

            # PRESS
            m = re.match(r"PRESS\s+(.+)", action, re.IGNORECASE)
            if m:
                self.hand.press_key(m.group(1).strip())
                return ActionResult(ok=True, msg=f"Phím: {m.group(1)}", action=action)

            # TYPE
            m = re.match(r"TYPE\s+(.+)", action, re.IGNORECASE)
            if m:
                self.hand.type_text(m.group(1).strip())
                return ActionResult(ok=True, msg="Đã gõ text", action=action)

            # SCROLL
            m = re.match(r"SCROLL\s+(.+)", action, re.IGNORECASE)
            if m:
                self.hand.scroll(m.group(1).strip())
                return ActionResult(ok=True, msg=f"Cuộn {m.group(1)}", action=action)

            # CLICK variants
            for prefix in ("DOUBLECLICK", "RIGHTCLICK", "CLICK"):
                m = re.match(rf"{prefix}\s+(.+)", action, re.IGNORECASE)
                if m:
                    target = m.group(1).strip()
                    return self._click_with_retry(prefix, target, img_path, eye)

            return ActionResult(ok=False, msg=f"Không nhận diện: {action}", action=action)

        except Exception as e:
            return ActionResult(ok=False, msg=f"Lỗi: {e}", action=action)

    def _click_with_retry(
        self, click_type: str, target: str, img_path: str, eye, max_retries: int = 2
    ) -> ActionResult:
        for attempt in range(max_retries + 1):
            coords = eye.find_element(img_path, target)
            if coords:
                sx = int(coords[0] * self.hand.screen_w)
                sy = int(coords[1] * self.hand.screen_h)

                if click_type == "DOUBLECLICK":
                    self.hand.double_click(sx, sy)
                elif click_type == "RIGHTCLICK":
                    self.hand.right_click(sx, sy)
                else:
                    self.hand.click(sx, sy)

                return ActionResult(
                    ok=True,
                    msg=f"{click_type} '{target}' tại ({sx},{sy})",
                    action=f"{click_type} {target}",
                )

            if attempt < max_retries:
                self._log("see", f"🔁 Retry tìm '{target}' (lần {attempt+2})...")
                time.sleep(0.5)
                new_screen = capture_screen_to_image()
                new_screen.save(img_path, "PNG")

        return ActionResult(
            ok=False,
            msg=f"Không tìm thấy '{target}' ({max_retries+1} lần thử)",
            action=f"{click_type} {target}",
        )

    # ═══════════════════════════════════════════════════════════════
    # DATABASE PERSISTENCE
    # ═══════════════════════════════════════════════════════════════

    def _persist_step(self, step: int, action: str, result: ActionResult):
        """Persist step to SQLite."""
        if not self._task_id:
            return
        try:
            from database.repository import StepRepository, LogRepository
            action_type = action.split()[0].upper() if action else ""
            StepRepository.create(
                task_id=self._task_id,
                step_number=step,
                phase="act",
                action_type=action_type,
                action_data={"raw": action},
                target=action[len(action_type):].strip() if action_type else "",
            )
            LogRepository.write(
                message=f"{action} → {'OK' if result.ok else 'FAIL'}: {result.msg}",
                level="INFO" if result.ok else "WARNING",
                event_type="action",
                task_id=self._task_id,
                step_number=step,
            )
        except Exception:
            pass

    def _finalize_task(self, success: bool, duration: float):
        """Finalize task in DB after completion."""
        if not self._task_id:
            return
        try:
            from database.repository import TaskRepository
            TaskRepository.complete(
                task_id=self._task_id,
                success=success,
                result=f"{'Completed' if success else 'Failed'}: {self.successful_actions} actions",
                duration_ms=int(duration * 1000),
            )
            TaskRepository.update_progress(
                task_id=self._task_id,
                total_steps=self.total_actions,
                successful_steps=self.successful_actions,
                failed_steps=self.failed_actions_count,
                confidence=self.successful_actions / max(self.total_actions, 1),
                duration_ms=int(duration * 1000),
            )
        except Exception:
            pass

    # ═══════════════════════════════════════════════════════════════
    # EVENT EMISSION
    # ═══════════════════════════════════════════════════════════════

    def _log(self, event: str, message: str):
        if self.event_bridge:
            self.event_bridge.emit_log(event, message, self.memory.current_step)
        if self.callback:
            self.callback(event, message)
        else:
            print(f"[{event.upper()}] {message}")

    def _emit_status(self, status: str, step: int, max_steps: int, goal: str):
        if self.event_bridge:
            self.event_bridge.emit_status(status, step, max_steps, goal)

    def _emit_screenshot(self, b64: str, step: int):
        if self.event_bridge:
            self.event_bridge.emit_screenshot(b64, step)

    def _emit_action(self, action: str, result: dict, step: int):
        if self.event_bridge:
            self.event_bridge.emit_action(action, result, step)

    def _emit_complete(self, success: bool, steps: int, duration: float):
        if self.event_bridge:
            self.event_bridge.emit_complete(success, steps, duration)

    def _emit_thinking(self, thought: str, plan: str):
        if self.event_bridge:
            self.event_bridge.emit("agent_thinking", thought=thought, plan=plan)

    def _emit_subtask_update(self, subtask):
        if self.event_bridge:
            self.event_bridge.emit("subtask_update",
                id=subtask.id, desc=subtask.description,
                status=subtask.status, steps=getattr(subtask, 'steps_taken', 0))


# Backward compatibility
UnifiedAgent = AgentOrchestrator
AutonomousAgent = AgentOrchestrator
OllamaAgent = AgentOrchestrator
