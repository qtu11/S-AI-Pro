"""
Eye Module — AI Vision (Mắt thần).
Cung cấp khả năng nhìn và hiểu màn hình cho Agent.
Hỗ trợ: Cloud (Gemini, GPT-4o, Claude...) và Local (Ollama, Moondream).
Bản quyền © 2025-2026 Qtus Dev (Anh Tú)
"""
import os
import re
import threading
from typing import Optional, Tuple
from PIL import Image

from core.analyzer import analyze_router
from config.prompts import VISION_SCREEN_PROMPT, VISION_OCR_PROMPT

# --- OCR System (Lazy Load) ---
_ocr_reader = None

def get_ocr_reader():
    global _ocr_reader
    if _ocr_reader is None:
        try:
            import easyocr
            # Hỗ trợ Tiếng Việt & Tiếng Anh. Sử dụng GPU nếu có, tự động fallback sang CPU.
            _ocr_reader = easyocr.Reader(['vi', 'en'], gpu=True)
            print("[OCR] Đã khởi tạo EasyOCR thành công.")
        except ImportError:
            print("[OCR] Chưa cài easyocr. Chạy: pip install easyocr")
            return None
    return _ocr_reader

def ocr_find_element(image_path: str, target_text: str) -> Optional[Tuple[float, float]]:
    """Dùng OCR tìm chuỗi text trên ảnh và trả về tỷ lệ (x_ratio, y_ratio)."""
    reader = get_ocr_reader()
    if not reader:
        return None
        
    try:
        results = reader.readtext(image_path)
        # Loại bỏ nháy đơn/kép thừa do AI (Ví dụ: "YouTube" -> YouTube)
        target_lower = target_text.lower().strip().strip("\"'")
        
        # Tìm gần đúng (phòng sai sót OCR)
        best_match = None
        for bbox, text, conf in results:
            text_lower = text.lower()
            if target_lower in text_lower or text_lower in target_lower:
                # Ưu tiên độ tin cậy nhỉnh hơn nếu có nhiều kết quả
                if not best_match or conf > best_match[2]:
                    best_match = (bbox, text, conf)
        
        if best_match:
            bbox, found_text, conf = best_match
            print(f"[OCR] Tìm thấy '{found_text}' tại độ tin cậy {conf:.2f}")
            
            # EasyOCR bbox: [top_left, top_right, bottom_right, bottom_left]
            top_left = bbox[0]
            bottom_right = bbox[2]
            
            center_x = (top_left[0] + bottom_right[0]) / 2.0
            center_y = (top_left[1] + bottom_right[1]) / 2.0
            
            with Image.open(image_path) as img:
                width, height = img.size
                
            return (center_x / width, center_y / height)
            
    except Exception as e:
        print(f"[OCR Error] {e}")
        
    return None



