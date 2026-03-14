from __future__ import annotations

from pathlib import Path

import requests
from openai import OpenAI


def generate_image(api_key: str, prompt: str, size: str = "1024x1536") -> str:
    client = OpenAI(api_key=api_key)
    response = client.images.generate(
        model="gpt-image-1",
        prompt=prompt,
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
