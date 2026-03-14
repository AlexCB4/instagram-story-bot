from __future__ import annotations

import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


STORY_WIDTH = 1080
STORY_HEIGHT = 1920


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


def create_story(
    background_path: str | Path,
    output_path: str | Path,
    title_text: str,
    subtitle_text: str,
    cta_text: str,
    brand_text: str,
    font_path: str | Path,
) -> Path:
    background = _fit_background(Image.open(background_path))
    overlay = Image.new("RGBA", (STORY_WIDTH, STORY_HEIGHT), (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)

    for y in range(560):
        alpha = int((y / 560) * 170)
        overlay_draw.rectangle([(0, y), (STORY_WIDTH, y + 1)], fill=(0, 0, 0, alpha))

    for y in range(560):
        y_pos = STORY_HEIGHT - 560 + y
        alpha = int(((560 - y) / 560) * 185)
        overlay_draw.rectangle([(0, y_pos), (STORY_WIDTH, y_pos + 1)], fill=(0, 0, 0, alpha))

    image = Image.alpha_composite(background.convert("RGBA"), overlay).convert("RGB")
    draw = ImageDraw.Draw(image)

    title_font = _load_font(font_path, 108)
    subtitle_font = _load_font(font_path, 72)
    cta_font = _load_font(font_path, 60)
    brand_font = _load_font(font_path, 42)

    wrapped_title = textwrap.fill(title_text.strip(), width=16)
    wrapped_subtitle = textwrap.fill(subtitle_text.strip(), width=24) if subtitle_text.strip() else ""

    title_box = draw.multiline_textbbox((0, 0), wrapped_title, font=title_font, spacing=10, align="center")
    title_x = (STORY_WIDTH - (title_box[2] - title_box[0])) // 2
    draw.multiline_text((title_x, 170), wrapped_title, font=title_font, fill="white", spacing=10, align="center")

    if wrapped_subtitle:
        subtitle_box = draw.multiline_textbbox((0, 0), wrapped_subtitle, font=subtitle_font, spacing=8, align="center")
        subtitle_x = (STORY_WIDTH - (subtitle_box[2] - subtitle_box[0])) // 2
        draw.multiline_text((subtitle_x, 450), wrapped_subtitle, font=subtitle_font, fill="white", spacing=8, align="center")

    if cta_text.strip():
        cta_box = draw.textbbox((0, 0), cta_text, font=cta_font)
        cta_x = (STORY_WIDTH - (cta_box[2] - cta_box[0])) // 2
        draw.text((cta_x, STORY_HEIGHT - 270), cta_text, font=cta_font, fill="white")

    if brand_text.strip():
        brand_box = draw.textbbox((0, 0), brand_text, font=brand_font)
        brand_x = (STORY_WIDTH - (brand_box[2] - brand_box[0])) // 2
        draw.text((brand_x, STORY_HEIGHT - 110), brand_text, font=brand_font, fill="#D9D9D9")

    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    image.save(destination, format="PNG", optimize=True)
    return destination
