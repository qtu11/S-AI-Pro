"""
Hand Module v2.0 — PyAutoGUI executor với human-like movements + Verify After Act.
Hỗ trợ: CLICK, DOUBLECLICK, RIGHTCLICK, TYPE, PRESS, HOTKEY, SCROLL, DRAG, WAIT.
+ Window management, smart typing, focus detection.
Copyright © 2025-2026 Qtus Dev (Anh Tú)
"""
import time
import random
from typing import Optional, Tuple, List

import pyautogui

# Safety
pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.08


class AutoHand:
    """PyAutoGUI executor v2 — human-like behavior + verify logic."""

    def __init__(self):
        self.screen_w, self.screen_h = pyautogui.size()
        self.logs: List[str] = []
        self._last_click_pos: Optional[Tuple[int, int]] = None
        self._action_count = 0

        # Cursor overlay (visual indicator)
        try:
            from gui.cursor_overlay import CursorOverlay
            self._cursor = CursorOverlay()
        except Exception:
            self._cursor = _DummyCursor()

    def _log(self, msg: str) -> None:
        self.logs.append(msg)

    def get_logs(self) -> List[str]:
        logs = self.logs.copy()
        self.logs.clear()
        return logs

    # ─── Human-like Mouse Movement (Bezier) ──────────────────────

    def _bezier_move(self, target_x: int, target_y: int, duration: float = 0.6) -> None:
        """Di chuột theo đường cong Bezier — speed tùy thuộc khoảng cách."""
        start_x, start_y = pyautogui.position()

        # Adaptive duration based on distance
        dist = ((target_x - start_x)**2 + (target_y - start_y)**2)**0.5
        if dist < 100:
            duration = min(duration, 0.3)
        elif dist > 800:
            duration = min(duration * 1.3, 1.5)

        # Randomized control point
        cx = (start_x + target_x) // 2 + random.randint(-60, 60)
        cy = (start_y + target_y) // 2 + random.randint(-40, 40)

        steps = max(12, int(duration * 50))
        for i in range(steps + 1):
            t = i / steps
            # Ease-in-out curve
            t_smooth = t * t * (3 - 2 * t)
            x = (1 - t_smooth) ** 2 * start_x + 2 * (1 - t_smooth) * t_smooth * cx + t_smooth ** 2 * target_x
            y = (1 - t_smooth) ** 2 * start_y + 2 * (1 - t_smooth) * t_smooth * cy + t_smooth ** 2 * target_y
            pyautogui.moveTo(int(x), int(y), _pause=False)
            self._cursor.move_to(int(x), int(y))
            time.sleep(duration / steps)

        time.sleep(0.15)

    def _to_screen_coords(self, ratio_x: float, ratio_y: float) -> Tuple[int, int]:
        return int(ratio_x * self.screen_w), int(ratio_y * self.screen_h)

    # ─── Actions ────────────────────────────────────────────────────

    def click(self, x: int, y: int, button: str = "left") -> None:
        """Click tại tọa độ pixel."""
        # Clamp to screen bounds
        x = max(0, min(x, self.screen_w - 1))
        y = max(0, min(y, self.screen_h - 1))
        self._bezier_move(x, y)
        pyautogui.click(x, y, button=button)
        self._last_click_pos = (x, y)
        self._action_count += 1
        self._log(f"[Hand] Click {button} tại ({x}, {y})")

    def click_ratio(self, rx: float, ry: float, button: str = "left") -> None:
        x, y = self._to_screen_coords(rx, ry)
        self.click(x, y, button)

    def double_click(self, x: int, y: int) -> None:
        x = max(0, min(x, self.screen_w - 1))
        y = max(0, min(y, self.screen_h - 1))
        self._bezier_move(x, y)
        pyautogui.doubleClick(x, y)
        self._last_click_pos = (x, y)
        self._action_count += 1
        self._log(f"[Hand] Double-click tại ({x}, {y})")

    def right_click(self, x: int, y: int) -> None:
        self.click(x, y, button="right")

    def type_text(self, text: str, interval: float = 0.03) -> None:
        """Gõ text — hỗ trợ Unicode/tiếng Việt qua Clipboard."""
        text = text.strip("\"'")
        if not text:
            return
        try:
            import pyperclip
            pyperclip.copy(text)
            time.sleep(0.05)
            self.hotkey("ctrl+v")
        except Exception:
            pyautogui.typewrite(text, interval=interval)
        time.sleep(0.3)
        self._action_count += 1
        self._log(f"[Hand] Đã gõ: '{text[:50]}{'...' if len(text) > 50 else ''}'")

    def press_key(self, key: str) -> None:
        """Ấn 1 phím."""
        key = key.strip().lower()
        try:
            pyautogui.press(key)
            self._log(f"[Hand] Ấn phím: '{key}'")
        except Exception as e:
            self._log(f"[Hand] Lỗi phím '{key}': {e}")
        self._action_count += 1
        time.sleep(0.3)

    def hotkey(self, keys_str: str) -> None:
        """Ấn tổ hợp phím (vd: 'ctrl+s', 'alt+tab')."""
        keys = [k.strip().lower() for k in keys_str.split("+")]
        try:
            pyautogui.hotkey(*keys)
            self._log(f"[Hand] Hotkey: {'+'.join(keys)}")
        except Exception as e:
            self._log(f"[Hand] Lỗi hotkey '{keys_str}': {e}")
        self._action_count += 1
        time.sleep(0.6)

    def scroll(self, direction: str, amount: int = 500) -> None:
        direction = direction.upper()
        clicks = amount if "UP" in direction else -amount
        pyautogui.scroll(clicks)
        self._log(f"[Hand] Cuộn {direction}")
        self._action_count += 1
        time.sleep(0.5)

    def drag(self, from_x: int, from_y: int, to_x: int, to_y: int, duration: float = 0.8) -> None:
        self._bezier_move(from_x, from_y, duration=0.3)
        pyautogui.mouseDown()
        time.sleep(0.1)
        self._bezier_move(to_x, to_y, duration=duration)
        pyautogui.mouseUp()
        self._action_count += 1
        self._log(f"[Hand] Drag ({from_x},{from_y}) → ({to_x},{to_y})")
        time.sleep(0.3)

    def wait(self, seconds: float = 1.0) -> None:
        seconds = min(max(seconds, 0.1), 30)
        self._log(f"[Hand] Chờ {seconds}s...")
        time.sleep(seconds)

    # ─── Window Management (v2.0) ────────────────────────────────

    def focus_window(self, title_contains: str) -> bool:
        """Tìm và focus vào window theo title."""
        try:
            windows = pyautogui.getWindowsWithTitle(title_contains)
            if windows:
                win = windows[0]
                if win.isMinimized:
                    win.restore()
                win.activate()
                time.sleep(0.5)
                self._log(f"[Hand] Focus window: '{win.title}'")
                return True
        except Exception as e:
            self._log(f"[Hand] Lỗi focus window: {e}")
        return False

    @property
    def action_count(self) -> int:
        return self._action_count


class _DummyCursor:
    """Fallback cursor khi không có GUI overlay."""
    def move_to(self, x, y): pass
    def hide(self): pass
    def show(self): pass
