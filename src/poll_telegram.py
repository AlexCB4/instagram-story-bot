from __future__ import annotations

import os

from src.gsheet import SheetManager
from src.settings import require_env
from src.state_store import StateStore
from src.telegram_api import get_updates, send_message

ALLOWED_COMMANDS = {"approve", "reject", "regen"}


def process_command(command: str, date_str: str, sheet: SheetManager) -> str:
    if command == "approve":
        updated = sheet.update_story_status(date_str, "approved")
        return f"Approved {date_str}." if updated else f"No row found for {date_str}."
    if command == "reject":
        updated = sheet.update_story_status(date_str, "rejected")
        return f"Rejected {date_str}." if updated else f"No row found for {date_str}."
    if command == "regen":
        updated = sheet.update_story_status(date_str, "regenerate")
        return f"Marked {date_str} for regeneration." if updated else f"No row found for {date_str}."
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
    regen_requested = False
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
        if command == "regen" and response.startswith("Marked"):
            regen_requested = True
        send_message(bot_token, chat_id, response)

    if max_update_id > last_update_id:
        state.set_last_update_id(max_update_id)
        print(f"Stored last processed update_id={max_update_id}")
    else:
        print("No new Telegram updates to process.")

    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a", encoding="utf-8") as handle:
            handle.write(f"regen_requested={'true' if regen_requested else 'false'}\n")


if __name__ == "__main__":
    main()
