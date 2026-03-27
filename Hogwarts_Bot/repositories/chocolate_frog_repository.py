import json
from pathlib import Path


class ChocolateFrogRepository:
    def __init__(self, json_path: str):
        self.json_path = Path(json_path)
        self._items = self._load_items()
        self._by_id = {int(item["id"]): item for item in self._items}

    def _load_items(self) -> list[dict]:
        with self.json_path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, list):
            raise ValueError("Chocolate frog JSON must contain a list.")

        return data

    def get_all(self) -> list[dict]:
        return self._items

    def get_total_count(self) -> int:
        return len(self._items)

    def get_by_id(self, card_id: int) -> dict | None:
        return self._by_id.get(card_id)