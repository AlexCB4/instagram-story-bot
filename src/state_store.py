from __future__ import annotations

from src.gsheet import SheetManager


class StateStore:
    def __init__(self, sheet_manager: SheetManager) -> None:
        self.sheet_manager = sheet_manager

    def get_last_update_id(self) -> int:
        value = self.sheet_manager.get_state("telegram_last_update_id", "0")
        try:
            return int(value)
        except ValueError:
            return 0

    def set_last_update_id(self, update_id: int) -> None:
        self.sheet_manager.set_state("telegram_last_update_id", str(update_id))
