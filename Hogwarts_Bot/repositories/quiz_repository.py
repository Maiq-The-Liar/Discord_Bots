from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class QuizRepository:
    """Read-only repository for quiz question JSON files.

    Used by the casual quiz and duel systems. Questions are loaded once at
    construction time and exposed as dictionaries to preserve the existing
    service/cog expectations.
    """

    def __init__(self, questions_path: str | Path):
        self.questions_path = Path(questions_path)
        self._questions: list[dict[str, Any]] = self._load_questions()
        self._by_id: dict[int, dict[str, Any]] = {
            int(question["id"]): question
            for question in self._questions
            if isinstance(question, dict) and "id" in question
        }

    def _load_questions(self) -> list[dict[str, Any]]:
        if not self.questions_path.exists():
            return []
        with self.questions_path.open("r", encoding="utf-8") as fh:
            raw = json.load(fh)
        if not isinstance(raw, list):
            return []
        questions: list[dict[str, Any]] = []
        for item in raw:
            if isinstance(item, dict) and "id" in item and "question" in item:
                questions.append(dict(item))
        return questions

    def get_all(self) -> list[dict[str, Any]]:
        return [dict(question) for question in self._questions]

    def get_by_id(self, question_id: int) -> dict[str, Any] | None:
        question = self._by_id.get(int(question_id))
        return dict(question) if question is not None else None
