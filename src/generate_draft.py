from __future__ import annotations

from datetime import datetime, timezone
import random
import yaml

from src.gsheet import SheetManager
from src.randomization import build_seed, caption_fingerprint, is_caption_too_similar, pick_value
from src.settings import WEEKLY_PLAN_PATH, require_env
from src.sources import openai_text
from src.telegram_api import send_message


def _today_utc() -> tuple[str, str]:
    now = datetime.now(timezone.utc)
    return now.strftime("%Y-%m-%d"), now.strftime("%A")


def load_plan() -> dict:
    with WEEKLY_PLAN_PATH.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def build_caption_review_message(date_str: str, topic: str, full_caption: str) -> str:
    return (
        f"Caption for {date_str}\n"
        f"Topic: {topic}\n\n"
        f"{full_caption}\n\n"
        f"Approve caption: /approve_caption {date_str}\n"
        f"Modify caption: /caption {date_str} <your new text>"
    )


def main() -> None:
    openai_key = require_env("OPENAI_API_KEY")
    telegram_bot_token = require_env("TELEGRAM_BOT_TOKEN")
    telegram_chat_id = require_env("TELEGRAM_CHAT_ID")
    google_credentials = require_env("GOOGLE_CREDENTIALS")
    google_sheet_id = require_env("GOOGLE_SHEET_ID")
    sheet = SheetManager(google_credentials, google_sheet_id)

    today, weekday = _today_utc()
    weekday_key = weekday.lower()

    existing = sheet.get_row_by_date(today)
    if existing and existing.get("status") != "regenerate":
        print(f"Story for {today} already exists with status {existing.get('status')}. Skipping.")
        return

    generation_attempt = 1
    if existing and existing.get("status") == "regenerate":
        generation_attempt = int(existing.get("generation_attempt") or "1") + 1

    rng = random.Random(build_seed(today, generation_attempt))

    plan = load_plan().get(weekday_key)
    if not plan:
        raise RuntimeError(f"No plan configured for {weekday_key}")

    source_type = plan["source"]
    topic_text = pick_value(plan.get("topic"), "Story", rng)
    style_text = pick_value(plan.get("caption_tones"), pick_value(plan.get("prompt_style"), "friendly", rng), rng)
    cta_text = pick_value(plan.get("cta_variations"), pick_value(plan.get("cta"), "", rng), rng)
    caption_hook = pick_value(plan.get("caption_hooks"), "", rng)
    caption_variation = pick_value(
        plan.get("caption_variations"),
        "Use fresh wording and a slightly different angle from previous posts.",
        rng,
    )
    if caption_hook:
        caption_variation = f"{caption_variation} Preferred opening style: {caption_hook}."

    caption = openai_text.generate_caption(
        api_key=openai_key,
        topic=topic_text,
        style=style_text,
        cta=cta_text,
        variation_hint=caption_variation,
    )

    recent_rows = sheet.get_recent_rows(days=21, exclude_date=today)
    recent_captions = [row.get("caption", "") for row in recent_rows]
    if is_caption_too_similar(caption, recent_captions):
        caption = openai_text.generate_caption(
            api_key=openai_key,
            topic=topic_text,
            style=style_text,
            cta=cta_text,
            variation_hint=(
                f"{caption_variation} Use clearly different wording and opening compared with recent captions."
            ),
        )

    hashtags = " ".join(plan.get("hashtags", []))
    full_caption = caption if not hashtags else f"{caption}\n\n{hashtags}"

    telegram_message = send_message(
        bot_token=telegram_bot_token,
        chat_id=telegram_chat_id,
        text=build_caption_review_message(today, topic_text, full_caption),
    )

    row = {
        "date": today,
        "weekday": weekday,
        "topic": topic_text,
        "source_type": source_type,
        "status": "pending_caption_approval",
        "caption": full_caption,
        "telegram_message_id": "",
        "telegram_file_id": "",
        "caption_message_id": telegram_message.get("message_id", ""),
        "attribution": "",
        "notes": "",
        "generation_attempt": str(generation_attempt),
        "reference_image_name": "",
        "caption_fingerprint": caption_fingerprint(caption),
        "image_fingerprint": "",
    }
    sheet.upsert_story_row(row)
    print(f"Generated caption for {today}; waiting for Telegram caption approval.")


if __name__ == "__main__":
    main()
