from __future__ import annotations

import re

from openai import OpenAI


def _normalize_caption_whitespace(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    text = re.sub(r"([¿¡])\s+", r"\1", text)
    text = re.sub(r"([,.;:!?])(\S)", r"\1 \2", text)
    return text


def generate_caption(api_key: str, topic: str, style: str, cta: str) -> str:
    client = OpenAI(api_key=api_key)
    prompt = f"""Create a short Instagram story caption in Spanish.

Topic: {topic}
Style: {style}
Call to action: {cta}

Requirements:
- casual, natural Spanish
- maximum 20 words, strictly enforced
- 1 emoji maximum
- use single spaces only between words and after punctuation
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
