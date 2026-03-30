"""
S-AI-Pro v6.0 — Semantic Vision Processor.
Multi-turn vision analysis, interface understanding, element detection.
Uses Moondream (local) or Cloud vision models.
Copyright © 2025-2026 Qtus Dev (Anh Tú)
"""
import re
import time
import hashlib
from typing import Optional, List, Dict, Tuple, Any
from dataclasses import dataclass, field

from core.analyzer import analyze_router
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
class UIElement:
    """Detected UI element on screen."""
    element_type: str = ""      # button, text_field, link, icon, menu, label
    text: str = ""
    bbox: List[int] = field(default_factory=list)  # [x1, y1, x2, y2]
    center: Tuple[float, float] = (0.0, 0.0)      # normalized (0-1)
    confidence: float = 0.0
    interactive: bool = False


@dataclass
class ScreenUnderstanding:
    """Full semantic understanding of current screen state."""
    page_type: str = "unknown"   # desktop, browser, dialog, login, search, results, editor, loading
    app_name: str = ""
    title: str = ""
    description: str = ""
    elements: List[UIElement] = field(default_factory=list)
    interactive_elements: List[UIElement] = field(default_factory=list)
    text_content: str = ""
    has_errors: bool = False
    error_message: str = ""
    is_loading: bool = False
    confidence: float = 0.0
    screen_hash: str = ""
    analysis_time_ms: int = 0


# ═══════════════════════════════════════════════════════════════
# PROMPTS
# ═══════════════════════════════════════════════════════════════

SCREEN_ANALYSIS_PROMPT = """Analyze this screen capture in detail:

1. PAGE TYPE: What type of page/app is shown? 
   (desktop, browser, dialog, login, search_form, results, editor, loading, error, settings)
2. APP NAME: What application/website is in focus?
3. TITLE: Window or page title
4. KEY ELEMENTS: List ALL visible interactive elements:
   - Buttons (with text)
   - Input fields (with labels)
   - Links (with text)
   - Icons (describe)
   - Menus/tabs
5. CURRENT STATE: 
   - Is the page fully loaded or still loading?
   - Any error messages visible?
   - What is the cursor/focus on?
6. TEXT: Important text visible on screen

Respond as a concise JSON:
{{
  "page_type": "...",
  "app_name": "...",
  "title": "...",
  "elements": [
    {{"type": "button", "text": "...", "interactive": true}},
    {{"type": "text_field", "text": "...", "label": "...", "interactive": true}}
  ],
  "is_loading": false,
  "has_errors": false,
  "error_message": "",
  "text_summary": "...",
  "confidence": 0.9
}}"""

ELEMENT_FIND_PROMPT = """Find the EXACT position of this UI element on screen:
Target: "{target}"

Return ONLY in this format:
COORDS x_ratio y_ratio

Where x_ratio and y_ratio are 0.0-1.0 (0.0=left/top, 1.0=right/bottom).
If not found: NOT_FOUND

Example: COORDS 0.52 0.34"""

SCREEN_COMPARE_PROMPT = """Compare these two screen states:

BEFORE: {before_desc}
AFTER: {after_desc}

Action performed: {action}

Answer:
1. Did the action succeed? (YES/NO)
2. What changed on screen?
3. Suggested next action?

Respond concisely."""


# ═══════════════════════════════════════════════════════════════
# VISION CACHE
# ═══════════════════════════════════════════════════════════════

class VisionCache:
    """Cache vision model responses to avoid redundant calls."""

    def __init__(self, ttl: int = 300, max_size: int = 50):
        self._cache: Dict[str, Dict] = {}
        self._ttl = ttl
        self._max_size = max_size

    def get(self, image_hash: str) -> Optional[Dict]:
        if image_hash in self._cache:
            entry = self._cache[image_hash]
            if time.time() - entry["timestamp"] < self._ttl:
                return entry["result"]
            else:
                del self._cache[image_hash]
        return None

    def set(self, image_hash: str, result: Dict) -> None:
        # Evict oldest if at capacity
        if len(self._cache) >= self._max_size:
            oldest_key = min(self._cache, key=lambda k: self._cache[k]["timestamp"])
            del self._cache[oldest_key]

        self._cache[image_hash] = {
            "result": result,
            "timestamp": time.time(),
        }

    def clear(self) -> None:
        self._cache.clear()

    @property
    def size(self) -> int:
        return len(self._cache)