class CloudEye:
    """
    Mắt thần dùng Cloud API (Gemini, OpenAI, Anthropic...).
    Sử dụng analyze_router để tự động điều hướng tới provider phù hợp.
    """

    def __init__(self, provider: str = "gemini", model_name: str = "gemini-2.5-flash"):
        self.provider = provider
        self.model_name = model_name

    def find_element(self, image_path: str, description: str) -> Optional[Tuple[float, float]]:
        """Tìm tọa độ (x_ratio, y_ratio) 0-1 của một element."""
        # 1. OCR Tìm theo chữ (Chính xác tuyệt đối 99%)
        ocr_coords = ocr_find_element(image_path, description)
        if ocr_coords:
            return ocr_coords
            
        # 2. Học Máy / Mắt thần Cloud (Dự báo 40-70%)

        prompt = (
            f"Tìm vị trí CHÍNH XÁC của phần tử UI sau trên màn hình:\n"
            f"Target: \"{description}\"\n\n"
            f"Trả lời BẮT BUỘC theo format:\n"
            f"COORDS x_ratio y_ratio\n\n"
            f"x_ratio, y_ratio = số 0.0-1.0 (0.0=trái/trên, 1.0=phải/dưới).\n"
            f"Không tìm thấy → NOT_FOUND\n"
            f"Ví dụ: COORDS 0.52 0.34"
        )
        try:
            result = analyze_router(
                provider=self.provider,
                model_name=self.model_name,
                image_path=image_path,
                question=prompt
            )
            return self._parse_coords(result)
        except Exception as e:
            print(f"[CloudEye Find Error] {e}")
            return None

    def describe_screen(self, image_path: str = None, image_bytes: bytes = None) -> str:
        """Mô tả nội dung màn hình chi tiết, hỗ trợ cả đường dẫn và bytes."""
        try:
            if not image_path and not image_bytes:
                return "Không có ảnh đầu vào."
                
            question = "Mô tả ngắn gọn màn hình này (UI, buttons, text). Liệt kê các thành phần chính dưới dạng danh sách ngắn."
            
            # Cần thêm analyze_router_bytes nếu hỗ trợ bytes, tạm thời dùng file
            if image_path:
                return analyze_router(
                    provider=self.provider,
                    model_name=self.model_name,
                    image_path=image_path,
                    question=question
                )
            else:
                return "Phân tích bytes chưa được triển khai cho CloudEye."
        except Exception as e:
            return f"[CloudEye Describe Error] {e}"

    @staticmethod
    def _parse_coords(text: str) -> Optional[Tuple[float, float]]:
        match = re.search(r"COORDS\s+([\d.]+)\s+([\d.]+)", text)
        if match:
            try:
                x, y = float(match.group(1)), float(match.group(2))
                if 0 <= x <= 1 and 0 <= y <= 1:
                    return (x, y)
            except ValueError:
                pass
        return None


class OllamaEye:
    """
    Mắt thần dùng Ollama Vision model (llava, moondream, llama3.2-vision).
    100% offline, không cần internet.
    """

    def __init__(self, model_name: str = ""):
        self._model_name = model_name

    @property
    def model_name(self) -> str:
        return self._model_name

    @model_name.setter
    def model_name(self, value: str):
        self._model_name = value

    def auto_select_model(self) -> Optional[str]:
        """Tự động chọn vision model tốt nhất đã cài."""
        from core.ollama_manager import is_ollama_running, list_model_names, is_vision_model
        if not is_ollama_running():
            return None
        installed = list_model_names()
        priority = ["moondream", "llava", "bakllava", "llama3.2-vision", "minicpm-v"]
        for pref in priority:
            for name in installed:
                if name.startswith(pref) and is_vision_model(name):
                    self._model_name = name
                    return name
        return None

    def find_element(self, image_path: str, description: str) -> Optional[Tuple[float, float]]:
        # 1. OCR Tìm theo chữ (Nhanh & Chuẩn xác)
        ocr_coords = ocr_find_element(image_path, description)
        if ocr_coords:
            return ocr_coords

        # 2. Mắt thần Local dự đoán (Fallback)
        if not self._model_name:
            if not self.auto_select_model(): return None
        
        from core.ollama_manager import vision_find_element
        result = vision_find_element(self._model_name, image_path, description)
        if result:
            return (result["x"], result["y"])
        return None

    def describe_screen(self, image_path: str = None, image_b64: str = None) -> str:
        """Mô tả màn hình (hỗ trợ file path hoặc text base64 trực tiếp)."""
        if not self._model_name:
            if not self.auto_select_model(): return "Không có vision model Ollama."
        
        from core.ollama_manager import generate, image_to_base64
        
        b64_data = image_b64
        if not b64_data and image_path:
            b64_data = image_to_base64(image_path)
            
        if not b64_data:
            return "Lỗi ảnh."
            
        return generate(
            model_name=self._model_name,
            prompt="Mô tả ngắn gọn màn hình này: giao diện đang mở, các nút, text nổi bật. Gạch đầu dòng.",
            images=[b64_data]
        )


# Backward Compatibility Aliases
GeminiEye = CloudEye
