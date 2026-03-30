"""
S-AI-Pro v6.0 — Advanced Reasoning Engine.
Chain-of-thought reasoning + Extended thinking + Task planning.
Model routing: DeepSeek-R1 (deep) | Gemma3 (fast) | Moondream (vision).
Copyright © 2025-2026 Qtus Dev (Anh Tú)
"""
import re
import time
import json
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field

from core.analyzer import analyze_router, stream_router
from config.models import get_default_model


# ═══════════════════════════════════════════════════════════════
# DATA STRUCTURES
# ═══════════════════════════════════════════════════════════════

@dataclass
class DeepThought:
    """Result of deep reasoning process."""
    goal_analysis: Dict[str, Any] = field(default_factory=dict)
    thinking: str = ""
    plan: List[Dict[str, Any]] = field(default_factory=list)
    risk_assessment: List[Dict[str, Any]] = field(default_factory=list)
    confidence: float = 0.0
    estimated_time: str = ""
    complexity: str = "medium"  # low | medium | high | extreme
    tokens_used: int = 0


@dataclass
class ActionPlan:
    """Structured action plan from reasoning."""
    thought: str = ""
    plan_text: str = ""
    check_state: str = ""
    actions: List[str] = field(default_factory=list)
    expected_change: str = ""
    confidence: float = 0.0
    goal_achieved: bool = False
    requires_user_input: bool = False
    user_input_prompt: str = ""
    error_detected: bool = False
    error_message: str = ""
    recovery_strategy: Optional[str] = None


# ═══════════════════════════════════════════════════════════════
# PROMPTS
# ═══════════════════════════════════════════════════════════════

DEEP_THINKING_PROMPT = """You are an advanced AI reasoning engine performing deep analysis.

GOAL: {goal}
CURRENT CONTEXT: {context}

Perform thorough analysis following this structure:

<thinking>
1. GOAL ANALYSIS:
   - Primary objective: What exactly needs to be achieved?
   - Constraints: What limitations exist?
   - Success criteria: How do we know when done?
   
2. DECOMPOSITION:
   - Break the goal into numbered phases
   - Each phase has clear actions
   - Estimate time per phase

3. RISK ASSESSMENT:
   - What could go wrong?
   - Probability (Low/Medium/High)
   - Mitigation strategy for each risk

4. CONFIDENCE ESTIMATE:
   - Overall confidence score (0.0-1.0)
   - Complexity level (low/medium/high/extreme)
</thinking>

Respond with a JSON object containing:
{{
  "goal_analysis": {{
    "primary_objective": "...",
    "constraints": ["..."],
    "success_criteria": "..."
  }},
  "phases": [
    {{
      "phase": 1,
      "name": "...",
      "actions": ["..."],
      "estimated_time": "..."
    }}
  ],
  "risks": [
    {{
      "risk": "...",
      "probability": "Low|Medium|High",
      "mitigation": "..."
    }}
  ],
  "confidence": 0.0,
  "complexity": "low|medium|high|extreme",
  "estimated_total_time": "..."
}}
"""