# ═══════════════════════════════════════════════════════════════
# SCREENSHOT CACHE
# ═══════════════════════════════════════════════════════════════

class ScreenshotCache:
    """Keep recent screenshots with diff tracking."""

    def __init__(self, max_size: int = 10):
        self._screenshots = []
        self._max_size = max_size

    def add(self, image, screen_hash: str = "") -> int:
        """Add screenshot, return index."""
        if len(self._screenshots) >= self._max_size:
            self._screenshots.pop(0)

        self._screenshots.append({
            "image": image,
            "hash": screen_hash,
            "timestamp": time.time(),
        })
        return len(self._screenshots) - 1

    def get_latest(self):
        """Get latest screenshot."""
        return self._screenshots[-1]["image"] if self._screenshots else None

    def get_previous(self):
        """Get second-to-last screenshot."""
        if len(self._screenshots) >= 2:
            return self._screenshots[-2]["image"]
        return None

    def has_changed(self) -> bool:
        """Check if screen changed between last 2 captures."""
        if len(self._screenshots) < 2:
            return True
        return self._screenshots[-1]["hash"] != self._screenshots[-2]["hash"]

    @property
    def count(self) -> int:
        return len(self._screenshots)


# ═══════════════════════════════════════════════════════════════
# VISION PROCESSOR
# ═══════════════════════════════════════════════════════════════

