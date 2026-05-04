from __future__ import annotations

import random
import shutil
from datetime import datetime
from pathlib import Path

import yaml

from src.gsheet import SheetManager
from src.randomization import build_seed, image_fingerprint, pick_owned_image, pick_value
from src.render import create_story
from src.settings import DEFAULT_FONT_PATH, OUTPUT_DIR, OWNED_ASSETS_DIR, WEEKLY_PLAN_PATH, require_env
from src.sources import nanobanana_image, openai_image, pexels
from src.telegram_api import extract_photo_file_id, send_media_group

BRAND_HANDLE = "@parterre_c"


def load_plan() -> dict:
    with WEEKLY_PLAN_PATH.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def caption_parts(caption: str) -> tuple[str, str]:
    normalized = [line.strip() for line in caption.splitlines() if line.strip()]
    if not normalized:
        return "Story", ""
    if len(normalized) == 1:
        return normalized[0], ""
    return normalized[0], " ".join(normalized[1:])


def build_image_review_caption(date_str: str, full_caption: str) -> str:
    return (
        f"Image for {date_str}\n\n"
        f"Caption: {full_caption}\n\n"
        f"Approve: /approve {date_str}\n"
        f"Regenerate: /regen {date_str}\n"
        f"Reject: /reject {date_str}"
    )


def _weekday_from_row(row: dict[str, str], row_date: str) -> str:
    weekday = (row.get("weekday") or "").strip()
    if weekday:
        return weekday
    return datetime.strptime(row_date, "%Y-%m-%d").strftime("%A")


def _resolve_source_type(row: dict[str, str], day_plan: dict) -> str:
    from_row = (row.get("source_type") or "").strip().lower()
    if from_row:
        return from_row
    return str(day_plan.get("source", "")).strip().lower()


def _build_image_prompt(day_plan: dict, rng: random.Random) -> tuple[str, str, str]:
    base_prompt = pick_value(day_plan.get("ai_prompt"), "", rng)
    if not base_prompt:
        raise RuntimeError("Missing ai_prompt for selected image source")
    variation = pick_value(
        day_plan.get("image_variations"),
        "Use a composition and framing different from recent posts.",
        rng,
    )
    mood = pick_value(day_plan.get("image_moods"), "", rng)
    composition = pick_value(day_plan.get("image_compositions"), "", rng)
    full_prompt = " ".join(part for part in [base_prompt, variation, mood, composition] if part).strip()
    return full_prompt, mood, composition


def _generate_background(
    row: dict[str, str],
    day_plan: dict,
    rng: random.Random,
    output_path: Path,
) -> tuple[str, str]:
    source_type = _resolve_source_type(row, day_plan)

    if source_type == "pexels":
        pexels_key = require_env("PEXELS_API_KEY")
        query = pick_value(day_plan.get("search_query"), "flowers", rng)
        result = pexels.search_image(pexels_key, query)
        pexels.download_image(result["url"], output_path)
        return result["attribution"], "pexels"

    if source_type == "openai":
        openai_key = require_env("OPENAI_API_KEY")
        ai_prompt, _, _ = _build_image_prompt(day_plan, rng)
        image_base64 = openai_image.generate_image(openai_key, ai_prompt)
        openai_image.save_base64_image(image_base64, output_path)
        return "Generated with OpenAI", f"openai|{ai_prompt}"

    if source_type == "owned":
        owned_image = pick_owned_image(OWNED_ASSETS_DIR, rng)
        shutil.copy2(owned_image, output_path)
        return "Own photo", f"owned|{owned_image.name}"

    if source_type == "nanobanana":
        nano_key = require_env("NANO_BANANA_API_KEY")
        ai_prompt, mood, composition = _build_image_prompt(day_plan, rng)
        reference_image = pick_owned_image(OWNED_ASSETS_DIR, rng)
        input_bytes = reference_image.read_bytes()
        image_bytes = nanobanana_image.generate_image(
            api_key=nano_key,
            prompt=ai_prompt,
            input_image=input_bytes,
            aspect_ratio="9:16",
            image_size="2K",
        )
        nanobanana_image.save_image_bytes(image_bytes, output_path)
        signature = f"nanobanana|{ai_prompt}|{mood}|{composition}|{reference_image.name}"
        return "Generated with Nano Banana", signature

    raise RuntimeError(f"Unsupported source type: {source_type}")


