import random
import re

from repositories.quiz_repository import QuizRepository
from repositories.casual_quiz_repository import CasualQuizRepository


class CasualQuizService:
    def __init__(
        self,
        quiz_repo: QuizRepository,
        casual_quiz_repo: CasualQuizRepository,
    ):
        self.quiz_repo = quiz_repo
        self.casual_quiz_repo = casual_quiz_repo

    def normalize_answer(self, text: str) -> str:
        text = text.casefold().strip()
        text = text.replace("’", "'")
        text = re.sub(r"[^a-z0-9\s'/.-]", "", text)
        text = re.sub(r"\s+", " ", text)
        return text

    def get_next_question(self, channel_id: int) -> dict:
        all_questions = self.quiz_repo.get_all()
        if not all_questions:
            raise ValueError("No quiz questions available.")

        asked_ids = self.casual_quiz_repo.get_asked_question_ids(channel_id)
        available = [q for q in all_questions if int(q["id"]) not in asked_ids]

        if not available:
            self.casual_quiz_repo.clear_history(channel_id)
            available = all_questions

        chosen = random.choice(available)
        question_id = int(chosen["id"])

        self.casual_quiz_repo.mark_question_asked(channel_id, question_id)
        self.casual_quiz_repo.set_current_question(channel_id, question_id)

        return chosen

    def get_current_question(self, channel_id: int) -> dict | None:
        state = self.casual_quiz_repo.get_channel_state(channel_id)
        if state is None or state["current_question_id"] is None:
            return None

        return self.quiz_repo.get_by_id(int(state["current_question_id"]))

    def is_correct_answer(self, question: dict, message_content: str) -> bool:
        candidate = self.normalize_answer(message_content)
        accepted = {
            self.normalize_answer(answer)
            for answer in question["answers"]
        }
        return candidate in accepted