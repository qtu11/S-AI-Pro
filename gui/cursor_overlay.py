import tkinter as tk
from threading import Thread
import time

class CursorOverlay:
    """Cửa sổ Chuột Ảo hiển thị trên cùng (Always on top)."""

    def __init__(self):
        self.root = None
        self.cursor = None
        self._thread = Thread(target=self._run, daemon=True)
        self._thread.start()
        
        # Đợi cửa sổ thực sự được tạo
        time.sleep(0.5)

    def _run(self):
        self.root = tk.Tk()
        self.root.overrideredirect(True) # Xóa thanh tiêu đề
        self.root.attributes("-topmost", True) # Luôn nổi
        
        # Windows: Làm cho cửa sổ trong suốt và không cản trở thao tác chuột
        self.root.attributes("-transparentcolor", "black")
        self.root.config(bg="black")
        self.root.attributes("-alpha", 0.8)

        # Tránh việc cửa sổ bị focus và ăn mất click của user / AI
        try:
            from ctypes import windll
            # WS_EX_TRANSPARENT | WS_EX_LAYERED
            windll.user32.SetWindowLongW(self.root.winfo_id(), -20, 0x00080000 | 0x00000020)
        except Exception:
            pass

        # Kích thước khung con trỏ
        size = 40
        self.root.geometry(f"{size}x{size}+-100+-100")

        # Vẽ tâm đỏ (chuột ảo)
        self.canvas = tk.Canvas(self.root, width=size, height=size, bg="black", highlightthickness=0)
        self.canvas.pack()
        
        # Tạo hiệu ứng Crosshair ngắm bắn
        c = size // 2
        r = 10
        self.cursor = self.canvas.create_oval(c-r, c-r, c+r, c+r, outline="red", width=3, fill="red", stipple="gray50")
        
        # Tạo hiệu ứng Radar
        self.radar = self.canvas.create_oval(c-r-5, c-r-5, c+r+5, c+r+5, outline="yellow", width=2, dash=(2, 2))

        self.root.mainloop()

    def move_to(self, x: int, y: int):
        """Di chuyển Chuột Ảo tới tọa độ pixel. Căn giữa chuẩn xác."""
        if self.root:
            try:
                # -20 để điểm giữa của canvas 40x40 khớp với mũi nhọn chuột
                self.root.geometry(f"+{x - 20}+{y - 20}") 
            except Exception:
                pass

    def hide(self):
        if self.root:
            try:
                self.root.geometry("+-100+-100")
            except Exception:
                pass

    def stop(self):
        if self.root:
            self.root.quit()