def main() -> None:
    telegram_bot_token = require_env("TELEGRAM_BOT_TOKEN")
    telegram_chat_id = require_env("TELEGRAM_CHAT_ID")
    google_credentials = require_env("GOOGLE_CREDENTIALS")
    google_sheet_id = require_env("GOOGLE_SHEET_ID")

    sheet = SheetManager(google_credentials, google_sheet_id)
    plan = load_plan()
    rows = sheet.get_rows_by_status("caption_approved")
    if not rows:
        print("No rows pending image generation.")
        return

    for row in rows:
        date_str = row.get("date", "").strip()
        if not date_str:
            continue

        weekday = _weekday_from_row(row, date_str)
        day_plan = plan.get(weekday.lower())
        if not day_plan:
            print(f"Skipping {date_str}: no plan configured for {weekday}.")
            continue

        generation_attempt = int(row.get("generation_attempt") or "1")
        rng = random.Random(build_seed(date_str, generation_attempt))
        caption = row.get("caption", "")

        recent_rows = sheet.get_recent_rows(days=21, exclude_date=date_str)
        recent_fingerprints = {r.get("image_fingerprint", "") for r in recent_rows if r.get("image_fingerprint")}

        background_path = OUTPUT_DIR / f"background_{date_str}.png"
        attribution, signature = _generate_background(row, day_plan, rng, background_path)
        image_hash = image_fingerprint(signature)

        if image_hash in recent_fingerprints:
            reroll_rng = random.Random(build_seed(date_str, generation_attempt + 1))
            attribution, signature = _generate_background(row, day_plan, reroll_rng, background_path)
            image_hash = image_fingerprint(signature)

        title_text, subtitle_text = caption_parts(caption)
        story_top_path = OUTPUT_DIR / f"story_{date_str}_top.png"
        story_bottom_path = OUTPUT_DIR / f"story_{date_str}_bottom.png"

        create_story(
            background_path=background_path,
            output_path=story_top_path,
            title_text=title_text,
            subtitle_text=subtitle_text,
            brand_text=BRAND_HANDLE,
            font_path=DEFAULT_FONT_PATH,
            text_position="top",
        )
        create_story(
            background_path=background_path,
            output_path=story_bottom_path,
            title_text=title_text,
            subtitle_text=subtitle_text,
            brand_text=BRAND_HANDLE,
            font_path=DEFAULT_FONT_PATH,
            text_position="bottom",
        )

        telegram_messages = send_media_group(
            bot_token=telegram_bot_token,
            chat_id=telegram_chat_id,
            photo_paths=[story_top_path, story_bottom_path],
            caption=(
                "Option 1: text at top\n"
                "Option 2: text at bottom\n\n"
                + build_image_review_caption(date_str, caption)
            ),
        )
        telegram_message = telegram_messages[-1]

        update_data: dict[str, str] = {
            "status": "pending_image_approval",
            "telegram_message_id": str(telegram_message.get("message_id", "")),
            "telegram_file_id": extract_photo_file_id(telegram_message),
            "attribution": attribution,
            "image_fingerprint": image_hash,
        }

        if signature.startswith("nanobanana|"):
            ref_name = signature.rsplit("|", 1)[-1]
            update_data["reference_image_name"] = ref_name

        sheet.update_story_fields(date_str, update_data)
        print(f"Generated image variants for {date_str}")


if __name__ == "__main__":
    main()
