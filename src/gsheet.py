from __future__ import annotations

import json
from datetime import datetime, timedelta
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
    "caption_message_id",
    "attribution",
    "notes",
    "generation_attempt",
    "reference_image_name",
    "caption_fingerprint",
    "image_fingerprint",
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

    @staticmethod
    def _column_letter(column_number: int) -> str:
        result = ""
        n = column_number
        while n > 0:
            n, remainder = divmod(n - 1, 26)
            result = chr(65 + remainder) + result
        return result

    @staticmethod
    def _date_from_row(value: str) -> datetime | None:
        try:
            return datetime.strptime(value, "%Y-%m-%d")
        except ValueError:
            return None

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
        last_col = self._column_letter(len(MAIN_HEADERS))
        cell_range = f"A{row_number}:{last_col}{row_number}"
        self.main_sheet.update(cell_range, [ordered_row], value_input_option="USER_ENTERED")

    def update_story_status(self, date_str: str, status: str, notes: str = "") -> bool:
        updates: dict[str, Any] = {"status": status}
        if notes:
            updates["notes"] = notes
        return self.update_story_fields(date_str, updates)

    def update_story_fields(self, date_str: str, updates: dict[str, Any]) -> bool:
        existing = self.get_row_by_date(date_str)
        if existing is None:
            return False
        row_number = int(existing["row_number"])

        merged = {header: existing.get(header, "") for header in MAIN_HEADERS}
        for key, value in updates.items():
            if key in merged:
                merged[key] = "" if value is None else str(value)

        ordered_row = [merged.get(header, "") for header in MAIN_HEADERS]
        last_col = self._column_letter(len(MAIN_HEADERS))
        self.main_sheet.update(
            f"A{row_number}:{last_col}{row_number}",
            [ordered_row],
            value_input_option="USER_ENTERED",
        )
        return True

    def get_rows_by_status(self, status: str) -> list[dict[str, str]]:
        records = self.main_sheet.get_all_records(expected_headers=MAIN_HEADERS)
        results: list[dict[str, str]] = []
        for index, record in enumerate(records, start=2):
            row = {key: str(value) for key, value in record.items()}
            if row.get("status", "").strip() == status:
                row["row_number"] = str(index)
                results.append(row)
        return results

    def get_recent_rows(self, days: int, exclude_date: str | None = None) -> list[dict[str, str]]:
        cutoff = datetime.utcnow() - timedelta(days=days)
        records = self.main_sheet.get_all_records(expected_headers=MAIN_HEADERS)
        recent: list[dict[str, str]] = []
        for index, record in enumerate(records, start=2):
            row = {key: str(value) for key, value in record.items()}
            row_date = self._date_from_row(row.get("date", ""))
            if row_date is None or row_date < cutoff:
                continue
            if exclude_date and row.get("date", "").strip() == exclude_date:
                continue
            row["row_number"] = str(index)
            recent.append(row)
        return recent

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
