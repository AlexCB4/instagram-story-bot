from __future__ import annotations

import random
import re
from typing import Iterable

from openai import OpenAI
from openai import APIConnectionError, APIError, APITimeoutError, RateLimitError


CAPTION_VARIATION_HINTS = [
    "Use a warm, intimate tone with fresh wording.",
    "Use a playful tone and avoid repeating common phrases.",
    "Use an elegant editorial tone with concise wording.",
    "Use an uplifting tone with a new angle for this topic.",
    "Use a simple, modern tone and avoid cliché expressions.",
]


def _trim_words(text: str, max_words: int) -> str:
    words = text.split()
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words]).strip()


def _pick_first_non_empty(values: Iterable[str]) -> str:
    for value in values:
        clean = str(value or "").strip()
        if clean:
            return clean
    return ""


def _fallback_caption(topic: str, style: str, cta: str) -> str:
    opener = _pick_first_non_empty([
        topic,
        "Inspiracion floral",
    ])
    tone = _pick_first_non_empty([
        style,
        "natural",
    ])
    call_to_action = _pick_first_non_empty([
        cta,
        "Escribenos para mas ideas",
    ])
    text = f"{opener}. Estilo {tone}. {call_to_action}"
    # Keep fallback captions short to match existing constraints.
    return _trim_words(_normalize_caption_whitespace(text), 20)


def _normalize_caption_whitespace(text: str) -> str:
    text = text.replace("\u00A0", " ")
    text = re.sub(r"[\u200B-\u200D\uFEFF]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    text = re.sub(r"([¿¡])\s+", r"\1", text)
    text = re.sub(r"([,.;:!?])(\S)", r"\1 \2", text)
    return text.rstrip()


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
- no trailing spaces at the end of the sentence
- avoid repeating generic opening lines and repeated wording
- return only the caption text, no hashtags
"""
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You write concise Instagram story copy."},
                {"role": "user", "content": prompt},
            ],
            max_tokens=120,
            temperature=0.8,
        )
        caption = _normalize_caption_whitespace((response.choices[0].message.content or "").strip())
        if caption:
            return caption
    except (RateLimitError, APITimeoutError, APIConnectionError, APIError) as exc:
        print(f"OpenAI caption generation unavailable ({type(exc).__name__}). Using local fallback caption.")

    return _fallback_caption(topic=topic, style=style, cta=cta)
