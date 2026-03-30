"""
Autonomous Agent — Hệ thống tự động hóa máy tính đa nền tảng.
Hỗ trợ: Local (Ollama) và Cloud (Gemini, OpenAI, Anthropic, Groq, DeepSeek).
Kiến trúc: Brain (LLM) → Eye (Vision) → Hand (PyAutoGUI).
Bản quyền © 2025-2026 Qtus Dev (Anh Tú)
"""
import time
import threading
import os
from typing import Optional, List, Dict, Callable

from core.screen import capture_screen
from agent.hand import AutoHand
from config.prompts import BRAIN_ACTION_PROMPT


class AutonomousAgent:
    """
    Agent AI tự trị hỗ trợ đa Provider.
    Brain = LLM (Ollama, Gemini, GPT, Claude, Groq, DeepSeek)
    Eye   = Vision (Ollama Vision, Gemini Vision, GPT Vision, Claude Vision)
    Hand  = PyAutoGUI
    """

    def __init__(
        self,
        brain_provider: str = "ollama",
        brain_model: str = "gemma3:4b",
        eye_provider: str = "ollama",
        eye_model: str = "",
        max_steps: int = 15,
        step_delay: float = 0.8,
        callback: Optional[Callable[[str, str], None]] = None,
        hide_ui_callback: Optional[Callable] = None,
        show_ui_callback: Optional[Callable] = None,
    ):
        self.brain_provider = brain_provider
        self.brain_model = brain_model
        self.eye_provider = eye_provider
        self.eye_model = eye_model
        
        self.max_steps = max_steps
        self.step_delay = step_delay
        self.callback = callback
        self.hide_ui = hide_ui_callback
        self.show_ui = show_ui_callback

        self.hand = AutoHand()
        self._history: List[Dict] = []
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def run(self, goal: str, blocking: bool = False) -> None:
        if self._running: return
        self._history = []
        self._running = True
        
        # Bắt đầu gọi Chuột ảo
        self.hand._cursor.move_to(-100, -100) # Đưa ra khỏi màn hình

        def _run():
            try: 
                if self.hide_ui: 
                    self.hide_ui()
                    time.sleep(0.5)
                self._loop(goal)
            finally: 
                self._running = False
                self.hand._cursor.hide()
                if self.show_ui: 
                    self.show_ui()

        if blocking: _run()
        else:
            self._thread = threading.Thread(target=_run, daemon=True)
            self._thread.start()

    def stop(self) -> None:
        self._running = False

    def _loop(self, goal: str) -> None:
        self._log("think", f"🚀 Agent khởi động — Brain: {self.brain_provider}/{self.brain_model}")
        self._log("think", f"🎯 Mục tiêu: {goal}")

        # Khởi tạo Eye
        eye = self._init_eye()
        fail_count = 0

        for step in range(1, self.max_steps + 1):
            if not self._running:
                self._log("done", "⛔ Đã dừng.")
                break

            self._log("see", f"\n{'─'*40}")
            self._log("see", f"📸 BƯỚC {step}/{self.max_steps}")

            # 1. EYE: Nhìn màn hình (Live Capture)
            # Ứng dụng đã được ẩn trước đó, nên camera giờ quét 100% sạch.
            img_path = capture_screen()
            
            self._log("see", "👁️ Đang quét màn hình hiện tại...")
            try:
                screen_desc = eye.describe_screen(img_path)
                preview = screen_desc[:250].replace("\n", " | ")
                self._log("see", f"Màn hình: {preview}...")
            except Exception as e:
                self._log("error", f"Lỗi Eye: {e}")
                screen_desc = "Không thể đọc màn hình."
            # Trích xuất Vị trí Chuột Hiện Tại (Mouse Tracking)
            import pyautogui
            mx, my = pyautogui.position()
            
            # Cải tiến thông điệp nạp vào Não: Nhét thêm Tọa độ Chuột + Tình trạng UI
            screen_context = (
                f"{screen_desc}\n"
                f"---\n"
                f"TỌA ĐỘ CHUỘT HIỆN TẠI CỦA BẠN: (X: {mx}, Y: {my})\n"
                f"(Hãy dùng CLICK [Nút] MÀ KHÔNG CẦN CHỈ ĐỊNH TỌA ĐỘ NẾU NÚT ĐANG NẰM NGAY DƯỚI CHUỘT!)"
            )

            # 2. BRAIN: Suy nghĩ (Trích xuất chuỗi Macro Combo & Plan)
            self._log("think", f"🧠 Đang suy nghĩ (Chuột đang ở: {mx}, {my})...")
            think_result = self._think(goal, screen_context)

            actions = think_result.get("actions", [])
            plan = think_result.get("plan", "")
            check = think_result.get("check", "")

            if plan:
                self._log("think", f"🧠 [LẬP KẾ HOẠCH]:\n{plan}")
            if check:
                self._log("see", f"🔎 [HIỆN TRẠNG MÀN HÌNH]:\n{check}")

            if not actions:
                fail_count += 1
                self._log("error", f"Brain không trả lời đúng format Action (lần {fail_count}/3)")
                if fail_count >= 3:
                    self._log("error", "❌ Brain thất bại quá nhiều. Dừng.")
                    break
                time.sleep(2)
                continue

            fail_count = 0 
            
            # Lưu lịch sử (Gộp thành 1 chuỗi)
            history_str = " | ".join(actions)
            self._log("think", f"▶ [LỆNH COMBO]: {history_str}")
            self._history.append({"step": step, "action": history_str})

            # 3. HAND: Thực thi liên hoàn Combo
            is_done = False
            for act in actions:
                if act.strip().upper() == "DONE":
                    self._log("done", "\n✅ Đã hoàn thành mục tiêu!")
                    is_done = True
                    break
                    
                self._log("act", f"✋ Thực thi: {act}")
                result = self._execute(act, img_path, eye)
                
                if result["ok"]:
                    self._log("act", f"✅ {result['msg']}")
                else:
                    self._log("error", f"❌ {result['msg']} (Lỗi: {result.get('error', 'N/A')})")
                    # Dừng combo nếu 1 lệnh quan trọng hụt (mắt nhìn mù)
                    if not act.upper().startswith("WAIT"): 
                        break

                time.sleep(max(0.2, self.step_delay))
                
            if is_done:
                break

        else:
            self._log("done", f"⏱️ Đã qua {self.max_steps} bước. Agent kết thúc.")

    def _init_eye(self):
        """Tự động khớp Mắt với Não để đạt hiệu suất cao nhất."""
        from agent.eye import OllamaEye, CloudEye
        
        # Nếu Eye là "auto" hoặc không đặt, dùng chính Brain Provider làm Eye
        effective_eye_provider = self.eye_provider if self.eye_provider and self.eye_provider != "auto" else self.brain_provider
        
        if effective_eye_provider == "ollama":
            eye = OllamaEye(self.eye_model)
            selected = eye.auto_select_model() if not self.eye_model else self.eye_model
            if selected:
                self._log("see", f"Sử dụng Eye Local (Ollama: {selected})")
                return eye
            else:
                self._log("see", "LỖI: Ollama không có vision model -> Fallback sang Gemini")
                return CloudEye(provider="gemini")
        else:
            self._log("see", f"Sử dụng Eye Cloud ({effective_eye_provider})")
            from config.models import get_default_model
            model = self.eye_model or get_default_model(effective_eye_provider)
            return CloudEye(provider=effective_eye_provider, model_name=model)

    def _think(self, goal: str, screen_context: str) -> Dict:
        from core.analyzer import stream_router
        import os
        
        hist_lines = [f"Step {h['step']}: {h['action']}" for h in self._history[-5:]]
        hist_text = "\n".join(hist_lines) if hist_lines else "None"

        # Đọc Tôn Chỉ Hành Động (ai_skill.md)
        skill_text = ""
        skill_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "ai_skill.md")
        try:
            if os.path.exists(skill_path):
                with open(skill_path, "r", encoding="utf-8") as f:
                    skill_text = f.read()
        except:
            pass

        prompt = BRAIN_ACTION_PROMPT.format(instruction=goal, history=hist_text)
        if skill_text:
            prompt = f"{skill_text}\n\n{prompt}"

        try:
            full_response = ""
            for chunk in stream_router(
                provider=self.brain_provider,
                model_name=self.brain_model,
                image_path=None, # Brain suy nghĩ dựa trên description từ Eye
                question=f"{prompt}\n\nMàn hình hiện tại và Tọa độ chuột:\n{screen_context}"
            ):
                full_response += chunk
                # Log từng chunk để boss thấy AI đang nghĩ gì (nếu cần)
                # self._log("think_stream", chunk) 
            
            return self._clean_action(full_response)
        except Exception as e:
            self._log("error", f"Lỗi Brain: {e}")
            return {"plan": "", "check": "", "actions": []}

    def _clean_action(self, raw: str) -> Dict:
        import re
        
        # 1. Loại bỏ dữ liệu trong thẻ <thought> (DeepSeek-R1)
        cleaned = re.sub(r"<thought>.*?</thought>", "", raw, flags=re.DOTALL).strip()
        
        # 2. Loại bỏ code block markdown nếu model sinh ra
        cleaned = re.sub(r"```.*?```", "", cleaned, flags=re.DOTALL).strip()

        # Trích xuất PLAN và CHECK_STATE
        plan_match = re.search(r"\[PLAN\](.*?)(?:\[CHECK_STATE\]|\[ACTION\]|$)", cleaned, flags=re.DOTALL | re.IGNORECASE)
        check_match = re.search(r"\[CHECK_STATE\](.*?)(?:\[ACTION\]|$)", cleaned, flags=re.DOTALL | re.IGNORECASE)
        
        plan_str = plan_match.group(1).strip() if plan_match else ""
        check_str = check_match.group(1).strip() if check_match else ""

        # Trích xuất đoạn Action
        action_block = cleaned
        action_match = re.search(r"\[ACTION\](.*?)$", cleaned, flags=re.DOTALL | re.IGNORECASE)
        if action_match:
            action_block = action_match.group(1)
        
        # 3. Quét mọi dòng xem có khớp Valid commands không
        valid = ("CLICK", "DOUBLECLICK", "RIGHTCLICK", "TYPE", "PRESS", "HOTKEY", "SCROLL", "WAIT", "SCREENSHOT", "DONE")
        
        actions = []
        lines = action_block.split("\n")
        for line in lines:
            line = line.strip()
            for cmd in valid:
                if line.upper().startswith(cmd):
                    actions.append(line)
                    break 
                    
        return {
            "plan": plan_str,
            "check": check_str,
            "actions": actions
        }

    def _execute(self, action: str, img_path: str, eye) -> Dict:
        import re
        action = action.strip()
        action_upper = action.upper()

        try:
            if action_upper == "DONE": return {"ok": True, "msg": "Hoàn thành nhiệm vụ"}
            if action_upper == "SCREENSHOT": return {"ok": True, "msg": "Đã chụp lại màn hình"}
            
            # WAIT
            m = re.match(r"WAIT\s+([\d.]+)", action, re.IGNORECASE)
            if m:
                s = float(m.group(1))
                time.sleep(s)
                return {"ok": True, "msg": f"Đã chờ {s} giây"}

            # HOTKEY/PRESS/TYPE
            m_hk = re.match(r"HOTKEY\s+(.+)", action, re.IGNORECASE)
            if m_hk:
                self.hand.hotkey(m_hk.group(1).strip())
                return {"ok": True, "msg": f"Hotkey: {m_hk.group(1)}"}

            m_pr = re.match(r"PRESS\s+(.+)", action, re.IGNORECASE)
            if m_pr:
                self.hand.press_key(m_pr.group(1).strip())
                return {"ok": True, "msg": f"Phím: {m_pr.group(1)}"}

            m_ty = re.match(r"TYPE\s+(.+)", action, re.IGNORECASE)
            if m_ty:
                self.hand.type_text(m_ty.group(1).strip())
                return {"ok": True, "msg": f"Đã gõ text"}

            # CLICK logic
            for prefix in ("CLICK", "DOUBLECLICK", "RIGHTCLICK"):
                m = re.match(rf"{prefix}\s+(.+)", action, re.IGNORECASE)
                if m:
                    target = m.group(1).strip()
                    coords = eye.find_element(img_path, target)
                    if coords:
                        sx, sy = int(coords[0] * self.hand.screen_w), int(coords[1] * self.hand.screen_h)
                        if prefix == "DOUBLECLICK": self.hand.double_click(sx, sy)
                        elif prefix == "RIGHTCLICK": self.hand.right_click(sx, sy)
                        else: self.hand.click(sx, sy)
                        return {"ok": True, "msg": f"{prefix} '{target}' tại ({sx},{sy})"}
                    return {"ok": False, "msg": f"Không tìm thấy '{target}'"}

            return {"ok": False, "msg": f"Hành động lạ: {action}"}
        except Exception as e:
            return {"ok": False, "msg": f"Lỗi thực thi", "error": str(e)}

    def _log(self, event: str, message: str) -> None:
        if self.callback: self.callback(event, message)
        else: print(f"[{event.upper()}] {message}")


# Backward Compatibility Alias
OllamaAgent = AutonomousAgent
