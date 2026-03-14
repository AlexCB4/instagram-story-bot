from __future__ import annotations

import json
from typing import Any

import gspread
from google.oauth2.service_account import Credentials

SHEETS_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

MAIN_HEADERS = [
    "date",
    "weekday",
    "topic",
    "source_type",
    "status",
    "caption",
    "telegram_message_id",
    "telegram_file_id",
    "attribution",
    "notes",
]

STATE_HEADERS = ["key", "value"]


class SheetManager:
    def __init__(self, credentials_json: str, sheet_id: str) -> None:
        creds_info = json.loads(credentials_json)
        credentials = Credentials.from_service_account_info(creds_info, scopes=SHEETS_SCOPES)
        self.client = gspread.authorize(credentials)
        self.spreadsheet = self.client.open_by_key(sheet_id)
        self.main_sheet = self.spreadsheet.sheet1
        self.state_sheet = self._get_or_create_worksheet("state", rows=50, cols=2)
        self._ensure_headers(self.main_sheet, MAIN_HEADERS)
        self._ensure_headers(self.state_sheet, STATE_HEADERS)

    def _get_or_create_worksheet(self, title: str, rows: int, cols: int):
        try:
            return self.spreadsheet.worksheet(title)
        except gspread.WorksheetNotFound:
            return self.spreadsheet.add_worksheet(title=title, rows=rows, cols=cols)

    def _ensure_headers(self, worksheet, headers: list[str]) -> None:
        existing = worksheet.row_values(1)
        if existing != headers:
            worksheet.update("A1", [headers])

    def get_row_by_date(self, date_str: str) -> dict[str, str] | None:
        records = self.main_sheet.get_all_records(expected_headers=MAIN_HEADERS)
        for index, record in enumerate(records, start=2):
            if str(record.get("date", "")).strip() == date_str:
                return {**{key: str(value) for key, value in record.items()}, "row_number": str(index)}
        return None

    def upsert_story_row(self, row_data: dict[str, Any]) -> None:
        existing = self.get_row_by_date(str(row_data["date"]))
        ordered_row = [str(row_data.get(header, "")) for header in MAIN_HEADERS]
        if existing is None:
            self.main_sheet.append_row(ordered_row, value_input_option="USER_ENTERED")
            return
        row_number = int(existing["row_number"])
        cell_range = f"A{row_number}:J{row_number}"
        self.main_sheet.update(cell_range, [ordered_row], value_input_option="USER_ENTERED")

    def update_story_status(self, date_str: str, status: str, notes: str = "") -> bool:
        existing = self.get_row_by_date(date_str)
        if existing is None:
            return False
        row_number = int(existing["row_number"])
        self.main_sheet.update(f"E{row_number}:J{row_number}", [[
            status,
            existing.get("caption", ""),
            existing.get("telegram_message_id", ""),
            existing.get("telegram_file_id", ""),
            existing.get("attribution", ""),
            notes or existing.get("notes", ""),
        ]], value_input_option="USER_ENTERED")
        return True

    def set_state(self, key: str, value: str) -> None:
        records = self.state_sheet.get_all_records(expected_headers=STATE_HEADERS)
        for index, record in enumerate(records, start=2):
            if str(record.get("key", "")).strip() == key:
                self.state_sheet.update(f"A{index}:B{index}", [[key, value]], value_input_option="USER_ENTERED")
                return
        self.state_sheet.append_row([key, value], value_input_option="USER_ENTERED")

    def get_state(self, key: str, default: str = "") -> str:
        records = self.state_sheet.get_all_records(expected_headers=STATE_HEADERS)
        for record in records:
            if str(record.get("key", "")).strip() == key:
                return str(record.get("value", default))
        return default
