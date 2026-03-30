"""
S-AI-Pro v6.0 — Self-Check & Verification Module.
Verify actions, detect failures, trigger recovery.
Copyright © 2025-2026 Qtus Dev (Anh Tú)
"""
import os
import time
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field

from core.perception import (
    capture_screen_to_image,
    compute_screen_hash,
    compute_screen_diff,
    image_to_base64,
)


@dataclass
class VerificationResult:
    """Result of verifying an action."""
    action_succeeded: bool = False
    screen_changed: bool = False
    diff_ratio: float = 0.0
    change_description: str = ""
    new_screen_hash: str = ""
    confidence: float = 0.0
    suggested_next: str = ""
    error_detected: bool = False
    error_message: str = ""
    verification_time_ms: int = 0


class SelfChecker:
    """
    Verification after each action:
    1. Compare screenshots before/after
    2. Detect if action had intended effect
    3. Identify error states
    4. Suggest recovery if needed
    """

    def __init__(self, vision_processor=None):
        self._vision = vision_processor
        self._consecutive_failures = 0
        self._max_retries = 3
        self._verification_history: List[VerificationResult] = []

    def verify_action(
        self,
        screen_before,
        action: str,
        delay: float = 0.5,
        screenshot_path: str = "",
    ) -> VerificationResult:
        """
        Verify if an action had the intended effect.
        
        1. Wait for UI to update
        2. Capture new screenshot
        3. Compare with before
        4. Analyze changes
        """
        start = time.time()
        result = VerificationResult()

        # Wait for UI update
        time.sleep(max(0.2, delay))

        # Capture current screen
        screen_after = capture_screen_to_image()

        # Compare
        if screen_before is not None:
            diff = compute_screen_diff(screen_before, screen_after)
            result.screen_changed = diff["changed"]
            result.diff_ratio = diff["diff_ratio"]
            result.change_description = diff["description"]
        else:
            result.screen_changed = True

        # Compute new hash
        result.new_screen_hash = compute_screen_hash(screen_after)

        # Determine success
        action_upper = action.strip().upper()
        is_passive = action_upper.startswith(("WAIT", "SCREENSHOT", "SCROLL"))

        if is_passive:
            # Passive actions always "succeed"
            result.action_succeeded = True
            result.confidence = 0.9
        elif result.screen_changed:
            # Screen changed = likely success
            result.action_succeeded = True
            result.confidence = min(0.95, 0.5 + result.diff_ratio * 2)
            self._consecutive_failures = 0
        else:
            # No change after active action = possible failure
            result.action_succeeded = False
            result.confidence = 0.2
            self._consecutive_failures += 1

            if self._consecutive_failures >= 3:
                result.error_detected = True
                result.error_message = f"Action failed {self._consecutive_failures} times consecutively"

        # Save screenshot if path provided
        if screenshot_path:
            try:
                screen_after.save(screenshot_path, "PNG")
            except Exception:
                pass

        result.verification_time_ms = int((time.time() - start) * 1000)
        self._verification_history.append(result)

        return result

    def is_stuck(self, threshold: int = 3) -> bool:
        """Check if agent is stuck (multiple consecutive failures)."""
        return self._consecutive_failures >= threshold

    def get_failure_streak(self) -> int:
        """Get number of consecutive failures."""
        return self._consecutive_failures

    def reset_failure_count(self) -> None:
        """Reset consecutive failure counter."""
        self._consecutive_failures = 0

    def detect_error_state(self, image_path: str) -> Dict[str, Any]:
        """
        Check if screen shows an error state.
        Uses vision processor if available, else basic heuristics.
        """
        if self._vision:
            try:
                state = self._vision.detect_page_state(image_path)
                return {
                    "is_error": state == "ERROR",
                    "is_loading": state == "LOADING",
                    "is_dialog": state == "DIALOG",
                    "state": state,
                }
            except Exception:
                pass

        return {
            "is_error": False,
            "is_loading": False,
            "is_dialog": False,
            "state": "UNKNOWN",
        }

    def suggest_recovery(self, failed_action: str, attempts: int = 1) -> List[str]:
        """
        Suggest recovery actions based on failure pattern.
        Returns list of alternative actions to try.
        """
        action_upper = failed_action.upper()
        suggestions = []

        if "CLICK" in action_upper:
            # Click failed — try alternatives
            suggestions.extend([
                "PRESS escape",       # Close any overlay
                "WAIT 2",             # Wait for element to appear
                "SCROLL DOWN",        # Scroll to find element
                "SCREENSHOT",         # Re-analyze screen
            ])
        elif "TYPE" in action_upper:
            suggestions.extend([
                "PRESS escape",
                "HOTKEY ctrl+a",      # Select all first
                "PRESS backspace",    # Clear field
            ])
        elif "PRESS" in action_upper:
            suggestions.extend([
                "WAIT 1",
                "CLICK center of screen",
            ])

        # Universal recovery
        if attempts >= 2:
            suggestions.extend([
                "HOTKEY alt+tab",     # Switch focus
                "PRESS escape",       # Close dialogs
                "HOTKEY ctrl+w",      # Close current tab
            ])

        if attempts >= 3:
            suggestions.extend([
                "HOTKEY win+d",       # Show desktop
                "WAIT 3",
            ])

        return suggestions[:3]

    def get_stats(self) -> Dict:
        """Get verification statistics."""
        total = len(self._verification_history)
        if not total:
            return {"total": 0, "success_rate": 0}

        succeeded = sum(1 for v in self._verification_history if v.action_succeeded)
        avg_diff = sum(v.diff_ratio for v in self._verification_history) / total

        return {
            "total_verifications": total,
            "succeeded": succeeded,
            "failed": total - succeeded,
            "success_rate": round(succeeded / total * 100, 1),
            "avg_diff_ratio": round(avg_diff, 4),
            "consecutive_failures": self._consecutive_failures,
        }
