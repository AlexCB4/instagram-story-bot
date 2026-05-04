from __future__ import annotations

import hashlib
import random
import re
from pathlib import Path
from difflib import SequenceMatcher

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}


def build_seed(date_str: str, generation_attempt: int) -> int:
    seed_text = f"{date_str}:{generation_attempt}"
    return int(hashlib.sha256(seed_text.encode("utf-8")).hexdigest()[:16], 16)


def pick_value(value, default: str = "", rng: random.Random | None = None) -> str:
    picker = rng.choice if rng else random.choice
    if isinstance(value, list):
        options = [str(item).strip() for item in value if str(item).strip()]
        return picker(options) if options else default
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def normalize_caption(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def caption_fingerprint(text: str) -> str:
    normalized = normalize_caption(text)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


def image_fingerprint(signature: str) -> str:
    return hashlib.sha256(signature.strip().lower().encode("utf-8")).hexdigest()[:16]


def is_caption_too_similar(candidate: str, recent_captions: list[str], threshold: float = 0.9) -> bool:
    candidate_norm = normalize_caption(candidate)
    if not candidate_norm:
        return False
    for recent in recent_captions:
        recent_norm = normalize_caption(recent)
        if not recent_norm:
            continue
        if candidate_norm == recent_norm:
            return True
        if SequenceMatcher(None, candidate_norm, recent_norm).ratio() >= threshold:
            return True
    return False


def pick_owned_image(folder: Path, rng: random.Random) -> Path:
    images = [item for item in folder.iterdir() if item.suffix.lower() in IMAGE_SUFFIXES]
    if not images:
        raise RuntimeError(f"No owned images found in {folder}")
    return rng.choice(images)
