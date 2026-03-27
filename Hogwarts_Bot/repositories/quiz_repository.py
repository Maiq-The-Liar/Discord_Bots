import json
from pathlib import Path


class QuizRepository:
    def __init__(self, json_path: str):
        self.json_path = Path(json_path)
        self._questions = self._load_questions()
        self._by_id = {int(item["id"]): item for item in self._questions}

    def _load_questions(self) -> list[dict]:
        with self.json_path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, list):
            raise ValueError("Quiz JSON must contain a list.")

        return data

    def get_all(self) -> list[dict]:
        return self._questions

    def get_by_id(self, question_id: int) -> dict | None:
        return self._by_id.get(question_id)