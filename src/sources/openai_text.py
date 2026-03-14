from __future__ import annotations

from openai import OpenAI


def generate_caption(api_key: str, topic: str, style: str, cta: str, max_length: int = 180) -> str:
    client = OpenAI(api_key=api_key)
    prompt = f"""Create a short Instagram story caption in Spanish.

Topic: {topic}
Style: {style}
Call to action: {cta}
Max length: {max_length} characters

Requirements:
- casual, natural Spanish
- 1 or 2 emojis maximum
- concise enough for an Instagram story
- return only the caption text
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
    return (response.choices[0].message.content or "").strip()
