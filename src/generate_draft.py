from __future__ import annotations

import random
from datetime import datetime, timezone
from pathlib import Path

import shutil
import yaml

from src.gsheet import SheetManager
from src.render import create_story
from src.settings import DEFAULT_FONT_PATH, OUTPUT_DIR, OWNED_ASSETS_DIR, WEEKLY_PLAN_PATH, require_env
from src.sources import openai_image, openai_text, pexels
from src.telegram_api import extract_photo_file_id, send_photo

BRAND_HANDLE = "@parterre_c"


def load_plan() -> dict:
    with WEEKLY_PLAN_PATH.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def get_today_keys() -> tuple[str, str]:
    now = datetime.now(timezone.utc)
    return now.strftime("%Y-%m-%d"), now.strftime("%A")


def pick_owned_image(folder_value: str | None) -> tuple[Path, str]:
    folder = Path(folder_value) if folder_value else OWNED_ASSETS_DIR
    if not folder.is_absolute():
        folder = OWNED_ASSETS_DIR.parent.parent / folder
    images = [item for item in folder.iterdir() if item.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}]
    if not images:
        raise RuntimeError(f"No owned images found in {folder}")
    return random.choice(images), "Own photo"


def caption_parts(caption: str) -> tuple[str, str]:
    normalized = [line.strip() for line in caption.splitlines() if line.strip()]
    if not normalized:
        return "Story", ""
    if len(normalized) == 1:
        return normalized[0], ""
    return normalized[0], " ".join(normalized[1:])


def build_telegram_caption(date_str: str, topic: str, full_caption: str) -> str:
    return (
        f"Draft for {date_str}\n"
        f"Topic: {topic}\n\n"
        f"{full_caption}\n\n"
        f"Approve: /approve {date_str}\n"
        f"Reject: /reject {date_str}\n"
        f"Regenerate: /regen {date_str}"
    )


def main() -> None:
    openai_key = require_env("OPENAI_API_KEY")
    telegram_bot_token = require_env("TELEGRAM_BOT_TOKEN")
    telegram_chat_id = require_env("TELEGRAM_CHAT_ID")
    google_credentials = require_env("GOOGLE_CREDENTIALS")
    google_sheet_id = require_env("GOOGLE_SHEET_ID")
    sheet = SheetManager(google_credentials, google_sheet_id)

    today, weekday = get_today_keys()
    weekday_key = weekday.lower()

    existing = sheet.get_row_by_date(today)
    if existing and existing.get("status") != "regenerate":
        print(f"Story for {today} already exists with status {existing.get('status')}. Skipping.")
        return

    plan = load_plan().get(weekday_key)
    if not plan:
        raise RuntimeError(f"No plan configured for {weekday_key}")

    source_type = plan["source"]
    background_path = OUTPUT_DIR / f"background_{today}.png"
    attribution = ""

    if source_type == "pexels":
        pexels_key = require_env("PEXELS_API_KEY")
        result = pexels.search_image(pexels_key, plan["search_query"])
        pexels.download_image(result["url"], background_path)
        attribution = result["attribution"]
    elif source_type == "openai":
        image_base64 = openai_image.generate_image(openai_key, plan["ai_prompt"])
        openai_image.save_base64_image(image_base64, background_path)
        attribution = "Generated with OpenAI"
    elif source_type == "owned":
        owned_image, attribution = pick_owned_image(plan.get("folder"))
        shutil.copy2(owned_image, background_path)
    else:
        raise RuntimeError(f"Unsupported source type: {source_type}")

    caption = openai_text.generate_caption(
        api_key=openai_key,
        topic=plan["topic"],
        style=plan.get("prompt_style", "friendly"),
        cta=plan.get("cta", ""),
    )
    hashtags = " ".join(plan.get("hashtags", []))
    full_caption = caption if not hashtags else f"{caption}\n\n{hashtags}"
    title_text, subtitle_text = caption_parts(caption)

    story_path = OUTPUT_DIR / f"story_{today}.png"
    create_story(
        background_path=background_path,
        output_path=story_path,
        title_text=title_text,
        subtitle_text=subtitle_text,
        cta_text=plan.get("cta", ""),
        brand_text=BRAND_HANDLE,
        font_path=DEFAULT_FONT_PATH,
    )

    telegram_message = send_photo(
        bot_token=telegram_bot_token,
        chat_id=telegram_chat_id,
        photo_path=story_path,
        caption=build_telegram_caption(today, plan["topic"], full_caption),
    )

    row = {
        "date": today,
        "weekday": weekday,
        "topic": plan["topic"],
        "source_type": source_type,
        "status": "pending_approval",
        "caption": full_caption,
        "telegram_message_id": telegram_message.get("message_id", ""),
        "telegram_file_id": extract_photo_file_id(telegram_message),
        "attribution": attribution,
        "notes": "",
    }
    sheet.upsert_story_row(row)
    print(f"Generated draft for {today}: {story_path}")


if __name__ == "__main__":
    main()
