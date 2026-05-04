from __future__ import annotations

import os
import re

from src.gsheet import SheetManager
from src.settings import require_env
from src.state_store import StateStore
from src.telegram_api import get_updates, send_message

DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
ALLOWED_COMMANDS = {"approve", "reject", "regen", "approve_caption", "caption"}


def process_command(command: str, arg_text: str, sheet: SheetManager) -> str:
    arg_text = arg_text.strip()

    if command == "caption":
        parts = arg_text.split(maxsplit=1)
        if len(parts) != 2:
            return "Usage: /caption YYYY-MM-DD your new caption"
        date_str, new_caption = parts[0], parts[1].strip()
        if not DATE_PATTERN.match(date_str):
            return "Invalid date format. Use YYYY-MM-DD."
        if not new_caption:
            return "Caption cannot be empty."
        updated = sheet.update_story_fields(
            date_str,
            {
                "caption": new_caption,
                "status": "caption_approved",
            },
        )
        return f"Caption updated and approved for {date_str}." if updated else f"No row found for {date_str}."

    date_str = arg_text
    if not DATE_PATTERN.match(date_str):
        return "Invalid date format. Use YYYY-MM-DD."

    if command == "approve":
        updated = sheet.update_story_status(date_str, "approved")
        return f"Approved {date_str}." if updated else f"No row found for {date_str}."
    if command == "approve_caption":
        updated = sheet.update_story_status(date_str, "caption_approved")
        return f"Caption approved for {date_str}." if updated else f"No row found for {date_str}."
    if command == "reject":
        updated = sheet.update_story_status(date_str, "rejected")
        return f"Rejected {date_str}." if updated else f"No row found for {date_str}."
    if command == "regen":
        row = sheet.get_row_by_date(date_str)
        if row is None:
            return f"No row found for {date_str}."
        current_attempt = int(row.get("generation_attempt") or "1")
        updated = sheet.update_story_fields(
            date_str,
            {
                "status": "caption_approved",
                "generation_attempt": str(current_attempt + 1),
            },
        )
        return f"Image regeneration queued for {date_str}." if updated else f"No row found for {date_str}."
    return "Unsupported command."


def main() -> None:
    bot_token = require_env("TELEGRAM_BOT_TOKEN")
    chat_id = require_env("TELEGRAM_CHAT_ID")
    google_credentials = require_env("GOOGLE_CREDENTIALS")
    google_sheet_id = require_env("GOOGLE_SHEET_ID")

    sheet = SheetManager(google_credentials, google_sheet_id)
    state = StateStore(sheet)
    last_update_id = state.get_last_update_id()
    updates = get_updates(bot_token, offset=last_update_id + 1)

    max_update_id = last_update_id
    for update in updates:
        update_id = int(update.get("update_id", 0))
        max_update_id = max(max_update_id, update_id)
        message = update.get("message") or {}
        message_chat_id = str((message.get("chat") or {}).get("id", ""))
        if message_chat_id != str(chat_id):
            continue

        text = (message.get("text") or "").strip()
        if not text.startswith("/"):
            continue

        parts = text.split(maxsplit=1)
        command = parts[0][1:].split("@", 1)[0].lower()
        if command not in ALLOWED_COMMANDS or len(parts) != 2:
            continue

        response = process_command(command, parts[1].strip(), sheet)
        send_message(bot_token, chat_id, response)

    if max_update_id > last_update_id:
        state.set_last_update_id(max_update_id)
        print(f"Stored last processed update_id={max_update_id}")
    else:
        print("No new Telegram updates to process.")

    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a", encoding="utf-8") as handle:
            handle.write("regen_requested=false\n")


if __name__ == "__main__":
    main()
