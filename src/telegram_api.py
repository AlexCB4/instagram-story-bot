from __future__ import annotations

from pathlib import Path
from typing import Any

import requests

BASE_URL = "https://api.telegram.org"


def get_updates(bot_token: str, offset: int | None = None, timeout: int = 15) -> list[dict[str, Any]]:
    response = requests.get(
        f"{BASE_URL}/bot{bot_token}/getUpdates",
        params={"timeout": timeout, **({"offset": offset} if offset is not None else {})},
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    if not payload.get("ok"):
        raise RuntimeError(f"Telegram getUpdates failed: {payload}")
    return payload.get("result", [])


def send_message(bot_token: str, chat_id: str, text: str) -> dict[str, Any]:
    response = requests.post(
        f"{BASE_URL}/bot{bot_token}/sendMessage",
        data={"chat_id": chat_id, "text": text},
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    if not payload.get("ok"):
        raise RuntimeError(f"Telegram sendMessage failed: {payload}")
    return payload["result"]


def send_photo(bot_token: str, chat_id: str, photo_path: str | Path, caption: str = "") -> dict[str, Any]:
    photo_file = Path(photo_path)
    with photo_file.open("rb") as handle:
        response = requests.post(
            f"{BASE_URL}/bot{bot_token}/sendPhoto",
            data={"chat_id": chat_id, "caption": caption},
            files={"photo": handle},
            timeout=60,
        )
    response.raise_for_status()
    payload = response.json()
    if not payload.get("ok"):
        raise RuntimeError(f"Telegram sendPhoto failed: {payload}")
    return payload["result"]


def extract_photo_file_id(message: dict[str, Any]) -> str:
    photos = message.get("photo", [])
    if not photos:
        return ""
    return photos[-1].get("file_id", "")