ACTION_PLANNING_PROMPT = """You are a professional autonomous computer agent (S-AI-Pro v6.0) on Windows.
Your mission: {goal}

Current step: {step}/{max_steps}

Past actions:
{history}

{failed_text}

{skill_text}

═══ CURRENT SCREEN STATE ═══
{screen_context}

═══ INSTRUCTIONS ═══
Follow the OODA loop STRICTLY:
1. OBSERVE the screen description carefully.
2. ORIENT: Understand context — what app is open, UI state.
3. DECIDE what to do next based on observations and goal.
4. ACT with precise commands.

═══ RESPONSE FORMAT (REQUIRED) ═══

[PLAN]
Numbered list of high-level steps. Mark completed ✅, current ➡️.

[CHECK_STATE]
- What is currently on screen?
- Did the last action succeed or fail?
- What step of the plan are we on?
- Any unexpected dialogs, popups, loading?

[ACTION]
Output ONE or MORE actions. One per line.
NO code blocks. NO explanations after actions.

═══ AVAILABLE ACTIONS ═══
CLICK [element_text_or_description]
DOUBLECLICK [element_text_or_description]
RIGHTCLICK [element_text_or_description]
TYPE [text_to_type]
PRESS [key_name]
HOTKEY [key1+key2]
SCROLL [UP or DOWN]
WAIT [seconds]
SCREENSHOT
DONE

═══ CRITICAL RULES ═══
1. Desktop icons → DOUBLECLICK, not CLICK!
2. Be PRECISE with element descriptions.
3. After clicking address bar: TYPE url, then PRESS enter.
4. If page loading → WAIT 2-3 before continuing.
5. If action failed → try DIFFERENT approach (hotkey, keyboard nav, etc.).
6. DONE only when goal FULLY achieved.
7. If stuck → PRESS escape, HOTKEY alt+tab, click elsewhere.
8. Output 2-5 actions per step for efficiency.
9. NEVER repeat a failed action!

═══ GOAL COMPLETION ═══
If the goal is fully achieved, output:
[ACTION]
DONE

Only output DONE when you are 100% sure the goal is completed.
"""

RECOVERY_PROMPT = """Agent is stuck. Suggest alternative approaches.

Goal: {goal}
Failed actions: {failed_actions}
Current screen: {screen_state}
Attempts made: {attempts}

Suggest 2-3 alternative strategies. Each should be different from what already failed.
Use the same action format: CLICK/TYPE/PRESS/HOTKEY/SCROLL/WAIT/DONE.

[ACTION]
(alternative actions here, one per line)
"""


# ═══════════════════════════════════════════════════════════════
# REASONING ENGINE
# ═══════════════════════════════════════════════════════════════

