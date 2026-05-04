from __future__ import annotations

import base64
import io
from pathlib import Path

from PIL import Image
from google import genai
from google.genai import types


DEFAULT_MODEL = "gemini-3.1-flash-image-preview"


def _extract_image_bytes(response) -> bytes:
    parts = list(getattr(response, "parts", []) or [])
    if not parts and getattr(response, "candidates", None):
        for candidate in response.candidates:
            content = getattr(candidate, "content", None)
            if content and getattr(content, "parts", None):
                parts.extend(content.parts)

    for part in parts:
        inline_data = getattr(part, "inline_data", None)
        if inline_data is None:
            continue
        mime_type = str(getattr(inline_data, "mime_type", ""))
        data = getattr(inline_data, "data", None)
        if not mime_type.startswith("image/") or data is None:
            continue
        if isinstance(data, bytes):
            return data
        if isinstance(data, str):
            return base64.b64decode(data)

    for part in parts:
        as_image = getattr(part, "as_image", None)
        if not callable(as_image):
            continue
        image = as_image()
        if image is None:
            continue
        output = io.BytesIO()
        image.save(output, format="PNG")
        return output.getvalue()

    raise RuntimeError("Nano Banana response did not contain image data")


def generate_image(
    api_key: str,
    prompt: str,
    input_image: bytes | None = None,
    model: str = DEFAULT_MODEL,
    aspect_ratio: str = "9:16",
    image_size: str = "2K",
) -> bytes:
    client = genai.Client(api_key=api_key)
    contents: list[object] = [prompt]
    if input_image:
        contents.append(Image.open(io.BytesIO(input_image)))

    response = client.models.generate_content(
        model=model,
        contents=contents,
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE"],
            image_config=types.ImageConfig(
                aspect_ratio=aspect_ratio,
                image_size=image_size,
            ),
        ),
    )
    return _extract_image_bytes(response)


def save_image_bytes(image_bytes: bytes, output_path: str | Path) -> Path:
    destination = Path(output_path)
    destination.write_bytes(image_bytes)
    return destination
