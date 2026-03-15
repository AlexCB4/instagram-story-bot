from __future__ import annotations

import json
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


def send_media_group(
    bot_token: str,
    chat_id: str,
    photo_paths: list[str | Path],
    caption: str = "",
) -> list[dict[str, Any]]:
    if len(photo_paths) < 2:
        raise ValueError("Telegram media groups require at least two photos")

    media: list[dict[str, Any]] = []
    files: dict[str, Any] = {}
    handles = []

    try:
        for index, photo_path in enumerate(photo_paths):
            attachment_name = f"photo_{index}"
            path = Path(photo_path)
            handle = path.open("rb")
            handles.append(handle)
            files[attachment_name] = handle
            item = {"type": "photo", "media": f"attach://{attachment_name}"}
            if index == 0 and caption:
                item["caption"] = caption
            media.append(item)

        response = requests.post(
            f"{BASE_URL}/bot{bot_token}/sendMediaGroup",
            data={"chat_id": chat_id, "media": json.dumps(media, ensure_ascii=False)},
            files=files,
            timeout=90,
        )
    finally:
        for handle in handles:
            handle.close()

    response.raise_for_status()
    payload = response.json()
    if not payload.get("ok"):
        raise RuntimeError(f"Telegram sendMediaGroup failed: {payload}")
    return payload["result"]


def extract_photo_file_id(message: dict[str, Any]) -> str:
    photos = message.get("photo", [])
    if not photos:
        return ""
    return photos[-1].get("file_id", "")
