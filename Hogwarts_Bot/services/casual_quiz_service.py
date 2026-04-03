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
        text = re.sub(r"[^a-z0-9\s]", " ", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def tokenize(self, text: str) -> list[str]:
        normalized = self.normalize_answer(text)
        if not normalized:
            return []
        return normalized.split()

    def edit_distance_leq_one(self, a: str, b: str) -> bool:
        if a == b:
            return True

        len_a = len(a)
        len_b = len(b)

        if abs(len_a - len_b) > 1:
            return False

        # Same length -> allow one substitution
        if len_a == len_b:
            mismatches = sum(ch1 != ch2 for ch1, ch2 in zip(a, b))
            return mismatches <= 1

        # Length differs by 1 -> allow one insertion/deletion
        if len_a > len_b:
            longer, shorter = a, b
        else:
            longer, shorter = b, a

        i = 0
        j = 0
        edits = 0

        while i < len(longer) and j < len(shorter):
            if longer[i] == shorter[j]:
                i += 1
                j += 1
            else:
                edits += 1
                if edits > 1:
                    return False
                i += 1

        # If one trailing char remains in the longer word, that counts as one edit
        if i < len(longer):
            edits += 1

        return edits <= 1

    def words_match(self, required_word: str, candidate_token: str) -> bool:
        if required_word == candidate_token:
            return True

        # For short words, require exact match to avoid too many false positives.
        if len(required_word) <= 3:
            return False

        return self.edit_distance_leq_one(required_word, candidate_token)

    def group_matches(self, required_words: list[str], candidate_tokens: list[str]) -> bool:
        if not required_words:
            return False

        for required_word in required_words:
            if not any(self.words_match(required_word, token) for token in candidate_tokens):
                return False

        return True

    def build_answer_groups(self, question: dict) -> list[list[str]]:
        groups: list[list[str]] = []

        # New format:
        # "answer_groups": [
        #   ["rowena", "ravenclaw"],
        #   ["salazar", "slytherin"]
        # ]
        raw_groups = question.get("answer_groups")
        if isinstance(raw_groups, list):
            for group in raw_groups:
                if isinstance(group, list):
                    words = []
                    for item in group:
                        if isinstance(item, str):
                            words.extend(self.tokenize(item))
                    if words:
                        groups.append(words)

        # Backward compatibility with old format:
        # "answers": ["severus snape", "snape", "severus"]
        raw_answers = question.get("answers")
        if isinstance(raw_answers, list):
            for answer in raw_answers:
                if isinstance(answer, str):
                    words = self.tokenize(answer)
                    if words:
                        groups.append(words)

        return groups

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
        candidate_tokens = self.tokenize(message_content)
        if not candidate_tokens:
            return False

        answer_groups = self.build_answer_groups(question)
        if not answer_groups:
            return False

        return any(
            self.group_matches(group, candidate_tokens)
            for group in answer_groups
        )