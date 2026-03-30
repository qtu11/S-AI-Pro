"""
Brain Module — LLM reasoning for action planning.
"""
import re
from typing import List, Optional

from config.prompts import BRAIN_ACTION_PROMPT
from core.analyzer import analyze_router


class ActionBrain:
    """LLM-based action planner cho automation."""

    def __init__(self, provider: str = "gemini", model_name: str = "gemini-2.5-pro"):
        self.provider = provider
        self.model_name = model_name
        self.history: List[str] = []
        self.max_history = 10

    def plan_next_action(self, image_path: str, instruction: str) -> str:
        """
        Phân tích screenshot + instruction → trả về 1 action duy nhất.
        Format: CLICK/TYPE/PRESS/SCROLL/DRAG/HOTKEY/WAIT/SCREENSHOT/DONE
        """
        hist_text = "None"
        if self.history:
            hist_text = "\n".join(self.history[-self.max_history:])

        prompt = BRAIN_ACTION_PROMPT.format(instruction=instruction, history=hist_text)

        try:
            ans = analyze_router(
                self.provider, self.model_name,
                image_path=image_path, file_path=None, question=prompt,
            )
            # Nhận diện error outputs từ LLM/provider
            if ans.startswith("[LỖI") or ans.startswith("[LỖI Ollama"):
                return f"ERROR: {ans}"
            return self._clean_action(ans)
        except Exception as e:
            return f"ERROR: {e}"

    def record_action(self, action: str, result: str) -> None:
        """Ghi nhận kết quả action vào history."""
        self.history.append(f"Thực hiện: {action} -> {result}")
        # Trim history nếu quá dài
        if len(self.history) > self.max_history * 2:
            self.history = self.history[-self.max_history:]

    def reset(self) -> None:
        """Xóa history."""
        self.history.clear()

    @staticmethod
    def _clean_action(raw: str) -> str:
        """Làm sạch output từ LLM, trích xuất action."""
        raw = raw.strip()
        # Loại bỏ markdown code blocks
        raw = raw.replace("```json", "").replace("```text", "").replace("```", "")
        raw = raw.replace("Action:", "").strip()

        # Lấy dòng action cuối cùng (bỏ qua Thought:)
        lines = [
            line.strip() for line in raw.split("\n")
            if line.strip() and not line.strip().startswith("Thought:")
        ]
        if lines:
            # Ưu tiên dòng bắt đầu bằng keyword action
            valid_prefixes = (
                "CLICK", "DOUBLECLICK", "RIGHTCLICK", "TYPE", "PRESS",
                "HOTKEY", "SCROLL", "DRAG", "WAIT", "SCREENSHOT", "DONE"
            )
            for line in reversed(lines):
                for prefix in valid_prefixes:
                    if line.upper().startswith(prefix):
                        return line
            return lines[-1]
        return raw

    @staticmethod
    def parse_action(action_text: str) -> dict:
        """
        Parse action text thành structured dict.
        Returns: {"type": "CLICK", "target": "...", "extra": "..."}
        """
        action_text = action_text.strip()

        # DRAG [source] TO [target]
        drag_match = re.match(r"DRAG\s+(.+?)\s+TO\s+(.+)", action_text, re.IGNORECASE)
        if drag_match:
            return {"type": "DRAG", "target": drag_match.group(1).strip(), "extra": drag_match.group(2).strip()}

        # HOTKEY [key1+key2]
        hotkey_match = re.match(r"HOTKEY\s+(.+)", action_text, re.IGNORECASE)
        if hotkey_match:
            return {"type": "HOTKEY", "target": hotkey_match.group(1).strip()}

        # Standard actions: CLICK/TYPE/PRESS/SCROLL/WAIT/SCREENSHOT/DONE
        for prefix in ("DOUBLECLICK", "RIGHTCLICK", "CLICK", "TYPE", "PRESS", "SCROLL", "WAIT", "SCREENSHOT", "DONE"):
            match = re.match(rf"{prefix}\s*(.*)", action_text, re.IGNORECASE)
            if match:
                return {"type": prefix.upper(), "target": match.group(1).strip()}

        return {"type": "UNKNOWN", "target": action_text}
