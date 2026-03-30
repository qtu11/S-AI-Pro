"""
Agent Orchestrator v5.0 — OODA Loop + Task Decomposition + Self-Healing.
Kiến trúc: Observe → Orient → Decide → Act → Verify
Provider Failover: Gemini → OpenAI → Ollama (auto-switch khi rate limit)
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


# ═══════════════════════════════════════════════════════════════
# DATA STRUCTURES
# ═══════════════════════════════════════════════════════════════

@dataclass
class SubTask:
    """Mô tả 1 sub-task được decompose từ goal."""
    id: int = 0
    description: str = ""
    status: str = "pending"  # pending | running | done | failed | skipped
    steps_taken: int = 0
    max_steps: int = 10
    result: str = ""


@dataclass
class AgentDecision:
    """Kết quả suy nghĩ của Brain."""
    thought: str = ""
    plan: str = ""
    check_state: str = ""
    actions: List[str] = field(default_factory=list)
    expected_change: str = ""  # Mô tả kỳ vọng sau action
    confidence: float = 0.0


@dataclass
class ActionResult:
    """Kết quả thực thi action."""
    ok: bool = False
    msg: str = ""
    action: str = ""
    screen_changed: bool = False


PROVIDER_FAILOVER_CHAIN = []


def _build_failover_chain(primary: str) -> list:
    """Xây dựng chain failover dựa trên API keys có sẵn."""
    available = []
    key_map = {
        "gemini": GEMINI_API_KEY,
        "openai": OPENAI_API_KEY,
        "anthropic": ANTHROPIC_API_KEY,
        "groq": GROQ_API_KEY,
        "deepseek": DEEPSEEK_API_KEY,
    }

    # Primary first
    if primary == "ollama" or key_map.get(primary):
        available.append(primary)

    # Then others
    for provider, key in key_map.items():
        if provider != primary and key:
            available.append(provider)

    # Ollama always as last resort
    if "ollama" not in available:
        available.append("ollama")

    return available


class AgentOrchestrator:
    """
    Agent v5.0 — OODA Loop Orchestrator.

    Improvements over v4.0:
    - OODA loop (Observe→Orient→Decide→Act) with Verify step
    - Task Decomposition: large goal → sub-tasks
    - Provider Failover: auto-switch when rate limited
    - Self-Healing: retry with different strategy on failure
    - Parallel perception: async-ready architecture
    - Smart timing: adaptive delays based on UI state
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
    ):
        self.brain_provider = brain_provider
        self.brain_model = brain_model or get_default_model(brain_provider)
        self.eye_provider = eye_provider
        self.eye_model = eye_model
        self.max_steps = max_steps
        self.step_delay = step_delay
        self.event_bridge = event_bridge
        self.callback = callback

        # Failover chain
        self._failover_chain = _build_failover_chain(brain_provider)
        self._current_provider_idx = 0
        self._rate_limit_cooldown: Dict[str, float] = {}

        # Components
        self.hand = AutoHand()
        self.memory = AgentMemory()
        self._running = False
        self._paused = False
        self._thread: Optional[threading.Thread] = None
        self._start_time = 0.0

        # Sub-tasks
        self.sub_tasks: List[SubTask] = []
        self.current_sub_task: Optional[SubTask] = None

        # Stats
        self.total_actions = 0
        self.successful_actions = 0
        self.failed_actions_count = 0
        self.provider_switches = 0

    # ═══════════════════════════════════════════════════════════════
    # PUBLIC API
    # ═══════════════════════════════════════════════════════════════

    def run(self, goal: str, blocking: bool = False) -> None:
        """Khởi chạy agent."""
        if self._running:
            return
        self._running = True
        self._paused = False
        self._start_time = time.time()
        self.memory.reset(goal)
        self.sub_tasks = []
        self.total_actions = 0
        self.successful_actions = 0
        self.failed_actions_count = 0
        self.provider_switches = 0

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
        """Trả về trạng thái hiện tại."""
        return {
            "running": self._running,
            "paused": self._paused,
            "step": self.memory.current_step,
            "max_steps": self.max_steps,
            "provider": self._get_active_provider(),
            "model": self.brain_model,
            "sub_tasks": [
                {"id": st.id, "desc": st.description, "status": st.status}
                for st in self.sub_tasks
            ],
            "stats": {
                "total_actions": self.total_actions,
                "successful": self.successful_actions,
                "failed": self.failed_actions_count,
                "provider_switches": self.provider_switches,
                "duration": round(time.time() - self._start_time, 1) if self._start_time else 0,
            },
        }

    # ═══════════════════════════════════════════════════════════════
    # MAIN OODA LOOP
    # ═══════════════════════════════════════════════════════════════

    def _main_loop(self, goal: str) -> None:
        active_provider = self._get_active_provider()
        active_model = self._get_active_model()

        self._log("think", f"🚀 Agent v5.0 — Brain: {active_provider}/{active_model}")
        self._log("think", f"🎯 Mục tiêu: {goal}")
        self._log("system", f"🔄 Failover chain: {' → '.join(self._failover_chain)}")
        self._emit_status("planning", 0, self.max_steps, goal)

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

            # ── PHASE 1: OBSERVE ──
            self._emit_status("seeing", step, self.max_steps, goal)
            screen_image = capture_screen_to_image()
            screen_hash = compute_screen_hash(screen_image)

            # Screen diff detection
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

            # Loop detection
            if self.memory.detect_loop(screen_hash, threshold=3):
                self._log("error", "🔄 LOOP — Màn hình không đổi 3 bước liên tiếp!")
                fail_count += 1
                if fail_count >= 4:
                    self._log("error", "❌ Quá nhiều loop. Agent dừng.")
                    break
                # Self-healing: try pressing Escape or clicking elsewhere
                self._log("think", "🔧 Self-healing: thử thoát khỏi trạng thái kẹt...")
                self.hand.press_key("escape")
                time.sleep(1)
                continue

            self.memory.record_screen(step, "", screen_hash)

            # Send preview to UI
            preview = smart_resize(screen_image, 1600)
            preview_b64 = image_to_base64(preview, "JPEG", 90)
            self._emit_screenshot(preview_b64, step)

            # Eye describes screen
            self._log("see", "👁️ Đang quét màn hình...")
            temp_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "screen.png")
            screen_image.save(temp_path, "PNG")

            try:
                screen_desc = eye.describe_screen(temp_path)
                
                # Bắt lỗi cứng từ API response thay vì feed cho Brain
                if self._is_rate_limited(screen_desc) or "[LỖI" in screen_desc:
                    raise RuntimeError(screen_desc)
                    
                preview_text = screen_desc[:300].replace("\n", " | ")
                self._log("see", f"Màn hình: {preview_text}...")
                
            except Exception as e:
                self._log("error", f"Lỗi Eye: {str(e)[:150]}")
                self._handle_rate_limit("eye")
                
                # Bắt buộc chờ xíu và bỏ qua luôn phase Decide/Act để tránh hallucination
                time.sleep(1)
                eye = self._init_eye()
                continue

            # Mouse position
            mx, my = pyautogui.position()

            # ── PHASE 2: ORIENT — Build context ──
            screen_context = (
                f"{screen_desc}\n"
                f"---\n"
                f"MOUSE: ({mx}, {my})\n"
                f"{diff_info}\n"
                f"Resolution: {screen_image.size[0]}x{screen_image.size[1]}\n"
                f"Step: {step}/{self.max_steps}"
            )

            # ── PHASE 3: DECIDE ──
            self._emit_status("thinking", step, self.max_steps, goal)
            self._log("think", f"🧠 Đang suy nghĩ ({self._get_active_provider()})...")

            decision = self._decide(goal, screen_context, step)

            # Handle rate limit in brain response
            if not decision.actions and fail_count == 0:
                # Maybe rate limited
                pass

            if decision.thought:
                self._log("think", f"💭 {decision.thought[:250]}")
            if decision.plan:
                self._log("plan", f"📋 Kế hoạch:\n{decision.plan}")
            if decision.check_state:
                self._log("see", f"🔎 Nhận định:\n{decision.check_state}")

            if not decision.actions:
                fail_count += 1
                self._log("error", f"⚠️ Brain không trả action (lần {fail_count}/4)")
                if fail_count >= 4:
                    self._log("error", "❌ Brain thất bại quá nhiều. Dừng.")
                    break
                # Try switching provider
                if fail_count >= 2:
                    self._handle_rate_limit("brain_empty")
                time.sleep(1.5)
                continue

            fail_count = 0  # Reset on success
            combo = " → ".join(decision.actions)
            self._log("think", f"▶ Combo: {combo}")

            # Broadcast thinking event
            self._emit_thinking(decision.thought, decision.plan)

            # ── PHASE 4: ACT ──
            self._emit_status("acting", step, self.max_steps, goal)
            is_done = False

            for act in decision.actions:
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
                    result_ok=result.ok,
                    result_msg=result.msg,
                )
                self._emit_action(act, {"ok": result.ok, "msg": result.msg}, step)

                if result.ok:
                    self.successful_actions += 1
                    self._log("act", f"✅ {result.msg}")
                else:
                    self.failed_actions_count += 1
                    self._log("error", f"❌ {result.msg}")
                    # Don't break on non-critical failures
                    if "Không tìm thấy" in result.msg:
                        self._log("think", "🔧 Element không tìm thấy — thử phương án khác trong bước tiếp.")
                        break

                time.sleep(max(0.15, self.step_delay))

            if is_done:
                break

            # ── PHASE 5: VERIFY (mới v5.0) ──
            if decision.actions and not is_done:
                time.sleep(0.3)  # Wait for UI update
                verify_image = capture_screen_to_image()
                verify_diff = compute_screen_diff(screen_image, verify_image)

                if not verify_diff["changed"] and not any(
                    a.upper().startswith(("WAIT", "SCREENSHOT")) for a in decision.actions
                ):
                    self._log("see", f"⚠️ Verify: Màn hình không thay đổi sau action! (diff={verify_diff['diff_ratio']})")
                else:
                    self._log("see", f"✅ Verify: Màn hình đã thay đổi ({verify_diff['description']})")

            prev_image = screen_image
        else:
            self._log("done", f"⏱️ Đạt giới hạn {self.max_steps} bước.")

    # ═══════════════════════════════════════════════════════════════
    # PROVIDER FAILOVER
    # ═══════════════════════════════════════════════════════════════

    def _get_active_provider(self) -> str:
        """Lấy provider hiện tại (có thể đã failover)."""
        idx = min(self._current_provider_idx, len(self._failover_chain) - 1)
        return self._failover_chain[idx]

    def _get_active_model(self) -> str:
        """Lấy model phù hợp cho provider hiện tại."""
        provider = self._get_active_provider()
        if provider == self.brain_provider:
            return self.brain_model
        return get_default_model(provider)

    def _is_rate_limited(self, response: str) -> bool:
        """Kiểm tra response có phải rate limit error."""
        rate_limit_signals = [
            "429", "RESOURCE_EXHAUSTED", "rate limit", "quota",
            "Too Many Requests", "RateLimitError",
        ]
        response_upper = response.upper()
        return any(s.upper() in response_upper for s in rate_limit_signals)

    def _handle_rate_limit(self, source: str = "unknown"):
        """Xử lý rate limit → switch provider."""
        current = self._get_active_provider()
        self._rate_limit_cooldown[current] = time.time() + 60  # Cooldown 60s

        if self._current_provider_idx < len(self._failover_chain) - 1:
            self._current_provider_idx += 1
            new_provider = self._get_active_provider()
            new_model = self._get_active_model()
            self.provider_switches += 1

            self._log("system",
                f"🔄 FAILOVER: {current} bị rate limit → Chuyển sang {new_provider}/{new_model}")
            self._emit_status("provider_switch", self.memory.current_step, self.max_steps,
                f"Chuyển từ {current} → {new_provider}")
        else:
            self._log("error", f"⚠️ Tất cả providers đều bị rate limit! Chờ 30s...")
            time.sleep(30)
            # Reset to try again
            self._current_provider_idx = 0
            self._rate_limit_cooldown.clear()

    # ═══════════════════════════════════════════════════════════════
    # BRAIN — DECIDE
    # ═══════════════════════════════════════════════════════════════

    def _decide(self, goal: str, screen_context: str, step: int) -> AgentDecision:
        """Brain suy nghĩ và quyết định action."""
        from core.analyzer import stream_router
        from config.prompts import BRAIN_ACTION_PROMPT_V2

        hist_text = self.memory.get_action_history_text(last_n=8)
        failed_text = self.memory.get_failed_actions_text()

        # Load AI skill
        skill_text = ""
        skill_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "ai_skill.md")
        try:
            if os.path.exists(skill_path):
                with open(skill_path, "r", encoding="utf-8") as f:
                    skill_text = f.read()
        except Exception:
            pass

        prompt = BRAIN_ACTION_PROMPT_V2.format(
            instruction=goal,
            history=hist_text,
            step=step,
            max_steps=self.max_steps,
        )
        if failed_text:
            prompt += f"\n\n{failed_text}"
        if skill_text:
            prompt = f"{skill_text}\n\n{prompt}"

        active_provider = self._get_active_provider()
        active_model = self._get_active_model()

        # Try with current provider, failover on rate limit
        for attempt in range(len(self._failover_chain)):
            try:
                full_response = ""
                for chunk in stream_router(
                    provider=active_provider,
                    model_name=active_model,
                    image_path=None,
                    question=f"{prompt}\n\nMàn hình hiện tại:\n{screen_context}",
                ):
                    full_response += chunk

                # Check rate limit in response
                if self._is_rate_limited(full_response):
                    self._handle_rate_limit("brain")
                    active_provider = self._get_active_provider()
                    active_model = self._get_active_model()
                    continue

                return self._parse_brain_output(full_response)

            except Exception as e:
                error_str = str(e)
                if self._is_rate_limited(error_str):
                    self._handle_rate_limit("brain")
                    active_provider = self._get_active_provider()
                    active_model = self._get_active_model()
                    continue
                self._log("error", f"Lỗi Brain ({active_provider}): {e}")
                return AgentDecision()

        return AgentDecision()

    def _parse_brain_output(self, raw: str) -> AgentDecision:
        """Parse output từ Brain thành AgentDecision."""
        cleaned = re.sub(r"<thought>.*?</thought>", "", raw, flags=re.DOTALL).strip()
        cleaned = re.sub(r"```.*?```", "", cleaned, flags=re.DOTALL).strip()

        thought_match = re.search(r"<thought>(.*?)</thought>", raw, re.DOTALL)
        plan_match = re.search(
            r"\[PLAN\](.*?)(?:\[CHECK_STATE\]|\[ACTION\]|$)", cleaned, re.DOTALL | re.IGNORECASE
        )
        check_match = re.search(
            r"\[CHECK_STATE\](.*?)(?:\[ACTION\]|$)", cleaned, re.DOTALL | re.IGNORECASE
        )

        thought_str = thought_match.group(1).strip() if thought_match else ""
        plan_str = plan_match.group(1).strip() if plan_match else ""
        check_str = check_match.group(1).strip() if check_match else ""

        # Extract actions
        action_block = cleaned
        action_match = re.search(r"\[ACTION\](.*?)$", cleaned, re.DOTALL | re.IGNORECASE)
        if action_match:
            action_block = action_match.group(1)

        valid_cmds = (
            "CLICK", "DOUBLECLICK", "RIGHTCLICK", "TYPE", "PRESS",
            "HOTKEY", "SCROLL", "WAIT", "SCREENSHOT", "DONE",
        )

        actions = []
        for line in action_block.split("\n"):
            line = line.strip()
            if not line:
                continue
            for cmd in valid_cmds:
                if line.upper().startswith(cmd):
                    actions.append(line)
                    break

        return AgentDecision(
            thought=thought_str,
            plan=plan_str,
            check_state=check_str,
            actions=actions,
        )

    # ═══════════════════════════════════════════════════════════════
    # EYE — INIT
    # ═══════════════════════════════════════════════════════════════

    def _init_eye(self):
        """Khởi tạo Eye module — dùng provider phù hợp."""
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
                self._log("see", "⚠️ Ollama không có vision model → fallback Cloud")
                effective = "gemini" if GEMINI_API_KEY else self._get_active_provider()

        model = self.eye_model or get_default_model(effective)
        self._log("see", f"👁️ Eye: {effective}/{model}")
        return CloudEye(provider=effective, model_name=model)

    # ═══════════════════════════════════════════════════════════════
    # HAND — EXECUTE
    # ═══════════════════════════════════════════════════════════════

    def _execute(self, action: str, img_path: str, eye) -> ActionResult:
        """Thực thi action với retry logic."""
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

            # CLICK variants with retry
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
        """Click với retry logic — tìm lại element nếu fail."""
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
                # Recapture screen for retry
                new_screen = capture_screen_to_image()
                new_path = img_path
                new_screen.save(new_path, "PNG")

        return ActionResult(
            ok=False,
            msg=f"Không tìm thấy '{target}' ({max_retries+1} lần thử)",
            action=f"{click_type} {target}",
        )

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

    def _emit_subtask_update(self, subtask: SubTask):
        if self.event_bridge:
            self.event_bridge.emit("subtask_update",
                id=subtask.id, desc=subtask.description,
                status=subtask.status, steps=subtask.steps_taken)


# Backward compatibility
UnifiedAgent = AgentOrchestrator
AutonomousAgent = AgentOrchestrator
OllamaAgent = AgentOrchestrator
