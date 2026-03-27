import json
from pathlib import Path


class PatronusRepository:
    def __init__(self, json_path: str):
        self.json_path = Path(json_path)
        self._items = self._load_items()

    def _load_items(self) -> list[dict]:
        with self.json_path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, list):
            raise ValueError("Patronus JSON must contain a list.")

        # optional optimization
        self._by_id = {int(item["id"]): item for item in data}

        return data

    def get_by_id(self, patronus_id: int) -> dict | None:
        return self._by_id.get(patronus_id)
    
    def get_by_id(self, patronus_id: int) -> dict | None:
        for item in self._items:
            if int(item["id"]) == patronus_id:
                return item
        return None

    def get_by_rarity(self, rarity: str) -> list[dict]:
        return [item for item in self._items if item["rarity"] == rarity]