class VisionProcessor:
    """
    Semantic vision understanding engine.
    Combines OCR + AI vision + caching for efficient screen analysis.
    """

    def __init__(
        self,
        provider: str = "gemini",
        model: str = "gemini-2.5-flash",
        cache_ttl: int = 300,
    ):
        self.provider = provider
        self.model = model
        self.vision_cache = VisionCache(ttl=cache_ttl)
        self.screenshot_cache = ScreenshotCache()

    def analyze_screen(self, image_path: str) -> ScreenUnderstanding:
        """
        Full semantic analysis of screen — cached.
        Returns structured ScreenUnderstanding.
        """
        start = time.time()
        result = ScreenUnderstanding()

        # Compute hash for caching
        try:
            from PIL import Image
            img = Image.open(image_path)
            screen_hash = compute_screen_hash(img)
            result.screen_hash = screen_hash
        except Exception:
            screen_hash = ""

        # Check cache
        if screen_hash:
            cached = self.vision_cache.get(screen_hash)
            if cached:
                cached["analysis_time_ms"] = 0  # Instant from cache
                return self._dict_to_understanding(cached)

        # Call vision model
        try:
            response = analyze_router(
                provider=self.provider,
                model_name=self.model,
                image_path=image_path,
                question=SCREEN_ANALYSIS_PROMPT,
            )

            parsed = self._parse_screen_response(response)
            result = self._dict_to_understanding(parsed)
            result.screen_hash = screen_hash
            result.analysis_time_ms = int((time.time() - start) * 1000)

            # Cache it
            if screen_hash:
                self.vision_cache.set(screen_hash, parsed)

        except Exception as e:
            result.description = f"Vision error: {e}"
            result.confidence = 0.0

        return result

    def describe_screen_simple(self, image_path: str) -> str:
        """Quick text description of screen (for Brain context)."""
        try:
            question = (
                "Mô tả ngắn gọn màn hình này (UI, buttons, text). "
                "Liệt kê các thành phần chính dưới dạng danh sách ngắn."
            )
            return analyze_router(
                provider=self.provider,
                model_name=self.model,
                image_path=image_path,
                question=question,
            )
        except Exception as e:
            return f"[Vision Error] {e}"

    def find_element(self, image_path: str, target: str) -> Optional[Tuple[float, float]]:
        """
        Find UI element coordinates using multi-strategy approach.
        Strategy: OCR → Vision AI → Coordinate prediction.
        Returns (x_ratio, y_ratio) in 0-1 range, or None.
        """
        # Strategy 1: OCR (fastest, most accurate for text)
        try:
            from agent.eye import ocr_find_element
            coords = ocr_find_element(image_path, target)
            if coords:
                return coords
        except Exception:
            pass

        # Strategy 2: Vision AI
        try:
            prompt = ELEMENT_FIND_PROMPT.format(target=target)
            response = analyze_router(
                provider=self.provider,
                model_name=self.model,
                image_path=image_path,
                question=prompt,
            )
            coords = self._parse_coords(response)
            if coords:
                return coords
        except Exception:
            pass

        return None

    def compare_screens(
        self,
        before_path: str,
        after_path: str,
        action: str = "",
    ) -> Dict[str, Any]:
        """Compare two screenshots for verification."""
        try:
            from PIL import Image
            img_before = Image.open(before_path)
            img_after = Image.open(after_path)

            diff = compute_screen_diff(img_before, img_after)
            result = {
                "changed": diff["changed"],
                "diff_ratio": diff["diff_ratio"],
                "description": diff["description"],
            }

            # If significant change, use vision to describe
            if diff["changed"] and diff["diff_ratio"] > 0.1:
                before_desc = self.describe_screen_simple(before_path)
                after_desc = self.describe_screen_simple(after_path)

                prompt = SCREEN_COMPARE_PROMPT.format(
                    before_desc=before_desc[:300],
                    after_desc=after_desc[:300],
                    action=action,
                )
                analysis = analyze_router(
                    provider=self.provider,
                    model_name=self.model,
                    question=prompt,
                )
                result["analysis"] = analysis
                result["action_succeeded"] = "YES" in analysis.upper()[:50]

            return result

        except Exception as e:
            return {"changed": False, "error": str(e)}

    def wait_for_change(
        self,
        baseline_hash: str,
        timeout: float = 30.0,
        interval: float = 1.0,
    ) -> bool:
        """Wait until screen changes from baseline. Returns True if changed."""
        start = time.time()
        while time.time() - start < timeout:
            try:
                img = capture_screen_to_image()
                current_hash = compute_screen_hash(img)
                if current_hash != baseline_hash:
                    return True
            except Exception:
                pass
            time.sleep(interval)
        return False

    def detect_page_state(self, image_path: str) -> str:
        """
        Quick classification of page state.
        Returns: loading | normal | dialog | error | login
        """
        try:
            prompt = (
                "Classify this screen state. Choose ONE:\n"
                "LOADING (spinner, progress, blank)\n"
                "NORMAL (ready to interact)\n"
                "DIALOG (popup, alert, modal open)\n"
                "ERROR (404, crash, error message)\n"
                "LOGIN (login form)\n\n"
                "Respond with ONE word only."
            )
            response = analyze_router(
                provider=self.provider,
                model_name=self.model,
                image_path=image_path,
                question=prompt,
            )
            state = response.strip().upper().split()[0] if response.strip() else "NORMAL"
            valid = {"LOADING", "NORMAL", "DIALOG", "ERROR", "LOGIN"}
            return state if state in valid else "NORMAL"
        except Exception:
            return "NORMAL"

    # ─── Parsing Helpers ────────────────────────────────────

    def _parse_screen_response(self, response: str) -> Dict:
        """Parse vision model response into dict."""
        import json as json_mod
        try:
            # Try to extract JSON
            json_match = re.search(r"\{[\s\S]*\}", response)
            if json_match:
                return json_mod.loads(json_match.group())
        except json_mod.JSONDecodeError:
            pass

        # Fallback: construct from text
        return {
            "page_type": "unknown",
            "app_name": "",
            "title": "",
            "elements": [],
            "is_loading": False,
            "has_errors": False,
            "error_message": "",
            "text_summary": response[:500],
            "confidence": 0.3,
        }

    @staticmethod
    def _parse_coords(text: str) -> Optional[Tuple[float, float]]:
        """Parse COORDS x y response."""
        match = re.search(r"COORDS\s+([\d.]+)\s+([\d.]+)", text)
        if match:
            try:
                x, y = float(match.group(1)), float(match.group(2))
                if 0 <= x <= 1 and 0 <= y <= 1:
                    return (x, y)
            except ValueError:
                pass
        return None

    @staticmethod
    def _dict_to_understanding(data: Dict) -> ScreenUnderstanding:
        """Convert dict to ScreenUnderstanding dataclass."""
        elements = []
        for e in data.get("elements", []):
            elements.append(UIElement(
                element_type=e.get("type", ""),
                text=e.get("text", ""),
                interactive=e.get("interactive", False),
                confidence=e.get("confidence", 0.5),
            ))

        interactive = [e for e in elements if e.interactive]

        return ScreenUnderstanding(
            page_type=data.get("page_type", "unknown"),
            app_name=data.get("app_name", ""),
            title=data.get("title", ""),
            description=data.get("text_summary", ""),
            elements=elements,
            interactive_elements=interactive,
            has_errors=data.get("has_errors", False),
            error_message=data.get("error_message", ""),
            is_loading=data.get("is_loading", False),
            confidence=float(data.get("confidence", 0.5)),
        )
