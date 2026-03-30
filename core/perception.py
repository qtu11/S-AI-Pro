"""
Perception Engine — Unified screen understanding.
Grid overlay, screen diff, smart crop, element detection.
Copyright © 2025-2026 Qtus Dev (Anh Tú)
"""
import io
import hashlib
from typing import Optional, Tuple, List, Dict
from PIL import Image, ImageDraw, ImageFont


def create_grid_overlay(
    image: Image.Image,
    grid_cols: int = 16,
    grid_rows: int = 9,
    label_size: int = 12,
) -> Image.Image:
    """
    Vẽ grid tọa độ lên screenshot.
    Mỗi ô ghi label (A1, B2...) để AI dễ chỉ vị trí.
    Returns: PIL Image đã annotated.
    """
    img = image.copy().convert("RGB")
    draw = ImageDraw.Draw(img)
    w, h = img.size

    cell_w = w / grid_cols
    cell_h = h / grid_rows

    # Font
    try:
        font = ImageFont.truetype("arial.ttf", label_size)
    except Exception:
        font = ImageFont.load_default()

    # Vẽ grid lines
    grid_color = (100, 100, 180, 80)  # Nhạt để không che content
    for col in range(1, grid_cols):
        x = int(col * cell_w)
        draw.line([(x, 0), (x, h)], fill=(60, 60, 100), width=1)

    for row in range(1, grid_rows):
        y = int(row * cell_h)
        draw.line([(0, y), (w, y)], fill=(60, 60, 100), width=1)

    # Vẽ labels ở góc trên-trái mỗi ô
    col_labels = "ABCDEFGHIJKLMNOP"[:grid_cols]
    for row in range(grid_rows):
        for col in range(grid_cols):
            label = f"{col_labels[col]}{row + 1}"
            x = int(col * cell_w) + 3
            y = int(row * cell_h) + 2

            # Background cho label
            bbox = draw.textbbox((x, y), label, font=font)
            draw.rectangle(
                [bbox[0] - 1, bbox[1] - 1, bbox[2] + 1, bbox[3] + 1],
                fill=(20, 20, 40, 180),
            )
            draw.text((x, y), label, fill=(150, 150, 220), font=font)

    return img


def grid_to_pixel(
    grid_label: str,
    image_width: int,
    image_height: int,
    grid_cols: int = 16,
    grid_rows: int = 9,
) -> Optional[Tuple[int, int]]:
    """
    Convert grid label (e.g. 'C3') → pixel coordinates (center of cell).
    """
    if len(grid_label) < 2:
        return None

    col_char = grid_label[0].upper()
    try:
        row_num = int(grid_label[1:])
    except ValueError:
        return None

    col_labels = "ABCDEFGHIJKLMNOP"
    col_idx = col_labels.find(col_char)
    if col_idx < 0 or col_idx >= grid_cols:
        return None
    if row_num < 1 or row_num > grid_rows:
        return None

    cell_w = image_width / grid_cols
    cell_h = image_height / grid_rows

    center_x = int((col_idx + 0.5) * cell_w)
    center_y = int((row_num - 1 + 0.5) * cell_h)

    return (center_x, center_y)


def compute_screen_hash(image: Image.Image, thumbnail_size: int = 16) -> str:
    """
    Hash nhanh screenshot để detect thay đổi.
    Resize xuống nhỏ → hash MD5.
    """
    thumb = image.copy().convert("L").resize((thumbnail_size, thumbnail_size))
    pixels = list(thumb.getdata())
    return hashlib.md5(bytes(pixels)).hexdigest()[:12]


def compute_screen_diff(img1: Image.Image, img2: Image.Image, threshold: float = 0.02) -> Dict:
    """
    So sánh 2 screenshots.
    Returns: { changed: bool, diff_ratio: float, description: str }
    """
    # Resize cả 2 về cùng size nhỏ
    size = (64, 36)
    a = img1.copy().convert("L").resize(size)
    b = img2.copy().convert("L").resize(size)

    pixels_a = list(a.getdata())
    pixels_b = list(b.getdata())

    total = len(pixels_a)
    diff_pixels = sum(1 for pa, pb in zip(pixels_a, pixels_b) if abs(pa - pb) > 20)
    diff_ratio = diff_pixels / total

    changed = diff_ratio > threshold

    if diff_ratio < 0.01:
        desc = "Không thay đổi"
    elif diff_ratio < 0.05:
        desc = "Thay đổi nhỏ"
    elif diff_ratio < 0.2:
        desc = "Thay đổi vừa"
    elif diff_ratio < 0.5:
        desc = "Thay đổi lớn"
    else:
        desc = "Màn hình khác hoàn toàn"

    return {
        "changed": changed,
        "diff_ratio": round(diff_ratio, 4),
        "description": desc,
    }


def smart_resize(image: Image.Image, max_size: int = 1920) -> Image.Image:
    """Resize ảnh thông minh cho gửi API (giữ ratio, max dimension)."""
    w, h = image.size
    if max(w, h) <= max_size:
        return image

    ratio = max_size / max(w, h)
    new_w = int(w * ratio)
    new_h = int(h * ratio)
    return image.resize((new_w, new_h), Image.LANCZOS)


def annotate_cursor(image: Image.Image, cursor_x: int, cursor_y: int) -> Image.Image:
    """Vẽ cursor position lên screenshot."""
    img = image.copy().convert("RGB")
    draw = ImageDraw.Draw(img)

    # Crosshair
    size = 15
    color = (255, 50, 50)
    draw.line([(cursor_x - size, cursor_y), (cursor_x + size, cursor_y)], fill=color, width=2)
    draw.line([(cursor_x, cursor_y - size), (cursor_x, cursor_y + size)], fill=color, width=2)

    # Circle
    draw.ellipse(
        [cursor_x - size, cursor_y - size, cursor_x + size, cursor_y + size],
        outline=color, width=2,
    )

    # Label
    try:
        font = ImageFont.truetype("arial.ttf", 11)
    except Exception:
        font = ImageFont.load_default()
    label = f"({cursor_x}, {cursor_y})"
    draw.text((cursor_x + size + 4, cursor_y - 6), label, fill=color, font=font)

    return img


def image_to_base64(image: Image.Image, format: str = "PNG", quality: int = 85) -> str:
    """Convert PIL Image → base64 string."""
    import base64
    buf = io.BytesIO()
    if format.upper() == "JPEG":
        image.convert("RGB").save(buf, format="JPEG", quality=quality, optimize=True)
    else:
        image.save(buf, format="PNG", optimize=True)
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def capture_screen_to_image() -> Image.Image:
    """Chụp màn hình trả về PIL Image (không lưu file)."""
    try:
        import pyautogui
        return pyautogui.screenshot()
    except Exception:
        import mss
        with mss.mss() as sct:
            monitor = sct.monitors[0]
            sct_img = sct.grab(monitor)
            return Image.frombytes("RGB", sct_img.size, sct_img.rgb)
