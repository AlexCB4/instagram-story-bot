from __future__ import annotations

import random
import textwrap
import math
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

_PAD_X = 8       # horizontal padding inside highlight pill
_PAD_Y = 6       # vertical padding inside highlight pill
_LINE_GAP = 7    # gap between consecutive highlighted lines
_BLOCK_GAP = 52  # gap between title block and subtitle block
_RADIUS = 12     # corner radius of highlight pill
_OUTER_MARGIN_X = 64  # minimum space between highlight pill and image edge


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
    uniform_rect_width: int | None = None,
) -> tuple[list[tuple], list[tuple], int]:
    """Return (highlight_rects, text_items, end_y).

    highlight_rects: (x1, y1, x2, y2, rgba_color)
    text_items:      (x, y, text, font)
    """
    rects: list[tuple] = []
    texts: list[tuple] = []
    y = start_y
    for line in lines:
        clean_line = " ".join(line.split())
        if not clean_line:
            y += font.size // 2
            continue

        # textlength gives tighter horizontal advance than textbbox for lines ending in punctuation.
        text_w = math.ceil(draw.textlength(clean_line, font=font))
        bbox = draw.textbbox((0, 0), clean_line, font=font)
        text_h = bbox[3] - bbox[1]
        rect_w = uniform_rect_width if uniform_rect_width is not None else text_w + _PAD_X * 2
        rect_h = text_h + _PAD_Y * 2
        rx = (STORY_WIDTH - rect_w) // 2
        rects.append((rx, y, rx + rect_w, y + rect_h, highlight_color))
        text_x = rx + (rect_w - text_w) // 2 - bbox[0]
        texts.append((text_x, y + _PAD_Y - bbox[1], clean_line, font))
        y += rect_h + _LINE_GAP
    end_y = y - _LINE_GAP if lines else start_y
    return rects, texts, end_y


def _compute_uniform_rect_width(draw: ImageDraw.ImageDraw, line_specs: list[tuple[str, any]]) -> int:
    max_text_w = 0
    for line, font in line_specs:
        clean_line = " ".join(line.split())
        if not clean_line:
            continue
        max_text_w = max(max_text_w, math.ceil(draw.textlength(clean_line, font=font)))
    target_w = max_text_w + _PAD_X * 2
    max_allowed = STORY_WIDTH - (_OUTER_MARGIN_X * 2)
    return min(target_w, max_allowed)


def _render_text_block(
    draw: ImageDraw.ImageDraw,
    title_lines: list[str],
    subtitle_lines: list[str],
    title_font,
    subtitle_font,
    start_y: int,
    highlight_color: tuple,
    uniform_rect_width: int,
) -> tuple[list[tuple], list[tuple]]:
    rects: list[tuple] = []
    texts: list[tuple] = []

    t_rects, t_texts, title_end_y = _layout_lines(
        draw, title_lines, title_font, start_y, highlight_color, uniform_rect_width
    )
    rects.extend(t_rects)
    texts.extend(t_texts)

    if subtitle_lines:
        s_rects, s_texts, _ = _layout_lines(
            draw, subtitle_lines, subtitle_font, title_end_y + _BLOCK_GAP, highlight_color, uniform_rect_width
        )
        rects.extend(s_rects)
        texts.extend(s_texts)

    return rects, texts


def create_story(
    background_path: str | Path,
    output_path: str | Path,
    title_text: str,
    subtitle_text: str,
    brand_text: str,
    font_path: str | Path,
    text_position: str = "top",
) -> Path:
    highlight_color = random.choice(_HIGHLIGHT_COLORS)

    background = _fit_background(Image.open(background_path))

    title_font = _load_font(font_path, 70)
    subtitle_font = _load_font(font_path, 50)
    brand_font = _load_font(font_path, 30)

    title_lines = textwrap.wrap(" ".join(title_text.split()), width=28)
    subtitle_lines = textwrap.wrap(" ".join(subtitle_text.split()), width=42) if subtitle_text.strip() else []

    # Measure using a scratch draw (1×1 px) so positioning is independent of compositing order
    scratch = ImageDraw.Draw(Image.new("RGBA", (1, 1)))

    all_rects: list[tuple] = []
    all_texts: list[tuple] = []

    line_specs: list[tuple[str, any]] = [(line, title_font) for line in title_lines]
    line_specs.extend((line, subtitle_font) for line in subtitle_lines)
    if brand_text.strip():
        line_specs.append((brand_text.strip(), brand_font))
    uniform_rect_width = _compute_uniform_rect_width(scratch, line_specs)

    if text_position not in {"top", "bottom"}:
        raise ValueError(f"Unsupported text_position: {text_position}")

    if text_position == "top":
        block_rects, block_texts = _render_text_block(
            scratch, title_lines, subtitle_lines, title_font, subtitle_font, 110, highlight_color, uniform_rect_width
        )
        brand_y = STORY_HEIGHT - 110
    else:
        block_rects, block_texts = _render_text_block(
            scratch,
            title_lines,
            subtitle_lines,
            title_font,
            subtitle_font,
            int(STORY_HEIGHT * 0.67),
            highlight_color,
            uniform_rect_width,
        )
        brand_y = 70

    all_rects.extend(block_rects)
    all_texts.extend(block_texts)

    if brand_text.strip():
        b_rects, b_texts, _ = _layout_lines(
            scratch,
            [brand_text.strip()],
            brand_font,
            brand_y,
            highlight_color,
            uniform_rect_width,
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
