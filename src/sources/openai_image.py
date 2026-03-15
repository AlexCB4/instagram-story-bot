from __future__ import annotations

from pathlib import Path
import random

import requests
from openai import OpenAI


PASTEL_STYLE_SUFFIX = (
    " Use an elegant, airy pastel palette."
    " Favor cream, blush, peach, sage, sky blue, and white tones."
    " Avoid dark, saturated, neon, or harsh contrast colors."
)

IMAGE_VARIATION_HINTS = [
    "Use a macro composition with delicate depth of field.",
    "Use a clean editorial composition with soft window light.",
    "Use a dreamy bokeh background with airy negative space.",
    "Use a minimalist composition with gentle textures.",
    "Use a natural candid composition with subtle motion.",
]


def generate_image(api_key: str, prompt: str, size: str = "1024x1536", variation_hint: str | None = None) -> str:
    client = OpenAI(api_key=api_key)
    chosen_hint = variation_hint or random.choice(IMAGE_VARIATION_HINTS)
    response = client.images.generate(
        model="gpt-image-1",
        prompt=f"{prompt.rstrip()} {chosen_hint}{PASTEL_STYLE_SUFFIX}",
        size=size,
    )
    image_base64 = response.data[0].b64_json
    if image_base64:
        return image_base64
    raise RuntimeError("OpenAI image generation did not return image data")


def save_base64_image(image_base64: str, output_path: str | Path) -> Path:
    import base64

    destination = Path(output_path)
    destination.write_bytes(base64.b64decode(image_base64))
    return destination


def download_image(url: str, output_path: str | Path) -> Path:
    destination = Path(output_path)
    response = requests.get(url, timeout=60)
    response.raise_for_status()
    destination.write_bytes(response.content)
    return destination
