from __future__ import annotations

from openai import OpenAI


def _normalize_caption_whitespace(text: str) -> str:
    return " ".join(text.split())


def generate_caption(api_key: str, topic: str, style: str, cta: str, max_length: int = 180) -> str:
    client = OpenAI(api_key=api_key)
    prompt = f"""Create a short Instagram story caption in Spanish.

Topic: {topic}
Style: {style}
Call to action: {cta}
Max length: 30 words total

Requirements:
- casual, natural Spanish
- maximum 30 words, strictly enforced
- 1 emoji maximum
- concise enough to display as large text on an Instagram story image
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
