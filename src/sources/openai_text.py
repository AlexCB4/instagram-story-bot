from __future__ import annotations

import random
import re

from openai import OpenAI


CAPTION_VARIATION_HINTS = [
    "Use a warm, intimate tone with fresh wording.",
    "Use a playful tone and avoid repeating common phrases.",
    "Use an elegant editorial tone with concise wording.",
    "Use an uplifting tone with a new angle for this topic.",
    "Use a simple, modern tone and avoid cliché expressions.",
]


def _normalize_caption_whitespace(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    text = re.sub(r"([¿¡])\s+", r"\1", text)
    text = re.sub(r"([,.;:!?])(\S)", r"\1 \2", text)
    return text


def generate_caption(api_key: str, topic: str, style: str, cta: str, variation_hint: str | None = None) -> str:
    client = OpenAI(api_key=api_key)
    chosen_hint = variation_hint or random.choice(CAPTION_VARIATION_HINTS)
    prompt = f"""Create a short Instagram story caption in Spanish.

Topic: {topic}
Style: {style}
Call to action: {cta}
Variation hint: {chosen_hint}

Requirements:
- casual, natural Spanish
- maximum 20 words, strictly enforced
- 1 emoji maximum
- use single spaces only between words and after punctuation
- avoid repeating generic opening lines and repeated wording
- return only the caption text, no hashtags
"""
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You write concise Instagram story copy."},
            {"role": "user", "content": prompt},
        ],
        max_tokens=120,
        temperature=0.8,
    )
    return _normalize_caption_whitespace((response.choices[0].message.content or "").strip())
