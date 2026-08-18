"""Stage 7b: thumbnail.

Reuses the first scene's AI image (already on-brand with the locked style
guide) rather than generating a dedicated thumbnail image, and overlays a
short title treatment with Pillow. Cheaper than a second AI image call per
video and keeps the thumbnail visually consistent with the video itself.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

THUMBNAIL_SIZE = (1280, 720)


def build_thumbnail(
    source_image_path: Path,
    title_text: str,
    out_path: Path,
    *,
    font_path: str | None = None,
) -> Path:
    img = Image.open(source_image_path).convert("RGB")
    img = _cover_resize(img, THUMBNAIL_SIZE)

    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    band_height = int(img.size[1] * 0.32)
    draw.rectangle(
        [(0, img.size[1] - band_height), img.size],
        fill=(0, 0, 0, 160),
    )

    font = _load_font(font_path, size=72)
    text = title_text.upper()
    margin = 48
    max_width = img.size[0] - 2 * margin
    lines = _wrap_to_width(draw, text, font, max_width)
    y = img.size[1] - band_height + 24
    for line in lines:
        draw.text((margin, y), line, font=font, fill=(255, 255, 255, 255))
        bbox = draw.textbbox((margin, y), line, font=font)
        y = bbox[3] + 8

    composed = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    composed.save(out_path, quality=92)
    return out_path


def _cover_resize(img: Image.Image, size: tuple[int, int]) -> Image.Image:
    target_w, target_h = size
    target_ratio = target_w / target_h
    w, h = img.size
    ratio = w / h
    if ratio > target_ratio:
        new_w = int(h * target_ratio)
        img = img.crop(((w - new_w) // 2, 0, (w - new_w) // 2 + new_w, h))
    else:
        new_h = int(w / target_ratio)
        img = img.crop((0, (h - new_h) // 2, w, (h - new_h) // 2 + new_h))
    return img.resize(size, Image.LANCZOS)


def _load_font(font_path: str | None, size: int) -> ImageFont.FreeTypeFont:
    candidates = [font_path] if font_path else []
    candidates += [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return ImageFont.truetype(candidate, size)
    return ImageFont.load_default(size=size)


def _wrap_to_width(draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        width = draw.textbbox((0, 0), candidate, font=font)[2]
        if width > max_width and current:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines[:3]
