"""
Screen capture & image enhancement module.
"""
import os
import io
from PIL import Image

from config import SCREENSHOT_PATH, ENHANCED_PATH


def capture_screen(path: str = SCREENSHOT_PATH) -> str:
    """Chụp toàn màn hình. Ưu tiên pyautogui, fallback mss."""
    try:
        import pyautogui
        image = pyautogui.screenshot()
        image.save(path)
        return path
    except Exception:
        try:
            import mss
            with mss.mss() as sct:
                monitor = sct.monitors[0]
                sct_img = sct.grab(monitor)
                img = Image.frombytes("RGB", sct_img.size, sct_img.rgb)
                img.save(path)
                return path
        except Exception:
            raise RuntimeError("Không thể chụp màn hình: cả pyautogui và mss đều thất bại.")


def enhance_image(src_path: str, dst_path: str = ENHANCED_PATH) -> str:
    """Nâng chất lượng ảnh cho OCR: upsample + unsharp mask + PNG lossless."""
    with Image.open(src_path) as im:
        im = im.convert("RGB")
        w, h = im.size
        scale = 1.5 if max(w, h) < 1800 else 1.0
        if scale > 1.0:
            im = im.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
        try:
            from PIL import ImageFilter
            im = im.filter(ImageFilter.UnsharpMask(radius=1.5, percent=140, threshold=2))
        except Exception:
            pass
        im.save(dst_path, format="PNG", optimize=False, compress_level=1)
        return dst_path


def image_to_png_bytes(image_path: str) -> bytes:
    """Chuyển ảnh sang PNG bytes để gửi API."""
    with Image.open(image_path) as im:
        with io.BytesIO() as buf:
            im.convert("RGBA").save(buf, format="PNG")
            return buf.getvalue()
