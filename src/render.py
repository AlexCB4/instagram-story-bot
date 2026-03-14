from __future__ import annotations

import random
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


STORY_WIDTH = 1080
STORY_HEIGHT = 1920

# Instagram-style highlight colours (RGBA): soft pink, orange, blue, green
_HIGHLIGHT_COLORS = [
    (255, 182, 193, 210),
    (255, 164, 84,  210),
    (100, 176, 255, 210),
    (100, 220, 140, 210),
]

_PAD_X = 12      # horizontal padding inside highlight pill
_PAD_Y = 6       # vertical padding inside highlight pill
_LINE_GAP = 7    # gap between consecutive highlighted lines
_BLOCK_GAP = 52  # gap between title block and subtitle block
_RADIUS = 12     # corner radius of highlight pill


def _fit_background(image: Image.Image) -> Image.Image:
    image = image.convert("RGB")
    source_ratio = image.width / image.height
    target_ratio = STORY_WIDTH / STORY_HEIGHT
    if source_ratio > target_ratio:
        new_width = int(image.height * target_ratio)
        left = (image.width - new_width) // 2
        image = image.crop((left, 0, left + new_width, image.height))
    else:
        new_height = int(image.width / target_ratio)
        top = (image.height - new_height) // 2
        image = image.crop((0, top, image.width, top + new_height))
    return image.resize((STORY_WIDTH, STORY_HEIGHT), Image.Resampling.LANCZOS)


def _load_font(font_path: str | Path, size: int):
    try:
        return ImageFont.truetype(str(font_path), size)
    except OSError:
        return ImageFont.load_default()


def _layout_lines(
    draw: ImageDraw.ImageDraw,
    lines: list[str],
    font,
    start_y: int,
    highlight_color: tuple,
) -> tuple[list[tuple], list[tuple], int]:
    """Return (highlight_rects, text_items, end_y).

    highlight_rects: (x1, y1, x2, y2, rgba_color)
    text_items:      (x, y, text, font)
    """
    rects: list[tuple] = []
    texts: list[tuple] = []
    y = start_y
    for line in lines:
        if not line.strip():
            y += font.size // 2
            continue
        bbox = draw.textbbox((0, 0), line, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        rect_w = text_w + _PAD_X * 2
        rect_h = text_h + _PAD_Y * 2
        rx = (STORY_WIDTH - rect_w) // 2
        rects.append((rx, y, rx + rect_w, y + rect_h, highlight_color))
        texts.append((rx + _PAD_X - bbox[0], y + _PAD_Y - bbox[1], line, font))
        y += rect_h + _LINE_GAP
    end_y = y - _LINE_GAP if lines else start_y
    return rects, texts, end_y


def create_story(
    background_path: str | Path,
    output_path: str | Path,
    title_text: str,
    subtitle_text: str,
    brand_text: str,
    font_path: str | Path,
) -> Path:
    highlight_color = random.choice(_HIGHLIGHT_COLORS)

    background = _fit_background(Image.open(background_path))

    title_font = _load_font(font_path, 70)
    subtitle_font = _load_font(font_path, 50)
    brand_font = _load_font(font_path, 30)

    title_lines = textwrap.wrap(" ".join(title_text.split()), width=20)
    subtitle_lines = textwrap.wrap(" ".join(subtitle_text.split()), width=30) if subtitle_text.strip() else []

    # Measure using a scratch draw (1×1 px) so positioning is independent of compositing order
    scratch = ImageDraw.Draw(Image.new("RGBA", (1, 1)))

    all_rects: list[tuple] = []
    all_texts: list[tuple] = []

    # Top third: title (must stay above y=640)
    t_rects, t_texts, _ = _layout_lines(scratch, title_lines, title_font, 140, highlight_color)
    all_rects.extend(t_rects)
    all_texts.extend(t_texts)

    # Bottom third: subtitle starts at 67 % mark (y≈1280), keeping centre clear
    if subtitle_lines:
        subtitle_start_y = int(STORY_HEIGHT * 0.67)
        s_rects, s_texts, _ = _layout_lines(
            scratch, subtitle_lines, subtitle_font, subtitle_start_y, highlight_color
        )
        all_rects.extend(s_rects)
        all_texts.extend(s_texts)

    if brand_text.strip():
        b_rects, b_texts, _ = _layout_lines(
            scratch, [brand_text.strip()], brand_font, STORY_HEIGHT - 110, highlight_color
        )
        all_rects.extend(b_rects)
        all_texts.extend(b_texts)

    # Draw semi-transparent highlight pills onto a transparent overlay, then composite
    overlay = Image.new("RGBA", (STORY_WIDTH, STORY_HEIGHT), (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    for (x1, y1, x2, y2, color) in all_rects:
        overlay_draw.rounded_rectangle([(x1, y1), (x2, y2)], radius=_RADIUS, fill=color)

    image = Image.alpha_composite(background.convert("RGBA"), overlay).convert("RGB")
    draw = ImageDraw.Draw(image)
    for (tx, ty, text, font) in all_texts:
        draw.text((tx, ty), text, font=font, fill="white")

    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    image.save(destination, format="PNG", optimize=True)
    return destination