class ReasoningEngine:
    """
    Advanced reasoning with chain-of-thought, extended thinking,
    and multi-model routing.
    """

    def __init__(
        self,
        provider: str = "gemini",
        model: str = "",
        reasoning_model: str = "",
        speed_model: str = "",
    ):
        self.provider = provider
        self.model = model or get_default_model(provider)
        self.reasoning_model = reasoning_model  # For deep thinking (e.g. deepseek-r1)
        self.speed_model = speed_model  # For quick decisions (e.g. gemma3:4b)

    def think_deeply(self, goal: str, context: str = "") -> DeepThought:
        """
        Perform deep chain-of-thought analysis.
        Uses reasoning model (DeepSeek-R1) if available, else primary model.
        """
        result = DeepThought()
        start = time.time()

        prompt = DEEP_THINKING_PROMPT.format(goal=goal, context=context or "No additional context.")

        # Use reasoning model if available
        use_provider = self.provider
        use_model = self.model
        if self.reasoning_model:
            use_provider = "ollama"
            use_model = self.reasoning_model

        try:
            response = analyze_router(
                provider=use_provider,
                model_name=use_model,
                question=prompt,
            )

            # Extract thinking
            thinking_match = re.search(r"<thinking>(.*?)</thinking>", response, re.DOTALL)
            if thinking_match:
                result.thinking = thinking_match.group(1).strip()

            # Extract JSON
            json_match = re.search(r"\{[\s\S]*\}", response)
            if json_match:
                try:
                    data = json.loads(json_match.group())
                    result.goal_analysis = data.get("goal_analysis", {})
                    result.plan = data.get("phases", [])
                    result.risk_assessment = data.get("risks", [])
                    result.confidence = float(data.get("confidence", 0.5))
                    result.estimated_time = data.get("estimated_total_time", "unknown")
                    result.complexity = data.get("complexity", "medium")
                except json.JSONDecodeError:
                    result.confidence = 0.3

            result.tokens_used = len(response.split())

        except Exception as e:
            result.thinking = f"Reasoning error: {e}"
            result.confidence = 0.1

        return result

    def plan_actions(
        self,
        goal: str,
        screen_context: str,
        step: int,
        max_steps: int,
        history: str = "None",
        failed_text: str = "",
        skill_text: str = "",
    ) -> ActionPlan:
        """
        Analyze screen + context and produce an action plan.
        Primary method for OODA loop decide phase.
        """
        prompt = ACTION_PLANNING_PROMPT.format(
            goal=goal,
            step=step,
            max_steps=max_steps,
            history=history,
            failed_text=failed_text,
            skill_text=skill_text,
            screen_context=screen_context,
        )

        try:
            full_response = ""
            for chunk in stream_router(
                provider=self.provider,
                model_name=self.model,
                question=prompt,
            ):
                full_response += chunk

            # Check for rate limit
            if self._is_rate_limited(full_response):
                return ActionPlan(
                    error_detected=True,
                    error_message="Rate limit detected",
                )

            return self._parse_action_plan(full_response)

        except Exception as e:
            error_str = str(e)
            if self._is_rate_limited(error_str):
                return ActionPlan(error_detected=True, error_message="Rate limit")
            return ActionPlan(error_detected=True, error_message=str(e))

    def plan_recovery(
        self,
        goal: str,
        failed_actions: List[str],
        screen_state: str,
        attempts: int = 1,
    ) -> ActionPlan:
        """Generate recovery plan when primary approach fails."""
        prompt = RECOVERY_PROMPT.format(
            goal=goal,
            failed_actions="\n".join(failed_actions[-5:]),
            screen_state=screen_state[:500],
            attempts=attempts,
        )

        try:
            response = analyze_router(
                provider=self.provider,
                model_name=self.model,
                question=prompt,
            )
            return self._parse_action_plan(response)
        except Exception as e:
            return ActionPlan(error_detected=True, error_message=str(e))

    def quick_decide(self, question: str, context: str = "") -> str:
        """
        Quick decision using speed model (Gemma3:4b).
        For simple yes/no decisions, element selection, etc.
        """
        use_provider = self.provider
        use_model = self.model

        if self.speed_model:
            use_provider = "ollama"
            use_model = self.speed_model

        try:
            return analyze_router(
                provider=use_provider,
                model_name=use_model,
                question=f"{question}\n\nContext: {context}" if context else question,
            )
        except Exception:
            return ""

    # ─── Parsing ──────────────────────────────────────────────

    def _parse_action_plan(self, raw: str) -> ActionPlan:
        """Parse LLM response into structured ActionPlan."""
        result = ActionPlan()

        # Extract thought
        thinking_match = re.search(r"<thinking>(.*?)</thinking>", raw, re.DOTALL)
        if thinking_match:
            result.thought = thinking_match.group(1).strip()

        # Clean markdown
        cleaned = re.sub(r"<thinking>.*?</thinking>", "", raw, flags=re.DOTALL).strip()
        cleaned = re.sub(r"```.*?```", "", cleaned, flags=re.DOTALL).strip()

        # Extract plan
        plan_match = re.search(
            r"\[PLAN\](.*?)(?:\[CHECK_STATE\]|\[ACTION\]|$)", cleaned, re.DOTALL | re.IGNORECASE
        )
        if plan_match:
            result.plan_text = plan_match.group(1).strip()

        # Extract check_state
        check_match = re.search(
            r"\[CHECK_STATE\](.*?)(?:\[ACTION\]|$)", cleaned, re.DOTALL | re.IGNORECASE
        )
        if check_match:
            result.check_state = check_match.group(1).strip()

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
            # Check if DONE
            if line.upper().strip() == "DONE":
                result.goal_achieved = True
                actions.append("DONE")
                break
            for cmd in valid_cmds:
                if line.upper().startswith(cmd):
                    actions.append(line)
                    break

        result.actions = actions

        # Estimate confidence from plan clarity
        if actions:
            result.confidence = min(0.95, 0.5 + len(actions) * 0.1)
        if result.goal_achieved:
            result.confidence = 1.0

        return result

    @staticmethod
    def _is_rate_limited(text: str) -> bool:
        signals = [
            "429", "RESOURCE_EXHAUSTED", "rate limit", "quota",
            "Too Many Requests", "RateLimitError",
        ]
        text_upper = text.upper()
        return any(s.upper() in text_upper for s in signals)
