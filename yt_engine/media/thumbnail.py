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
    """Text is meant to be short and punchy (2-5 words -- see
    ``thumbnail_text`` in publish/metadata.py), not the full video title, so
    it can be rendered large enough to actually read at feed-thumbnail size.
    """
    img = Image.open(source_image_path).convert("RGB")
    img = _cover_resize(img, THUMBNAIL_SIZE)

    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    band_height = int(img.size[1] * 0.34)
    draw.rectangle(
        [(0, img.size[1] - band_height), img.size],
        fill=(0, 0, 0, 150),
    )

    margin = 56
    max_width = img.size[0] - 2 * margin
    max_height = band_height - 40
    text = title_text.upper()
    font, lines = _fit_text(draw, text, font_path, max_width, max_height)

    line_heights = [draw.textbbox((0, 0), line, font=font)[3] for line in lines]
    total_height = sum(line_heights) + 12 * (len(lines) - 1)
    y = img.size[1] - band_height + (max_height - total_height) // 2 + 20

    for line, line_height in zip(lines, line_heights):
        line_width = draw.textbbox((0, 0), line, font=font)[2]
        x = (img.size[0] - line_width) // 2
        draw.text(
            (x, y), line, font=font, fill=(255, 255, 255, 255),
            stroke_width=max(3, font.size // 20), stroke_fill=(0, 0, 0, 255),
        )
        y += line_height + 12

    composed = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    composed.save(out_path, quality=92)
    return out_path


def _fit_text(
    draw: ImageDraw.ImageDraw, text: str, font_path: str | None, max_width: int, max_height: int
) -> tuple[ImageFont.FreeTypeFont, list[str]]:
    """Picks the largest font size (within a sane range) whose wrapped
    lines still fit the available band -- short thumbnail text should
    dominate the frame, not sit at a fixed small size."""
    for size in range(140, 47, -8):
        font = _load_font(font_path, size=size)
        lines = _wrap_to_width(draw, text, font, max_width)
        total_height = sum(draw.textbbox((0, 0), line, font=font)[3] for line in lines) + 12 * (len(lines) - 1)
        if len(lines) <= 2 and total_height <= max_height:
            return font, lines
    font = _load_font(font_path, size=48)
    return font, _wrap_to_width(draw, text, font, max_width)


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
